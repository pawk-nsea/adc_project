# Final prototype code review

15 October 2026 · DEC-070. Review of the current working tree for clarity,
maintainability and scaling limits, with no implementation changes. The user
reports that final hardening, clean-install validation and both presentations
are complete; this review does not independently assess those external artifacts.

The code is suitable for the local walking-skeleton submission. API handlers,
application services and provider adapters have understandable responsibilities.
Typed contracts, dependency injection, page provenance, bounded correction and
atomic message persistence make the main paths straightforward to explain and
test. Enterprise scalability has not been demonstrated.

## Findings and possible follow-up

These findings do not block submitting the private local prototype. They would
need a separate implementation and validation stage before shared enterprise use.
Priorities describe that future work, not a claim that the case requires it now.

| Priority | Finding and practical impact | Possible follow-up and implementation reference |
| --- | --- | --- |
| High for shared use | There is no authenticated user or document authorization. Listing, restoring, deleting and opening workspaces are available to callers; a conversation ID is only a data filter. | Apply identity and document permissions consistently to retrieval, storage and source viewing. [Conversation API](../app/api/conversations.py#L23), [PDF API](../app/api/documents.py#L18), [workspace service](../app/services/conversations.py#L88). |
| Medium | Async routes directly call synchronous parsing, embedding, database and Gemini work. Those calls can block the serving event loop and delay other requests. | Offload blocking work or use suitable async clients; separate slow ingestion from serving and measure concurrent requests. [Chat route](../app/api/chat.py#L23), [upload route](../app/api/upload.py#L24), [Gemini request/retry](../app/providers/llm.py#L191). |
| Medium | Every lexical search loads and tokenizes all chunks in the workspace. Context enrichment also reads whole selected documents to find their start and issues individual page reads. Work grows with corpus size even though returned evidence is bounded. | Use an indexed lexical search and targeted/batched context reads after measuring realistic corpora. [Keyword search](../app/providers/vector_store.py#L210), [document starts](../app/providers/vector_store.py#L299), [page reads](../app/providers/vector_store.py#L357). |
| Medium | The saved-chat list performs document and message queries per conversation, without pagination. Selecting full Document objects also loads retained PDF bytes; restoring a chat loads its full message history. Growing workspaces increase query, memory and response costs. | Fetch summary columns/counts, defer PDF bytes to source viewing and paginate lists/history. [Workspace listing](../app/services/conversations.py#L88), [restoration](../app/services/conversations.py#L144), [PDF column](../app/models.py#L70). |
| Medium | Chunk-count and output-token bounds are present, but the combined model input has no token budget. Per-request timeouts, provider retries and answer correction do not impose a whole-chat deadline. | Budget complete inputs and elapsed time; measure long questions, large pages and provider failures. [Retrieval enrichment](../app/services/retrieval.py#L73), [prompt assembly](../app/services/prompt_builder.py#L26), [correction loop](../app/services/chat.py#L154), [provider retries](../app/providers/llm.py#L191). |
| Medium | SQLite and Chroma have separate commits. Compensation handles ordinary ingestion failures, but interrupted processing can leave processing records or inconsistent stores. Duplicate detection is a read-before-write check without a database uniqueness constraint; overlapping uploads can race. Deletion can remove some vectors before a later failure. | For concurrent deployment, define idempotency, recovery/reconciliation and deletion behavior, with interruption/concurrency tests. [Ingestion](../app/services/ingestion.py#L80), [document schema](../app/models.py#L49), [deletion](../app/services/conversations.py#L230). |
| Low | Tokenizer preparation depends on a private Chroma method and adapter attributes. The SDK/provider seam is clear, but upstream internal changes can break it during upgrades. Direct dependencies are pinned; transitive versions are not locked. | Keep this dependency inside the embedding adapter, verify upgrades with the real cached model and evaluate a public tokenizer interface if needed. [Embedding adapter](../app/providers/embeddings.py#L26), [dependencies](../pyproject.toml). |

Policy precedence and follow-up detection are explicit heuristics with useful
comments and focused tests. Their limits remain important: only retrieved policy
metadata is compared, interim matches can be broad, and future dates/employee
scope are not resolved by Python. The semantic gate checks reported issues and
status agreement; it cannot establish the truth of an empty issue list. Current
live defects and their measured scopes remain in the
[quality report](QUALITY_IMPROVEMENT_RESULTS.md). This review establishes no new
live semantic score.

## Checks and delivery scope

- All **150 pytest checks pass** in both the working tree and an exported copy of
  the staged submission. The export reuses the existing Python environment;
  this does not establish another independent dependency installation.
- Python AST parsing, evaluation JSON parsing, Bash syntax, dependency consistency
  (`pip check`) and `git diff --check` pass. No Node.js executable is available for
  a separate JavaScript syntax check; the browser code was inspected statically.
- A SHA-256 baseline covers 58 implementation/configuration files. Final comparison
  verifies that this review changes none of them; only documentation is added or
  updated. Existing code changes from earlier authorized stages are included in
  the final delivery.
- Candidate files and 338 reachable Git objects were scanned for the actual local
  credential and common credential signatures; no matches were found. This is a
  bounded submission check, not a general security audit. Local environment files,
  runtime/model caches, raw evaluation reports and archives remain excluded.
- The existing GitHub repository is private and its default branch is `main`.
  The user explicitly authorizes committing and pushing this final project.
  Reviewer access and presentation contents are not independently verified here.

No production code, prompt, configuration, dependency or public interface changes
are made in this review. No new Gemini calls or live evaluation runs are needed
for this stage.
