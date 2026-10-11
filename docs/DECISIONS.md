# Decision Log

Statuses are **proposed**, **accepted**, or **superseded**. An accepted documentation decision does not imply an application or technology decision.

## DEC-001 — Source hierarchy and transcription workflow

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should the team use the case without repeatedly extracting it or accidentally changing its meaning?
- **Related requirements:** All; especially E-004.
- **Realistic alternatives:** Reopen the PDF for every task; work only from extraction output; maintain a verified Markdown transcription while retaining the PDF as authority.
- **Choice and reasoning:** The PDF remains authoritative. Use the verified `reference/CASE_BRIEF.md` transcription for routine work and `docs/REQUIREMENTS.md` for traceability. Return to the PDF only for ambiguity, discrepancy, incomplete extraction, or source change. This reduces repeated work while preserving an escalation path to the source.
- **Disadvantages and trade-offs:** The transcription is another artifact that can become stale or contain a transcription error.
- **Assumptions and evidence:** The supplied PDF is stable, readable, unencrypted, and six pages. Raw and layout extractions agreed on substantive wording during Stage 0.
- **Verification approach:** Cross-check transcription headings, numbered sections, bullets, endpoints, exact “last 5” detail, citations, deliverables, all strategy questions, and evaluation criteria against the PDF; repeat if the source changes.
- **Conditions for revisiting:** The PDF changes, a discrepancy is found, or a visually encoded detail was lost in extraction.

## DEC-002 — Requirement classification and evidence policy

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How can mandatory scope remain distinct from suggestions, permissions, and judging criteria?
- **Related requirements:** R-001–R-004, E-001–E-004, all mandatory items.
- **Realistic alternatives:** Keep one undifferentiated checklist; organize by source only; assign stable IDs and explicit classifications with acceptance evidence.
- **Choice and reasoning:** Track mandatory requirements/deliverables, recommendations, permissions/assumptions, and evaluation criteria separately under stable IDs. A requirement remains pending until observable evidence exists.
- **Disadvantages and trade-offs:** The tracker is longer and must be maintained whenever scope or evidence changes.
- **Assumptions and evidence:** The case explicitly distinguishes required Python from recommended technologies and says extra functionality is optional.
- **Verification approach:** Audit every statement in the case transcription against at least one tracker entry; validate linked evidence at each stage boundary.
- **Conditions for revisiting:** ADC clarifies scope/classification or the source document changes.

## DEC-003 — Stage-gated delivery

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should work remain explainable and avoid premature implementation choices?
- **Related requirements:** E-001–E-004 and all deliverables.
- **Realistic alternatives:** Build the entire solution at once; plan in broad prototype/strategy halves; use observable stages that isolate foundation, ingestion, retrieval, chat, hardening, strategy, and packaging.
- **Choice and reasoning:** Use Stages 0–7 in `docs/PLAN.md` and work only on the stage explicitly requested. Each stage has visible completion criteria and updates requirements/decisions before handoff.
- **Disadvantages and trade-offs:** More checkpoints and documentation upkeep; some integration discoveries may require revisiting earlier choices.
- **Assumptions and evidence:** The candidate wants to build and understand the project stage by stage.
- **Verification approach:** At each boundary, report changed artifacts, relevant checks, evidence, and uncertainty; do not mark a stage complete with unmet criteria.
- **Conditions for revisiting:** The user changes sequencing or a dependency makes the sequence impractical.

## DEC-004 — Stage 0 contains no implementation setup

- **Status:** Accepted (10 October 2026)
- **Question or problem:** What activity is in scope during initial setup?
- **Related requirements:** D-003–D-004, E-004.
- **Realistic alternatives:** Scaffold the API while documenting; install/evaluate candidate stacks; perform documentation and read-only inspection only.
- **Choice and reasoning:** Stage 0 is limited to documentation and read-only source-data inspection. No code, tests, prompts, dependencies, framework, model calls, or deployment configuration are introduced, matching the explicit request and keeping future choices reversible.
- **Disadvantages and trade-offs:** Technology assumptions and runnable commands remain unresolved.
- **Assumptions and evidence:** This is a temporary stage restriction, not a permanent ban on implementation.
- **Verification approach:** Inspect the final repository diff/file list for only requested documentation while preserving supplied data and PDF files.
- **Conditions for revisiting:** It expires only when the user explicitly requests a later implementation stage.

## DEC-005 — Treat supplied PDFs as untrusted source data

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Can text inside policy PDFs direct repository or agent behavior?
- **Related requirements:** P-002, P-007–P-010, S-010, S-015–S-016.
- **Realistic alternatives:** Treat extracted content as instructions; manually whitelist every sentence; treat documents solely as application data with provenance and validation boundaries.
- **Choice and reasoning:** Policy documents are data, never coding-agent instructions. Later ingestion must preserve provenance and avoid allowing document text to control tools, system behavior, or implementation work.
- **Disadvantages and trade-offs:** Requires explicit trust boundaries and adversarial checks in later stages.
- **Assumptions and evidence:** Documents may contain arbitrary text; the current corpus is benign but conflicts across versions.
- **Verification approach:** Review prompt construction and tests for instruction hierarchy, injection resistance, provenance, and grounded output in Stages 4–5.
- **Conditions for revisiting:** The trust model or document source changes; the separation itself should remain.

## DEC-006 — Keep implementation and cloud stack open

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Should documentation setup select frameworks, databases, vector stores, model providers, or cloud services?
- **Related requirements:** R-001–R-003, S-008, A-008–A-010.
- **Realistic alternatives:** Adopt all named recommendations immediately; choose a complete stack from personal preference; defer choices until requirements and environment constraints can be evaluated.
- **Choice and reasoning:** Do not select a technology stack in Stage 0. Prototype choices will be made before their implementation stage using simplicity, explainability, reproducibility, data handling, cost, and evidence. Enterprise choices will also require organizational/cloud constraints.
- **Disadvantages and trade-offs:** Architecture remains conceptual and Stage 1 begins with decision work.
- **Assumptions and evidence:** The case mandates Python but describes the named tools as recommendations and allows stubs or real model APIs.
- **Verification approach:** Before adding a dependency or provider, add or update a decision with realistic alternatives and a verification plan.
- **Conditions for revisiting:** Stage 1 authorization and environment facts; enterprise stakeholder constraints in Stage 6.

## DEC-007 — Separate local prototype from enterprise target

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should a minimal walking skeleton relate to a global platform without overengineering the prototype?
- **Related requirements:** P-001, S-001–S-018, E-003.
- **Realistic alternatives:** Build enterprise patterns directly into the prototype; describe one design as if it serves both scales; keep a minimal local prototype and separately map its concepts to a future governed platform.
- **Choice and reasoning:** Maintain two explicit architecture views. The prototype proves ingestion, retrieval, chat, persistence, and citations simply. The enterprise design may introduce asynchronous ingestion, managed services, identity, governance, observability, evaluation gates, and adoption operations.
- **Disadvantages and trade-offs:** Some components will differ, so the presentation must explain the conceptual migration clearly.
- **Assumptions and evidence:** The case asks for both a minimal working API and a production roadmap; enterprise live upload may be omitted.
- **Verification approach:** Ensure diagrams and narratives label “implemented prototype” versus “proposed enterprise”; never claim proposed services are running.
- **Conditions for revisiting:** A future instruction requires the prototype to demonstrate a specific enterprise mechanism.

## DEC-008 — Use corpus conflicts as planned evaluation cases

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should the deliberately overlapping sample policies influence later verification?
- **Related requirements:** P-003, P-016, E-002, S-010, S-016.
- **Realistic alternatives:** Test only straightforward facts; discard older documents before indexing; retain corpus provenance and explicitly test precedence, conflict disclosure, and abstention.
- **Choice and reasoning:** Preserve all supplied substantive policies during evaluation and create cases covering newer/older versions, explicit supersession, temporary guidance, cross-policy dependencies, and absent answers. The exact prototype conflict policy remains open until its stage.
- **Disadvantages and trade-offs:** Evaluation and response rules become more demanding than simple top-k retrieval.
- **Assumptions and evidence:** Stage 0 found the same T&E policy ID in versions 2.6 and 3.2 with conflicting limits, plus temporary/current work and data-handling conflicts.
- **Verification approach:** Stage 3 labeled retrieval set and Stage 5 end-to-end checks must include these categories and record failures.
- **Conditions for revisiting:** The supplied corpus changes or ADC clarifies authoritative source precedence.

## DEC-009 — Prototype framework and relational persistence stack

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Which local stack best balances case alignment, readability, persistence, and interview explainability?
- **Related requirements:** P-001, P-004–P-020, R-001–R-002, E-001.
- **Realistic alternatives:** FastAPI with SQLAlchemy/SQLite; Flask with direct SQLite; a provider framework such as LangChain over the same components.
- **Choice and reasoning:** Use FastAPI and SQLAlchemy with SQLite. This follows the case recommendations, provides explicit API/data boundaries, and keeps orchestration visible rather than hidden by a large framework. The vector store remains a separate Stage 2 decision.
- **Disadvantages and trade-offs:** SQLAlchemy adds concepts and a dependency compared with direct `sqlite3`; synchronous database access can block an async route under load, which is acceptable only for this small local prototype.
- **Assumptions and evidence:** The prototype is local and small; enterprise scale is a separate design. Startup, schema creation, validation, and route publication were verified in Stage 1.
- **Verification approach:** Eight automated foundation tests cover API health/contracts/schema, and a Uvicorn smoke check confirmed startup plus localhost responses.
- **Conditions for revisiting:** User rejects the proposal, dependency compatibility is poor, or a simpler alternative meets the same acceptance criteria with less operational burden.

## DEC-014 — Verified Python and API-test runtime

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Which local runtime and test path are verified and reproducible for Stage 1?
- **Related requirements:** P-001, E-001, D-003.
- **Realistic alternatives:** Use the system Python 3.14; use the available Python 3.13; test through Starlette's threaded `TestClient`; test through HTTPX's direct ASGI transport.
- **Choice and reasoning:** Support Python 3.11–3.13, use `.python-version` 3.13 for the verified setup, and exercise API requests with HTTPX ASGI transport plus explicit lifespan handling. Pin the direct dependencies actually tested in `pyproject.toml`.
- **Disadvantages and trade-offs:** Python 3.14 is temporarily excluded; direct ASGI tests need a small helper and are less concise than `TestClient` examples.
- **Assumptions and evidence:** In this environment, Starlette's blocking-portal `TestClient` repeatedly hung under both tested FastAPI/Starlette combinations. Direct ASGI requests succeeded, and all eight tests completed on Python 3.13.15.
- **Verification approach:** Recreate the virtual environment with the documented commands, run all tests, start Uvicorn, and check `/health` and `/openapi.json`.
- **Conditions for revisiting:** The test-client/runtime compatibility is resolved and verified, or the supported deployment runtime changes.

## DEC-015 — Stage 2 parsing, embedding, and vector components

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Which components provide a real, local, explainable ingestion path without API credentials?
- **Related requirements:** P-002, P-007, P-009–P-012, R-002–R-003, A-008, A-012.
- **Realistic alternatives:** `pypdf` + local Sentence Transformers + Chroma; hosted Mistral embeddings + Chroma; `pypdf` + Sentence Transformers with manual in-memory similarity/FAISS.
- **Choice and reasoning:** Use page-wise `pypdf`, local `sentence-transformers/all-MiniLM-L6-v2` through Chroma's CPU ONNX adapter, and Chroma `PersistentClient`. Compute embeddings explicitly through our provider and give them to Chroma, keeping model and storage responsibilities visible and independently testable. ONNX replaced the initially proposed `sentence-transformers` Python package after dependency resolution showed that package would install PyTorch plus a multi-gigabyte CUDA stack unnecessary for this CPU prototype.
- **Disadvantages and trade-offs:** A 79.3 MiB first download (roughly 174 MiB cached after extraction), CPU latency, a general-purpose English model, a private Chroma preparation method isolated in the adapter, a second persistence system, and explicit cross-store cleanup.
- **Assumptions and evidence:** The corpus is small, English, text-readable, and contains no OCR-only PDF. Current official documentation supports page extraction, local semantic-search encoding, persistent vector storage, document/metadata records, and metadata filtering.
- **Verification approach:** All eight policies were extracted and indexed with the real model; 22 relationally recorded chunks matched Chroma counts and remained readable through a reopened persistent client. Deterministic fakes cover orchestration/failure tests.
- **Conditions for revisiting:** Dependency/runtime incompatibility, unacceptable download/runtime cost, extraction failures, or a user preference for a hosted embedding API.

## DEC-016 — Stage 2 chunk, duplicate, and failure semantics

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should the first ingestion baseline preserve citation provenance and behave under duplicates or partial failure?
- **Related requirements:** P-008, P-010–P-012, A-005–A-007, A-009.
- **Realistic alternatives:** Whole-page chunks; fixed-size chunks across pages; complex semantic chunking; idempotently return an existing duplicate; reject a duplicate; delete every failed record; retain failed status and remove vectors.
- **Choice and reasoning:** Use page-local logical chunks measured by the model tokenizer, targeting 180 word pieces with a 220 maximum and up to 30 tokens of overlap; reject same-conversation `processing` or `indexed` content duplicates with `409`; keep a failed relational record while deleting partial vectors. Duplicate detection remains application-level so a failed upload can be retried.
- **Disadvantages and trade-offs:** Page boundaries may split related content, overlap duplicates text, `409` requires client action, concurrent duplicate requests are not protected by a database constraint, and retained failure records need eventual operational cleanup.
- **Assumptions and evidence:** Page-level citations are valuable for later trust, files are small, and Stage 3 exists specifically to measure retrieval before tuning.
- **Verification approach:** Tests cover page boundaries, token limits, stable IDs, duplicates in same/different conversations, cleanup after a partial vector write, and stored provenance/counts. Real-stack verification indexed all eight documents without exceeding model input limits.
- **Conditions for revisiting:** Extraction/retrieval evidence shows harmful splits or truncation, users require idempotent retries, or operational requirements define a different failure lifecycle.

## DEC-010 — Model-provider boundary

- **Status:** Superseded by DEC-019 (10 October 2026)
- **Question or problem:** How can the prototype show a real model call while keeping tests deterministic and provider choice replaceable?
- **Related requirements:** P-009, P-018, R-003, A-008.
- **Realistic alternatives:** Stub all model calls; call Mistral directly throughout the services; define small embedding/chat interfaces with deterministic test fakes and a Mistral-backed runtime.
- **Choice and reasoning:** Propose narrow provider interfaces, deterministic fakes for automated tests, and a real Mistral-backed runtime for the demonstrable path. This satisfies the case’s allowed model options while separating repeatable checks from network behavior.
- **Disadvantages and trade-offs:** Interfaces and fakes add code; live use needs credentials, network, cost/rate-limit awareness, and an explicit sample-data handling decision.
- **Assumptions and evidence:** The case permits either stubs or a real API and explicitly mentions Mistral. Current API behavior and exact packages still require official-documentation verification before implementation.
- **Verification approach:** Contract tests run against fakes; a separately reported live smoke check runs only when configured and must never be silently substituted or claimed.
- **Conditions for revisiting:** No acceptable credentials/network are available, data-sharing constraints disallow hosted calls, or a local model is explicitly preferred.

## DEC-011 — Conversation and document scope

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should `conversation_id` creation and uploaded-document visibility behave?
- **Related requirements:** P-005–P-006, P-014–P-016, A-001, A-004.
- **Realistic alternatives:** Global document corpus for every chat; optional server-generated conversation ID; required caller ID that is created on first upload and scopes its documents.
- **Choice and reasoning:** Require a non-empty caller-provided ID. `/upload` reuses it when present or creates it when new; `/chat` will return 404 for an unknown ID. Uploaded documents and retrieval are scoped to that conversation, making the identifier meaningful and avoiding cross-conversation leakage.
- **Disadvantages and trade-offs:** Documents must be uploaded again for another conversation and the design does not model a shared enterprise knowledge base.
- **Assumptions and evidence:** Both endpoint inputs explicitly include `conversation_id`; `/upload` says retrieve/create. The case does not define global visibility.
- **Verification approach:** Integration tests cover create/reuse/unknown behavior and prove that retrieval cannot return another conversation’s chunks.
- **Conditions for revisiting:** User intends a shared corpus, ADC clarifies scope, or later requirements introduce users/knowledge bases independently of conversations.

## DEC-012 — Synchronous upload and history semantics

- **Status:** Superseded (10 October 2026)
- **Question or problem:** What do indexing confirmation and “last 5 messages” mean in the local prototype?
- **Related requirements:** P-012, P-015, A-002, A-005.
- **Realistic alternatives:** Background upload with polling; synchronous upload; five interaction pairs; five individual role messages.
- **Choice and reasoning:** This combined two independent stage decisions. Synchronous upload is now accepted separately in DEC-017. The interpretation of the five latest individual user/assistant records remains proposed until Stage 4.
- **Disadvantages and trade-offs:** Upload latency grows with document size/provider speed; five individual records may split a prior user/assistant pair at the history boundary.
- **Assumptions and evidence:** The prototype corpus is small, and the case explicitly contrasts enterprise slow/fast decoupling while only requiring upload confirmation locally.
- **Verification approach:** API timing/state tests ensure no premature success; history tests use more than five messages and assert exact selection/order.
- **Conditions for revisiting:** User prefers interaction-pair semantics, corpus size makes synchronous upload impractical, or the contract is clarified.

## DEC-017 — Synchronous Stage 2 upload completion

- **Status:** Accepted (10 October 2026)
- **Question or problem:** When may `/upload` truthfully return `indexed` in the local prototype?
- **Related requirements:** P-012, A-005.
- **Realistic alternatives:** Return immediately and expose job polling; process synchronously through verified persistence; return before cross-store verification.
- **Choice and reasoning:** Process the small prototype upload synchronously and return `201 indexed` only after Chroma contains the expected chunk count and SQLite is finalized. This makes the demo contract direct and observable.
- **Disadvantages and trade-offs:** Parsing and CPU inference occupy the request path, so latency grows with file size and this architecture is unsuitable for enterprise ingestion volume.
- **Assumptions and evidence:** Uploads are capped at 10 MiB and the supplied corpus is small. All eight policies completed through the real stack; repeated cached corpus runs took under one second in this environment.
- **Verification approach:** API tests assert response and persisted facts; real-stack verification compares SQLite/Chroma counts and reopens the persistent client.
- **Conditions for revisiting:** Upload sizes or concurrency increase, a job-status contract is added, or enterprise ingestion is implemented.

## DEC-013 — Response and citation contract

- **Status:** Superseded by DEC-019 (10 October 2026)
- **Question or problem:** What JSON shape provides the required PDF citation and remains easy to consume and verify?
- **Related requirements:** P-003, P-020, A-003, A-007.
- **Realistic alternatives:** Answer string containing only inline filename citations; structured citations only; answer markers plus a structured citation array.
- **Choice and reasoning:** Propose `conversation_id`, `answer`, and `citations`. The answer uses `[n]` markers; each structured citation contains matching ID, filename, and one-based page number. This visibly meets the example while making sources machine-readable and verifiable.
- **Disadvantages and trade-offs:** The model output and retrieved evidence must be reconciled carefully; page citations are more demanding than filename-only citations.
- **Assumptions and evidence:** The case requires a PDF citation and JSON but leaves fields/granularity open. The supplied files have extractable page boundaries.
- **Verification approach:** Citation assembly uses retrieval metadata rather than trusting model-invented filenames; tests check marker/source consistency and page validity.
- **Conditions for revisiting:** Page extraction is unreliable, the user wants a simpler contract, or frontend/submission needs require a different schema.

## DEC-018 — Stage 3 retrieval baseline and evaluation

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should retrieval be implemented and judged before adding answer generation?
- **Related requirements:** P-003, P-016, E-002, A-006–A-007.
- **Realistic alternatives:** Rely on manual examples; evaluate only final LLM answers; isolate retrieval with a labeled set and explicit top-k evidence checks; add reranking immediately.
- **Choice and reasoning:** Embed questions with the same normalized MiniLM model, run cosine search in Chroma, enforce conversation/model metadata filters, and return `top_k=5`. After the initial 11/12 result showed same-page chunks crowding out page-spanning evidence, retrieve up to 15 candidates and keep the strongest chunk per document page. Evaluate independently against labeled filename/page evidence across facts, tables, conflicts, cross-policy cases, and an unsupported question. This exposes retrieval failures before an LLM can hide them behind fluent text.
- **Disadvantages and trade-offs:** The small hand-labeled set can overfit the supplied corpus, top five may provide excess context later, cosine rank has no universal answerability threshold, and no reranker or authority/freshness rule is included yet.
- **Assumptions and evidence:** The corpus is small and all document vectors use one model/version. The user approved the Stage 3 plan and explicitly wants page-boundary and contradiction behavior examined.
- **Verification approach:** Twenty-eight tests cover orchestration, validation, real-Chroma ranking, conversation/model isolation, and page diversification. The real-model evaluation over all eight documents improved from 11/12 to 12/12 answerable cases after the documented diversification change; one unsupported case remains diagnostic.
- **Conditions for revisiting:** Labeled recall misses the target, Stage 4 context limits require fewer results, corpus scale increases, multiple embedding versions coexist, or conflict/authority policy is decided.

## DEC-019 — Stage 4 Mistral, grounding, history, and citations

- **Status:** Superseded by DEC-020 (10 October 2026)
- **Question or problem:** How should the prototype turn retrieved evidence and recent history into a safe, verifiable answer?
- **Related requirements:** P-003, P-014–P-020, R-003, A-002–A-003, A-006–A-008.
- **Realistic alternatives:** Deterministic stub only; local chat model; hosted Mistral with free-tier credentials; raw text output; structured answer with application-validated source IDs.
- **Choice and reasoning:** Use the official Mistral SDK with pinned `mistral-small-2603`, temperature `0.1`, and JSON mode, behind a provider protocol with deterministic test fakes. Pass the five latest individual stored messages chronologically, explicit retrieved context, and the separate current question. Require grounded/abstaining/conflict-aware output and validate all model source IDs against retrieval metadata before constructing public citations.
- **Disadvantages and trade-offs:** Live use needs an account, API key, network access, and sends retrieved policy text/history to a hosted service. Low temperature improves consistency but does not make output deterministic or correct. JSON mode still requires schema validation. Conservative conflict behavior can be verbose, and the prototype lacks organizational authority metadata.
- **Assumptions and evidence:** The case permits a real provider and names Mistral. Current official documentation supports free-mode keys with limits, chat completions, JSON output, and the selected model family. The user selected Mistral after reviewing the alternatives.
- **Verification approach:** Test prompt inputs, fake-provider contracts, citation rejection, exact history, persistence, errors, abstention, and conflicts locally. Run and report a separate live smoke test only when a key is configured.
- **Conditions for revisiting:** Data-sharing policy disallows hosted inference, the selected model becomes unavailable, live quality/cost is unacceptable, or a local/deployment provider is required.

## DEC-020 — Replace Mistral runtime with Gemini Flash

- **Status:** Superseded by DEC-022 (10 October 2026)
- **Question or problem:** Which real model can complete the demonstrable chat path after Mistral API access proved unavailable?
- **Related requirements:** P-018, R-003, A-008; supersedes the provider-specific parts of DEC-019 while preserving its grounding, history, citation, and persistence rules.
- **Realistic alternatives:** Keep retrying Mistral; use only the permitted deterministic stub; run a small local model through Ollama; use GitHub Models; use Gemini Flash through the Gemini Developer API.
- **Choice and reasoning:** Replace Mistral with `gemini-3.8-flash` through the official `google-genai` SDK. Gemini provides a stronger general-purpose hosted model than the small CPU-local options practical on this machine, supports Pydantic structured output, and currently has free-tier access. Keep the provider protocol and deterministic test fake; do not silently fall back at runtime.
- **Disadvantages and trade-offs:** Availability and quotas remain external dependencies. Retrieved policy text and recent history leave the machine. Google states that free-tier content may be used to improve its products, so only the artificial case documents are appropriate without further approval. Reviewers need their own key for live use.
- **Assumptions and evidence:** Mistral returned provider-side `429 rate_limited` responses during its first live calls even though its Playground worked, and the user reported the API was disabled for their situation. GitHub Models was retired on 30 July 2026. Google documentation and the installed SDK support Gemini Flash, Python 3.13, Pydantic structured output, temperature, output limits, and request timeouts. The user explicitly selected Gemini instead of Mistral.
- **Verification approach:** Thirty-eight automated tests cover orchestration and Gemini-specific request mapping without network access. The first live request found that the SDK's Pydantic conversion serialized `additionalProperties` incompatibly; its raw JSON-schema option now omits that generation-only keyword while the returned JSON still receives strict Pydantic validation. The repeated live check succeeded with a grounded cross-version answer, four verified page citations, and two persisted messages.
- **Conditions for revisiting:** Gemini access fails, data-sharing approval is unavailable, live quality is inadequate, free-tier conditions change, or a reproducible local model becomes preferable.

## DEC-021 — Gemini request deadline and provider errors

- **Status:** Superseded by DEC-022 (10 October 2026)
- **Question or problem:** Why did the persistent application return a generic Gemini failure after the isolated live check succeeded?
- **Related requirements:** P-001, P-018–P-020, E-001.
- **Realistic alternatives:** Keep a 30-second deadline; use a faster/lower-quality model; increase the deadline; make generation asynchronous; retry indefinitely.
- **Choice and reasoning:** Use a 120-second local-prototype deadline and translate provider timeout and rate-limit errors into explicit `504` and `503` responses. Preserve the current Gemini model for answer quality and keep failed turns out of history. Enterprise latency design remains separate.
- **Disadvantages and trade-offs:** A request may keep a worker occupied for up to two minutes, which is unsuitable for scaled async serving. A longer deadline does not guarantee provider success.
- **Assumptions and evidence:** A diagnostic request using the latest indexed conversation reproduced `504 DEADLINE_EXCEEDED` with the 30-second setting, while the same provider had already completed the Stage 4 isolated check successfully.
- **Verification approach:** Automated tests cover the 120-second SDK configuration, public `504` mapping, and no partial persistence. The same real persistent-conversation request that failed at 30 seconds succeeded with `answered` status after approximately 79 seconds under the new deadline.
- **Conditions for revisiting:** Latency remains unacceptable, a faster model is selected, streaming/background generation is added, or enterprise SLOs are defined.

## DEC-022 — Select Gemini 3.5 Flash-Lite for interactive latency

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Which Gemini model provides usable interactive latency while retaining sufficient grounded policy-answer quality?
- **Related requirements:** P-001, P-018–P-020, E-001; supersedes the exact model and deadline choices in DEC-020 and DEC-021 while preserving Gemini as the provider.
- **Realistic alternatives:** Keep `gemini-3.8-flash` with a long deadline; use retired `gemini-2.5-flash-lite`; select supported `gemini-3.5-flash-lite`; make slow generation asynchronous.
- **Choice and reasoning:** Use `gemini-3.5-flash-lite` with temperature `0.1`, the existing structured-output/citation controls, and a 60-second safety deadline. Retrieval supplies the policy knowledge, so a fast instruction-following model is a better prototype fit than a long-horizon model that makes the Swagger interaction appear broken.
- **Disadvantages and trade-offs:** Flash-Lite may have lower reasoning quality than 3.8 Flash on complex synthesis. Provider availability and free-tier limits remain external dependencies.
- **Assumptions and evidence:** `gemini-3.8-flash` took approximately 79 seconds on one identical-context request and exceeded 120 seconds on another. Google rejected `gemini-2.5-flash-lite` as retired for new users and directed the application to `gemini-3.5-flash-lite`, which answered the same grounded request in 1.69 seconds with a valid structured status and source.
- **Verification approach:** Thirty-nine automated tests pass. The same-context benchmark completed in 1.69 seconds, and the complete two-policy live check returned the correct current/older limits, explicit supersession, and three validated PDF/page citations.
- **Conditions for revisiting:** Answer evaluation shows a material quality regression, latency becomes unstable, the model is retired, or asynchronous generation is introduced.

## DEC-023 — Preserve page diversity without discarding same-page rules

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should retrieval handle a standard rule and its exception when chunking places both on the same PDF page but in neighboring chunks?
- **Related requirements:** P-003, P-016, P-018–P-020, E-002.
- **Realistic alternatives:** Keep exactly one chunk per page; remove page diversification; merge every page into one large chunk; use a diversity-first pass and spend remaining top-k capacity on the next-ranked chunks.
- **Choice and reasoning:** Keep the strongest chunk from each available document page first, preserving the cross-page recall improvement from Stage 3. If that produces fewer than `top_k` results, fill the unused capacity with the remaining candidates in semantic-rank order. This lets a small two-page upload provide both the standard USD 180 limit and the USD 230 conditional exception without allowing duplicate chunks to crowd out distinct pages when five or more pages are relevant.
- **Disadvantages and trade-offs:** Context can contain multiple source IDs with the same filename/page, candidate recall is still bounded, and this heuristic does not understand policy structure. A reranker or section-aware/page-window retriever would be stronger at larger scale.
- **Assumptions and evidence:** The live Asia-Pacific question ranked the exception/meals page-2 chunk first and the standard-limit page-2 chunk second, but strict page deduplication returned only the first plus page 1. The missing standard rule caused a misleading answer even though it existed in the index.
- **Verification approach:** A focused Chroma regression test covers diversity followed by same-page capacity fill. The exact persistent-conversation query is inspected to ensure both page-2 chunks are now returned. A live re-check is left to the user's already-running application because the isolated development environment did not authorize sending stored history and retrieved policy text to the external provider. The full test suite is deliberately not rerun at the user's request.
- **Conditions for revisiting:** Evaluation shows reduced recall, context duplication harms generation, the corpus grows, or section-aware retrieval/reranking is introduced.

## DEC-024 — Add a dependency-light employee-facing web demo

- **Status:** Accepted (10 October 2026); active-ID startup restoration superseded by DEC-029.
- **Question or problem:** How should the completed API be demonstrated without making users operate Swagger or manually coordinate conversation IDs?
- **Related requirements:** P-001, P-004–P-005, P-013–P-014, P-020, R-004, E-001, E-003. This is an optional enhancement, not a new case requirement.
- **Realistic alternatives:** Keep Swagger as the only interface; build a Streamlit/Gradio demo; add a React SPA and Node toolchain; serve a semantic HTML/CSS/plain-JavaScript page from FastAPI.
- **Choice and reasoning:** Use a FastAPI-served single-page “Sources + Chat” workspace using semantic HTML, a small CSS layer, and plain JavaScript. Generate the conversation ID in the browser, retain the active ID locally, and add a read-only server endpoint to restore documents and messages. This removes the main demo friction while keeping one runtime, no frontend build step, and the existing required API contracts. The user explicitly approved Stage 4.5 and requested a chat-first experience similar to the current assistant interaction.
- **Disadvantages and trade-offs:** Plain JavaScript provides less structure as UI complexity grows; the extra read endpoint expands the prototype surface; a local-storage pointer is browser-specific; sequential multi-file uploads are slower than a batch API; citation PDF preview remains unavailable because original files are not retained.
- **Assumptions and evidence:** The case requires a Python REST API, not a frontend, and explicitly permits additional functionality. Live use showed that Swagger forces the user to remember a conversation ID and understand endpoint ordering, which is unsuitable for an employee-facing demonstration.
- **Verification approach:** Focused ASGI checks cover page/static delivery and conversation isolation/ordering. A recorded manual browser checklist covers the end-to-end workflow, reload, responsive layout, keyboard use, and all meaningful result/error states. Stage 5 remains responsible for broader robustness evaluation.
- **Conditions for revisiting:** The user prefers a separate frontend framework, PDF preview becomes required, authentication defines conversation ownership, or the UI grows beyond a small demonstrator.

## DEC-025 — Enrich conversational retrieval with user topic and document headers

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should retrieval find the governing rule across all eight PDFs when short follow-ups omit their original subject and amount-bearing chunks omit version/supersession text?
- **Related requirements:** P-003, P-015–P-018, E-001–E-002.
- **Realistic alternatives:** Embed only the current message; include all prior user/assistant messages; ask the hosted LLM to rewrite every query; globally increase `top_k`; add a production reranker/metadata extraction pipeline; use deterministic follow-up expansion plus bounded document-header context.
- **Choice and reasoning:** Detect dependent wording and prepend up to two recent user questions to the semantic query, never previous assistant claims. Add applicability vocabulary for version/current-policy intent. Preserve the top-five semantic results and append the first chunk from the two strongest matching documents when absent. This provides version, effective-date, scope, and supersession evidence without replacing fact-bearing chunks or adding another hosted-model call.
- **Disadvantages and trade-offs:** Follow-up detection is heuristic; two prior questions may still add stale topic terms; a first chunk is only a structural proxy for governance metadata; context can grow from five to seven chunks; start chunks have no semantic similarity score. A reranker and explicit policy metadata would be stronger in a production corpus.
- **Assumptions and evidence:** The supplied policies put identifying/applicability information at their start. In the observed failure, amount pages for both 2022 and 2025 were retrieved while the 2025 supersession statement was omitted. A later non-reimbursable query exposed accidental version-intent detection from the internal `Current question:` label; intent now considers user text only. The all-eight-document conversation evaluation passes 9/9 turns and the prior baseline remains 12/12.
- **Verification approach:** Deterministic unit checks cover expansion/enrichment and conversation isolation. `scripts/evaluate_conversation_retrieval.py` rebuilds all eight documents and checks labeled pages over three conversations; the original evaluation is rerun independently.
- **Conditions for revisiting:** Follow-up cases miss their topic, added headers crowd the model context, policy headers are not structurally consistent, corpus/token budgets grow, or explicit governance metadata/reranking is introduced.

## DEC-026 — Retry one citation-contract failure without weakening validation

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should the API handle a useful-looking Gemini answer whose inline markers do not match its structured source list?
- **Related requirements:** P-003, P-018–P-020, E-001–E-002.
- **Realistic alternatives:** Return the technical `502` immediately; auto-repair markers in application code; accept the response without validation; retry indefinitely; retry once with explicit validation feedback.
- **Choice and reasoning:** Keep strict citation validation and retry exactly once using the same evidence, the invalid structured response, and a narrow marker/list correction. Validate the retry identically. If it also fails, return a friendly verifiable-answer error and persist nothing. This recovers transient formatting errors without inventing a source mapping or hiding repeated model failure.
- **Disadvantages and trade-offs:** The rare invalid response incurs another provider request, adding latency and quota use. The retry can still fail and does not prove that a cited claim is semantically entailed by its chunk.
- **Assumptions and evidence:** Live UI use produced a marker/source-list mismatch that the existing validator correctly rejected. Focused tests prove valid retry recovery, repeated-failure rejection, and no partial persistence.
- **Verification approach:** Deterministic provider sequences return invalid-then-valid and invalid-twice responses; assertions cover call count, public citations/error, and persistence behavior.
- **Conditions for revisiting:** Formatting failures become frequent, provider structured-output guarantees improve, latency limits forbid a retry, or citation entailment checking is added.

## DEC-027 — Add bounded page companions for chat retrieval

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Why did the region-only “To Asia?” follow-up answer from the 2022 policy even though the 2025 policy was indexed and explicitly supersedes it?
- **Related requirements:** P-003, P-015–P-020, E-001–E-002.
- **Realistic alternatives:** Rely on prompt instructions; remove page diversity; globally increase `top_k`; merge whole PDF pages during ingestion; add a production reranker; enrich only the strongest pages with their neighboring stored chunks.
- **Choice and reasoning:** Recognize short location fragments and policy-conflict questions as follow-ups, retaining up to two recent user questions. For chat retrieval only, keep the diverse top five, then add up to two missing chunks from the two strongest document pages before document-start governance context. This ensures that a standard rule and exception split across neighboring chunks remain available together while retaining broad evidence recall.
- **Disadvantages and trade-offs:** Chat context may grow to nine chunks; companion chunks receive structural rather than semantic scores; unrelated material elsewhere on a long page could be included. The heuristic does not replace explicit policy metadata or reranking at enterprise scale.
- **Assumptions and evidence:** In the observed sequence, the 2022 standard-limit chunk ranked first and the 2025 exception chunk second; page diversity excluded the adjacent 2025 standard-limit chunk. The exact four-turn regression now retrieves both current page-2 chunks plus page-1 supersession evidence and passes the all-eight-document conversation evaluation.
- **Verification approach:** Seven focused tests cover follow-up expansion, authority vocabulary, page lookup/enrichment, and retained document headers. The real local embedding evaluation passes 13/13 conversation turns, including Europe → Zurich → Asia → document conflict. The full test suite was not rerun at the user's request.
- **Conditions for revisiting:** Context size harms answer quality or latency, pages become much longer, a reranker/section-aware retriever is introduced, or explicit applicability metadata becomes available.

## DEC-028 — Derive saved-chat titles and delete complete workspaces

- **Status:** Accepted (10 October 2026)
- **Question or problem:** How should users return to earlier conversations and remove obsolete local workspaces without managing technical IDs or leaving vector data behind?
- **Related requirements:** Optional usability enhancement under R-004; preserves P-004–P-005 and P-019.
- **Realistic alternatives:** Store only the last active ID in the browser; add a database title column and migration; call Gemini to generate titles; derive titles from the first prompt at read time; delete only relational rows; delete the complete relational/vector workspace.
- **Choice and reasoning:** Add a server-backed conversation list ordered by latest activity. Derive a normalized, bounded title from the first user prompt, falling back to the first indexed filename, so existing chats work without a migration or another model call. Switching reloads the authoritative SQLite summary. Confirmed deletion removes every document's vectors before deleting messages, documents, and the conversation record.
- **Disadvantages and trade-offs:** Listing performs simple per-conversation queries suitable only for this small prototype; titles are useful excerpts rather than semantic summaries; deletion is permanent; vectors and SQLite cannot share one atomic transaction. The local prototype also has no authentication, so list/load/delete are not user-scoped.
- **Assumptions and evidence:** The prototype is single-user and local, the conversation count is small, and existing messages/documents are already durable. Six focused API checks pass, including activity ordering, title derivation, complete deletion, vector cleanup, isolation, and unknown IDs. CSS now gives desktop grid children a zero minimum height and explicit overflow regions for long sources and chats.
- **Verification approach:** Focused ASGI tests cover list/restore/delete behavior and Python compilation. Manual browser verification remains required for pointer interaction, confirmation, and long-list scrolling because no browser automation runtime is installed.
- **Conditions for revisiting:** Authentication or shared deployment is introduced, conversation volume makes per-item queries slow, product-quality semantic titles are required, soft-delete/retention rules are introduced, or cross-store deletion needs a durable job/outbox.

## DEC-029 — Always open a fresh chat and support legacy conversation IDs

- **Status:** Accepted (10 October 2026)
- **Question or problem:** Why could the old `reimbursement_2025.pdf` workspace not be deleted, and should an application launch restore the last chat or begin a new one?
- **Related requirements:** Optional usability enhancement under R-004; preserves P-004–P-005 and P-019.
- **Realistic alternatives:** Restore the last active ID from browser storage; open the most recently updated server chat; always create a fresh browser ID while keeping saved chats selectable; reject or migrate legacy IDs containing URL-reserved characters.
- **Choice and reasoning:** Always generate a fresh in-memory conversation ID at application startup and remove the obsolete browser-storage pointer. Prior chats remain server-backed and selectable. Use FastAPI's path converter for conversation load/delete routes so legacy caller-provided IDs containing encoded `/`, `#`, or `?` characters can still be addressed and removed.
- **Disadvantages and trade-offs:** Reloading while working opens a new empty chat rather than resuming automatically; the user must click the prior title to continue. Accepting legacy path-shaped IDs makes the route more permissive than newly generated UUIDs, though length validation and exact database lookup remain in place.
- **Assumptions and evidence:** The user explicitly prefers every launch to open a new chat. Inspection of the local database showed the undeletable workspace ID contained URL-reserved characters, including `/` and `#`, which the earlier single-segment route could not capture. Seven focused web/API tests pass, including load and delete of an encoded legacy ID.
- **Verification approach:** A focused ASGI regression seeds an ID containing `/`, `#`, and `?`, then loads and deletes it through encoded URLs and verifies vector cleanup. Manual browser confirmation remains pending.
- **Conditions for revisiting:** Users prefer automatic resume, authentication provides a user-specific recent-chat preference, or legacy arbitrary IDs are migrated to UUID-only identifiers.

## DEC-030 — Resolve policy scope before labeling conflicts

- **Status:** Accepted (10 October 2026).
- **Problem:** The assistant applied an Asia-Pacific exception to Zurich and risked treating different data classifications as contradictions.
- **Related requirements:** P-003, P-016–P-020, E-002; informs S-010 and S-016.
- **Alternatives:** Edit source PDFs; hard-code answers per city/file; use only a generic grounding instruction; explicitly define scope, temporal authority, ambiguity and boundary rules with source-backed regressions.
- **Choice:** Keep source PDFs intact. Expand the prompt's interpretation rules and record source findings in `docs/POLICY_CONFLICT_BOARD.md`. Permit basic geography/arithmetic to interpret evidence, without inventing company policy. Treat materially ambiguous exceptions within a document as `conflicting_sources`; state clear standards and refer unresolved intent to the appropriate owner. Respect historical questions, exact thresholds, scope differences, and compatible cross-policy conditions.
- **Trade-offs:** The prompt remains model-enforced and can fail. The Zurich example is a known-corpus regression, not a general geographic validation engine. The board must not become an alternative source of policy authority.
- **Verification:** Exact-evidence evaluation plus optional live Gemini status/content/citation checks and manual answer rubrics. Fake-provider tests are reported only as orchestration evidence, never as proof of policy reasoning.
- **Revisit when:** More policies require structured applicability metadata, the ambiguity status needs its own API field, or live semantic errors justify a stronger verifier/model.

## DEC-031 — Bounded comparison context and safe empty-evidence handling

- **Status:** Accepted (10 October 2026).
- **Problem:** A top-five fact search cannot support a broad conflict review; selected pages can still omit a neighboring stipend chunk. Generic follow-up terms also polluted standalone topic changes.
- **Alternatives:** Send the entire library for every query; add a second model planner/reranker; expand context for comparison intent within fixed limits.
- **Choice:** For policy comparisons/conflict reviews, request top 20 and add up to 20 missing chunks from selected pages, plus existing header enrichment (at most 42 chunks). Ordinary questions retain their existing budget. Remove generic “Can I/Do I/Should I” follow-up triggers while preserving genuinely dependent phrases. Abstain deterministically when there is no indexed evidence and save that completed turn.
- **Trade-offs:** Comparison requests cost more tokens and do not guarantee corpus-wide completeness. Intent detection is heuristic. The zero-evidence branch deliberately skips an unnecessary model call; supported chats still follow the normal required RAG path.
- **Verification:** Local real-embedding cases check supporting phrases, including the USD 50 stipend; deterministic tests check wider retrieval, ordinary budgets, topic isolation, correction history, and no provider call for empty evidence.
- **Revisit when:** Corpus scale demands pagination/systematic policy comparison, intent detection misses a case, or latency/context budgets require reranking.

## DEC-032 — Normalize only unambiguous citation ordering

- **Status:** Superseded by DEC-037 (11 October 2026).
- **Problem:** Live otherwise usable answers triggered extra provider calls when inline markers and declared IDs had identical membership but different ordering.
- **Alternatives:** Retry every mismatch; accept any model citation; validate exact membership and assign public numbers by first appearance.
- **Choice:** Require all IDs to exist, uniqueness of the declared list, and exact marker/list set equality. Expand grouped `[S1, S2]` references before validation and number valid citations in inline first-appearance order. Reject malformed groups instead of allowing them through the old single-marker regex. Retain one retry with precise validation feedback for other errors. Never synthesize a missing source ID or accept an unknown marker.
- **Trade-offs:** This proves provenance mapping, not that the source entails the claim. The model can still omit a citation or cite an irrelevant passage.
- **Verification:** Regression tests cover reordered valid IDs without a retry, plus unknown, duplicate, undeclared and numeric marker rejection without partial persistence.
- **Revisit when:** Citation entailment validation or a different model output format is introduced.

## DEC-033 — Exercise real answers and bound recovery for invalid structured output

- **Status:** Accepted (10 October 2026).
- **Problem:** Correct retrieval and fake-provider tests did not detect geography, threshold, completeness or malformed-refusal failures in real generation.
- **Alternatives:** Treat page recall as sufficient quality evidence; add only canned-answer tests; run a separate real-answer regression harness with explicit rubrics.
- **Choice:** Add 17 source-backed or synthetic scenarios, exact supporting-text checks, live answer status/content/citation checks, and manual rubrics. Isolate test databases and never use stored user chats. Pace requests and stop live calls after the first rate limit or other provider outage, reporting completed and skipped cases separately. Print model and prompt/case hashes. Increase the default output cap from 600 to 1,000 tokens for complete comparisons. Extend the existing single corrective retry to invalid JSON; do not retry provider errors indefinitely.
- **Trade-offs:** Live results vary and consume quota. Pattern matches cannot establish entailment, so manual answer review remains necessary. A larger output cap can increase response latency/token use. Partial or failed runs must be reported honestly.
- **Verification:** Focused tests cover schema-retry recovery and persistence; separate local evidence and live answer results are recorded in Stage 5 results. Neither canned responses nor keyword success is claimed as proof that all future questions work.
- **Revisit when:** Evaluation volume requires a CI service, data changes require reviewed labels, or recurring semantic failures justify claim verification or a stronger model.

## DEC-034 — Validate configuration early and preserve recoverable failure state

- **Status:** Accepted (11 October 2026).
- **Problem:** Invalid numeric settings could survive startup until a later upload/query failed, and a vector-cleanup exception could escape the ingestion service as an uncontrolled error.
- **Alternatives:** Trust environment values; validate inside each use site; validate coherent limits in `Settings` and convert cleanup failure to an explicit ingestion outcome.
- **Choice:** Add positive/range constraints for upload, embedding, retrieval and chat settings plus a cross-field chunk-window check. If vector cleanup fails after indexing failure, record the document as failed and raise a controlled `IngestionError` stating that cleanup was incomplete. Preserve relational conversation state when deletion cannot complete in Chroma.
- **Trade-offs:** Startup is stricter and rejects previously tolerated invalid values. Cross-store consistency is still compensating behavior rather than a distributed transaction.
- **Verification:** Parameterized invalid-setting tests, count-mismatch, cleanup-failure, failed-upload retry, vector-deletion failure and atomic message-trigger tests pass.
- **Revisit when:** A durable job/outbox or transactional storage architecture replaces local SQLite/Chroma compensation.

## DEC-035 — Expand context for completeness and authority ambiguity

- **Status:** Accepted (11 October 2026).
- **Problem:** The expanded policy evaluation found that normal top-five retrieval could select a related chunk while omitting the adjacent complete list or operative handling section. This affected complete non-reimbursable lists and whether interim USB guidance remains authoritative.
- **Alternatives:** Increase context for every query; weaken evaluation evidence; hard-code filenames; detect high-recall intents and use the existing bounded comparison path.
- **Choice:** Keep the normal retrieval budget for ordinary facts. Reuse the bounded top-20/page-expansion path for explicit complete-list requests and authority-ambiguity wording such as “still,” “definitely,” “explicitly,” or revocation questions that name policy/guidance/documents. This is generic intent handling, not a USB- or expense-specific answer rule.
- **Trade-offs:** Heuristics can miss paraphrases or widen context unnecessarily. A large enterprise corpus still needs query planning, metadata filters and reranking.
- **Verification:** The failures reproduce before the change and pass after it. Exact evidence now passes 33/33 and multi-turn retrieval passes 22/22; ordinary-question budget tests remain green.
- **Revisit when:** Evaluation finds new completeness phrasing, context cost becomes material, or structured authority/section metadata and reranking are introduced.

## DEC-036 — Use layered assurance and one implemented blueprint

- **Status:** Accepted (11 October 2026).
- **Problem:** Test counts from deterministic fakes, real embeddings and hosted generation answer different questions; scattered design documents made it easy to overstate assurance or miss the current implementation flow.
- **Alternatives:** Report one aggregate pass count; replace historical documents; consolidate current assurance and architecture while retaining chronological records.
- **Choice:** Keep separate results for deterministic tests, real-embedding retrieval, exact evidence and live generation. Add `docs/TESTING_REPORT.md` as the assurance record and `docs/SOLUTION_BLUEPRINT.md` as the single implemented code/flow blueprint, while retaining stage documents and this decision log for history.
- **Trade-offs:** Some information is intentionally summarized in more than one entry-point document and must be kept consistent. Live semantic correctness still requires external calls and human rubric review.
- **Verification:** The complete suite passes 124/124, direct retrieval 12/12, conversational retrieval 22/22 and exact evidence 33/33. A complete Gemini run passed 33/33 automated checks and was manually reviewed; final focused regressions cover the additional defects found by that review. Documentation links and JSON/compilation checks pass; Node/browser automation remains an explicit gap.
- **Revisit when:** Stage 6 enterprise architecture is selected or Stage 7 packaging needs a shorter reviewer-facing version.

## DEC-037 — Canonicalize inline citations and enforce semantic scope after live review

- **Status:** Accepted (11 October 2026); supersedes DEC-032's exact marker/list-membership rule and DEC-033's single-correction limit.
- **Problem:** Complete live evaluation showed that correct answers could fail because the model's redundant `source_ids` metadata disagreed with valid inline markers. It also showed that keyword rubrics can miss semantic scope errors: unrelated Zurich ambiguity, borrowing an Asia-Pacific value for missing Latin America history, mixing Procurement and Travel portals, partial answers mislabeled insufficient, and gift/procurement thresholds transferred to sponsored dinners.
- **Alternatives:** Trust regex scores; keep retrying every redundant-list mismatch; use unrestricted retries; add a second verifier model; deterministically validate unambiguous known scope relationships while retaining human review.
- **Choice:** Treat inline `[S<number>]` markers as canonical after verifying every marker exists in retrieved evidence; normalize the redundant list rather than trusting it. Continue rejecting unknown, malformed and public numeric markers. Allow at most two corrective attempts for invalid structure, status, citations or scope, with no partial persistence after exhaustion. Add evidence-aware completeness and narrowly source-backed scope guards for the supplied corpus, while keeping the general prompt rules for unseen cases. Manual live-answer review remains required because patterns do not prove entailment.
- **Trade-offs:** A third provider attempt can add latency and quota in rare failure paths. Dataset-specific guards improve this case corpus but are not a universal policy reasoning engine. Marker validation establishes provenance mapping, not semantic entailment. A stronger production design should use structured policy metadata and/or claim verification.
- **Verification:** The deterministic suite passes 124/124, including third-failure rollback, second-correction recovery, marker canonicalization, broad-data completeness, Zurich/history handling, partial support, separate portals, and vendor gift/procurement threshold isolation. Exact evidence passes 33/33. The complete live run passed 33/33 automated checks; manual review defects were converted into tests and final focused live regressions, which pass.
- **Revisit when:** A provider can guarantee the full output contract, latency budgets cannot tolerate correction calls, policy volume makes explicit scope rules impractical, or a claim-entailment verifier is added.
