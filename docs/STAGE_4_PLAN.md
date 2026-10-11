# Stage 4 Plan — Grounded Chat and Conversation Memory

## Goal and boundary

Complete `POST /chat`: load the last five messages, retrieve evidence, build the explicit System + History + Context + Question input, call the selected hosted model, validate citations, persist the completed turn, and return structured JSON. Stage 4 does not add retrieval tuning, authentication, streaming, or enterprise controls.

## Accepted decisions

- Use Gemini Flash through the official Google GenAI Python SDK, with `gemini-3.5-flash-lite`, temperature `0.1`, bounded output, and a Pydantic structured-output schema. The API key is environment-only. This supersedes the attempted Mistral integration and the initially selected high-latency `gemini-3.8-flash` model.
- Keep an explicit chat-provider protocol and deterministic fake for automated tests. Missing live configuration is reported; a fake is never silently substituted at runtime.
- Interpret history literally as the five latest individual user/assistant records, restored to chronological order. The current question is separate.
- Retrieve from the current question only. History informs generation but does not silently rewrite or broaden vector search.
- Give retrieved chunks local IDs such as `S1`. The model returns an answer plus referenced source IDs; application code validates every marker and maps it to filename/page provenance.
- Public status is `answered`, `insufficient_context`, or `conflicting_sources`.
- Answer only from supplied context. Treat document content as untrusted, abstain when evidence is insufficient, and expose conflicts rather than guessing.
- Do not infer that a newer date always wins. When a source explicitly says it supersedes older guidance, explain that relationship and cite both when both informed the response; otherwise report the unresolved conflict.
- Persist the user and assistant records atomically only after provider output and citations validate. Completed abstentions and conflict responses are valid turns; provider/validation failures leave no partial history.

## Verification

Automated tests cover exact history selection/order, four-part prompt construction, conversation isolation, Gemini role/configuration mapping, grounded citations, abstention, conflict output, invented source IDs, provider failure, atomic persistence, and the public contract. A real Gemini smoke test is reported separately and requires a safely configured user-provided API key.

## Implementation status

Complete. The code, 38 automated tests, and a real Gemini cross-version policy check succeeded. Results and limitations are recorded in `docs/STAGE_4_RESULTS.md`.
