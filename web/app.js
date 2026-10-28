import { t } from "./i18n.js";
import { FIELDS, STATUS_ICON, buildProfile, describeErrors, langFromNavigator, safeHttpsUrl, valuesFromProfile } from "./logic.js";

// Server-provided text is only ever inserted as text nodes (see h() below), never parsed as markup.
const state = {
  lang: langFromNavigator(navigator), values: {}, assistantText: "", assistant: null, assistantOpen: false,
  view: "idle", results: [], detail: null, errors: [],
};
const L = (key) => t(state.lang, key);

function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

async function post(path, body) {
  let res;
  try {
    res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  } catch { throw { network: true }; }
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON error body */ }
  return { ok: res.ok, status: res.status, data };
}
const errorsFrom = (r) => { const e = describeErrors(r.data?.detail); return e.length ? e : [L("errorGeneric")]; };
const errorsFromThrown = (e) => [e && e.network ? L("errorNetwork") : L("errorGeneric")];

function fmtValue(v) {
  if (v === null || v === undefined) return L("notProvided");
  if (typeof v === "boolean") return v ? L("yes") : L("no");
  if (typeof v === "object") return Object.entries(v).map(([k, x]) => `${L("field." + k)}: ${fmtValue(x)}`).join(", ");
  return String(v);
}
const link = (url, text) => { const href = safeHttpsUrl(url); return href ? h("a", { href, target: "_blank", rel: "noopener noreferrer" }, text) : null; };

// ---------- actions ----------
async function search() {
  state.view = "loading"; paintResults();
  try {
    const r = await post("/api/opportunities/search", { profile: buildProfile(state.values), language: state.lang });
    if (r.ok) { state.results = r.data.results; state.view = "results"; }
    else { state.errors = errorsFrom(r); state.view = "error"; }
  } catch (e) { state.errors = errorsFromThrown(e); state.view = "error"; }
  paintResults(true);
}

async function openDetail(row) {
  state.view = "loading"; paintResults();
  const body = { profile: buildProfile(state.values) };
  const id = encodeURIComponent(row.program_id);
  try {
    const [explain, narrative, checklist] = await Promise.all([
      post(`/api/matches/${id}/explain`, { ...body, language: state.lang }),
      post(`/api/matches/${id}/narrative`, { ...body, language: state.lang }),
      post("/api/checklists/generate", { ...body, program_id: row.program_id, language: state.lang }),
    ]);
    const bad = [explain, narrative, checklist].find((r) => !r.ok);
    if (bad) { state.errors = errorsFrom(bad); state.view = "error"; }
    else { state.detail = { row, explain: explain.data, narrative: narrative.data, checklist: checklist.data }; state.view = "detail"; }
  } catch (e) { state.errors = errorsFromThrown(e); state.view = "error"; }
  paintResults(true);
}

async function askAssistant() {
  const message = state.assistantText.trim();
  if (!message) return;
  state.assistant = { busy: true };
  paintPage();
  try {
    const r = await post("/api/assistant/message", { message, language: state.lang });
    if (r.status === 503) state.assistant = { message: L("assistantUnavailable") };
    else if (!r.ok) state.assistant = { message: r.status === 422 ? errorsFrom(r).join(" ") : L("assistantFailed") };
    else {
      state.values = { ...state.values, ...valuesFromProfile(r.data.profile) };
      state.assistant = { warnings: r.data.warnings, questions: r.data.questions };
      state.results = r.data.results; state.view = "results";
    }
  } catch (e) { state.assistant = { message: errorsFromThrown(e)[0] }; }
  paintPage(); paintResults();
}

function toggleLang() {
  state.lang = state.lang === "ur" ? "en" : "ur";
  paintPage(); paintResults();
  if (state.view === "detail") openDetail(state.detail.row);   // refresh narrative in the new language
}

// ---------- views ----------
function formField(f) {
  const id = `f-${f.name}`;
  const val = state.values[f.name] ?? "";
  const onchange = (e) => { state.values[f.name] = e.target.value; };
  let control;
  if (f.type === "select" || f.type === "bool") {
    const opts = f.type === "bool" ? [["true", L("yes")], ["false", L("no")]] : f.options.map((o) => [o, L("opt." + o)]);
    control = h("select", { id, name: f.name, onchange },
      h("option", { value: "" }, L("choose")),
      opts.map(([v, label]) => h("option", { value: v, selected: v === val }, label)));
  } else {
    control = h("input", { id, name: f.name, type: "number", inputmode: "decimal", dir: "ltr", min: f.min, max: f.max, step: f.step, value: val, onchange });
  }
  return h("div", { class: "field" }, h("label", { for: id }, L("field." + f.name)), control);
}

function profileForm() {
  return h("section", {},
    h("h2", {}, L("formTitle")), h("p", { class: "hint" }, L("formHint")),
    h("form", { onsubmit: (e) => { e.preventDefault(); search(); } },
      h("div", { class: "grid" }, FIELDS.map(formField)),
      h("button", { class: "primary", type: "submit", disabled: state.view === "loading" }, state.view === "loading" ? L("finding") : L("find"))));
}

function assistantBox() {
  const a = state.assistant || {};
  return h("details", { class: "box", open: state.assistantOpen || !!state.assistant, ontoggle: (e) => { state.assistantOpen = e.target.open; } },
    h("summary", {}, L("assistantTitle")),
    h("p", { class: "hint" }, L("assistantHint")),
    h("textarea", { id: "assistant-text", "aria-label": L("assistantTitle"), maxlength: "2000", oninput: (e) => { state.assistantText = e.target.value; } }, state.assistantText),
    h("p", {}, h("button", { type: "button", disabled: !!a.busy, onclick: askAssistant }, a.busy ? L("finding") : L("assistantSend"))),
    a.message ? h("p", { class: "err", role: "status" }, a.message) : null,
    a.warnings?.length ? h("ul", {}, a.warnings.map((w) => h("li", {}, w))) : null,
    a.questions?.length ? h("div", {}, h("h3", {}, L("questionsTitle")), h("ul", {}, a.questions.map((q) => h("li", {}, q.text)))) : null);
}

function statusBadge(status) { return h("span", { class: `badge ${status}` }, L("status." + status)); }

function resultCard(row) {
  const c = row.condition_counts;
  return h("article", { class: "card" },
    h("h3", {}, h("bdi", {}, row.name)),
    h("p", { class: "org" }, h("bdi", {}, row.organization)),
    h("p", {}, statusBadge(row.status)),
    h("p", { class: "meta" }, `${L("counts")}: ${c.met} / ${c.not_met} / ${c.unknown}`),
    row.application.confirmed_open ? null : h("p", { class: "meta" }, L("openWindowUnconfirmed")),
    row.application.deadline ? null : h("p", { class: "meta" }, L("deadlineUnconfirmed")),
    h("button", { type: "button", onclick: () => openDetail(row) }, L("why")));
}

function conditionItem(e, narrativeItems, byModel) {
  const nar = byModel ? narrativeItems[e.rule_id] : null;
  const src = link(e.source_url, L("source"));
  return h("li", {},
    h("details", {},
      h("summary", {},
        h("span", { class: `cond ${e.status}` }, `${STATUS_ICON[e.status]} ${L("cond." + e.status)}`),
        h("span", { dir: "auto" }, e.text.requirement)),
      nar ? h("p", {}, nar) : null,
      h("p", {}, e.text.reason),
      h("p", {}, h("strong", {}, `${L("yourAnswer")}: `), fmtValue(e.profile_value)),
      e.missing_fields?.length ? h("p", {}, h("strong", {}, `${L("missing")}: `), e.missing_fields.map((f) => L("field." + f)).join(", ")) : null,
      e.source_passage ? h("div", { class: "passage" }, h("p", { class: "label" }, L("sourceText")), h("p", { dir: "ltr", lang: "en" }, e.source_passage)) : null,
      h("p", { class: "meta" }, src, src ? " · " : "",
        `${L("lastChecked")}: `, h("bdi", {}, e.source_last_checked ?? "-"), " · ",
        `${L("published")}: `, h("bdi", {}, e.source_published ?? L("undated"))),
      e.text.ambiguity ? h("p", {}, h("strong", {}, `${L("unclear")}: `), e.text.ambiguity) : null,
      e.status !== "met" ? h("p", {}, h("strong", {}, `${L("nextStep")}: `), e.text.next_action) : null));
}

function detailView() {
  const { row, explain, narrative, checklist } = state.detail;
  const byModel = narrative.generated_by === "model";
  const items = Object.fromEntries(narrative.items.map((i) => [i.rule_id, i.text]));
  return [
    h("button", { type: "button", onclick: () => { state.view = "results"; paintResults(true); } }, "← " + L("back")),
    h("h2", {}, h("bdi", {}, row.name)),
    h("p", {}, statusBadge(explain.status)),
    h("div", { class: "card" },
      h("h3", {}, L("summary")), h("p", {}, narrative.summary),
      h("span", { class: "tag" }, byModel ? L("byModel") : L("byTemplate"))),
    h("h3", {}, L("conditions")),
    h("ul", { class: "conds" }, explain.entries.map((e) => conditionItem(e, items, byModel))),
    h("h3", {}, L("checklist")),
    h("ol", { class: "todo" }, checklist.items.map((i) =>
      h("li", {}, h("strong", {}, `${L("kind." + i.kind)}: `), h("span", { dir: "auto" }, i.text), " ", link(i.source_url, `(${L("source")})`)))),
    h("p", { class: "notice" }, L("disclaimer")),
  ];
}

function resultsContent() {
  switch (state.view) {
    case "loading": return [h("p", { role: "status" }, L("finding"))];
    case "error": return [h("div", { class: "err", role: "alert" }, state.errors.map((m) => h("p", {}, m)))];
    case "results": return [h("h2", {}, L("resultsTitle")), state.results.length ? state.results.map(resultCard) : h("p", {}, L("noResults")), h("p", { class: "notice" }, L("disclaimer"))];
    case "detail": return detailView();
    default: return [];
  }
}

function paintResults(focus = false) {
  const box = document.getElementById("results");
  if (!box) return;
  box.replaceChildren(...resultsContent());
  if (focus) box.focus();
}

function paintPage() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = state.lang === "ur" ? "rtl" : "ltr";
  document.title = L("title");
  document.getElementById("app").replaceChildren(
    h("header", { class: "top" },
      h("h1", {}, L("title")),
      h("button", { type: "button", onclick: toggleLang, lang: state.lang === "ur" ? "en" : "ur" }, L("language"))),
    h("main", { class: "wrap" },
      h("p", {}, L("tagline")),
      h("p", { class: "notice" }, L("disclaimer")),
      h("p", { class: "notice" }, L("privacy")),
      assistantBox(), profileForm(),
      h("div", { id: "results", tabindex: "-1", "aria-live": "polite" })));
}

paintPage();
