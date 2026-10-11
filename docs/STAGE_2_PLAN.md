# Stage 2 Plan — PDF Ingestion and Indexing

This document records the accepted and implemented Stage 2 scope. It does not include retrieval, prompt construction, chat-model calls, conversation history, or answer generation.

## 1. Goal

Turn `POST /upload` from an explicit placeholder into a working synchronous ingestion endpoint:

```text
PDF upload
  → validate
  → retrieve/create conversation
  → parse each page
  → create logical, page-aware chunks
  → create local semantic embeddings
  → persist vectors and provenance
  → finalize relational metadata
  → return indexed confirmation
```

Stage 2 ends after the document is demonstrably indexed. `/chat` must continue returning `501 Not Implemented`.

## 2. Recommended components

### PDF parser: `pypdf`

Use `PdfReader` on the uploaded bytes and extract each page separately. This preserves one-based page numbers for later citations. The supplied corpus is text-readable, so OCR is deliberately excluded.

Why:

- Small, focused dependency.
- Direct page-by-page extraction.
- Supports normal and layout-oriented extraction modes, which we can compare against the supplied policies before choosing.

Limitation: PDF text extraction does not reconstruct document meaning perfectly. Tables, reading order, and unusual layouts must be checked against the sample corpus rather than assumed correct.

### Embeddings: local MiniLM through ONNX Runtime

Use the `sentence-transformers/all-MiniLM-L6-v2` model through Chroma's explicit `ONNXMiniLM_L6_V2` adapter. The application computes document embeddings through its own provider rather than asking the vector store to choose a hidden default model. This is the same selected model, but avoids installing PyTorch and a multi-gigabyte CUDA dependency tree on a CPU-only prototype.

Why:

- Works locally through ONNX Runtime after the initial 79.3 MiB compressed model download.
- No API key, usage cost, or policy text sent to an external API.
- Small and common enough for an interview prototype.
- Produces normalized 384-dimensional embeddings with a 256-word-piece input limit.

Trade-offs:

- The extracted model plus download archive use roughly 174 MiB in the ignored local cache.
- CPU embedding is slower than a hosted endpoint, though acceptable for eight small PDFs.
- It is an English/general-purpose model, not a finance-policy-specific model.
- Chroma's ONNX adapter exposes no public model-preparation method, so the provider wraps its verified download method before loading an untruncated tokenizer for chunk sizing. This dependency is isolated in one adapter.

Tests use a deterministic fake embedding provider. The fake proves orchestration and error behavior; only the real model proves that genuine embeddings are produced.

### Vector store: local persistent Chroma

Use a `PersistentClient` with data under `data/runtime/chroma/` and one collection named `policy_chunks`. Pass precomputed embeddings, document text, and explicit scalar metadata to Chroma.

Why:

- The case recommends Chroma as an option.
- Local persistence is appropriate for a walking skeleton.
- It stores an embedding, document text, and source metadata together.
- Metadata filtering will allow Stage 3 retrieval to enforce `conversation_id` isolation.

Trade-offs:

- SQLite and Chroma cannot participate in one atomic transaction.
- It adds a sizable dependency and a second persistence mechanism.
- The embedded persistent client is for local development, not the enterprise architecture.

## 3. Code structure to add

```text
app/
├── api/
│   └── upload.py                 # HTTP concerns only
├── services/
│   ├── __init__.py
│   ├── ingestion.py              # coordinates the complete workflow
│   ├── pdf_parser.py             # bytes → page-numbered text
│   └── chunker.py                # page text → logical chunks
├── providers/
│   ├── __init__.py
│   ├── embeddings.py             # interface + local model implementation
│   └── vector_store.py           # interface + Chroma implementation
├── config.py                     # ingestion/model/vector settings
└── models.py                     # duplicate constraint/status adjustments

tests/
├── fixtures/
│   └── policies/                 # minimal generated/selected test inputs
├── unit/
│   ├── test_pdf_parser.py
│   └── test_chunker.py
└── integration/
    └── test_upload.py
```

Do not add a generic repository layer, event bus, background worker, or framework such as LangChain in this stage. Direct, focused services are easier to understand and explain.

## 4. Internal data contracts

Use small typed records between components.

### Parsed page

```text
page_number: one-based integer
text: extracted and minimally normalized text
```

### Text chunk

```text
id: document ID + page number + page-local chunk number
document_id
conversation_id
filename
page_number
chunk_index
text
```

### Embedding provider

```text
embed_documents(list[str]) → list[list[float]]
count_tokens(str) → int
```

Stage 3 will add the corresponding query-embedding operation. Keeping the interface explicit means application services do not import or depend directly on model internals.

### Vector store

```text
add_chunks(chunks, embeddings)
delete_document(document_id)
count_document_chunks(document_id)
```

Search is intentionally deferred to Stage 3.

## 5. Upload behavior

### Request

Keep the Stage 1 multipart contract:

- `conversation_id`: required, non-blank, at most 128 characters.
- `file`: required upload.

### Validation order

1. Sanitize the client filename to its base name.
2. Enforce the accepted 10 MiB prototype limit while reading.
3. Require a `.pdf` extension.
4. Require the `%PDF-` file signature; do not trust MIME type alone.
5. Parse with `pypdf`.
6. Reject encrypted PDFs.
7. Reject documents with no extractable non-whitespace text.

Implemented errors:

- `413`: file exceeds the documented prototype limit.
- `415`: file is not recognizably a PDF.
- `422`: PDF is encrypted, unreadable, or contains no extractable text.
- `409`: identical PDF already indexed in the same conversation.
- `500`: unexpected internal/index failure, with no secrets exposed.

### Conversation and duplicate semantics

- Reuse the conversation when the supplied ID exists; otherwise create it.
- Compute SHA-256 from the original bytes.
- Treat an indexed or processing `(conversation_id, content_sha256)` as an application-level duplicate. Failed attempts can therefore be retried without a schema migration.
- An identical upload in the same conversation returns `409 Conflict` with the existing document ID.
- The same PDF may be indexed in another conversation because retrieval is conversation-scoped.

## 6. Chunking strategy

Start with a deterministic, readable algorithm and evaluate it on the supplied policies.

1. Never combine content from different PDF pages. This keeps page citations unambiguous.
2. Normalize repeated spaces while preserving paragraph and line boundaries needed for headings/lists.
3. Split a page into logical blocks using blank lines and recognizable headings/list boundaries.
4. Measure with the embedding model's own tokenizer and accumulate adjacent blocks toward 180 word pieces.
5. Enforce a 220-word-piece maximum, below the model's 256-token limit.
6. Carry up to 30 word pieces of boundary-aware overlap into the next chunk when a page needs multiple chunks.
7. Never create an empty chunk; keep small headings with the content that follows where possible.

These values are starting hypotheses, not quality claims. Stage 2 checks content preservation and model input length. Stage 3 measures retrieval and changes the values only when evidence supports it.

Why not split only by fixed character count: it can detach a heading from its rule, cut tables/lists arbitrarily, and make retrieved evidence harder to explain.

Why not build a complex semantic chunker now: it adds another model and makes the walking skeleton harder to understand before baseline retrieval has been measured.

## 7. Stored data

### SQLite document record

Use the existing fields:

- `id`
- `conversation_id`
- `filename`
- `uploaded_at`
- `content_sha256`
- `page_count`
- `chunk_count`
- `status`: `processing`, `indexed`, or `failed`

Duplicate detection uses conversation plus content hash and considers `processing` or `indexed` records. A failed record remains useful diagnostic evidence, its vectors are removed, and the same content can be retried.

### Chroma vector record

Store:

- ID: stable chunk ID.
- Document: exact chunk text embedded.
- Embedding: precomputed local vector.
- Metadata:
  - `conversation_id`
  - `document_id`
  - `filename`
  - `page_number`
  - `chunk_index`
  - `embedding_model`
  - `chunking_version`

Only scalar values should be placed in Chroma metadata. SQLite remains the source for relational document/conversation state; Chroma owns searchable chunk text and vectors.

## 8. Failure and consistency behavior

SQLite and Chroma do not share a transaction, so the order must be explicit:

1. Create/reuse the conversation.
2. Insert a `processing` document record.
3. Parse, chunk, and embed.
4. Add all chunk records to Chroma.
5. Verify the stored count for the document.
6. Update relational counts and status to `indexed`.

If steps 3–6 fail:

- Delete Chroma records for the document ID.
- Mark the relational document `failed` when possible.
- Return a clear error without claiming successful indexing.

Retry/idempotency beyond duplicate detection is deferred until Stage 5 unless Stage 2 testing demonstrates a concrete need.

## 9. Test plan

### Unit tests

- Extract page numbers and text from a small text-readable PDF.
- Reject encrypted/unreadable/empty-text input.
- Preserve all normalized source text across chunks except intentional overlap.
- Do not cross page boundaries.
- Respect target/hard chunk sizes and stable ordering.
- Produce deterministic chunk IDs.
- Fake embeddings have predictable dimensions and can simulate failure.

### API/integration tests with fakes

- First upload creates the conversation and returns `indexed`.
- Upload to an existing conversation reuses it.
- Response values match persisted document facts.
- Chroma/fake vector records contain complete provenance.
- Missing/non-PDF/oversized/empty uploads return the planned status codes.
- Duplicate upload within a conversation returns `409`.
- The same PDF in a different conversation is allowed.
- Embedding/vector failure removes vectors and records `failed`.
- `/chat` remains `501`.

### Real-component checks

- Extract every one of the eight supplied policy PDFs and compare page count/non-empty text with Stage 0 observations.
- Index all eight with the real local embedding model and persistent Chroma.
- Verify SQLite page/chunk counts against Chroma records.
- Reopen the persistent client and verify that indexed vectors remain available.
- Record model-download requirements, elapsed indexing time, and any warnings honestly.

Retrieval relevance is deliberately not claimed here; it is the purpose of Stage 3.

## 10. Stage 2 completion criteria

Stage 2 completion evidence:

- All eight supplied text-readable policy PDFs indexed successfully using the real local model: 12 pages became 22 persistent chunks.
- `/upload` returns the documented `indexed` response only after verified storage.
- Every vector maps back to conversation, document, filename, page, and chunk position.
- Duplicate, invalid, empty, and simulated-failure cases behave as documented.
- Persistence survives closing and reopening the vector-store client.
- Nineteen automated tests pass; repeated real-stack verification completed in under one second with the model cached in this environment.
- ONNX Runtime emitted a sandbox-specific warning because it could not persist a telemetry device identifier under the read-only home cache; it used an in-memory identifier and inference completed normally.
- Requirements P-002 and P-005–P-012 have evidence or an explicitly documented gap.
- `/chat` still returns `501`, and no Stage 3/4 functionality has been started.

## 11. Accepted checkpoint

The user approved Stage 2 implementation with these choices:

1. `pypdf` with page-by-page extraction; no OCR.
2. Local `sentence-transformers/all-MiniLM-L6-v2` through CPU ONNX Runtime for real embeddings, deterministic fake for tests.
3. Local Chroma `PersistentClient`, with embeddings computed explicitly by our provider.
4. Page-local logical chunks targeting 180 word pieces, with a 220 maximum and 30-token overlap.
5. 10 MiB prototype upload limit.
6. Duplicate PDF in the same conversation returns `409`; the same PDF in another conversation is allowed.
7. Failed documents remain marked `failed`, with any partial vectors removed.
