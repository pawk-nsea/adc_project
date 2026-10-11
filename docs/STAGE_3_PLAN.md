# Stage 3 Plan — Retrieval Verification

## Goal and boundary

Prove that a question retrieves useful, traceable policy chunks before an LLM is allowed to answer from them. Stage 3 adds no public endpoint, prompt, conversation history, or answer generation; `/chat` remains `501 Not Implemented`.

## Accepted approach

1. Embed each question with the same local `all-MiniLM-L6-v2` provider and normalization used for document chunks.
2. Search Chroma with cosine distance and filter by both `conversation_id` and embedding-model identity.
3. Retrieve up to fifteen candidates, keep the strongest chunk per document page, and return at most five diverse ranked chunks containing exact text, filename, one-based page, chunk position, document ID, distance, and derived cosine similarity.
4. Keep retrieval behind explicit provider and service boundaries. Stage 4 will consume the service rather than duplicating vector-store logic.
5. Use deterministic fakes for service tests, real Chroma for filter/ranking tests, and the real model plus all eight PDFs for the evaluation run.

## Evaluation set

The versioned JSON set covers direct facts, tables, older/newer versions, cross-policy questions, conflicts, page-spanning multi-part questions, and a missing-answer diagnostic. Each answerable case lists the filename/page evidence expected within the top five results.

Initial acceptance target:

- every answerable case retrieves all labeled evidence within the top five;
- no result crosses the requested conversation boundary;
- result provenance and rank order are complete and deterministic for fixed inputs;
- missing-answer cases are reported separately, because nearest-neighbor search always returns the closest available text and cannot by itself prove that an answer exists.

If the initial baseline misses a labeled case, record the failure before changing chunking or retrieval. Cross-page overlap, a larger candidate set, metadata-aware ranking, reranking, and score thresholds remain evidence-driven alternatives rather than assumed improvements.

The first run passed 11/12 answerable cases. The missed two-part travel question contained both required pages in the candidate list, but multiple chunks from page 2 crowded the current-policy page-1 evidence down to rank 7. Page-level diversification was therefore added without changing the stored chunks or their citation pages.

## Completion evidence

Stage 3 is complete when automated tests pass, the real evaluation report records per-case results and aggregate recall, limitations are documented, and `/chat` remains unchanged.
