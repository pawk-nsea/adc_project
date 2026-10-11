# Staged Plan and Progress

## Current position

- **Current stage:** Stage 5 complete; Stage 6 is the next optional stage.
- **Current boundary:** The local prototype, accepted Stage 4.5 interface, robustness evaluation, conflict handling and implemented blueprint are complete. Enterprise architecture remains conceptual work for Stage 6.
- **Next action:** Start Stage 6 only when the user chooses to move from the local prototype to enterprise architecture, LLMOps, governance and adoption planning.
- **Progress legend:** Not started · In progress · Complete · Blocked.

## Stage 0 — documentation, requirements, and source-data inspection

**Status:** Complete.

**Goal and scope:** Establish authoritative references, traceable requirements, staged work, conceptual boundaries, and initial decisions. Inspect the supplied case and policy corpus without implementing the application.

**Temporary Stage 0 restrictions:** Documentation and read-only inspection only. No application code, tests, model prompts, dependency installation, framework setup, model/API calls, or deployment configuration. These restrictions expire when the user explicitly starts a later stage; permanent repository rules in `AGENTS.md` continue to apply.

**Tasks and relevant IDs:**

- Inspect repository instructions and preserve existing work.
- Transcribe and verify the complete case PDF.
- Extract all P-, R-, D-, E-, and S-series items into the tracker.
- Inspect policy structure and identify retrieval/evaluation risks (P-002, E-002, S-010).
- Create the requested documentation set and log initial decisions (D-003, D-004, E-004).

**Dependencies:** Accessible case PDF and sample corpus.

**Outputs:** `AGENTS.md`, `reference/CASE_BRIEF.md`, `docs/REQUIREMENTS.md`, `docs/PLAN.md`, `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, and `README.md`.

**Observable completion criteria:** All requested files exist; transcription covers the entire six-page PDF and is extraction-cross-checked; every case requirement/deliverable/recommendation/evaluation criterion is tracked; policy corpus findings and unresolved questions are recorded; no implementation artifacts are created.

**Progress and unresolved questions:** Criteria met. Twelve ambiguities remain documented in `docs/REQUIREMENTS.md`; none prevents completing Stage 0.

## Stage 1 — application foundation

**Status:** Complete.

**Goal and scope:** Establish the smallest readable Python API structure and explicit contracts without yet implementing full ingestion/RAG behavior.

**Tasks and relevant IDs:**

- Resolve A-001, A-003, A-004, A-008, and relevant non-functional assumptions.
- Select and record framework, relational storage direction, model boundary, dependency/configuration approach, and API validation/error conventions (P-001, P-004–P-006, P-013–P-014, R-001–R-003, E-001).
- Define conversation, document, chunk, and interaction concepts with migration-friendly identifiers.
- Add minimal foundation tests and honest local setup documentation.

**Dependencies:** User authorization to start Stage 1; decisions recorded as accepted before dependent work.

**Outputs:** Minimal application skeleton, configuration boundary, API contracts, foundational tests, updated decisions and README.

**Detailed implementation blueprint:** See `docs/PROTOTYPE_BLUEPRINT.md` for the proposed stack, repository layout, API contracts, data model, request flows, implementation order, verification strategy, and exclusions.

**Observable completion criteria:** The selected framework starts locally; endpoint contracts are discoverable and input validation is tested; health/basic foundation behavior works; no endpoint falsely claims ingestion or chat completion.

**Progress and unresolved questions:** FastAPI application, environment settings, SQLAlchemy/SQLite schema, public contracts, explicit `501` placeholders, health endpoint, and eight foundation tests are implemented. The API was also started under Uvicorn and checked through localhost. Python 3.14 and Starlette's threaded `TestClient` were excluded from the verified setup after reproducible hangs; Python 3.13 and direct ASGI transport are verified. Vector, parsing, and model choices remain open for their stages.

## Stage 2 — PDF ingestion and indexing

**Status:** Complete.

**Goal and scope:** Turn valid policy PDFs into traceable chunks, embeddings, vector entries, and persistent metadata.

**Tasks and relevant IDs:**

- Implement upload/conversation behavior and PDF validation/parsing (P-002, P-005–P-007).
- Design and explain logical chunking with page/source traceability (P-008, E-002).
- Implement embedding and vector indexing through explicit interfaces (P-009–P-010).
- Persist filename/upload timestamp and return truthful indexing confirmation (P-011–P-012).
- Test representative structures and defined error cases; document PDF support boundary (A-005, A-012).

**Dependencies:** Stage 1 contracts and selected local components/model approach.

**Outputs:** Working ingestion flow, persistence/index artifacts, unit/integration tests, updated documentation.

**Detailed Stage 2 plan:** See `docs/STAGE_2_PLAN.md` for component choices, boundaries, data contracts, chunking, failure consistency, tests, and the approval checkpoint.

**Observable completion criteria:** Representative supplied PDFs upload and become retrievable; stored metadata and chunk provenance can be inspected; invalid inputs fail clearly; repeated-ingestion behavior is documented and tested.

**Progress and unresolved questions:** Implemented page-wise `pypdf` extraction, model-token-aware chunks, local ONNX MiniLM embeddings, persistent Chroma vectors, relational metadata, synchronous confirmation, validation, duplicate detection, and partial-failure cleanup. Nineteen tests pass. A real-stack check indexed all eight policies into 22 persistent chunks and verified reopened-store counts. Retrieval quality and conflict resolution intentionally remain Stage 3 concerns; concurrent duplicate uploads remain a documented prototype limitation.

## Stage 3 — retrieval verification

**Status:** Complete.

**Goal and scope:** Prove semantic retrieval quality separately from answer generation.

**Tasks and relevant IDs:**

- Build a small labeled question set covering direct facts, tables, cross-policy references, conflicts, and missing answers (P-016, E-002, S-010).
- Choose retrieval parameters with evidence and record limitations.
- Verify source/page traceability and assess freshness/conflict signals (P-003, A-006–A-007).

**Dependencies:** Indexed sample corpus from Stage 2.

**Outputs:** Reproducible retrieval checks, baseline results, documented parameter choice and known failures.

**Observable completion criteria:** Retrieval checks report expected sources and ranked results against stated thresholds; failures are visible and decisions cite results.

**Progress and unresolved questions:** Same-model cosine retrieval, strict conversation/model filtering, and page-diversified top-five results are implemented. Twenty-eight tests pass. The real evaluation retrieved all labeled evidence for 12/12 answerable cases; the initial non-diversified baseline was 11/12. Older policies can still outrank current policies, and nearest-neighbor search returns text for unsupported questions. These are recorded in `docs/STAGE_3_RESULTS.md`; authority and abstention are not silently inferred.

## Stage 4 — chat, conversation history, citations, and interaction persistence

**Status:** Complete.

**Goal and scope:** Complete a grounded, context-aware chat flow using verified retrieval.

**Tasks and relevant IDs:**

- Resolve history counting and final response/citation contracts (A-002–A-003, A-007).
- Retrieve the latest five messages and construct the four-part prompt (P-015, P-017).
- Invoke the selected LLM boundary, ground/abstain appropriately, and map evidence to citations (P-003, P-018, S-016).
- Persist user and assistant interaction records and return JSON (P-019–P-020).

**Dependencies:** Stages 1–3; model approach and data-handling decision.

**Outputs:** End-to-end chat behavior, persistence, citations, history tests, failure/abstention tests.

**Observable completion criteria:** Demonstrated multi-turn requests use only the defined recent history, cited answers map to retrieved PDFs, unsupported questions follow documented behavior, and interactions persist in order.

**Progress and unresolved questions:** The Gemini provider, explicit prompt, five-message history, structured response, citation validation, conflict/abstention behavior, API integration, and atomic persistence are implemented. Thirty-eight automated tests pass, including Gemini request mapping and Stage 4 success/failure paths. The real Gemini smoke check answered the current-versus-older Asia-Pacific lodging-limit question, returned citations to both PDFs and all four relevant pages, and persisted exactly two messages. Mistral remains documented as a superseded provider decision. See `docs/STAGE_4_RESULTS.md` for evidence and limitations.

## Stage 4.5 — usable web demo

**Status:** Complete.

**Goal and scope:** Add a small employee-facing browser workflow over the completed API so users can upload policies, chat, and read citations without manually managing a conversation ID. Preserve the required API endpoints and avoid changing the RAG pipeline.

**Tasks and relevant IDs:**

- Serve an accessible responsive UI at `/` while preserving `/docs` (optional enhancement under R-004).
- Generate and retain the technical conversation ID automatically.
- Add a read-only conversation-summary endpoint for reliable saved-chat selection.
- Provide clear upload, indexed-source, chat, citation, conflict, insufficient-context, timeout, and error states.
- Update the launcher and run guidance after the interface is verified.

**Dependencies:** Completed Stages 1–4; user confirmation of the UI stack, layout, restore endpoint, and citation-preview boundary.

**Outputs:** FastAPI-served web assets, conversation restore contract, focused checks, manual browser checklist/results, and updated documentation.

**Detailed plan:** See `docs/STAGE_4_5_WEB_UI_PLAN.md`.

**Observable completion criteria:** A first-time user can launch the app, upload one or more PDFs, ask a cited question, interpret non-answer/error states, and reopen a saved chat without typing or remembering a conversation ID. Every application launch starts with a fresh chat. `/upload`, `/chat`, and `/docs` remain compatible.

**Progress and unresolved questions:** The FastAPI-served HTML/CSS/JavaScript interface, automatic workspace lifecycle, sequential uploads, chat rendering, citation/status treatments, responsive behavior, and launcher change are implemented. A later bounded extension adds independently scrollable source/chat regions plus a server-backed saved-chat list, first-question titles, switching, and confirmed permanent deletion. Focused checks pass; the user accepted the overall visual direction before this extension. Restored messages still cannot reconstruct the live answer-status badge because that status is not separately persisted. See `docs/STAGE_4_5_RESULTS.md`.

## Stage 5 — robustness checks and evaluation

**Status:** Complete for the local prototype, including approved hosted-model evaluation.

**Goal and scope:** Test failure modes, consolidate prototype quality evidence, and add only justified improvements.

**Tasks and relevant IDs:**

- Exercise malformed/non-PDF uploads, empty text, duplicate uploads, missing conversations, model/storage failures, contradictory sources, and prompt/context limits (P-001–P-020, E-001–E-002).
- Run end-to-end evaluation and document limitations, security boundaries, latency observations, and reproducibility.
- Consider optional additions only where they materially demonstrate a criterion (R-004).

**Dependencies:** Complete prototype path.

**Outputs:** Automated checks, evaluation report/baseline, refined error handling and operational notes.

**Detailed plan:** See `docs/STAGE_5_PLAN.md`.

**Observable completion criteria:** All mandatory prototype acceptance criteria have linked evidence or an honestly documented gap; checks run reproducibly; known risks and exclusions are explicit.

**Progress and unresolved questions:** Conversational query expansion, bounded high-recall context, scope-aware answer validation, citation canonicalization, two bounded corrections, startup validation, cross-store compensation, and atomic chat persistence are implemented. The complete suite passes 124/124; retrieval passes 12/12 direct cases and 22/22 conversation turns; exact evidence passes 33/33 policy scenarios. All eight PDFs were reviewed into `docs/POLICY_CONFLICT_BOARD.md`. The approved complete Gemini run passed 33/33 automated checks; human review found additional Zurich/vendor-meal defects, which were converted into guards and final focused live regressions. Exact outcomes and limitations are recorded in `docs/STAGE_5_RESULTS.md` and `docs/TESTING_REPORT.md`.

## Stage 6 — enterprise architecture, LLMOps, governance, and adoption strategy

**Status:** Not started.

**Goal and scope:** Design a pragmatic global platform and business-facing roadmap without claiming that proposed enterprise components exist.

**Tasks and relevant IDs:**

- Design system integration, asynchronous ingestion, low-latency chat, caching, and cloud mapping (S-001–S-008).
- Define deployment, automated evaluation, regression gates, artifact versioning, data-quality controls, and feedback improvement (S-009–S-014).
- Define monitoring, groundedness guardrails, drift handling, incident ownership, and 10,000-person adoption/training (S-015–S-018).
- Tie architecture choices to risk, cost, business value, and measured outcomes (E-003).

**Dependencies:** Prototype lessons/evidence; stakeholder constraints for cloud, security, residency, identity, budget, and service levels.

**Outputs:** Architecture and pipeline visuals, roadmap, governance/operating model, adoption program, strategy presentation content.

**Observable completion criteria:** Each S-series acceptance criterion maps to a presentation section; flows and responsibilities are clear; assumptions and provider-specific choices are explicit; stakeholder narrative is review-ready.

**Progress and unresolved questions:** Not started; cloud and enterprise constraints remain open.

## Stage 7 — final documentation, presentation, and interview demo

**Status:** Not started.

**Goal and scope:** Package verified work into a clear, reproducible submission and presentation.

**Tasks and relevant IDs:**

- Validate clean local run instructions and finalize design-decision summary (D-003–D-004).
- Prepare 1–2 prototype slides and the three-pillar strategy deck (D-005, S-004).
- Rehearse a concise demo including a normal answer, conflict/freshness case, unsupported question, citations, and known limitations.
- Audit requirement evidence, links, language, and submission contents (D-001–D-002, E-001–E-004).

**Dependencies:** Stages 1–6; user direction on submission format and presentation constraints.

**Outputs:** Final README/docs, presentation materials, demo script, requirement evidence, repository link or ZIP when explicitly authorized.

**Observable completion criteria:** A clean-environment rehearsal succeeds; all mandatory items have evidence or clearly disclosed gaps; slides and demo fit the agreed timing; final package contains no secrets or unsupported claims.

**Progress and unresolved questions:** Not started.
