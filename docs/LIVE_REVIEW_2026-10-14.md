# Live answer review — 14 October 2026

The main defect in the supplied conversation is **question interpretation**, followed by unreliable semantic verification. The meal amounts in the pasted answers match the policy. The third answer adds the previous topic because a complete new question is incorrectly treated as a dependent follow-up. More correction attempts do not address that input error.

This review evaluates the current application without changing its code, prompts, models, defaults or saved workspaces. DEC-068 records the spending and Gemini data-transfer authorization.

## Results

| Evaluation | Scope | Result |
| --- | --- | --- |
| End-to-end policy fixtures | 44 questions | 34 fully sound; six partial; three incorrect; one without a final answer |
| Natural-language fixtures | 24 questions | 12 fully sound; seven partial; three incorrect; two without a final answer |
| Edge-case fixtures | Six questions | Four fully sound; one partial; one incorrect |
| **All answer fixtures** | **74 questions** | **50 fully sound (67.6%); 14 partial; seven incorrect; three without a final answer** |
| Synthetic fixed-draft verifier | 14 candidates | 12 matching verdicts; two sound candidates falsely rejected |
| Saved real-draft verifier | Five candidates | Two matching verdicts; all three deficient candidates falsely approved |
| Supplied conversation | Three independent three-turn runs | Expense question fails after verification in all three runs |
| Fresh-workspace comparison | Each supplied question asked independently | All three return answers; the expense answer has the correct list, without meal caps |
| Local retrieval | Existing labeled suites | 12/12 answerable cases and 22/22 conversation turns pass |

All 74 answer cases were attempted: 71 returned final answers and three exhausted validation/correction. No case was skipped for provider availability. The existing automatic answer checks pass 48/74; this is a separate pattern score, not the semantic score above. Expected fixture evidence is present in 74/74 preflight cases, which does not prove that every needed passage or condition was retrieved.

Manual grades assess the requested decision, factual/applicability accuracy, material conditions, citation support and status. Partial answers have a correct core or safe gap but a material omission, misleading framing or citation/status defect. Small optional wording improvements do not automatically fail an answer. For example, an accurate gift-disclosure gap does not require an invented recipient, and a narrow statement about what this security policy requires is distinguished from blanket permission to leave data unencrypted. Raw grades and reasons are retained for all cases.

These are single passes of selected fixture sets, plus three conversation repetitions. They are not a representative employee accuracy benchmark. The 74-case denominator differs from the earlier 44-case report, and the prompts changed after that historical run; neither score establishes a controlled improvement or regression. The natural-language and policy subsets also differ in difficulty, so their score difference does not isolate wording alone.

## What happened in the supplied conversation

The [follow-up detector](../app/services/conversation_context.py) searches short questions for words including `that`. It does not distinguish a reference such as “that expense” from a relative clause such as “expenses that are non reimbursable”. The exact third question is therefore resolved as:

```text
ANd howm uch can I spent on lunch, dinner, and breakfast?
Follow-up: what are expenses that are non reimbursable?
```

[Chat orchestration](../app/services/chat.py) passes that combined question to [semantic verification](../app/services/claim_verification.py). The verifier treats the earlier meal question as another requested task. In all three reproductions:

1. The first draft gives the correct four non-reimbursable items.
2. The verifier rejects it for omitting breakfast/lunch/dinner limits.
3. The revised draft switches to meal limits and omits the expense list.
4. Verification rejects that draft too; the application returns a controlled error.

This reproduces the failure mechanism rather than the exact originally pasted output. Original generation/audit payloads were not retained, so the old response's precise path is unknown.

A fixed-candidate comparison keeps the supplied third answer and policy pages constant. With the original expense question, the verifier flags the meal paragraph as irrelevant. With the combined question above, it approves the same paragraph. Each fixed audit ran once; the deterministic resolver result and repeated end-to-end traces provide the stronger evidence.

The error is not caused by missing expense-list text: the current policy's four-item list is present in the verifier input. A local wording probe also misclassifies “What is the policy for gifts that exceed USD 250?” after an unrelated meal question. Removing typos does not solve the relative-clause mistake.

## Other demonstrated weaknesses

- **Wrong numerical boundaries can pass verification.** `late_expense_gap` moves possible denial without exception from after 60 days to after 30. `timing_three_boundaries` says day 60 is not late, despite the 30-day submission deadline; its regex checks pass. Separately, the synthetic verifier rejects a correct answer by claiming that 80 is not greater than 30.
- **Conditions and silence become permission.** Two gift answers infer affirmative acceptance at USD 250 from the over-250 prohibition plus disclosure. `natural_confidential_laptop` revives historical encrypted-laptop permission because the current policy requires encryption. Encryption is not storage authorization.
- **Geographic applicability remains unresolved.** Both Zurich question variants return an unsupported exception interpretation; a correction case produces no final answer. The saved Zurich draft correctly describes the ambiguity but is falsely approved with `answered` instead of the required `conflicting_sources` status.
- **Related rules substitute for the requested decision.** Some vendor-dinner answers discuss acceptance/documentation without clearly resolving employee reimbursement. One natural answer reaches the right no-reimbursement conclusion but cites only conduct/procurement passages rather than the current travel policy's employee-incurred-expense definition.
- **Missing inputs are not consistently handled.** The unspecified late-expense question receives only travel rules, omitting the equipment deadline and a category/timing clarification. A Dropbox question is answered as if the account were known to be personal.
- **Audit prose and the issue list can disagree.** The saved vendor audit describes a reimbursement qualification problem but returns an empty issue list. The saved gift audit approves uncited policy facts under `insufficient_context`. Python enforces the returned issue/status gate, not the truth or completeness of those judgments.
- **Verification can add unnecessary requirements.** In the meal runs, audits sometimes demand a USD 90 total or hypothetical client-paid-dinner details that were not explicitly requested. One correction even produces an unsupported blanket statement that general non-client drinks are not covered. The synthetic verifier also rejects advice to contact the named Ethics Office, treating a clarification suggestion as an invented mandatory procedure.

## Improvements in priority order — proposals

| Priority | Proposed change | Why and how to verify |
| --- | --- | --- |
| 1 | Resolve only actual missing references; keep complete new questions independent. Preserve the current question separately from any historical reference context in both model inputs. | Fix the demonstrated relative-clause defect at its source. Replay the exact three-turn sequence and complete questions containing `that`; retain genuine continuations such as “What about Tokyo?” and “What if I encrypt it?”. Both readers should assess only the current requested answer. |
| 2 | Recalibrate verification against both correct controls and known bad real drafts before selecting prompt/model changes. Assess verdict, status and the reason together. | Require correct treatment of time boundaries, payer/action, current authority and source support. Include the false rejections as controls so stricter checking does not merely increase failures. Compare stronger/different verifier configurations on identical evidence; choose from measured results, not an assumption that greater spend or more thinking fixes errors. |
| 3 | Make answer scope and missing information explicit. Lead with the requested decision or gap; omit unrelated previous topics and hypothetical scenarios. | Check the exact employee questions, short/typo variants and topic changes. A meal-cap answer should not become a general ethics summary; a missing drinks allowance should remain a gap rather than an invented prohibition. Preserve meaningful units and exceptions. |
| 4 | Strengthen evaluation of relevance, status and citation support. | Keep regex checks as diagnostics. Add the complete conversation to reusable answer evaluation, not just PDF/page retrieval checks. Validate the 30/60/61-day decisions individually; include supported facts under an incorrect abstention status and correct conclusions with wrong controlling citations. |
| 5 | Retain bounded retrieval improvements as separate work. | The earlier selected-page completeness gap remains a realistic limitation, but did not cause this conversation's failure. Test completing already-selected pages within the existing budget against omitted-context cases and known-good controls before changing retrieval. |

More retries alone are not the recommended first change. They repeat the wrong combined task in the meal conversation, and an accepted incorrect answer does not enter another correction cycle. Hard-coding policy amounts or automatically approving valid citations would also leave the reasoning problem unresolved.

## Clearer targets for the three supplied answers

These are source-based writing targets, not new production rules or deployed responses:

- **Dinner/drinks:** “The daily dinner reimbursement cap is USD 45; tips are capped at 15%. Alcohol is reimbursable only as part of a documented client meal, with the applicable disclosure requirement. The policies do not give a separate drinks allowance.” Cite current travel page 2 and conduct page 1 for disclosure. Do not assume tips are an extra allowance on top of the meal cap.
- **Breakfast/lunch/dinner:** “Daily meal caps: breakfast USD 20, lunch USD 25, dinner USD 45.” Cite current travel page 2. A combined figure, if requested, must preserve these separate caps.
- **Non-reimbursable expenses:** “Personal travel upgrades, mini-bar charges, airline lounge memberships, and expenses incurred by family members.” Cite current travel page 2; omit meal spending limits.

## Usage, preservation and artifacts

The review made **240 physical Gemini HTTP requests**, all returning HTTP 200: 179 for the full answer suites (92 generation, 87 verification), 38 for the 12 meal/fresh-workspace turns, four supplied-answer audits and 19 fixed-draft checks. No recorded SDK/HTTP retries or unknown-usage responses occurred. This distinguishes successful provider requests from the six application-level no-answer outcomes across the full suite and conversation reproductions.

Reported usage is **1,057,275 input + 26,281 output = 1,083,556 tokens**, including 63,561 reported cached input tokens and zero thinking tokens. At [Google's checked standard Gemini 3.5 Flash-Lite rates](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite), the estimate is **US$0.36572** using reported cache tokens, or **US$0.38289** before cached-input discounts. Billing tier, invoices, taxes and account-specific credits were not inspected.

Mean full-suite answer-pipeline time is **2.70 seconds**, median **2.14**, maximum **5.99**. These figures include retrieval, corrections and recording overhead; they exclude deliberate two-second spacing and initial ingestion, and are not browser latency or a concurrency benchmark.

All 61 protected application/script/test/configuration/fixture files match the pre-run hashes. Production prompts, models, defaults and behavior are unchanged. Temporary evaluation databases/vector stores were removed by their context managers; existing saved workspaces were not used or modified. No full deterministic test suite, commit or push ran.

Raw artifacts remain locally under ignored `evaluation/results/live_review_2026-10-14/`: `answers.json`, `meal_reproduction.json`, both verifier reports, `manual_assessment.json`, `requests.json`, local preflight/retrieval logs, source-hash manifests and the evaluation-only recording driver. These raw files are excluded from Git; this report preserves the review findings. Existing historical reports are preserved.
