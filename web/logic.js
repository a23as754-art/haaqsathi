// Pure helpers (no DOM) so they can be unit-tested with `node --test`.
export const FIELDS = [
  { name: "education_level", type: "select", options: ["matric", "intermediate", "undergraduate", "masters", "mphil", "phd"] },
  { name: "domicile_province", type: "select", options: ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Islamabad Capital Territory", "Gilgit-Baltistan", "Azad Jammu and Kashmir"] },
  { name: "institution_sector", type: "select", options: ["public", "private"] },
  { name: "admission_basis", type: "select", options: ["open_merit", "self_finance", "other"] },
  { name: "marks_percent", type: "number", min: 0, max: 100, step: "0.01" },
  { name: "cgpa", type: "number", min: 0, max: 4, step: "0.01" },
  { name: "monthly_family_income_pkr", type: "number", min: 0, step: "1" },
  { name: "receives_other_scholarship", type: "bool" },
];

/** Form values (strings) -> API profile. Empty answers are omitted, never defaulted. */
export function buildProfile(values) {
  const out = {};
  for (const f of FIELDS) {
    const v = values[f.name];
    if (v === undefined || v === null || String(v).trim() === "") continue;
    if (f.type === "bool") out[f.name] = String(v) === "true";
    else out[f.name] = String(v).trim();
  }
  return out;
}

/** API profile -> form values (strings), for filling the form from the assistant. */
export function valuesFromProfile(profile) {
  const out = {};
  for (const f of FIELDS) {
    const v = profile?.[f.name];
    if (v === undefined || v === null) continue;
    out[f.name] = String(v);
  }
  return out;
}

/** Only plain https links are ever rendered as links. */
export function safeHttpsUrl(u) {
  try {
    const url = new URL(u);
    return url.protocol === "https:" ? url.href : null;
  } catch { return null; }
}

export const STATUS_ICON = { met: "✓", not_met: "✗", unknown: "?" };

/** Turn an API error body into a list of readable strings. */
export function describeErrors(detail) {
  if (!detail) return [];
  if (typeof detail === "string") return [detail];
  if (Array.isArray(detail)) return detail.map((d) => (d && d.msg) ? String(d.msg) : String(d));
  if (Array.isArray(detail.errors)) return detail.errors.map(String);
  return [];
}

export function langFromNavigator(nav) {
  const l = (nav?.language || "en").toLowerCase();
  return l.startsWith("ur") ? "ur" : "en";
}
