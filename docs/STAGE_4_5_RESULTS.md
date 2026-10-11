# Stage 4.5 Web Demo Results

## Implemented

- An employee-facing application is served at `/`; Swagger remains at `/docs`.
- The layout is chat-first, with a dominant conversation canvas and a compact policy-source rail.
- The browser generates a fresh active conversation ID whenever the application opens, while the ID remains available under advanced workspace details for debugging.
- Drag/drop and multiple-file selection call the existing single-file upload endpoint sequentially and show per-file progress or errors.
- Indexed PDFs appear as source cards with filename, date, and chunk count.
- Chat supports a welcoming empty state, suggested questions, Enter-to-send, Shift+Enter for a new line, a generating indicator, readable answers, and server-supplied citation chips.
- Live `conflicting_sources` and `insufficient_context` results receive distinct labels.
- Failed chat requests preserve the question for retry rather than displaying an unsaved user turn.
- `GET /conversations/{conversation_id}` restores indexed sources and saved messages when a saved chat is selected, without altering the required `/upload` or `/chat` contracts.
- “New workspace” creates a fresh browser conversation after confirmation when appropriate.
- Saved conversations are listed by latest activity, receive a deterministic title from their first user question, and can be reopened without remembering an ID.
- A confirmed delete action permanently removes the selected conversation's messages, document records, and vector entries. Deleting the active chat immediately opens a fresh empty workspace.
- The source rail, saved-chat list, and desktop message canvas have explicit shrink/overflow behavior so long PDF lists and conversations remain independently scrollable.
- `run_app.sh` now opens the employee interface and still prints the Swagger URL.
- The responsive layout, visible keyboard focus, semantic labels, live status announcements, and reduced-motion behavior establish the planned accessibility baseline.

## Focused verification completed

At the user's request, the full test suite was not rerun. The original four focused checks passed, followed by six focused checks for the saved-chat extension:

- employee page, CSS, and JavaScript asset delivery;
- unknown-conversation restore behavior;
- conversation-isolated, ordered document/message restore with citations;
- continued OpenAPI publication of the required foundation routes.
- stable latest-activity ordering and first-question title derivation;
- permanent relational/vector deletion, unknown-chat handling, and legacy IDs containing URL-reserved characters.

The changed Python modules compile successfully and `run_app.sh` passes Bash syntax checking. A Node-based JavaScript syntax check was unavailable because Node is not installed; JavaScript is delivered and referenced correctly by the focused route check.

The first asset test exposed the environment's already-documented worker-thread hang when Starlette served files through its synchronous/thread-offloaded path. The three small immutable web assets are therefore read when the application module loads and returned from async FastAPI handlers. This is intentionally simple for the local prototype; a production deployment would serve versioned static assets through a web server or CDN.

## Manual review completed

The user inspected the application with all eight policies uploaded and accepted the interface without visual changes. The live conversation exposed retrieval/generation-quality issues—false conflict treatment, weak follow-up resolution, and one citation-marker validation failure—which are now Stage 5 regression cases rather than UI changes.

The manual checklist covered the core visual/upload/chat flow. The remaining narrow-width and full keyboard audit can be revisited during final packaging if needed.

The original review checklist was:

1. visual balance and preferred styling;
2. PDF browse and drag/drop;
3. two files uploaded into the same workspace;
4. one grounded answer and its citation chips;
5. opening with a fresh chat and reopening a saved chat;
6. new-workspace confirmation;
7. narrow browser width and keyboard interaction.

Stage 4.5 is complete.

## Known boundaries

The database does not persist the structured answer status separately from the assistant text and citations. A conflict or insufficient-context badge is therefore shown for the live response but is not reconstructed after reload; the saved answer text and citations are still restored. Changing that would require an explicit schema migration and is deferred unless the badge itself is judged important enough to justify it.

This remains a local single-user prototype without authentication. Consequently, the saved-chat endpoint lists every persisted local conversation. A multi-user deployment must scope listing, loading, and deletion to the authenticated owner before exposing these operations.
