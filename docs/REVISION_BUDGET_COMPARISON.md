# Correction-budget comparison — DEC-066

14 October 2026. **Keep one correction as the application default.** In this five-question observation, allowing three or five corrections makes no difference: every sequence was accepted by the end of its first correction, including four deficient final answers.

## Controlled design

Five previously deficient DEC-061 questions were frozen before requests: Zurich lodging, vendor-paid reimbursement, Confidential storage, late expense claims and incomplete trip totals. Current prompts, both Gemini `gemini-3.5-flash-lite` models, retrieval, validation, authority metadata and correction feedback were held fixed. All five local evidence checks passed; actual live retrieved text/source ordering matches the local preflight. Source hashes match after the experiment.

One live trajectory per question used up to six attempt cycles in an isolated evaluation process. Its identical shared prefixes represent budgets of one, three and five corrections (two, four and six attempts). The normal acceptance gate stopped each trajectory; no manual rejection or continuation after acceptance was introduced. This avoids regenerated starting-draft variability and duplicated API calls. These are correlated prefix outcomes from five sequences, **not fifteen independent live runs**. Malformed-audit rechecks can consume an attempt cycle without revising a draft; none occurred here.

The user approved US$0.15 for this comparison. Metering reserved conservative costs before physical calls, including existing provider retries. Questions were spaced by 15 seconds; reported pipeline latency excludes this deliberate inter-question delay and one-time ingestion. Timing includes evaluation recording overhead and is not HTTP/browser latency.

## Budget comparison

| Allowed corrections | Fully sound final answers | Partial / incorrect | False approvals / false rejections | Mean pipeline elapsed | Logical / physical calls | Input / output tokens |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1/5 (20%) | 2 / 2 | 4 / 0 | 4.95 s | 16 / 16 | 69,505 / 2,154 |
| 3 | 1/5 (20%) | 2 / 2 | 4 / 0 | 4.95 s | 16 / 16 | 69,505 / 2,154 |
| 5 | 1/5 (20%) | 2 / 2 | 4 / 0 | 4.95 s | 16 / 16 | 69,505 / 2,154 |

All budgets yield five final responses, the same statuses/citations and the same actual work: eight generation and eight verification calls. **The physical total is 16 calls, not 48.** Four of seven audited bad candidates were falsely accepted (57.1%); the only fully sound candidate was accepted, so no false rejection was observed in this small selection. All returned citations passed structural checks; four answers still have semantic or controlling-support defects.

Three justified rejections led to corrections: geography improved, reimbursement relevance improved, and current-versus-historical storage interpretation improved. None became fully sound; all three revised candidates were prematurely accepted. Their audit reasoning is not uniformly sound: initial Zurich status feedback is incomplete, and the storage audit overstates explicit supersession.

## Comparison with saved observations

The same five DEC-061 questions had **0/5 fully sound answers**, two partial, two incorrect and one missing final response; 15 logical calls, 3.78 s mean pipeline elapsed, and 63,958 reported tokens (62,308 input / 1,650 output). This current observation has 1/5 fully sound, two partial and two incorrect, with five final responses, 16 calls, 4.95 s mean and 71,659 tokens.

The trip-total response had already succeeded in DEC-062 after the missing-information fix and remains sound here. The new observation is not a correction-budget gain. Historical prompts and runtime implementation differ, and starting drafts/audits can vary; increased elapsed time and token counts cannot be attributed to allowing additional corrections when none were used. No new full-suite score or statistically reliable latency effect is established.

## Exact questions and final answers

Each answer below is shared by all three correction budgets. Raw initial drafts, audits, feedback and exact messages are preserved in the artifacts.

### 1. zurich_exception

**Question:** How much can I spend per night on lodging in Zurich?

For Zurich, which is in Europe, the standard lodging limit is EUR 220 per night (excluding taxes) [1]. Additionally, for designated high-cost cities including Zurich, the cap may increase to USD 230, which requires pre-trip Finance approval [1].

**Status:** `answered`. **Semantic grade:** FAIL. **Actual corrections:** 1.

- [1] reimbursement_2025.pdf, page 2

Correction restores the European EUR 220 standard and excluding-taxes condition, but still authorizes the USD 230 exception without preserving the geographic scope/list ambiguity; answered should be conflicting_sources.

Initial geography rejection is justified but status feedback is incomplete; the final ambiguous entitlement is falsely approved.

### 2. vendor_paid_dinner_claim

**Question:** Can I get reimbursed for a vendor-paid dinner?

Because a vendor-paid dinner is already covered by the vendor, there is no out-of-pocket employee expense for the company to reimburse; however, employees may accept vendor-sponsored meals provided they comply with both the Travel & Expense Policy and the Code of Business Conduct to avoid conflicts of interest [1] [2]. If any related expenses or reimbursements are involved, employees must record and disclose them [1] [2], adhering to meal caps and documentation rules [3].

**Status:** `answered`. **Semantic grade:** PARTIAL. **Actual corrections:** 1.

- [1] Code of Business Conduct.pdf, page 1
- [2] vendor_procurement_policy.pdf, page 1
- [3] reimbursement_2025.pdf, page 2

Correction answers that an employee has no expense to reimburse when the vendor paid, but the controlling 2025 employee-incurred-expense definition on page 1 (S7) is not cited; acceptance rules and meal limits are substituted for that support.

Initial reimbursement-relevance rejection is justified; final approval overlooks missing controlling citation support.

### 3. confidential_local_storage_gap

**Question:** Where can I store my Confidential data?

Confidential data must be encrypted at rest and in transit [1]. While historical interim guidance permitted confidential data to be stored on local encrypted laptops [2], the governing Information Security & Data Classification Policy specifies encryption requirements but does not explicitly address local storage permissions [1].

**Status:** `answered`. **Semantic grade:** PARTIAL. **Actual corrections:** 1.

- [1] information_security_data.pdf, page 1
- [2] data_guidelines.pdf, page 1

Correction preserves current encryption requirements and a local-permission gap, but omits the applicable personal-cloud prohibition for the where-can-I-store question.

Initial current-permission rejection is justified, though the audit overstates formal supersession of interim guidance; final approval misses a material storage restriction.

### 4. late_expense_gap

**Question:** Will my current travel expense claim definitely be paid if I submit it 45 days after returning?

No, your travel expense claim will not definitely be paid if submitted 45 days after returning. Under the governing reimbursement policy, expenses submitted after 30 days of travel completion may be denied without exception. [1]

**Status:** `answered`. **Semantic grade:** FAIL. **Actual corrections:** 0.

- [1] reimbursement_2025.pdf, page 1

The no-guarantee conclusion is correct, but the answer moves may-be-denied-without-exception from after 60 days to after 30 days, inventing a consequence for the 31–60 interval.

False approval: its assessment states the correct 30-day deadline and after-60-day consequence yet passes the incompatible after-30-day candidate.

### 5. no_single_trip_total

**Question:** What is the single total amount I can spend on a five-day Asia-Pacific trip, including hotel, meals, taxes, and tips?

A single total amount cannot be established because tax amounts, specific daily meal selections, and tip variations are unspecified. However, the controlling component limits for a standard five-ay Asia-Pacific trip are as follows: lodging is capped at USD 180 per night excluding taxes [1], daily meal caps are USD 20 for breakfast [1], USD 25 for lunch [1], and USD 45 for dinner [1], and tips are capped at 15% [1]. For designated high-cost cities (Tokyo, Singapore, Hong Kong, Zurich), the Asia-Pacific lodging cap may increase to USD 230 with pre-trip Finance approval [1].

**Status:** `answered`. **Semantic grade:** PASS. **Actual corrections:** 0.

- [1] reimbursement_2025.pdf, page 2

Keeps cited component limits and their units, explains why no all-inclusive total can be established, and does not assume a lodging-night count or invent an aggregate. The literal city list is not a decision about Zurich applicability; a minor five-ay typo is non-material.

Valid partial-support answer accepted with answered status and current-policy citation.

## Cost and remaining limits

**Total:** 16 physical calls, 69,505 input + 2,154 output = 71,659 tokens, no reported thinking tokens; estimated **US$0.02624**, below US$0.15. No provider retries/errors, malformed audits or unknown-usage reserve occurred. Estimates use [Google's checked standard paid-tier rates](https://ai.google.dev/gemini-api/docs/pricing) of US$0.30 input and US$2.50 output including thinking per million tokens, excluding taxes and any free-tier/caching credits; account billing was not inspected.

Extra correction budgets are triggered only after rejection. They cannot repair answers the verifier has already accepted. This experiment therefore demonstrates identical budget behavior for these observed sequences, but does not establish whether three or five corrections help cases still correctly rejected after the second draft: no such sequence occurred. Do not claim additional revisions were generated or that larger budgets can never help.

The main remaining failures are unresolved applicability treated as permission, missing controlling citation support, omitted storage restrictions, and an assessment/verdict mismatch on deadlines. Keep the default; no prompt, model, retrieval or architecture fix is adopted in this stage. No additional live run, full suite, commit or push.

Artifacts: `evaluation/revision_budget_comparison/` contains frozen cases/baselines/criteria, local preflight, exact full live report, per-cycle messages/checks/outcomes/timings, physical cost ledger, manual assessment and the evaluation-only wrapper. Runtime data uses temporary storage; existing chats and policies are untouched.
