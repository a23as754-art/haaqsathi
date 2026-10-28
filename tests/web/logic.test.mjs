import test from "node:test";
import assert from "node:assert/strict";
import { buildProfile, valuesFromProfile, safeHttpsUrl, describeErrors, langFromNavigator, FIELDS } from "../../web/logic.js";
import { STRINGS, t } from "../../web/i18n.js";

test("buildProfile omits empty answers and converts booleans", () => {
  const p = buildProfile({ education_level: "masters", cgpa: " 3.2 ", marks_percent: "", receives_other_scholarship: "false", domicile_province: undefined });
  assert.deepEqual(p, { education_level: "masters", cgpa: "3.2", receives_other_scholarship: false });
});

test("buildProfile never invents defaults", () => {
  assert.deepEqual(buildProfile({}), {});
});

test("valuesFromProfile round-trips", () => {
  const v = valuesFromProfile({ education_level: "masters", receives_other_scholarship: true, marks_percent: 65, extra: "x" });
  assert.deepEqual(v, { education_level: "masters", marks_percent: "65", receives_other_scholarship: "true" });
});

test("safeHttpsUrl accepts only https", () => {
  assert.equal(safeHttpsUrl("https://www.hec.gov.pk/x"), "https://www.hec.gov.pk/x");
  assert.equal(safeHttpsUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpsUrl("http://example.com"), null);
  assert.equal(safeHttpsUrl("not a url"), null);
  assert.equal(safeHttpsUrl(null), null);
});

test("describeErrors handles API shapes", () => {
  assert.deepEqual(describeErrors({ errors: ["a", "b"] }), ["a", "b"]);
  assert.deepEqual(describeErrors([{ msg: "bad" }]), ["bad"]);
  assert.deepEqual(describeErrors("oops"), ["oops"]);
  assert.deepEqual(describeErrors(undefined), []);
});

test("language detection from navigator", () => {
  assert.equal(langFromNavigator({ language: "ur-PK" }), "ur");
  assert.equal(langFromNavigator({ language: "en-US" }), "en");
  assert.equal(langFromNavigator(undefined), "en");
});

test("English and Urdu have exactly the same keys", () => {
  const en = Object.keys(STRINGS.en).sort(), ur = Object.keys(STRINGS.ur).sort();
  assert.deepEqual(ur, en);
});

test("no empty strings and Urdu strings contain Urdu script", () => {
  for (const [k, v] of Object.entries(STRINGS.ur)) {
    assert.ok(v.trim().length > 0, k);
    if (k !== "language") assert.ok(/[\u0600-\u06ff]/.test(v) || /^[A-Z]+$/.test(v), `no Urdu script in ${k}`);
  }
});

test("every form field and option has a label in both languages", () => {
  for (const lang of ["en", "ur"]) {
    for (const f of FIELDS) {
      assert.notEqual(t(lang, `field.${f.name}`), `field.${f.name}`);
      for (const o of f.options || []) assert.notEqual(t(lang, `opt.${o}`), `opt.${o}`, `${lang} ${o}`);
    }
  }
});

test("all opportunity and condition statuses are translated", () => {
  const ops = ["potential_match", "needs_verification", "likely_not_eligible", "application_status_unconfirmed", "closed"];
  for (const lang of ["en", "ur"]) {
    for (const s of ops) assert.notEqual(t(lang, `status.${s}`), `status.${s}`);
    for (const s of ["met", "not_met", "unknown"]) assert.notEqual(t(lang, `cond.${s}`), `cond.${s}`);
  }
});

test("disclaimer says it is not an official service and gives no guarantee", () => {
  assert.match(STRINGS.en.disclaimer, /not an official/i);
  assert.match(STRINGS.en.disclaimer, /guarantees? funding/i);
});
