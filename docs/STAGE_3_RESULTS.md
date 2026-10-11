# Stage 3 Retrieval Results

## Verified configuration

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2` through CPU ONNX Runtime.
- Distance: cosine in persistent Chroma.
- Scope filter: exact `conversation_id` and embedding-model identity.
- Candidate pool: up to 15 nearest chunks.
- Returned context: top five using a diversity-first pass (the strongest chunk per document page), then filling unused capacity with the next-best same-page chunks.
- Evaluation data: all eight supplied PDFs, 22 chunks, 13 labeled questions.

Run the same check with:

```bash
python scripts/evaluate_retrieval.py
```

## Results

The initial direct top-five baseline passed 11 of 12 answerable cases. A two-part current travel question missed page 1 because four highly similar current/old page-2 chunks occupied most of the result list; the needed current page-1 chunk was rank 7.

After page-level diversification:

| Category | Passed |
|---|---:|
| Direct fact | 4/4 |
| Table | 2/2 |
| Version-specific | 1/1 |
| Cross-page | 2/2 |
| Conflict | 2/2 |
| Cross-policy | 1/1 |
| **Total answerable** | **12/12** |

The unsupported parental-leave question is a diagnostic and is not counted as a retrieval pass. Chroma still returned the nearest workplace and travel chunks even though none contains an answer.

## What the evidence means

Page-local chunking did not lose the two multi-page evaluation cases. Diversifying the returned pages was enough to expose both pieces of evidence without introducing cross-page chunks or ambiguous page citations. A later live question exposed the inverse failure mode: when the corpus had fewer than five distinct pages, the strict page filter discarded a second page-2 chunk containing the standard USD 180 lodging limit while retaining the USD 230 exception. Retrieval now preserves the diversity-first pass and fills only otherwise-unused capacity with same-page candidates.

The baseline achieves source/page recall at five for this small labeled set, but ranking is not authority-aware:

- the 2022 travel policy ranked above the current 2025 policy for the Asia-Pacific lodging question;
- temporary 2021 home-office guidance ranked above the current workplace policy for the monthly stipend question;
- both sides of the local-storage and home-office conflicts were retrieved, but retrieval does not decide which governs.

Similarity scores also cannot currently prove answerability. The unsupported question's top similarity was `0.353`, while one valid version-specific question had a top similarity of `0.426`; a threshold chosen from this tiny set would be fragile. Stage 4 must therefore use explicit grounding/abstention instructions, and authority/freshness treatment remains a deliberate later decision rather than an undocumented retrieval rule.

## Limitations

- Thirteen hand-labeled questions are useful regression evidence, not a production-quality benchmark.
- Exact ranking can vary after model, chunking, corpus, or HNSW configuration changes.
- The diversity-first fill strategy is a pragmatic heuristic; it can still miss useful chunks beyond the candidate/context budget and does not replace reranking.
- No lexical/hybrid search, reranker, freshness boost, policy-authority metadata, or answerability classifier is implemented.
- The evaluation measures whether labeled evidence is retrieved, not whether a generated answer is correct.
