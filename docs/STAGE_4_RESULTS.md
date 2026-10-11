# Stage 4 Implementation Results

## Outcome

The grounded chat path is implemented behind `POST /chat`. It retrieves evidence for the current question, supplies the five latest stored messages in chronological order, calls Gemini Flash, validates structured source IDs, constructs public filename/page citations, and atomically stores the completed user/assistant turn.

## Verified locally

- The full automated suite passes: 38 tests.
- Tests verify the exact five-message boundary and order, explicit prompt sections, citation mapping, rejection of invented or unverified citations, abstention, conflict responses, provider failure behavior, and no partial history on failed turns.
- Dependency consistency and Python compilation checks pass.
- A missing Gemini key produces an explicit configuration error; runtime does not fall back to a fake model.
- A provider-specific test verifies Gemini role mapping, model selection, timeout, temperature, output limit, and Pydantic structured-output configuration without a network call.
- The first Gemini live request exposed a Google SDK compatibility issue: strict Pydantic models emit `additionalProperties`, which the SDK serialized as an unsupported field. The provider now sends the supported raw JSON-schema form without that generation-only keyword and still performs strict Pydantic validation on the returned JSON.

## Live-provider status

The original Mistral live attempt reached the provider but returned `429 rate_limited`, including after its working Playground alias was selected. The user therefore replaced Mistral with Gemini Flash. The first Gemini request reached the provider but returned `400 INVALID_ARGUMENT` for the SDK schema-conversion issue described above; the adapter was corrected.

The repeated real Gemini check then succeeded. Against temporary storage containing the 2022 and 2025 travel policies, it reported:

- `answered` status;
- current Asia-Pacific lodging limit of USD 180, cited to `reimbursement_2025.pdf`, page 2;
- older limit of USD 200, cited to `travel_expenses_2022.pdf`, page 2;
- explicit 2025 supersession and older-policy context with page-1 citations to both PDFs;
- exactly two persisted messages for the completed user/assistant turn.

This verifies the real SDK path, retrieval-to-generation integration, structured response, application citation mapping, and completed-turn persistence. Stage 4 is complete.

A later request against the persistent application conversation reproduced intermittent Gemini `504 DEADLINE_EXCEEDED` behavior: `gemini-3.8-flash` took approximately 79 seconds once and exceeded 120 seconds on another request. The provider-recommended `gemini-3.5-flash-lite` completed the same retrieved-context request in 1.69 seconds with `answered` status and one grounded source. The complete two-policy live check also succeeded, correctly returning the USD 180 current limit, USD 200 older limit, explicit supersession, and three validated PDF/page citations. Flash-Lite is now the selected prototype model with a 60-second safety deadline. Timeout/rate-limit failures receive distinct safe API responses while preserving the no-partial-history rule.

## Known prototype limitations

- Retrieved context and up to five recent messages are sent to a hosted provider; Google states that free-tier content may be used to improve its products. Organizational data-sharing approval is outside this prototype.
- Low temperature improves consistency but does not guarantee deterministic or correct responses.
- Conflict handling is conservative because the corpus lacks general authority metadata. Dates alone do not establish precedence.
- The synchronous provider call currently runs in the request path. This is simple for a local demo but can block an async worker and is not the intended enterprise serving design.
- Structured output and citation validation prevent invented source references from reaching the caller, but they do not prove that every sentence is fully entailed by its cited text. Stage 5 will evaluate answer quality and failure modes.

## Focused quality correction after live use

The broad question “How much can I spend on a trip to Asia-Pacific?” initially produced a misleading answer that led with the USD 230 high-cost-city exception. Inspection showed that retrieval supplied the exception/meals chunk but had filtered out the neighboring page-2 chunk containing the standard USD 180 lodging limit. The page-diversity algorithm now fills unused top-five capacity with same-page candidates after its first diverse-page pass. The system prompt also explicitly requires standard rules before exceptions and prohibits inventing one total trip budget from separate per-night and daily caps.
