# Evaluation evidence and limitations

Updated 14 October 2026. This report separates repeatable structural checks from probabilistic answer-quality observations. [README.md](../README.md) contains commands; [the question/answer record](LIVE_QUESTIONS_AND_ANSWERS.md) preserves the complete DEC-061 run.

## What the checks establish

Deterministic tests use explicit fake model providers. They exercise uploads, storage failures, schemas, citations, conversation isolation/persistence, bounded correction and API errors. They prove application behavior under controlled inputs, not Gemini's semantic judgment.

Local retrieval runners use the real cached MiniLM model, sample PDFs and temporary Chroma/SQLite storage. They test evidence inclusion independently of generation. Live runs additionally call Gemini and require manual assessment; regex scores are only regression signals.

## Saved live observations

| Experiment | Scope | Result and decision |
| --- | --- | --- |
| DEC-056: prompt comparison | Five real questions, fixed drafts and three synthetic probes | No meaningful end-to-end improvement; candidate prompts restored |
| DEC-057: stronger verifier | Twelve fixed drafts per model | Lite 9/12 gold verdicts versus Flash 10/12; sound audits 7/12 versus 8/12, with a regression and invalid audit. Retain Lite |
| DEC-058: evidence/contract comparison | Fixed bad drafts and correct controls | Context pruning was not retained. Direct comparison and Python-derived verdict improved fixed-case agreement from 9/12 to 11/12; one false approval remained |
| DEC-061: expanded end-to-end suite | One 44-case pass | **32/44 fully acceptable**, seven partial, two incorrect and three without a final response. 107 calls, mean 2.96 s, 521,561 tokens, estimated US$0.17838 |
| DEC-062: missing-information fix | Six end-to-end cases, two false abstentions and one authorized total repeat | Initial pass: five fully sound responses and one partial total. Latest observations: all three affected cases return appropriate responses, three controls retained, both false abstentions rejected. Six-case controls preceded the last total-specific clarification; no final-prompt full rerun |
| DEC-066: correction-budget comparison | Five previously deficient questions; identical shared prefixes for 1, 3 and 5 corrections | All sequences stop within one correction: identical 1/5 fully sound, two partial and two incorrect; four false approvals. Extra-budget depths unexercised; keep default. Sixteen physical calls, mean 4.95 s, 71,659 tokens, estimated US$0.02624. [Exact answers and limitations](REVISION_BUDGET_COMPARISON.md) |
| DEC-068: complete current-fixture rerun and meal diagnosis | 74 end-to-end questions, 19 fixed drafts, 12 conversation/fresh-workspace turns and four supplied-answer audits | **50/74 fully sound**, 14 partial, seven incorrect, three without a final answer. Synthetic verifier 12/14 verdicts, saved verifier 2/5. Expense turn fails in all three conversation repetitions due to an incorrectly combined question. 240 physical calls, 1,083,556 tokens, estimated US$0.36572 using reported cached input. [Full diagnosis and proposed improvements](LIVE_REVIEW_2026-10-14.md) |
| DEC-069: general quality improvements | Selected 24 questions, focused repeats, fixed audits and 21 actual-history turns | Before-fix selection: 5/24 fully sound. Final-model/prompt snapshot before fresh redrafting: **17/24 fully sound**, two partial, four incorrect, one without a response. Final eight repeats: **5/8 fully sound**, three incorrect despite 8/8 pattern passes. Actual-history turns **19/21 fully sound**, two partial; no prior meal caps in all three expense turns. Generic verifier **10/10**. [Changes, limits, scopes and usage](QUALITY_IMPROVEMENT_RESULTS.md) |

DEC-062 used 16 physical calls, 70,227 tokens and estimated US$0.02517. Its initial six-case pass used 12 calls versus the saved baseline's 17, with mean elapsed 2.69 s versus 3.29 s. The first total answer assumed five nights from five days and was falsely accepted; that trace remains preserved. A single follow-up removed the assumption. No new combined 44-case score is inferred.

These are small, selected, usually single-run observations rather than randomized benchmarks. Model/network variability, changed question scopes and incomplete older token measurements limit causal comparisons. Costs are historical standard-rate estimates, not inspected invoices or current pricing quotes.

DEC-068 is a new assessment of the current fixtures, not a controlled comparison with DEC-061. The policy subset is 34/44 fully sound, natural-language subset 12/24, edge cases 4/6; their scopes/difficulties differ. All 74 fixture evidence checks pass, but the automated answer patterns pass only 48/74 and sometimes disagree with manual grades. No production change is made by this evaluation.

## Known reasoning and retrieval gaps

The examples below preserve failures observed before DEC-069; its final repeats still confirm unsupported permission, overstated obligations and citation defects. The [general quality-improvement report](QUALITY_IMPROVEMENT_RESULTS.md) records the changes and the narrower post-fix checks; earlier errors are not presented as new-run results. These observations concern model reasoning and evidence selection, not broken PDF/page citation IDs. The [README limitation table](../README.md#known-limitations) explains current extraction, chunking, metadata, API and storage constraints separately from untested enterprise risks.

- **Applicability:** Zurich's named exception and geographic scope are ambiguous. A reader can treat list membership as overriding the heading and produce or approve the wrong lodging decision. Source review and geography/exception calibration cases can expose this; they do not automatically settle ambiguous policy wording.
- **Requested decision:** Generation can substitute acceptance guidance for vendor-paid reimbursement, or omit the controlling citation. The verifier can approve that related-rule summary even when it misses the employee's actual decision. Review the actor, payer and requested action against the applicable rule; current prompt instructions already ask for this, but do not guarantee it.
- **Boundaries and completeness:** Readers can merge deadline/consequence thresholds, inherit historical authorization or fill missing procedures/quantities. This changes the employee's practical answer despite apparently relevant sources. Fixed-draft calibration and review of conditions, units and explicit gaps are possible mitigations; more correction attempts cannot help a draft already falsely accepted.
- **Omitted evidence:** A local replay of the saved Europe-budget question retrieves meal caps in the superseded 2022 policy, but omits the second chunk containing caps from the current policy. In that pre-DEC-069 replay, the two strongest page hits are historical; ordinary enrichment completes those pages while leaving another selected page partial. DEC-069 now prioritizes all selected pages within the original limits; unselected or over-budget evidence can still be omitted. Both model inputs lack that passage, so verification cannot check the current caps. Original provider payloads/audits were not persisted; this is a reconstruction rather than a historical wire trace.
- **Question contamination (DEC-068):** The pre-fix follow-up heuristic interprets the relative-clause word `that` as a reference in “expenses that are non reimbursable”. Verification then demands an answer to both the previous meal-budget question and the new expense question. All three current reproductions fail after correction. The same supplied answer's irrelevant meal paragraph is rejected under the raw expense question and accepted under the combined question. The current expense-list evidence is present, so this defect precedes retrieval/answer grading rather than requiring a missing-page fix.
- **Verifier false approvals/rejections (DEC-068):** Wrong 30/60-day boundaries, current permission inferred from encryption/historical rules and incorrect status/citation handling still pass some audits. Two correct synthetic candidates are rejected; all three deficient saved candidates are approved. DEC-069 separates the question from history and calibrates a stronger verifier; its fixed-draft checks still include two false approvals. These are improvements with measured limits, not guaranteed semantic verification. More correction attempts alone do not resolve falsely accepted answers.

The smallest proposed retrieval fix is to complete all already-selected pages within the existing companion budget before adding headers/neighbours. It has not been implemented during submission cleanup. Generation should describe a gap in supplied evidence rather than infer that an entire policy lacks a rule. No policy-specific production rule or answer is introduced.

## Submission validation

The approved cleanup preserves prompts, model defaults, retrieval/correction logic, frontend behavior, policy PDFs and the case transcription. Changes are documentation/ignore rules, explicit declaration of already-used Pydantic, an unused import removal and SDK client resource cleanup.

Earlier cleanup verification completed:

- **41 targeted pytest cases passed:** seven SDK configuration/resource/error/retry checks, plus 34 focused API checks covering upload, chat, citations, statuses, correction, history and the all-eight-PDF flow with fake model providers. No complete-suite score is claimed.
- **Eight packaged smoke checks passed:** build/install the wheel, start Uvicorn from the installed package in an isolated directory, serve UI/assets/docs, index a PDF with actual local MiniLM/Chroma, list/restore its workspace, return the original PDF and reject keyless chat without partial persistence.
- Required prompts/frontend assets and the explicit Pydantic requirement are in the wheel. All eight policy PDFs and eight evaluation fixture files remain eligible for Git; generated results, environment variants, runtime state and archives are ignored.
- Five saved-candidate verifier fixtures also pass their local structural/citation checks, without live calls. Current documentation links, shell syntax, Python parsing, dependency consistency and `git diff --check` pass. Before/after hashes show that prompts, defaults, retrieval/correction, frontend, policy bytes, scripts and case transcription are unchanged; Gemini request configurations also match.

The first offline build attempt lacked setuptools in the existing development environment. The normal isolated build succeeded using the already-declared build dependency. Package startup reused existing Python 3.13 dependencies and cached embeddings; it does not establish a fresh dependency installation on an independent machine or another OS. No full live suite, paid API calls, commit or push occurred.

## Documentation-pass verification (DEC-067)

The readability pass preserves executable logic and adds no quality feature. All 47 Python files compile and their syntax trees match the starting working tree after removing docstrings. Shell syntax, current documentation links and whitespace checks pass; OpenAPI and both Gemini request schemas match. Frontend/shell edits contain only comments; settings, dependencies, prompts and evaluation data remain unchanged.

Five focused pytest checks produce **four passes and one failure**. The failure, `test_four_unreadable_structured_responses_return_verified_abstention`, expects the superseded four-attempt saved fallback instead of the current two-attempt `502`. It also fails on the pre-edit snapshot, confirming an existing mismatch. The assertions are retained with an explanatory docstring because this stage permits documentation only. No full suite or live model evaluation ran; earlier scores and remaining semantic/retrieval gaps are unchanged.

## Reproducing and retaining evidence

Reusable question fixtures remain under `evaluation/`. The end-to-end runner supports selected cases, temporary storage and resume; the verifier runner supports fixed candidates and prior user context. `scripts/evaluate_conversations.py` adds actual multi-turn answer runs with repeats, rubrics and temporary storage; `--live` is required for hosted calls. Generated reports belong under ignored `evaluation/results/`.

Raw experiments remain locally in their original evaluation directories. Superseded documentation is preserved under ignored `docs/archive/` with a hash manifest, and the duplicate validation snapshot/ZIP remain local. These development artifacts are excluded from the GitHub submission; this report and the complete historical question/answer record are the curated evidence. Earlier full-suite counts in the decision history apply to their original revisions.

## General quality-fix verification (DEC-069)

All **150 local pytest checks pass**, including the current two-attempt error contract and fresh-redraft input regression. The earlier documentation-only failure was an obsolete expectation, now corrected without restoring the old fallback. Real cached-model conversation retrieval passes 22/22; Python/JSON parsing and active documentation links are checked. New live runs use sample/synthetic data and temporary storage, leaving existing saved chats untouched.

The final model defaults are Flash 3.8 LOW for both calls; output ceilings and the two-attempt budget remain unchanged. The full 74-case answer suite is not rerun after these changes. The 24-case snapshot precedes the fresh-redraft change, so later probes are reported separately. False approvals remain; neither all-green regex checks nor larger models establish semantic correctness. See the [quality report](QUALITY_IMPROVEMENT_RESULTS.md) for exact scopes, manual findings, rejected model/prompt options and US$2.4972 estimated known usage.
