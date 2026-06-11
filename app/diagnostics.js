import {
  selectedParishId,
  validateCommunity,
  validateLiturgical,
  validateParish,
  validateRegistry,
  validateServices,
} from "./web/calendar-core.js?v=6";

const FEED_ROOT = "feeds/v1";
const title = document.querySelector("#diagnostics-title");
const body = document.querySelector("#diagnostics-body");
const errorMessage = document.querySelector("#diagnostics-error");
const parishLogo = document.querySelector("#parish-logo");
const calendarLink = document.querySelector("#calendar-link");

async function fetchJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error(`${url} returned ${response.status}.`);
  return response.json();
}

function appendList(headingText, values) {
  const heading = document.createElement("h3");
  heading.textContent = headingText;
  const list = document.createElement("ul");
  (values.length ? values : ["None"]).forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  });
  body.append(heading, list);
}

async function loadDiagnostics() {
  try {
    const registry = validateRegistry(await fetchJSON(`${FEED_ROOT}/registry.json`));
    const parishId = selectedParishId(registry, window.location.search);
    const parishRoot = `${FEED_ROOT}/parishes/${parishId}`;
    const [parish, services, community, liturgical] = await Promise.all([
      fetchJSON(`${parishRoot}/parish.json`).then(validateParish),
      fetchJSON(`${parishRoot}/services.json`).then(validateServices),
      fetchJSON(`${parishRoot}/community.json`).then(validateCommunity),
      fetchJSON(`${FEED_ROOT}/liturgical.json`).then(validateLiturgical),
    ]);
    document.body.dataset.theme = parish.branding?.theme || "spcp";
    parishLogo.src = parish.branding?.logo || "assets/gc-pilgrim.svg";
    parishLogo.alt = parish.name;
    calendarLink.href = `index.html?parish=${encodeURIComponent(parishId)}`;
    const generated = new Date(services.generated_at);
    const ageHours = Math.max(0, (Date.now() - generated.getTime()) / 3_600_000);
    title.textContent = `${parish.name} · schema v${services.schema_version} · ${ageHours.toFixed(1)}h old`;

    const facts = document.createElement("dl");
    [
      ["Generated", generated.toLocaleString("en-AU")],
      ["Coverage", `${services.coverage.start} to ${services.coverage.end}`],
      ["Services", String(services.services.length)],
      ["Community events", String(community.events.length)],
      ["Liturgical dates", String(Object.keys(liturgical.dates).length)],
    ].forEach(([term, description]) => {
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = term;
      dd.textContent = description;
      facts.append(dt, dd);
    });
    body.append(facts);
    appendList("Registered parishes", registry.parishes);
    appendList(
      "Sources",
      services.sources.map((source) => `${source.name}: ${source.status}`),
    );
    appendList("Warnings", [...services.warnings, ...community.warnings]);
  } catch (error) {
    title.textContent = "Diagnostics unavailable";
    errorMessage.hidden = false;
    errorMessage.textContent = error.message;
  }
}

loadDiagnostics();
