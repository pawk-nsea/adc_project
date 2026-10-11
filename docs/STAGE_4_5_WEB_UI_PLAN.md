# Stage 4.5 — Usable Web Demo Plan

> Historical note: the original active-workspace restore behavior below was superseded after browser review. The implemented application now always opens a fresh chat and exposes prior conversations through the server-backed Saved chats list.

## Why this stage exists

The case explicitly requires a robust minimal Python REST API with `POST /upload` and `POST /chat`; it does not require a browser interface. Stages 1–4 now demonstrate the core ingestion and grounded-chat path, so the functional walking skeleton exists. Swagger remains useful for reviewers inspecting the API, but it exposes implementation details such as `conversation_id` and makes the user manually coordinate upload and chat. That is a poor demonstration of how an Apex employee would use the assistant.

Stage 4.5 will add a small, professional browser interface over the existing API before Stage 5 evaluates robustness. It is an optional demonstration layer, not a replacement for the required endpoints.

## Goal and boundary

Build one understandable workflow in which a user can start a policy workspace, upload one or more PDFs, ask questions, and inspect citations without manually creating or remembering a conversation ID.

This stage will not change embedding, retrieval, prompting, model selection, policy precedence, or enterprise architecture. It will not add authentication, user accounts, document editing, PDF rendering, streaming responses, or production deployment concerns.

## Proposed user flow

1. The launcher opens `/`, the employee-facing interface. `/docs` remains available for API inspection.
2. The browser creates a technical conversation ID automatically and keeps it out of the main workflow.
3. The empty state explains the two-step process: add policy PDFs, then ask questions about them.
4. The user drags in or selects one or more PDFs. The UI sends the existing one-file `POST /upload` requests sequentially under the same conversation ID.
5. Each file visibly progresses through uploading/indexing to indexed or failed. Successfully indexed documents appear in the Sources panel.
6. Chat becomes available after at least one document is indexed. Suggested questions help the first-time user understand that specific policy questions work better than vague keyword searches.
7. The user submits a question. The message appears immediately with a clear generating state; duplicate submission is prevented until the request finishes.
8. The assistant response renders as readable text, followed by filename/page citation chips. `conflicting_sources` and `insufficient_context` receive visually distinct explanations rather than looking like ordinary successful answers.
9. A “New workspace” action creates a fresh conversation after confirmation when the current workspace contains documents or messages. The technical ID is available only in a small advanced/debug area with a copy action.
10. Reloading the page restores the active conversation and its server-backed document/message summary rather than forcing the user to remember an ID.

## Proposed layout

Desktop uses a compact source rail and a dominant chat workspace. On narrow screens the source rail moves above the conversation.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Apex Global · Policy Assistant                New workspace   Help  │
├───────────────────────┬──────────────────────────────────────────────┤
│ SOURCES               │ Ask about your policies                     │
│                       │                                              │
│ Drop PDF files here   │  Welcome / suggested questions              │
│ or Browse             │                                              │
│                       │  User question                               │
│ ✓ reimbursement…pdf  │  Assistant answer                            │
│ ✓ travel…pdf         │  [reimbursement_2025.pdf · page 2]           │
│                       │                                              │
│ Advanced              │  ┌────────────────────────────────────────┐  │
│ Conversation ID       │  │ Ask a policy question…                 │  │
│ [copy]                │  └──────────────────────────────────── Send┘  │
└───────────────────────┴──────────────────────────────────────────────┘
```

## Visual direction

- Calm internal-enterprise appearance: light neutral surfaces, dark readable text, restrained blue accent, and clear success/warning/error colors.
- Dense enough for a work tool, but with one obvious primary action at each state.
- Conversation text remains the visual focus; uploads and technical details are secondary.
- Citations look interactive and scan-friendly even though PDF preview/download is outside this stage.
- Avoid decorative animations. Use a small progress indicator only when the system is genuinely working.
- Meet basic accessibility expectations: real labels, keyboard operation, visible focus, sufficient contrast, an `aria-live` status region, and reduced-motion support.

## Technical approach

### Frontend

Use a FastAPI-served single page made with semantic HTML, a small CSS file, and plain JavaScript modules. This avoids a Node/build-tool dependency for a two-screen demo and keeps the submission easy to run and explain. React or another SPA framework would become reasonable if the interface grew into a separately deployed product with routing, complex shared state, or a larger frontend team.

Planned files:

```text
app/
  web/
    index.html
    styles.css
    app.js
```

FastAPI will serve `/` plus static assets. The existing OpenAPI/Swagger interface stays at `/docs`.

### Conversation state

- Generate the ID in the browser with `crypto.randomUUID()` and store only the active ID in `localStorage`.
- Add a small read-only endpoint, proposed as `GET /conversations/{conversation_id}`, returning the indexed-document summary and saved messages needed to restore the screen.
- Keep SQLite authoritative. Do not duplicate full conversation history in browser storage.
- A brand-new browser ID may not exist server-side until the first successful upload; the UI treats a restore `404` as a valid empty workspace.

### Existing API compatibility

- Do not alter `POST /upload` or `POST /chat` request/response contracts.
- Multiple-file selection is a UI convenience implemented as sequential calls to the existing single-file upload endpoint.
- Render citation labels only from the server response; do not manufacture filenames or page numbers in JavaScript.
- Display safe server error details for validation, duplicate files, provider limits, and timeouts, with a retry action where appropriate.

## Important states to design explicitly

| State | User-visible behavior |
|---|---|
| Empty workspace | Short explanation, prominent PDF drop zone, chat disabled |
| Indexing | Per-file progress/status; chat remains usable for already indexed documents |
| Ready | Source list present, question input enabled, suggested questions shown when chat is empty |
| Generating | User message shown, input temporarily disabled, visible working indicator |
| Answered | Answer plus citation chips |
| Conflicting sources | Warning treatment explaining that policies disagree, with all citations visible |
| Insufficient context | Neutral “not found in uploaded policies” treatment and guidance to upload another document or rephrase |
| Recoverable error | Plain-language error and retry; typed question is preserved |
| Reload/resume | Server-backed sources and messages restored for the active ID |

## Implementation slices

1. **Shell and route:** serve the semantic page at `/`, add static assets, preserve `/docs`, and change the launcher to open `/`.
2. **Workspace lifecycle:** automatic ID creation, local active-ID persistence, new-workspace behavior, and read-only restore endpoint.
3. **Upload experience:** drag/drop and browse, sequential multiple upload, per-file status, source list, and error handling.
4. **Chat experience:** message rendering, loading state, response statuses, citation chips, textarea keyboard behavior, and retry-safe errors.
5. **Responsive/accessibility polish:** narrow-screen layout, focus states, labels, live status announcements, contrast, and reduced motion.
6. **Verification and documentation:** focused backend/UI-route tests, browser checklist, README screenshots/instructions, and decision/result updates.

Each slice should be usable before moving to the next; visual polish should not precede a correct end-to-end flow.

## Verification plan

Automated checks will focus on behavior that can be verified reliably without introducing a browser-test framework solely for this stage:

- `/` and static assets load successfully;
- `/docs`, `/upload`, and `/chat` remain available;
- the conversation-summary endpoint isolates conversations and returns documents/messages in stable order;
- response data needed by the UI has a typed schema;
- API errors used by the UI remain explicit.

A manual browser checklist will cover drag/drop, multiple uploads, reload/restore, new workspace, successful chat, citations, conflict, insufficient context, provider failure, narrow layout, and keyboard navigation. Stage 5 can decide whether a browser automation dependency is justified.

## Observable completion criteria

- `./run_app.sh` opens the employee-facing page rather than Swagger.
- A first-time user can upload a supplied PDF and ask a cited question without seeing or typing a conversation ID.
- Multiple PDFs can be indexed into one workspace with clear individual outcomes.
- Reload restores the active workspace from server-backed state.
- Answer, conflict, insufficient-context, timeout, and upload-error states are understandable.
- The required API contracts remain available and compatible.
- The page is usable at desktop and narrow widths and by keyboard.
- Focused checks and the manual browser checklist are recorded honestly; the full Stage 5 evaluation is not folded into this stage.

## Decisions to confirm before implementation

1. Use the recommended dependency-light FastAPI + HTML/CSS/JavaScript approach rather than React.
2. Use the proposed two-column “Sources + Chat” workspace rather than a multi-page wizard.
3. Add the read-only conversation-summary endpoint so reload/resume works reliably.
4. Keep PDF preview/download outside this stage; citations show filename and page only.
