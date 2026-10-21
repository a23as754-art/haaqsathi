# Source validation log

Checked: 2026-10-20. Method notes: the HEC introduction page was fetched directly. The HEC Eligibility Criteria and FAQ pages were read only as search-engine snippets of the hec.gov.pk URLs (not a full page fetch). HEC "How To Apply" and the PEEF student portal block automated access (robots), so they are UNREAD. Treat nothing below as a deadline or open-window confirmation.

Source tiers: **A** = official HEC page, **B** = official page of an individual university, **C** = news/blog/aggregator (leads only, never establishes a rule).

## 1. HEC Need-Based Scholarship (NBS)

| Item | Finding | Tier / URL | Status |
|---|---|---|---|
| Program exists, targets financially disadvantaged students | "over 10,000 scholarships" across "61 public sector universities". The page is undated ("This year"), so the cycle is unknown. | A: hec.gov.pk/.../HEC Need Based Scholarships/IntroductionObjectives.aspx (fetched) | verified (existence); cycle unknown |
| Level and institutions | Undergraduate (4-5 year) programs at HEC-selected public sector universities / degree-awarding institutions. Already-enrolled students in need may also apply. | A: hec.gov.pk/english/scholarshipsgrants/NBS/Pages/Eligibility-Criteria.aspx (snippet) | verified, page undated |
| Self-finance admission | Not eligible. | A: same Eligibility page; A: NBS FAQ page (snippet) | verified |
| Financial need | Assessed by each university's Institutional Scholarship Award Committee (ISAC) from family financial background. HEC pages show NO national income ceiling. | A: Eligibility page (snippet) | verified (absence seen only in snippets: confirm on full page) |
| Stipend | Eligibility page: Rs 6,000/month "for the complete program". Copies of the FAQ on university sites and a 2021 NED notice say 10 months. | A vs B/C | **CONFLICT: store as unknown, flag** |
| How to apply | Via the university's financial aid office; HEC does not accept applications directly. Form is on the HEC site (Downloads) and university sites. | A: NBS FAQ (snippet); C: eduvision | verified from snippets; read the full How-To-Apply page by hand |
| Deadline / window | HEC FAQ says HEC does not announce start/closing dates; each university announces its own. | A: NBS FAQ (snippet) | **No national deadline exists; confirm per university** |
| Rs 45,000 monthly income cap | Appears in university notices (GCUF 2025-26 notice per a blog; WUM page) but is NOT an HEC rule. | B: wum.edu.pk; C: pakera.pk | **Institution-level only; never a global rule** |
| "Not availing any other scholarship" | Appears on WUM page and blogs; not seen in HEC snippets. | B/C | unverified at HEC level |
| COMSATS Lahore Fall 2026 deadline 15 Oct 2026 | News report only. Do not mark closed without COMSATS's own notice. | C: propakistani.pk | lead only |
| Count of participating universities | 61 (HEC intro page) vs 98 (eduvision) | A vs C | conflict; use A |

### Consequences for the data model
1. An opportunity must be **(program, institution)**, e.g. "HEC NBS at GCUF". Income thresholds, deadlines and discipline lists are institution-level. A global `income <= 45000` rule for HEC NBS would be wrong.
2. Rules that HEC itself states and that apply nationally: undergraduate level, public-sector participating institution, not self-finance. Everything else defaults to `unknown` until the specific university's notice is captured.
3. Application status is `application_status_unconfirmed` for every NBS record until a current university notice is stored with its date.

## 2. PEEF Master Level Scholarship (read from official pages via search snippets; portal itself is robots-blocked)

| Item | Finding | Tier / URL | Status |
|---|---|---|---|
| Program | PEEF annual quota for master's students at partner universities | A: peef.punjab.gov.pk/masterlevel-scholarships | verified, page undated |
| Domicile | Punjab domicile | A: same | verified |
| Marks | At least 60% marks or CGPA 2.5 in bachelor's (exam in last three years, in Punjab) | A: same | verified (exam-year/location not modeled) |
| Income | Parents' declared monthly income PKR 40,000 or less, with exemptions (BPS 1-4 government employees; children of civilians martyred in terrorist attacks) | A: same | **stored `unverified`**: page undated, exemptions not modeled, third-party sites quote 37,000 / 60,000 (tier C, ignored) |
| Other scholarship | Must not be availing another educational scholarship that year | A: same | verified |
| Partner university, full-time admission | Required; page version on peef.org.pk refers to 2025-26 | A: peef.org.pk/masterlevel-scholarships | cycle unconfirmed |
| How to apply | Form from PEEF site, submitted to the university; direct applications to PEEF not entertained | A: peef.org.pk page | verified, undated |
| Deadline / window | Not found on the pages reviewed | n/a | **unknown** |
| Two official domains | peef.org.pk and peef.punjab.gov.pk show different versions of the page | A vs A | flag: use the newer-looking one but state the ambiguity |
| Claim "no PEEF scholarship needs Punjab domicile" | Contradicted by the official master's page | C: awamiportal.com | tier C rejected |

## 3. HEC scholarship directory and University of Karachi prospectus: NOT YET CHECKED

## Open actions
- [ ] Read HEC "How To Apply" page and NBS Downloads form by hand (robots blocked).
- [ ] Capture 3-5 individual university NBS notices (with dates) as tier-B sources.
- [ ] PEEF intermediate/undergraduate/MPhil programs and the student portal (robots-blocked): capture by hand if needed.
- [ ] Check the HEC scholarship directory for other programs.
