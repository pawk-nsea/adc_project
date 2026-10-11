# Stage 5 — Robustness and Answer-Quality Plan

> Historical planning baseline. The implemented result uses inline-marker
> canonicalization and up to two bounded corrections after live evaluation exposed
> limitations in the original exact-membership/single-retry design. See DEC-037,
> `docs/STAGE_5_RESULTS.md`, and `docs/SOLUTION_BLUEPRINT.md`.

## Goal

Demonstrate that a workspace containing all eight supplied PDFs can retrieve governing evidence, answer direct questions, preserve topic across follow-ups, produce verifiable citations, and fail safely. Stage 5 improves and evaluates the RAG path; the accepted Stage 4.5 interface remains visually unchanged.

No RAG system can guarantee every possible answer from a small evaluation set. The objective is a transparent, reproducible baseline with explicit failure behavior rather than an unsupported claim of perfect correctness.

## Problems observed in the accepted UI

1. A question about the standard Asia-Pacific limit retrieved both 2022 and 2025 amount pages but omitted the 2025 page establishing that it supersedes prior versions. The model therefore reported a false unresolved conflict.
2. Short questions such as “Which one is newest?” and “Should I use reimbursement 2025?” were embedded without their earlier topic, causing incomplete retrieval and abstention despite relevant indexed documents.
3. Gemini occasionally returned answer markers that did not match its declared source IDs. Validation correctly blocked the answer, but there was no recovery attempt and the public error was overly technical.
4. The prompt described grounding rules but did not strongly require a direct conclusion, applicability reasoning, marker/list parity, or completeness without irrelevant details.

## Workstreams

### 1. Full-workspace and conversational retrieval

- Keep all uploaded PDFs in the same conversation scope; no global cross-workspace leakage.
- For a dependent follow-up, embed the current question together with up to two recent user questions. Do not use prior assistant prose as evidence or retrieval facts.
- Add explicit applicability vocabulary for current/version/supersession questions.
- Preserve the normal top-five semantic results, then attach the first/header chunk for the two strongest matching documents when it is not already present. This adds version, effective-date, scope, and supersession evidence without replacing fact-bearing chunks or broadly increasing semantic `top_k`.
- Keep source/page provenance for every added chunk and validate with an all-eight-document conversation set.

### 2. Complete generation contract

- Separate policy evidence, conversational reference resolution, and untrusted document handling.
- Require the direct conclusion in the first sentence.
- Define answered, insufficient, and true-conflict behavior precisely.
- Require explicit supersession to govern older content; dates alone still do not establish authority.
- Require relevant conditions and exceptions while excluding unrelated retrieved facts.
- Define exact source-marker/source-list parity and ordering.

### 3. Citation recovery and safe failure

- Preserve strict application-side citation validation.
- Retry exactly once when model output violates the citation contract, using the same evidence plus a narrow correction instruction.
- Validate the retry identically; never weaken or auto-invent citations.
- If the retry also fails, return a friendly verifiable-answer error and persist neither side of the turn.

### 4. Evaluation and robustness

- Add the screenshot conversation as a multi-turn retrieval regression.
- Add Tokyo-exception and remote-work follow-ups.
- Retain the existing direct, table, cross-page, conflict, cross-policy, and missing-answer cases.
- Exercise malformed input, unknown conversations, provider errors, duplicate uploads, empty evidence, and conversation isolation using focused checks.
- Record live-provider checks separately from deterministic checks; do not claim a live result unless it was actually run.

## Observable completion criteria

- Selecting all eight PDFs in the UI indexes each into the same automatically managed workspace with individual status.
- The multi-turn retrieval evaluation retrieves all labeled governing pages, including the 2025 supersession and Asia-Pacific limit pages, for every travel follow-up.
- A direct current-policy question is not reported as an unresolved conflict when explicit supersession evidence is retrieved.
- A follow-up question retains its earlier user topic without treating an assistant answer as policy evidence.
- One malformed citation response is recovered when the retry is valid; two malformed responses produce a friendly error and no persisted partial turn.
- The prompt and focused regression checks document the answer contract.
- Remaining limitations and any live-provider uncertainty are stated explicitly.

## Stage boundary

Stage 5 does not add authentication, OCR, a production reranker, policy-owner approval workflows, cloud infrastructure, or broad enterprise governance. Those concerns belong to Stage 6 or a production implementation.
