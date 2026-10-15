# General answer-quality improvements

14 October 2026 · DEC-069. The history/retrieval fixes improve the reported conversation, but **semantic verification remains unreliable on some policy questions**. This report separates observed improvements from remaining errors. It does not establish a new whole-suite accuracy score.

## Implemented changes

- **Keep the current task separate.** Language heuristics provide retrieval hints only. Generation receives the actual question and role-separated history; verification receives that same question and recent user messages separately. A relative-clause `that` or an opening `and` no longer automatically turns an earlier question into another task.
- **Prioritize selected evidence pages.** Complete selected pages within the existing six-chunk page and 12/24-companion bounds before supplementary headers/neighbours. Search, embeddings and chunking are unchanged. Unselected or over-budget passages can still be omitted.
- **Clarify answer scope and reasoning.** Instructions ask models to preserve conditions/units, distinguish permission from prerequisites, request missing controlling facts, cite the requested conclusion and exclude unrelated prior answers. A conditional permission claim still needs a rule granting permission; uncertainty must not become a ban.
- **Use the measured model configuration.** Both calls now use `gemini-3.8-flash`, LOW reasoning, with separate drafting/audit instructions. Output ceilings remain 4,096/3,072 tokens. Optional generation reasoning configuration is passed through the existing provider and runners. The non-secret local model override is updated; the API key is unchanged.
- **Redraft after rejection.** Keep the original question/evidence and defect feedback without appending the rejected answer as another assistant turn. The two-attempt budget and malformed-audit recheck are unchanged.

Production code and prompts contain no sample-policy answers, amounts or location-specific branches. Expected answers remain evaluation data. HTTP contracts, storage schemas, dependencies and policy PDFs are unchanged.

Implementation: [conversation context](../app/services/conversation_context.py), [generation input](../app/services/prompt_builder.py), [audit input](../app/services/claim_verification.py), [chat](../app/services/chat.py), [retrieval](../app/services/retrieval.py), [generation instructions](../app/prompts/system.txt), [verification instructions](../app/prompts/verification.txt), [model settings](../app/config.py).

## Live regression results

All grades below are manual policy/rubric reviews unless identified as automated.

| Check | Result |
| --- | --- |
| Same 24 selected cases before these changes | 5 fully sound, 9 partial, 7 incorrect, 3 without a final answer |
| 24-case snapshot with final models/prompts, before the fresh-redraft change | **17 fully sound, 2 partial, 4 incorrect, 1 without a final answer**; all five known-good controls retained |
| Five-case fresh-redraft probe | 4 fully sound, 1 incorrect. The laptop case rejects historical permission and succeeds on its second draft; the vendor case still overstates documentation obligations |
| Eight final focused repeats with fresh redrafting | **5 fully sound, 3 incorrect**; both controls retained. Automated patterns pass 8/8, demonstrating why they are not semantic scores |
| Three real-history conversation scenarios, each repeated three times | **19/21 turns fully sound, 2 partial**, no missing responses |
| Ten balanced generic verifier fixtures | **10/10 expected verdicts**, including five correct controls and five defective answers |

The 24-case snapshot is not rerun after the small correction change; do not combine later observations into a new 24-case score. Its correction path was exercised by the laptop and gift follow-up cases, both covered again under the final code. Other phases use different prompts/models and remain separate artifacts. The ten matched drafting cases produce 8 fully sound Flash answers versus Lite's 6, but Flash also introduces two incorrect extra obligations; a larger model is not sufficient by itself.

**Reported conversation:** All three expense turns return the four documented exclusions without repeating the old meal limits; previously all three reproductions failed. All three other topic switches and all three genuine encryption follow-ups retain the right subject. One dinner answer omits the daily basis; one expense answer adds an unrelated computer-use restriction. Those two turns are partial, not passes. The corrected core expense response is therefore more reliable in this small test, while answer focus is not guaranteed.

**Remaining observed errors:** Encryption requirements still become unsupported storage permission in one final repeat. Vendor answers still promote “should record” to a mandatory obligation or omit the controlling citation. The snapshot also contains a misleading affirmative gift answer, a wrong conflict status and an offer to verify a supplier against Portal records the application cannot access. Valid source IDs and an empty audit issue list do not establish correctness. These are current limitations, not only hypothetical model risks.

## Verifier selection

Frozen candidates isolate auditing from draft generation. The first six rows use the same 35 cases: 21 defective drafts and 14 correct controls. Every arm already receives the separated current question, so the Lite row is not the untouched original system.

| Configuration | Expected verdicts | Decision |
| --- | ---: | --- |
| Lite 3.5 MINIMAL, fuller existing checks | 26/35 | Baseline |
| Lite 3.5 MINIMAL, shorter candidate | 27/35 | Reject: two correct controls rejected |
| Flash 3.8 LOW, fuller existing checks | 31/35 | Better fixed-case agreement |
| Flash 3.8 LOW, shorter candidate | 28/35 | Reject: misses more defects |
| Flash 3.8 LOW, citation/status clarifications | 33/35 | Retains all 14 correct controls; two false approvals |
| Flash 3.8 MEDIUM, same 3,072-token ceiling | 33/35 | Reject: correct control produces invalid audit; slower |
| Flash LOW, expanded 40-case calibration | 35/40 | Five false approvals remain; 14/14 controls accepted |
| Flash HIGH, 8,192 tokens, separate focused ten cases | 5/10 | Reject: two invalid audits, one 429, mean 30.81 s |
| Pro 3.1 preview LOW, 8,192 tokens, separate focused twelve cases | 8/12 | Four false approvals remain; mean 8.54 s; not promoted |
| Final permission clarification, Flash and Pro, six focused cases each | 6/6 each | Both reject two unsafe drafts and accept four controls; retain Flash LOW |

The final clarification is a narrow repeat, not a new 40-case score. These calibration sets were used to tune instructions; none is an independent accuracy benchmark. Pro catches some defects Flash misses, but it has not been validated end to end and still misses important defects. Retain the stable Flash configuration rather than infer reliability from a more expensive probe. [Flash 3.8 supports LOW/MEDIUM/HIGH, not MINIMAL](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash). Thinking consumes output allowance, so raising reasoning can leave invalid/truncated JSON; the exact finish details of the invalid probes were not retained. [Google's token-limit explanation](https://ai.google.dev/gemini-api/docs/thinking#token-limits-and-max_output_tokens).

## Local checks, usage and reproducibility

- **150 pytest checks pass.** They include question boundaries, task parity, user-only verifier history, selected-page priority, reasoning configuration, redraft input preservation and bounded failures. The obsolete four-attempt fallback test now checks the existing two-attempt error with no saved turn.
- **22/22 local retrieval-conversation turns pass** with real cached MiniLM and temporary storage. The selected-page priority defect has a synthetic regression. Three real Europe-trip queries contain current meal caps before and after the change; they show preservation, not demonstrated recovery of the historical omitted passage.
- Python/JSON parsing, whitespace/diff review and active documentation links are checked separately. Tests exercise controlled behavior; they do not establish live accuracy or enterprise readiness.

This stage uses **637 physical requests: 636 HTTP 200 and one HTTP 429** in the rejected HIGH probe. Reported successful usage totals **2,806,897 tokens**. Estimated known usage is **US$2.4972** using reported cached input, or US$2.5411 without cache discounts. One rejected request supplies no token usage and is excluded from that estimate. Rates are published standard prices as of 14 October 2026; invoices, tier allowances and taxes are uninspected. [Google pricing](https://ai.google.dev/gemini-api/docs/pricing).

The 24-case snapshot averages 5.56 seconds versus the same baseline selection's 3.34 seconds; final repeated conversations average 4.58 seconds. Deliberate spacing and ingestion are excluded; evaluation overhead is included. These single-run figures are not serving/load targets.

The [conversation runner](../scripts/evaluate_conversations.py) records its actual generated history, drafts/audits, timings and source hashes. The [verifier runner](../scripts/evaluate_verifier.py) accepts prior user context. [Conversation fixtures](../evaluation/conversation_answer_cases.json) cover the reported sequence, another relative-clause topic switch and a genuine follow-up. [Generic verifier fixtures](../evaluation/question_scope_verifier_cases.json) exercise the defects using unrelated studio rules.

Ignored raw reports, frozen inputs/prompts, manual grades, before-source snapshot and request ledgers remain under `evaluation/results/general_quality_fix_2026-10-14/`. Existing saved chats are neither read nor changed. No commit, push or deployment is performed.
