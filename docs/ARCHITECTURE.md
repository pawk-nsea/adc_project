# Conceptual Architecture

> This document preserves the prototype-to-enterprise architecture discussion.
> For the current implemented local codebase and request flows, use
> `docs/SOLUTION_BLUEPRINT.md`.

This document separates the implemented local prototype from later proposed enterprise components. See `docs/DECISIONS.md` for choices and `docs/REQUIREMENTS.md` for tracked scope.

## Local prototype information flow

### Ingestion

The ingestion steps below are implemented in Stage 2:

1. A caller sends a PDF and required `conversation_id` to `POST /upload`.
2. The API validates the request and retrieves the conversation when it exists or creates it when the supplied ID is new.
3. `pypdf` extracts text page by page; unreadable, encrypted, and text-empty PDFs are rejected.
4. A deterministic chunker keeps page boundaries, targets 180 model word pieces, caps chunks at 220, and uses up to 30 tokens of overlap.
5. `all-MiniLM-L6-v2` runs locally through CPU ONNX Runtime and creates normalized 384-dimensional vectors.
6. Persistent Chroma stores vectors, exact chunk text, and scalar provenance. SQLite records conversations and document metadata, including filename, upload time, hash, page/chunk counts, and processing status.
7. The endpoint confirms success only when the prototype’s documented indexing completion condition has been met.

### Chat (implemented; live provider verification pending)

1. A caller sends a `conversation_id` and message to `POST /chat`.
2. Relational storage provides the five latest individual user/assistant messages, restored to chronological order. The current question remains separate.
3. The retrieval service embeds the current question and runs cosine search filtered by conversation and embedding model. It considers up to 15 candidates and returns the five strongest distinct document pages.
4. Prompt construction keeps four explicit inputs: the system instruction, recent history, retrieved context, and current user question. Retrieved documents are treated as untrusted data, not higher-priority instructions.
5. Gemini Flash receives the bounded prompt and returns a schema-validated answer, status, and retrieved source IDs. The prompt requires context-only answers, abstention, and explicit conflict handling.
6. Citation validation rejects unknown, duplicate, mismatched, or model-invented public markers. The application maps accepted source IDs to numbered PDF filename and one-based page citations.
7. Relational storage atomically persists the user query and validated AI response in order. The API returns JSON containing `conversation_id`, `status`, `answer`, and `citations`.

### Proposed logical components

| Concern | Proposed responsibility | Unresolved choice |
|---|---|---|
| HTTP/API | Validate requests, coordinate use cases, return stable JSON/errors | FastAPI upload and chat implemented |
| PDF parsing | Extract readable text and page metadata | `pypdf` implemented; OCR excluded |
| Chunking | Produce meaningful, traceable retrieval units | Token-aware page-local baseline implemented and retrieval-evaluated |
| Embeddings | Convert chunks/queries into compatible vectors | Local ONNX MiniLM document and query embedding implemented |
| Vector retrieval | Index/search chunks and return scores/identifiers | Persistent Chroma cosine search, filtering, and page diversification implemented |
| Relational persistence | Store conversations, document metadata, and interactions | SQLAlchemy/SQLite implemented; migrations deferred |
| Prompt/model boundary | Assemble bounded inputs and invoke chat behavior | Explicit builder plus Gemini provider; real call pending safe key |
| Citation assembly | Connect answer evidence to source PDFs | Validated inline markers plus structured filename/page citations implemented |

## Future enterprise platform: proposed direction

The enterprise target is intentionally separate from the local walking skeleton. Live upload may be omitted, but governed integration with internal document systems is expected.

### Ingestion plane (slow, asynchronous)

- Source connectors discover approved files in enterprise repositories such as SharePoint and managed drives.
- Change events or scheduled scans place ingestion jobs on a durable queue. This prevents parsing, validation, chunking, embedding, and indexing from blocking chat traffic.
- Independent workers process jobs with retries, idempotency, dead-letter handling, malware/content validation, and observable status.
- A document catalog records source system, owner, access policy, effective/version dates, checksum, ingestion version, and supersession state. Data-quality checks flag duplicates, missing ownership, stale documents, and contradictory authoritative content for human stewardship.
- A versioned index is built and validated before promotion, allowing rollback and avoiding partially updated serving state.

### Serving plane (fast, synchronous)

- Enterprise identity and authorization determine the documents a user may retrieve; filtering must happen before protected content reaches the model.
- A chat service obtains bounded history, retrieves authorized evidence, optionally reranks it, constructs the prompt, invokes the model, checks the grounded response, and returns citations or an explicit abstention.
- Caching may reduce latency for safe, stable layers such as query embeddings, authorized retrieval results, and approved responses. Cache keys must include relevant user/access scope and data/index version; invalidation must follow document/index changes. Exact cache targets require risk and latency evidence.
- Rate limiting, timeouts, graceful fallbacks, trace correlation, and streaming are candidates for meeting an eventual latency objective.

### Control, evaluation, and governance plane

- Code, prompts, models, embedding configuration, data snapshots, and indexes receive separate versions linked in a deployment record.
- CI/CD runs deterministic unit/integration checks plus versioned retrieval and answer evaluations. Candidate results are compared with a baseline and promoted only through quality, security, cost, and latency gates.
- Production telemetry monitors service health, retrieval quality proxies, groundedness/citation behavior, abstention, feedback, query drift, data freshness, and policy violations with privacy-aware retention and access.
- Human workflows own document conflicts, flagged responses, feedback triage, incident response, evaluation-set updates, and release approval.
- Adoption combines phased rollout, role-specific training, examples that contrast keyword search with semantic questions, citation checking, limitation/feedback education, office hours, champions, and measurable usage/trust outcomes.

## Assumptions and unresolved choices

### Explicitly supported by the case

- The prototype uses Python.
- The enterprise solution may omit live upload.
- Enterprise integration with internal document stores is expected.

### Prototype assumptions

- The prototype can prioritize a single-process/local deployment and a synchronous upload flow for clarity.
- Enterprise ingestion and serving should use separate scaling/failure domains.
- Public citations include filename and one-based page; internal retrieval retains chunk provenance.

### Material choices still open

- Live Gemini behavior, cost, latency, and organizational approval to send the bounded prompt to a hosted provider. Free-tier data-use terms are unsuitable for confidential data without explicit approval.
- Retrieval/reranking and grounded-answer quality thresholds beyond the Stage 3 baseline.
- Prototype security boundary, model data-sharing constraints, and non-functional thresholds.
- Enterprise cloud provider/services, regions/residency, identity system, SLOs, scale, budget, compliance, and operational ownership.

These must be decided in the relevant stage and logged before dependent implementation or presentation work.
