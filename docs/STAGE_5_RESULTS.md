# Stage 5 Results — Retrieval and Answer Contract Baseline

## Current outcome

Stage 5 local hardening and evaluation are complete. The accepted web interface remains unchanged. A workspace can contain all eight supplied PDFs; semantic retrieval remains scoped to that workspace and adds the topic, page, and document-governance evidence needed for multi-turn and cross-policy questions.

## Changes verified

### Conversational retrieval

Dependent questions are detected with a small transparent language heuristic. When a question contains follow-up wording such as “which one,” “that,” or “should I use,” semantic search receives up to two recent user questions plus the current question. Generic “Can I” alone no longer marks a question as dependent, avoiding topic pollution. Previous assistant text is deliberately excluded because it may be wrong and is not policy evidence.

Questions about current, standard, latest, older, versioned, replaced, superseded, or applicable policy rules receive a short applicability hint for semantic retrieval. This is search vocabulary, not evidence supplied to the answer.

Short location fragments such as “To Asia?” and document-conflict questions are also treated as dependent turns. This corrects the observed web sequence where a region-only follow-up lost the lodging topic and favored the historical policy.

### Document applicability context

The normal top-five semantic evidence remains intact. The retriever then adds the first chunk of the two strongest matching documents when absent. In the supplied corpus, those opening chunks contain policy title, identifier, version, effective date, scope, and supersession language. They are passed with their real PDF/page provenance and may be cited like any other retrieved chunk.

For the two strongest matching document pages, the chat path also adds up to two missing neighboring chunks. This matters because the current Asia-Pacific standard amount and its conditional exception are separate chunks on the same PDF page. Page companions preserve Stage 3's cross-page diversity while ensuring a selected exception cannot hide the adjacent standard rule.

Broad policy comparisons, explicit complete-list requests, and questions about whether guidance is still/definitely/explicitly authoritative now use top 20 with up to 20 missing chunks from selected pages and the existing document headers. Ordinary fact questions keep the smaller budget. This remains bounded retrieval, not an exhaustive review guarantee for arbitrarily large libraries.

### Prompt and citations

The system prompt now explicitly separates evidence from conversational reference resolution, requires the conclusion in the first sentence, distinguishes true conflicts from explicitly superseded rules, and requires complete conditions without irrelevant details. Geography, policy scope, exact thresholds, historical questions, and partial answers are addressed explicitly. The default response allowance is 1,000 tokens to accommodate multi-policy comparisons.

Inline citation markers are canonical. Grouped references such as `[S1, S2]` are expanded, every inline ID must exist in retrieved evidence, and public `[1]` numbering follows first appearance. The redundant `source_ids` list is normalized from those validated markers instead of causing another model call when only that metadata differs. Unknown, malformed and public numeric markers remain errors. Invalid JSON, grounding status or citations receive at most two corrective attempts; a third failure returns an error and persists no partial turn. No-evidence requests abstain deterministically without calling Gemini.

## Reproducible results

The original all-eight-document retrieval evaluation remains **12/12 answerable cases passed**. Its unsupported parental-leave question remains diagnostic because nearest-neighbor retrieval always returns something even when the corpus lacks an answer.

The multi-turn evaluation indexes all eight PDFs into one temporary workspace and passes **22/22 turns**:

- Asia-Pacific current-policy sequence: 3/3;
- Tokyo exception and approval follow-up: 2/2;
- remote-work eligibility and country follow-up: 2/2;
- non-reimbursable expenses and “Are you sure?” confirmation: 2/2;
- the exact Europe, Zurich, Asia, and document-conflict web sequence: 4/4;
- gift disclosure/prohibition boundary follow-up: 2/2;
- data classification and authority follow-ups: 3/3;
- procurement threshold follow-up: 2/2;
- complete travel-to-security topic switch: 2/2.

For all Asia-Pacific turns, retrieval included `reimbursement_2025.pdf` page 2 for the rule and page 1 for version/applicability/supersession evidence. In the screenshot regression, page 2 now contains both the standard-limit and exception chunks.

The non-reimbursable regression exposed and corrected an intent-detection bug: the internal label `Current question:` was accidentally interpreted as a user request for current-policy/version context, so applicability terms were added to every semantic query. Intent detection now examines only the user's actual questions. The ordinary query and its confirmation follow-up both retrieve `reimbursement_2025.pdf` page 2, which contains the explicit non-reimbursable list.

The complete deterministic suite also verifies:

- recent user topic inclusion for a dependent follow-up;
- document-start enrichment for the strongest sources;
- successful recovery through a second bounded correction;
- friendly failure after three invalid responses;
- no partial persistence on invalid/provider failures;
- unchanged history ordering, conflict mapping, and insufficient-context mapping.
- startup configuration constraints, vector-count mismatch and cleanup failure;
- retry after failed ingestion and relational preservation on deletion failure;
- atomic chat persistence and controlled quota/timeout/provider errors;
- all-eight-PDF upload, chat, citation, persistence and restore through the API.

The full test suite was rerun after the user requested complete testing and passes **124/124**. Python compilation, Bash launcher syntax, and evaluation JSON parsing also pass. Node/browser automation is unavailable in this environment and remains a disclosed UI-testing gap.

Run the two retrieval evaluations independently with:

```bash
python scripts/evaluate_retrieval.py
python scripts/evaluate_conversation_retrieval.py
```

## What remains unverified

Live Gemini checks are recorded separately from retrieval and fake-provider tests. Early runs exposed real answer errors despite correct evidence: a 30/60-day threshold conflation, omission of requested topics, unsupported carry-over of Zurich into an ordinary Europe question, grouped citation leakage and malformed refusal JSON. These findings prompted the changes above. Provider failures are never counted as passes.

The full source review and expected handling are in `docs/POLICY_CONFLICT_BOARD.md`; cases and human-review rubrics are in `evaluation/policy_answer_cases.json`. The final local exact-evidence evaluation passes **33/33** scenarios with prompt SHA-256 `a032304ca618367d5aeee5abe3db489edd67b60f178f6ac89f0a02e55fb9942b` and case SHA-256 `f654e77492e270ced6a8f39404fc464940f4b69ee37574644297442c39c88e9e`. The expanded set adds exact receipts/procurement/eligibility boundaries, complete lists, Tokyo conditions, travel approvals, data authority silence, cross-policy scope, home-office cycles, VPN/cloud controls and no-invented-total behavior.

A complete approved live run passed **33/33 evidence checks and 33/33 automated answer checks** using `gemini-3.5-flash-lite`, prompt SHA-256 `d5ce2827ff5f4954c7611e21baf9f49de7ff6570cb64a96493b1a18d0baaced7`, and case SHA-256 `96ee3b05fbe1c5b29628aa1ed7549af0ec7349c96a9570a0bdf87e6c3cff8941`. Human reading was intentionally stricter than the regex score: it found historical-label clarity and vendor-meal threshold-scope defects. The final prompt, runtime guards and rubrics correct those issues; current focused live Zurich and vendor-meal regressions pass. The last narrow guard changes were not followed by another complete 33-call run, so that distinction remains explicit rather than being represented as a single final-version 33/33 pass.

Model correctness remains probabilistic. These controls materially improve evidence, data integrity and formatting reliability but cannot prove that every future phrasing will receive a correct answer. Full results, commands and remaining gaps are consolidated in `docs/TESTING_REPORT.md`.
