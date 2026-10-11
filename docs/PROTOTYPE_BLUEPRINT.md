# Prototype Implementation Blueprint (Historical Plan)

> This document records the pre-implementation plan and is retained for decision
> history. The current implemented structure, decisions and flow diagrams are in
> `docs/SOLUTION_BLUEPRINT.md`.

This is the pre-coding blueprint for Stages 1–5. It defines how the local prototype should look and in what order it should be built. Choices marked **proposed** require approval before dependent implementation. Enterprise architecture remains separate and will be designed in Stage 6.

## 1. Intended outcome

The prototype will be a small local Python REST API that demonstrates the complete RAG loop:

1. Upload a text-readable policy PDF into a conversation.
2. Extract page-aware text and split it into traceable chunks.
3. Embed and store those chunks.
4. Ask a question in the same conversation.
5. Retrieve relevant chunks, combine them with the last five messages, and call a chat model.
6. Return a grounded JSON answer with inline and structured PDF citations.
7. Persist document metadata and the user/assistant interaction.

It is a walking skeleton, not a miniature enterprise platform. Authentication, asynchronous ingestion, OCR, and cloud deployment belong outside the initial prototype unless later evidence justifies adding them.

## 2. Technical baseline

| Area | Choice or current proposal | Why it fits the interview | Realistic alternative / trade-off |
|---|---|---|---|
| Language | Supported Python 3.11+ runtime, exact version recorded when setup begins | Meets the only mandatory stack requirement and is widely reproducible | Pinning one exact version is more reproducible but may be less convenient for reviewers |
| HTTP framework | FastAPI with Uvicorn | Recommended by the case; typed contracts and generated API docs make the demo easy to inspect | Flask is smaller but needs more manual validation/documentation |
| Validation/config | Pydantic models and environment-based settings | Already aligned with FastAPI and keeps secrets out of code | Hand-written validation has fewer concepts but more repetitive code |
| Relational data | SQLite through SQLAlchemy | Durable local state, explicit schema, explainable queries, and a clear path to Postgres | Direct `sqlite3` is simpler; SQLAlchemy adds a dependency but gives cleaner schema/session boundaries |
| PDF parsing | `pypdf`, verified against the supplied corpus before acceptance | Pure Python and sufficient for the text-readable sample PDFs | PyMuPDF may extract some layouts better but introduces another licensing/dependency consideration |
| Vector storage | Persistent Chroma collection | Stores embeddings, text, and metadata together and supports simple filtered semantic search | FAISS is fast and focused but needs separate metadata/persistence coordination |
| Embeddings | Provider interface with local `all-MiniLM-L6-v2` through CPU ONNX Runtime | Keeps ingestion testable and prevents provider calls from leaking through the codebase without requiring PyTorch/CUDA | A hosted model reduces local setup but adds credentials, cost, and data sharing |
| Chat model | Provider interface; Gemini-backed runtime plus deterministic test fake | The case permits another provider; real behavior demos the complete flow while tests remain stable | Free-tier data handling and availability require disclosure; a local LLM adds setup and hardware burden |
| Testing | Pytest with unit tests plus API-level integration tests | Common, readable, and supports deterministic provider fakes | Framework-native/manual checks alone would provide weaker regression evidence |
| Dependency definition | One `pyproject.toml` with runtime and development groups | Single clear source for packaging, tooling, and installation | `requirements.txt` is familiar but separates project metadata and dependency intent |

Implemented dependency versions are pinned in `pyproject.toml`; proposed later-stage providers remain undecided until their implementation stage.

## 3. Proposed repository shape

```text
.
├── app/
│   ├── __init__.py
│   ├── main.py                 # app construction and route registration
│   ├── config.py               # environment-backed settings
│   ├── database.py             # engine/session lifecycle
│   ├── models.py               # relational persistence models
│   ├── schemas.py              # public request/response contracts
│   ├── api/
│   │   ├── health.py
│   │   ├── upload.py
│   │   └── chat.py
│   ├── services/
│   │   ├── ingestion.py        # parse, chunk, embed, index orchestration
│   │   ├── retrieval.py        # filtered semantic search
│   │   └── chat.py             # history, context, model, citation orchestration
│   ├── providers/
│   │   ├── embeddings.py       # embedding protocol and implementation
│   │   ├── llm.py              # chat protocol and implementation
│   │   └── vector_store.py     # vector operations and metadata filters
│   └── prompts/
│       └── system.txt          # versionable system prompt, introduced in Stage 4
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── evaluation/             # labeled retrieval/end-to-end cases
├── data/
│   ├── sampleset_policies/     # supplied, unchanged source data
│   └── runtime/                # ignored local database/vector state
├── docs/
├── reference/
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

This is intentionally shallow. We should combine files if a layer contains only trivial pass-through code and split a file only when it gains a distinct responsibility.

## 4. Public API contracts

### `GET /health` — optional operational endpoint

Purpose: make local startup and automated checks observable. This is an intentionally small addition, not an ADC functional requirement.

Proposed success response:

```json
{"status": "ok"}
```

It must not report downstream model/vector health unless those checks actually ran.

### `POST /upload`

Proposed request: `multipart/form-data`

- `conversation_id`: required non-empty string. If it exists, reuse it; if not, create it.
- `file`: required PDF file.

Proposed success response after Stage 2:

```json
{
  "conversation_id": "demo-conversation",
  "document_id": "generated-document-id",
  "filename": "reimbursement_2025.pdf",
  "status": "indexed",
  "chunks_indexed": 12,
  "uploaded_at": "ISO-8601 timestamp"
}
```

Upload processing is synchronous: `indexed` is returned only after relational metadata and vector chunk counts are verified. This is implemented in Stage 2.

### `POST /chat`

Proposed request: `application/json`

```json
{
  "conversation_id": "demo-conversation",
  "message": "What is the lodging limit in Asia-Pacific?"
}
```

Proposed success response after Stage 4:

```json
{
  "conversation_id": "demo-conversation",
  "answer": "The standard Asia-Pacific lodging limit is USD 180 per night, excluding taxes. [1]",
  "citations": [
    {
      "id": 1,
      "filename": "reimbursement_2025.pdf",
      "page": 2
    }
  ]
}
```

An unknown conversation should return `404`. An answer unsupported by retrieved context should clearly abstain and return an empty citations list. Stage 1 may expose the contract with `501 Not Implemented` until the complete chat path exists.

### Error behavior

Use ordinary HTTP semantics and a consistent JSON detail message:

- `400` for a semantically invalid request that passed structural validation.
- `404` for an unknown conversation/document resource.
- `415` for a non-PDF upload.
- `422` for missing or structurally invalid fields (FastAPI validation).
- `500` for an unexpected internal failure without leaking secrets or stack traces.
- `502` for a failed external model/provider call when no local fallback applies.

Exact error cases will be tested, not merely documented.

## 5. Data ownership and models

### Relational database

**Conversation**

- `id`: caller-provided string, primary key.
- `created_at`: UTC timestamp.

**Document**

- `id`: generated stable identifier.
- `conversation_id`: owning conversation.
- `filename`: safe original base filename.
- `uploaded_at`: UTC timestamp.
- `content_sha256`: supports duplicate detection and traceability.
- `page_count`, `chunk_count`: processing facts.
- `status`: processing state; success only after indexing.

**Message**

- `id`: generated stable identifier.
- `conversation_id`: owning conversation.
- `role`: `user` or `assistant`.
- `content`: persisted query or answer.
- `citations_json`: citations used for an assistant answer; empty for user messages.
- `created_at`: UTC timestamp plus stable ordering.

Each user and assistant entry is one message. Therefore “last 5 messages” is proposed to mean the latest five individual role records, in chronological order after retrieval. This follows the literal case wording.

### Vector collection

Each vector record should contain:

- Stable `chunk_id`.
- Embedded chunk text.
- `conversation_id` for mandatory retrieval filtering.
- `document_id` and filename.
- One-based PDF page number.
- Chunk position within the document/page.
- Parser/chunker version where useful for later reproducibility.

Documents are proposed to be conversation-scoped. This makes the supplied `conversation_id` meaningful, prevents one conversation from unexpectedly searching another conversation’s uploads, and models a basic privacy boundary.

## 6. Internal request flows

### Upload flow

```text
HTTP validation
  → retrieve/create conversation
  → validate PDF
  → create processing document record
  → extract page-aware text
  → create logical chunks
  → generate embeddings
  → write vector records with provenance
  → finalize document metadata/status
  → return indexed confirmation
```

Failure behavior must avoid claiming success. Because SQLite and the vector store do not share a transaction, the service needs explicit cleanup/retry behavior and tests for partial failure. The simplest acceptable Stage 2 rule is to mark the document as failed and remove any vectors written for that document.

### Chat flow

```text
HTTP validation
  → require existing conversation
  → load latest five individual messages
  → embed current question
  → semantic search filtered by conversation_id
  → build System + History + Context + Question prompt
  → call chat provider
  → validate/assemble source citations
  → persist user and assistant messages
  → return answer and citations
```

The current user question is not part of the prior five-message history. It is added separately as the “User Question” prompt element.

## 7. Implementation sequence

### Stage 1 — foundation

1. Approve or revise the proposed choices in this blueprint.
2. Record accepted choices in `docs/DECISIONS.md` and resolve A-001, A-003, A-004, and the Stage 1 portion of A-008/A-009.
3. Define `pyproject.toml`, `.gitignore`, and `.env.example`; do not include secrets.
4. Create the application factory, environment settings, and `/health` endpoint.
5. Define relational models and database lifecycle.
6. Define public upload/chat schemas and route contracts; return explicit `501` for behavior deferred to later stages.
7. Add focused tests for startup, health, validation, error shape, and database creation.
8. Add only commands actually run and verified to the README.

**Exit:** the app starts; API docs show the contracts; foundation tests pass; no RAG behavior is falsely advertised.

### Stage 2 — ingestion/indexing

1. Verify `pypdf` extraction against every supplied PDF and record limitations.
2. Define page-aware logical chunking and tests before embedding integration.
3. Implement embedding and vector-store boundaries with deterministic fakes.
4. Add the selected real embedding implementation.
5. Orchestrate synchronous upload, metadata persistence, rollback/failed state, and duplicate behavior.
6. Test happy paths and invalid, empty, duplicated, and provider-failure cases.

**Exit:** supplied PDFs can be indexed with durable metadata and inspectable provenance.

### Stage 3 — retrieval evidence

1. Create labeled questions for direct facts, tables, versions, conflicts, cross-policy references, and missing answers.
2. Measure retrieval separately from generation.
3. Tune chunking/top-k only from recorded evidence.
4. Establish a small baseline and document known failures.

**Exit:** retrieval choices have reproducible evidence rather than intuition alone.

### Stage 4 — chat

1. Write/version the system prompt and explicit abstention rule.
2. Implement history retrieval and bounded prompt assembly.
3. Add the real chat provider behind the testable interface.
4. Validate citation mapping against retrieved evidence.
5. Persist interactions only under documented success/failure semantics.
6. Test multi-turn history, supported answers, conflicts, abstention, provider failure, and citation accuracy.

**Exit:** end-to-end chat returns grounded, cited JSON and persists the interaction.

### Stage 5 — robustness and evaluation

1. Run the complete requirement matrix and evaluation set.
2. Test failure recovery and partial-state behavior.
3. Record latency and quality observations without inventing production SLOs.
4. Review security/data-handling boundaries and dependency risks.
5. Add an optional enhancement only if it improves a stated criterion.

**Exit:** every prototype requirement has evidence or a clearly disclosed gap.

## 8. Verification strategy

Use three levels, each answering a different question:

- **Unit tests:** Is parsing, chunking, prompt assembly, citation mapping, and history selection correct in isolation?
- **API integration tests:** Do validation, persistence, vector filtering, status codes, and JSON contracts work together?
- **Evaluation cases:** Does retrieval and generated behavior find the right sources, handle contradictions, and abstain when evidence is missing?

Provider fakes make automated tests deterministic. At least one separately marked live-provider smoke check should verify the configured real model path when credentials and network access are available. A skipped live check must never be reported as passed.

## 9. Deliberate exclusions from the local prototype

- Authentication, authorization, and per-user enterprise identity.
- Background queues and asynchronous ingestion.
- SharePoint/local-drive connectors.
- OCR for scanned PDFs and broad multilingual guarantees.
- Web UI.
- Cloud infrastructure and production deployment.
- Distributed caching, monitoring platform, and enterprise SLOs.

These remain important enterprise topics, but adding them now would obscure the required RAG mechanics and make the interview implementation harder to explain.

## 10. Approval checkpoint

Before code begins, confirm or revise these consequential proposals:

1. FastAPI + SQLAlchemy/SQLite + Chroma + `pypdf`.
2. Provider interfaces with deterministic test fakes and a real Gemini-backed runtime.
3. Required caller-provided `conversation_id`; create it on first upload.
4. Conversation-scoped uploaded documents and vector retrieval.
5. Synchronous prototype upload.
6. Last five individual user/assistant message records.
7. Inline citation markers plus structured filename/page citations.
8. The explicit prototype exclusions above.

No application implementation should start until this checkpoint is accepted or adjusted.
