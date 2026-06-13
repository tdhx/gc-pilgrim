const status = document.querySelector("#status");
const review = document.querySelector("#review");
const summary = document.querySelector("#summary");
const events = document.querySelector("#events");
const series = document.querySelector("#series");
const quarantined = document.querySelector("#quarantined");
const completeness = document.querySelector("#completeness");
const divergences = document.querySelector("#divergences");
const divergenceSummary = document.querySelector("#divergence-summary");
const schedule = document.querySelector("#schedule");
const parishJSON = document.querySelector("#parish-json");
const buttons = [...document.querySelectorAll("[data-parish]")];

function text(value, fallback = "Not supplied") {
  return value === null || value === undefined || value === "" ? fallback : String(value);
}

function card(title, facts, description) {
  const article = document.createElement("article");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const list = document.createElement("dl");
  facts.forEach(([term, value]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = text(value);
    list.append(dt, dd);
  });
  article.append(heading, list);
  if (description) {
    const paragraph = document.createElement("p");
    paragraph.textContent = description;
    article.append(paragraph);
  }
  return article;
}

function renderCards(container, values, renderer, emptyMessage) {
  container.replaceChildren();
  if (!values.length) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = emptyMessage;
    container.append(empty);
    return;
  }
  values.forEach((value) => container.append(renderer(value)));
}

function renderSummary(parish) {
  const documentLink = parish.document?.url
    ? `<a href="${parish.document.url}" target="_blank" rel="noreferrer">Open source document</a>`
    : "No document";
  summary.innerHTML = `
    <div><strong>${parish.name}</strong><span>${text(parish.document?.title, "No extraction yet")}</span></div>
    <div><strong>Published</strong><span>${text(parish.document?.published_date)}</span></div>
    <div><strong>Processed</strong><span>${text(parish.processed_at)}</span></div>
    <div><strong>Parser</strong><span>${text(parish.parser_mode)} · ${text(parish.model)}</span></div>
    <div><strong>Text quality</strong><span>${parish.text_quality?.usable ? "Usable" : "Review required"} · ${text(parish.text_quality?.characters, "0")} characters</span></div>
    <div><strong>Source</strong><span>${documentLink}</span></div>
  `;
}

function renderDivergences(values) {
  const counts = values.reduce((result, item) => {
    result[item.classification] = (result[item.classification] || 0) + 1;
    return result;
  }, {});
  divergenceSummary.replaceChildren();
  Object.entries(counts).sort().forEach(([name, count]) => {
    const badge = document.createElement("span");
    badge.textContent = `${name}: ${count}`;
    divergenceSummary.append(badge);
  });

  divergences.replaceChildren();
  if (!values.length) {
    divergences.textContent = "No worship observations.";
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Status</th><th>Observation</th><th>Church resolution</th><th>Matched / replacement</th><th>Publication</th><th>Why</th><th>Scheduled candidates</th></tr></thead>";
  const tbody = document.createElement("tbody");
  values.forEach((item) => {
    const row = document.createElement("tr");
    [
      item.classification,
      [
        item.date,
        item.start_time,
        item.event_type,
        item.church,
        item.title || item.evidence,
      ].map((value) => text(value)).join(" · "),
      [
        item.church_resolution,
        item.normalized_church,
        item.resolved_church_name,
        item.resolved_church_id,
      ].map((value) => text(value)).join(" · "),
      [
        `Matched: ${text(item.matched_source_id, "None")}`,
        `Replaces: ${text(item.replaces_event_type, "Nothing")}`,
      ].join("\n"),
      item.publication_decision || "audit-only",
      item.classification_reason,
      (item.schedule_candidates || []).map((candidate) => (
        `${candidate.date} ${candidate.start_time} · ${candidate.event_type} · `
        + `${text(candidate.church)} · ${text(candidate.title)}`
      )).join("\n") || "None",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = text(value);
      row.append(cell);
    });
    tbody.append(row);
  });
  table.append(tbody);
  divergences.append(table);
}

function renderSchedule(parish) {
  const dates = new Set(parish.divergences.map((item) => item.date).filter(Boolean));
  const relevant = parish.schedule.filter((item) => dates.has(item.start.slice(0, 10)));
  schedule.replaceChildren();
  if (!relevant.length) {
    schedule.textContent = "No scheduled services on observed dates.";
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = "<thead><tr><th>Date</th><th>Time</th><th>Type</th><th>Church</th><th>Title</th><th>Status</th><th>Newsletter result</th></tr></thead>";
  const tbody = document.createElement("tbody");
  relevant.forEach((item) => {
    const row = document.createElement("tr");
    [
      item.start.slice(0, 10),
      item.start.slice(11, 16),
      item.event_type,
      item.church,
      item.title,
      item.status,
      item.source_id?.startsWith("newsletter:") ? "Newsletter addition" : "Base schedule",
    ].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = text(value);
      row.append(cell);
    });
    tbody.append(row);
  });
  table.append(tbody);
  schedule.append(table);
}

function render(parish) {
  buttons.forEach((button) => {
    button.classList.toggle("selected", button.dataset.parish === parish.id);
  });
  renderSummary(parish);
  renderCards(
    events,
    parish.events,
    (event) => card(event.title, [
      ["Start", event.start],
      ["End", event.end],
      ["Status", event.status],
      ["Location", event.location],
      ["ID", event.id],
    ], event.description),
    "No accepted community events.",
  );
  renderCards(
    series,
    parish.series || [],
    (item) => card(item.series_title, [
      ["Occurrence title", item.occurrence_title],
      ["Category", item.category],
      ["Pattern", `${item.frequency} every ${item.interval}`],
      ["Days", (item.weekdays || []).join(", ")],
      ["Time", `${text(item.start_time)}–${text(item.end_time)}`],
      ["Venue", item.venue || item.location],
      ["Parent church", item.church_name],
      ["Last seen", item.last_seen],
      ["ID", item.series_id],
    ], item.description),
    "No accepted recurring series.",
  );
  renderCards(
    quarantined,
    [...parish.quarantined, ...(parish.series_quarantined || [])],
    (item) => card(item.candidate?.title || "Untitled candidate", [
      ["Reasons", item.reasons.join(", ")],
      ["Date", item.candidate?.date],
      ["Time", item.candidate?.start_time],
      ["Confidence", item.candidate?.confidence],
      ["Location", item.candidate?.location],
    ], item.candidate?.evidence),
    "No quarantined candidates.",
  );
  renderCards(
    completeness,
    parish.completeness?.unmatched_activity_headings || [],
    (heading) => card(heading, [
      ["Result", "No accepted record"],
    ]),
    "No likely activity headings were missed.",
  );
  renderDivergences(parish.divergences);
  renderSchedule(parish);
  parishJSON.textContent = JSON.stringify(parish.parish, null, 2);
}

async function load() {
  try {
    const response = await fetch("feeds/v1/newsletter-review.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`Review feed returned ${response.status}.`);
    const feed = await response.json();
    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        render(feed.parishes.find((parish) => parish.id === button.dataset.parish));
      });
    });
    status.hidden = true;
    review.hidden = false;
    render(feed.parishes[0]);
  } catch (error) {
    status.className = "error";
    status.textContent = error.message;
  }
}

load();
