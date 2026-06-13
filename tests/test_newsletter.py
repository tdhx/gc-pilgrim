import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sources.newsletter.pipeline import (
    NewsletterDocument,
    classify_divergence,
    completeness_audit,
    discover_burleigh,
    discover_surfer_files,
    extract_pdf_text,
    expand_series,
    process_latest,
    reconcile_community,
    reconcile_series,
    text_quality,
)
from generators.build_community import build as build_community
from generators.churches import resolve_church
from generators.newsletter_overlays import apply_newsletter_overlays


class FakePage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakeReader:
    def __init__(self, _path):
        self.pages = [
            FakePage("Parish newsletter Sunday 7 June 2026"),
            FakePage("Community lunch Friday 12 June at 12:30 pm. " * 30),
        ]


class NewsletterDiscoveryTests(unittest.TestCase):
    def test_burleigh_discovery_chooses_latest_dated_pdf(self):
        html = """
        <a href="https://example.test/24-May.pdf">
          Parish Newsletter 24 May 2026 (Pentecost)
        </a>
        <a href="https://example.test/31-May.pdf">
          Parish Newsletter 31 May 2026 (Trinity)
        </a>
        <a href="https://example.test/not-a-newsletter.pdf">Annual report</a>
        """
        document = discover_burleigh(html)
        self.assertEqual(document.published_date, "2026-05-31")
        self.assertTrue(document.download_url.endswith("31-May.pdf"))

    def test_newsletter_hub_selects_first_post_with_drive_pdf(self):
        html = """
        <div class="date-posts">
          <h3 class="post-title entry-title">SPCP e-news Sunday June 14 2026</h3>
          <a href="https://drive.google.com/file/d/new/view?usp=drive_link">PDF</a>
          <abbr class="published" title="2026-06-12T18:51:00+10:00">June 12</abbr>
        </div>
        <div class="date-posts">
          <h3 class="post-title entry-title">Older newsletter</h3>
          <a href="https://drive.google.com/file/d/old/view">PDF</a>
          <abbr class="published" title="2026-06-05T14:47:00+10:00">June 5</abbr>
        </div>
        """
        document = discover_surfer_files(html)
        self.assertEqual(document.source_id, "new")
        self.assertEqual(document.published_date, "2026-06-12")
        self.assertEqual(document.title, "SPCP e-news Sunday June 14 2026")
        self.assertEqual(
            document.download_url,
            "https://drive.google.com/uc?export=download&id=new",
        )


class TextExtractionTests(unittest.TestCase):
    def test_extract_pdf_text_preserves_page_boundaries(self):
        text = extract_pdf_text("unused.pdf", reader_factory=FakeReader)
        self.assertIn("--- Page 1 ---", text)
        self.assertIn("--- Page 2 ---", text)
        self.assertIn("Community lunch", text)

    def test_text_quality_accepts_readable_newsletter(self):
        text = (
            "Parish newsletter Sunday Mass community event at 10:30 am. "
            * 30
        )
        self.assertTrue(text_quality(text)["usable"])

    def test_text_quality_rejects_empty_and_short_text(self):
        self.assertEqual(text_quality("")["reason"], "empty")
        self.assertEqual(
            text_quality("Parish newsletter Sunday")["reason"],
            "too-short",
        )


class ReconciliationTests(unittest.TestCase):
    document = NewsletterDocument(
        parish_id="burleigh-heads",
        source_id="newsletter-1",
        title="Newsletter 1 June 2026",
        url="https://example.test/newsletter.pdf",
        download_url="https://example.test/newsletter.pdf",
        published_date="2026-06-01",
    )

    def candidate(self, **overrides):
        value = {
            "action": "add",
            "existing_event_id": None,
            "title": "Parish Trivia Night",
            "date": "2026-07-10",
            "start_time": "18:30",
            "end_time": None,
            "all_day": False,
            "location": "Parish Hall",
            "series_title": None,
            "category": "social",
            "description": "Teams of six.",
            "confidence": 0.95,
            "evidence": "Trivia Night Friday 10 July at 6.30pm",
            "ambiguity": None,
        }
        value.update(overrides)
        return value

    def test_add_is_idempotent_and_defaults_end_time(self):
        first, decisions, quarantined = reconcile_community(
            "burleigh-heads", [], [self.candidate()], self.document
        )
        second, second_decisions, _ = reconcile_community(
            "burleigh-heads", first, [self.candidate()], self.document
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(first[0]["id"], second[0]["id"])
        self.assertEqual(first[0]["end"][11:16], "19:30")
        self.assertIn("defaulted", decisions[0]["warnings"][0])
        self.assertEqual(second_decisions[0]["action"], "deduplicated")
        self.assertEqual(quarantined, [])

    def test_update_retains_id_and_omitted_events(self):
        existing, _, _ = reconcile_community(
            "burleigh-heads", [], [self.candidate()], self.document
        )
        original_id = existing[0]["id"]
        other = {
            **existing[0],
            "id": "other-event",
            "source_id": "newsletter:burleigh-heads:event:other-event",
            "title": "Other Event",
        }
        updated, _, _ = reconcile_community(
            "burleigh-heads",
            existing + [other],
            [self.candidate(
                action="update",
                existing_event_id=original_id,
                start_time="19:00",
            )],
            self.document,
        )
        by_id = {record["id"]: record for record in updated}
        self.assertEqual(set(by_id), {original_id, "other-event"})
        self.assertEqual(by_id[original_id]["start"][11:16], "19:00")
        self.assertEqual(by_id[original_id]["status"], "modified")

    def test_explicit_cancellation_and_low_confidence_quarantine(self):
        existing, _, _ = reconcile_community(
            "burleigh-heads", [], [self.candidate()], self.document
        )
        event_id = existing[0]["id"]
        records, decisions, quarantined = reconcile_community(
            "burleigh-heads",
            existing,
            [
                self.candidate(action="cancel", existing_event_id=event_id),
                self.candidate(title="Maybe Event", confidence=0.4),
            ],
            self.document,
        )
        self.assertEqual(records[0]["status"], "cancelled")
        self.assertEqual(decisions[0]["action"], "cancelled")
        self.assertEqual(quarantined[0]["reasons"], ["low-confidence"])

    def test_reconciled_record_builds_existing_community_contract(self):
        records, _, _ = reconcile_community(
            "burleigh-heads", [], [self.candidate()], self.document
        )
        feed = build_community(
            records,
            "2026-06-13T12:00:00+10:00",
            "Australia/Brisbane",
            [{"name": "Burleigh newsletter", "url": self.document.url}],
        )
        self.assertEqual(len(feed["events"]), 1)
        self.assertEqual(feed["events"][0]["id"], records[0]["id"])
        self.assertEqual(feed["events"][0]["status"], "active")

    def test_divergence_classification_does_not_mutate_services(self):
        services = [{
            "event_type": "mass",
            "start": "2026-07-12T09:00:00+10:00",
            "church": "Calvary",
            "source_id": "baseline-mass",
        }]
        original = json.loads(json.dumps(services))
        observation = {
            "action": "active",
            "event_type": "mass",
            "date": "2026-07-12",
            "start_time": "10:00",
            "church": "Calvary",
            "confidence": 0.99,
            "ambiguity": None,
        }
        classification, matched = classify_divergence(observation, services)
        self.assertEqual(classification, "changed")
        self.assertEqual(matched, "baseline-mass")
        self.assertEqual(services, original)

    def test_divergence_church_suffix_alias_matches_schedule(self):
        services = [{
            "event_type": "mass",
            "start": "2026-06-02T07:30:00+10:00",
            "end": "2026-06-02T08:30:00+10:00",
            "church": "Mary Mother of Mercy",
            "title": "Mary Mother of Mercy - Mass",
            "source_id": "baseline-mass",
        }]
        observation = {
            "action": "active",
            "event_type": "mass",
            "date": "2026-06-02",
            "start_time": "07:30",
            "church": "Mary Mother of Mercy Church",
            "confidence": 0.98,
            "ambiguity": None,
        }
        classification, matched = classify_divergence(observation, services)
        self.assertEqual(classification, "matched")
        self.assertEqual(matched, "baseline-mass")

    def test_parish_alias_resolves_to_one_canonical_church(self):
        parish = {
            "churches": [
                {
                    "id": "mercy",
                    "name": "Mary, Mother of Mercy Church",
                    "calendar_name": "Mary Mother of Mercy",
                    "aliases": ["Burleigh Waters"],
                },
            ],
        }
        resolution = resolve_church("Burleigh Waters Catholic Church", parish)
        self.assertEqual(resolution["status"], "matched")
        self.assertEqual(resolution["church"]["id"], "mercy")

    def test_community_venue_keeps_room_and_parent_church(self):
        parish = {
            "churches": [{
                "id": "sacred-heart",
                "name": "Sacred Heart Church",
                "calendar_name": "Sacred Heart",
                "venues": [{
                    "name": "Parish Hospitality Centre",
                    "aliases": ["Hospitality Centre"],
                }],
            }],
        }
        records, _, _ = reconcile_community(
            "surfers-paradise",
            [],
            [self.candidate(
                title="The Bible Timeline Adult Faith Formation: Session 20",
                series_title="The Bible Timeline Adult Faith Formation",
                category="faith-formation",
                location="Parish Hospitality Centre, 50 Fairway Drive",
            )],
            self.document,
            parish,
        )
        self.assertEqual(records[0]["church_id"], "sacred-heart")
        self.assertEqual(records[0]["venue"], "Parish Hospitality Centre")
        self.assertEqual(records[0]["category"], "faith-formation")

    def test_recurring_series_expands_stably_and_expires_after_90_days(self):
        candidate = {
            "action": "add",
            "existing_series_id": None,
            "series_title": "Parish Yoga",
            "occurrence_title": "Yoga at the Parish Hospitality Centre",
            "category": "wellbeing",
            "frequency": "weekly",
            "interval": 1,
            "weekdays": ["tuesday"],
            "ordinal": None,
            "start_date": "2026-06-01",
            "end_date": None,
            "start_time": "10:45",
            "end_time": "11:45",
            "location": "Parish Hospitality Centre",
            "description": "A social yoga class.",
            "confidence": 0.99,
            "evidence": "Classes run every Tuesday at 10:45 a.m.",
            "ambiguity": None,
        }
        series, _, quarantined = reconcile_series(
            "surfers-paradise", [], [candidate], self.document
        )
        events = expand_series(
            series,
            window_start=date.fromisoformat("2026-06-01"),
            window_end=date.fromisoformat("2026-06-30"),
            today=date.fromisoformat("2026-06-13"),
        )
        rerun = expand_series(
            series,
            window_start=date.fromisoformat("2026-06-01"),
            window_end=date.fromisoformat("2026-06-30"),
            today=date.fromisoformat("2026-06-13"),
        )
        expired = expand_series(
            series,
            window_start=date.fromisoformat("2026-09-01"),
            window_end=date.fromisoformat("2026-09-30"),
            today=date.fromisoformat("2026-09-15"),
        )
        self.assertEqual(quarantined, [])
        self.assertEqual(len(events), 5)
        self.assertEqual(
            [event["id"] for event in events],
            [event["id"] for event in rerun],
        )
        self.assertEqual(expired, [])

    def test_recurring_series_keeps_id_when_title_wording_changes(self):
        candidate = {
            "action": "add",
            "existing_series_id": None,
            "series_title": "Spanish Prayer Group",
            "occurrence_title": None,
            "category": "prayer",
            "frequency": "monthly",
            "interval": 1,
            "weekdays": ["saturday"],
            "ordinal": 3,
            "start_date": None,
            "end_date": None,
            "start_time": "11:00",
            "end_time": "14:00",
            "location": "Parish Hospitality Centre",
            "description": None,
            "confidence": 0.95,
            "evidence": "Third Saturday from 11am.",
            "ambiguity": None,
        }
        first, _, _ = reconcile_series(
            "surfers-paradise", [], [candidate], self.document
        )
        updated, _, _ = reconcile_series(
            "surfers-paradise",
            first,
            [{**candidate, "series_title": "Jesús de la Misericordia Prayer Group"}],
            self.document,
        )
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["series_id"], first[0]["series_id"])

    def test_unique_untimed_cancellation_matches_but_ambiguous_one_does_not(self):
        services = [{
            "event_type": "confession",
            "start": "2026-07-12T17:15:00+10:00",
            "end": "2026-07-12T17:45:00+10:00",
            "church": "Our Lady of the Way",
            "source_id": "confession-one",
        }]
        observation = {
            "action": "cancelled",
            "event_type": "confession",
            "date": "2026-07-12",
            "start_time": None,
            "church": "Palm Beach",
            "confidence": 0.99,
            "ambiguity": "The cancellation notice does not state a time.",
        }
        parish = {
            "churches": [{
                "id": "our-lady-of-the-way",
                "name": "Our Lady of the Way Church",
                "calendar_name": "Our Lady of the Way",
                "aliases": ["Palm Beach"],
            }],
        }
        classification, matched = classify_divergence(observation, services, parish)
        self.assertEqual(classification, "cancelled")
        self.assertEqual(matched, "confession-one")
        compound = {
            **observation,
            "church": "Our Lady of the Way Church, Palm Beach",
        }
        classification, matched = classify_divergence(compound, services, parish)
        self.assertEqual(classification, "cancelled")
        self.assertEqual(matched, "confession-one")
        ambiguous = services + [{
            **services[0],
            "start": "2026-07-12T18:15:00+10:00",
            "source_id": "confession-two",
        }]
        classification, matched = classify_divergence(observation, ambiguous, parish)
        self.assertEqual(classification, "quarantined")
        self.assertEqual(matched, "confession-one")

    def test_completeness_audit_flags_unrepresented_activity_heading(self):
        result = completeness_audit(
            "YOGA AT THE PARISH HOSPITALITY CENTRE\n"
            "Classes run every Tuesday.\n"
            "ART AND CRAFT GROUP\n",
            {
                "community_events": [],
                "community_series": [{
                    "series_title": "Parish Yoga",
                    "evidence": "YOGA AT THE PARISH HOSPITALITY CENTRE",
                }],
                "worship_observations": [],
            },
        )
        self.assertIn("ART AND CRAFT GROUP", result["unmatched_activity_headings"])
        self.assertNotIn(
            "YOGA AT THE PARISH HOSPITALITY CENTRE",
            result["unmatched_activity_headings"],
        )

    def test_explicit_mass_replacement_cancels_mass_and_adds_liturgy(self):
        parish = {
            "id": "burleigh-heads",
            "churches": [{
                "id": "our-lady-of-the-way",
                "name": "Our Lady of the Way Church",
                "calendar_name": "Our Lady of the Way",
                "aliases": ["Palm Beach"],
            }],
        }
        services = [{
            "id": "mass-id",
            "source_id": "baseline-mass",
            "title": "Mass",
            "event_type": "mass",
            "service_name": "Sunday Mass",
            "presiders": [],
            "associated_devotions": [],
            "start": "2026-07-12T07:00:00+10:00",
            "end": "2026-07-12T08:00:00+10:00",
            "all_day": False,
            "timezone": "Australia/Brisbane",
            "location": "Our Lady of the Way",
            "description": None,
            "liturgical_date": "2026-07-12",
            "church_id": "our-lady-of-the-way",
            "status": "active",
            "source": "Baseline",
            "last_updated": "2026-06-13T12:00:00+10:00",
        }]
        observation = {
            "newsletter_id": "newsletter-1",
            "action": "active",
            "event_type": "liturgy",
            "replaces_event_type": "mass",
            "title": "Liturgy of the Word with Communion",
            "date": "2026-07-12",
            "start_time": "07:00",
            "end_time": None,
            "church": "Palm Beach",
            "confidence": 0.99,
            "evidence": "Lay-led Liturgy and Communion (No Mass)",
            "ambiguity": None,
        }
        result = apply_newsletter_overlays(
            services, [observation], parish, "2026-06-13T12:00:00+10:00"
        )
        self.assertEqual(len(result), 2)
        mass = next(item for item in result if item["event_type"] == "mass")
        liturgy = next(item for item in result if item["event_type"] == "liturgy")
        self.assertEqual(mass["id"], "mass-id")
        self.assertEqual(mass["status"], "cancelled")
        self.assertEqual(liturgy["status"], "active")
        self.assertEqual(liturgy["church_id"], "our-lady-of-the-way")

    def test_ambiguous_church_never_publishes_overlay(self):
        parish = {
            "id": "test",
            "churches": [
                {"id": "one", "name": "St Mary Church", "aliases": ["Town"]},
                {"id": "two", "name": "St Joseph Church", "aliases": ["Town"]},
            ],
        }
        observation = {
            "newsletter_id": "newsletter-1",
            "action": "active",
            "event_type": "liturgy",
            "replaces_event_type": None,
            "title": "Liturgy of the Word with Communion",
            "date": "2026-07-12",
            "start_time": "07:00",
            "end_time": None,
            "church": "Town",
            "confidence": 0.99,
            "evidence": "Liturgy at Town",
            "ambiguity": None,
        }
        self.assertEqual(
            apply_newsletter_overlays(
                [], [observation], parish, "2026-06-13T12:00:00+10:00"
            ),
            [],
        )


class PipelineTests(unittest.TestCase):
    def test_process_uses_pdf_only_after_text_quality_failure(self):
        document = NewsletterDocument(
            parish_id="burleigh-heads",
            source_id="doc-1",
            title="Newsletter 1 June 2026",
            url="https://example.test/newsletter.pdf",
            download_url="https://example.test/newsletter.pdf",
            published_date="2026-06-01",
        )
        parsed = {
            "community_events": [],
            "community_series": [],
            "worship_observations": [],
        }
        calls = []

        def fake_parse(_client, _model, _document, _text, pdf_bytes=None):
            calls.append(pdf_bytes)
            return parsed

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "sources.newsletter.pipeline.extract_pdf_text",
                    return_value="unusable",
                ),
                patch(
                    "sources.newsletter.pipeline.parse_with_openai",
                    side_effect=fake_parse,
                ),
            ):
                result = process_latest(
                    "burleigh-heads",
                    services=[],
                    root=directory,
                    client=object(),
                    document=document,
                    pdf_bytes=b"%PDF fake",
                )
            self.assertEqual(result["parser_mode"], "pdf-fallback")
            self.assertEqual(calls, [b"%PDF fake"])
            state = json.loads(
                (
                    Path(directory)
                    / "raw/burleigh-heads/newsletter/state.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(state["latest_document_id"], "doc-1")

    def test_process_uses_text_when_quality_is_good_and_skips_rerun(self):
        document = NewsletterDocument(
            parish_id="burleigh-heads",
            source_id="doc-2",
            title="Newsletter 8 June 2026",
            url="https://example.test/newsletter.pdf",
            download_url="https://example.test/newsletter.pdf",
            published_date="2026-06-08",
        )
        good_text = (
            "Parish newsletter Sunday community Mass event at 10:30 am. "
            * 30
        )
        calls = []

        def fake_parse(_client, _model, _document, _text, pdf_bytes=None):
            calls.append(pdf_bytes)
            return {
                "community_events": [],
                "community_series": [],
                "worship_observations": [],
            }

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch(
                    "sources.newsletter.pipeline.extract_pdf_text",
                    return_value=good_text,
                ),
                patch(
                    "sources.newsletter.pipeline.parse_with_openai",
                    side_effect=fake_parse,
                ),
            ):
                first = process_latest(
                    "burleigh-heads",
                    services=[],
                    root=directory,
                    client=object(),
                    document=document,
                    pdf_bytes=b"%PDF fake",
                )
                second = process_latest(
                    "burleigh-heads",
                    services=[],
                    root=directory,
                    client=object(),
                    document=document,
                    pdf_bytes=b"%PDF fake",
                )
            self.assertEqual(first["parser_mode"], "text")
            self.assertEqual(second["status"], "unchanged")
            self.assertEqual(calls, [None])


if __name__ == "__main__":
    unittest.main()
