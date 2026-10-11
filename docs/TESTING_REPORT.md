# Complete Prototype Testing Report

## Purpose and assurance statement

This report records the complete local verification performed on 11 October 2026.
It separates deterministic software checks, real-embedding retrieval evaluation, and
hosted-model evaluation because they establish different kinds of confidence.

The current evidence supports the claim that the prototype is robust and reproducible
for the supplied case corpus. It does **not** support a claim that a probabilistic model
will answer every possible future wording correctly. Safe abstention, validated
citations, bounded retries, and visible conflict states are used where correctness
cannot be established.

## Final local results

| Verification layer | Result | Meaning |
| --- | ---: | --- |
| Complete automated suite | **124/124 passed** | Unit and API integration behavior |
| Baseline real-embedding retrieval | **12/12 passed** | Direct, table, version, cross-page, conflict and cross-policy recall |
| Multi-turn real-embedding retrieval | **22/22 passed** | Follow-ups, corrections, thresholds, authority and topic switching |
| Exact-evidence policy scenarios | **33/33 passed** | Required source text is available before generation |
| All-eight-PDF API flow | **Passed** | Upload all PDFs, chat, cite, persist and restore one workspace |
| Python compilation | **Passed** | `app`, `scripts`, and `tests` compile |
| Launcher shell syntax | **Passed** | `run_app.sh` parses with Bash |
| Evaluation JSON parsing | **Passed** | All versioned datasets are valid JSON |
| JavaScript syntax through Node | **Unavailable** | Node is not installed; static assets and routes are API-tested |
| Complete hosted Gemini run | **33/33 passed** | Live status/content/citation checks on all policy scenarios |
| Human semantic review | **Completed** | Extra defects became guards and regressions |
| Final focused hosted regressions | **Passed** | Current Zurich and vendor-meal scope behavior |

The complete live run used model `gemini-3.5-flash-lite`, prompt SHA-256
`d5ce2827ff5f4954c7611e21baf9f49de7ff6570cb64a96493b1a18d0baaced7`, and case
SHA-256 `96ee3b05fbe1c5b29628aa1ed7549af0ec7349c96a9570a0bdf87e6c3cff8941`.
Automated checks passed 33/33. Manual review then found an unclear historical Zurich
value and threshold-scope transfers in a vendor-meal answer. Those became runtime
guards, deterministic tests, stricter rubrics and focused live regressions.
The final local/focused version uses prompt SHA-256
`a032304ca618367d5aeee5abe3db489edd67b60f178f6ac89f0a02e55fb9942b` and case
SHA-256 `f654e77492e270ced6a8f39404fc464940f4b69ee37574644297442c39c88e9e`.

## Test layers

### 1. Deterministic unit and integration suite

`pytest` uses explicit fake embedding, vector-store, and chat-provider boundaries.
The application never silently uses these fakes at runtime. Coverage includes:

- API validation, health, OpenAPI routes, response shapes and status mappings;
- PDF signatures, malformed/encrypted/text-empty files and upload limits;
- page-local deterministic chunking, overlap, stable IDs and pathological long units;
- embedding empty-input and unexpected-dimension behavior;
- vector ranking, model/conversation filtering, page diversity and page companions;
- synchronous indexing, duplicate scope, count verification, cleanup and retry;
- five-message history order, dependent follow-ups and unrelated topic changes;
- prompt construction and JSON containment of untrusted document text;
- inline citation canonicalization, grouped citations, public numbering and unknown markers;
- up to two corrective structured-output attempts and safe failure after a third invalid answer;
- provider configuration, timeout, quota and generic failure behavior;
- atomic persistence of completed chat turns;
- conversation list, title fallback/truncation, restore and complete deletion;
- relational preservation when vector deletion fails;
- an end-to-end API flow with all eight supplied PDFs in one workspace.

### 2. Real-embedding retrieval evaluation

The retrieval scripts rebuild a temporary index using the real local
`all-MiniLM-L6-v2` model. They do not use the persistent user database.

- `evaluation/retrieval_cases.json` measures labeled page recall for twelve
  answerable questions and keeps a missing parental-leave question diagnostic.
- `evaluation/conversation_retrieval_cases.json` measures 22 turns across travel,
  workplace, gifts, procurement, data classification, authority and topic changes.
- `evaluation/policy_answer_cases.json` requires exact evidence phrases, not only
  the correct filename or page.

### 3. Policy reasoning and conflict scenarios

The 33 policy cases cover these reasoning classes:

| Class | Representative checks |
| --- | --- |
| Explicit supersession | 2025 versus 2022 travel deadlines, limits and portal use |
| Historical questions | Preserve the requested 2022 rule instead of forcing the current rule |
| Internal ambiguity | Zurich in an Asia-Pacific-only high-cost exception |
| Different scopes | Confidential versus Restricted data; employee versus contractor scope |
| Compatible policies | Procurement, ethics and reimbursement rules for vendor meals |
| Exact boundaries | USD 25 receipts, USD 250 gifts, USD 25,000 and USD 100,000 bands |
| Conditional exceptions | Tokyo high-cost lodging and required pre-trip Finance approval |
| Temporal gaps | 30-day submission versus possible denial after 60 days |
| Completeness | Every explicitly non-reimbursable item and multi-part answers |
| Missing evidence | Parental leave and missing historical Latin America value |
| Partial support | Answer lodging while stating parental-leave information is absent |
| Authority silence | New security policy does not expressly confirm or revoke USB guidance |
| Arithmetic/currency restraint | No invented single trip total or exchange rate |
| Injection resistance | Malicious user text and malicious retrieved-document instructions |

The expected treatment of every known relationship is maintained in
`docs/POLICY_CONFLICT_BOARD.md`.

## Failure and data-integrity guarantees tested

| Failure | Public behavior | Persistence behavior |
| --- | --- | --- |
| Bad/missing upload fields | `4xx` | No successful document |
| Parsing/indexing failure | Controlled `422`/`500` | Document recorded failed; written vectors cleaned when possible |
| Cleanup failure | Controlled `500` explaining incomplete cleanup | Document remains visibly failed |
| Duplicate active/indexed PDF | `409` | Existing index retained |
| Provider not configured/rate-limited | `503` | No partial chat turn |
| Provider timeout | `504` | No partial chat turn |
| Invalid JSON/citations after two corrections | `502` | No partial chat turn |
| Message database failure | `500` | User and assistant inserts roll back atomically |
| Vector deletion failure | `500` | Relational conversation is retained for retry |
| No retrieved evidence | Deterministic `insufficient_context` | Completed abstention turn is saved |

SQLite and Chroma do not share a transaction. Tests prove the implemented
compensation paths, but a process crash at the exact cross-store boundary can still
require reconciliation in a production system.

## Commands

```bash
python -m pytest -q
python scripts/evaluate_retrieval.py
python scripts/evaluate_conversation_retrieval.py
python scripts/evaluate_policy_answers.py
python -m compileall -q app scripts tests
bash -n run_app.sh
```

The optional hosted-model evaluation is:

```bash
python scripts/evaluate_policy_answers.py --live
```

That command sends bounded retrieved excerpts from the supplied PDFs and synthetic
test history to Gemini. It must be run only when that external data transfer is
approved. The runner prints model, prompt and case hashes, uses temporary storage,
paces requests, stops on a provider outage, and reports completed and skipped cases
separately. Pattern checks remain regression signals; every printed answer still
requires human semantic review.

## Remaining gaps

- No finite test set can prove correctness for every natural-language phrasing.
- The final narrow semantic guards were verified with focused live cases rather than
  another complete 33-call run. The complete run immediately before those guards was
  33/33, and the current local evidence suite remains 33/33.
- There is no installed browser-automation or JavaScript runtime in this environment;
  UI delivery and server contracts are automated, while rich interaction remains a
  manual-browser check.
- OCR, multilingual documents, concurrent multi-worker ingestion, crash recovery,
  authentication, access control, load, soak and penetration testing are outside the
  local prototype boundary.
- Citation validation proves that citations map to retrieved chunks. It does not by
  itself prove that every generated claim is entailed by the cited sentence.

These gaps are explicit release constraints, not hidden passes.
