# ADC Submission Checklist

Current stage: final code review and explicitly authorized GitHub delivery (DEC-070). The [review](docs/FINAL_CODE_REVIEW.md) records findings and local checks without implementation changes. The user reports final hardening, clean-install validation and both presentations complete; external setup/presentation evidence has not been independently reviewed here. Historical unchecked presentation items below describe repository evidence, not a request to repeat that work. [Evaluation evidence](docs/EVALUATION.md) separates measured results from remaining risks.

## Prototype and repository

- [x] Ingest PDFs, create local embeddings and persist metadata/vectors.
- [x] Retrieve workspace evidence and the latest five messages.
- [x] Generate and verify cited answers; persist completed turns.
- [x] Provide a browser interface, PDF viewing and saved chats.
- [x] Retain tests, evaluation fixtures and all eight sample PDFs.
- [x] Curate README, architecture, decisions, requirements and evaluation evidence.
- [x] Verify the documentation-only readability pass against the starting working tree.
- [x] Review retained legacy test assertions against the current two-attempt failure contract (DEC-069; all 150 tests pass again in DEC-070).
- [x] Keep credentials, runtime state, raw experiments and historical snapshots out of submission candidates.
- [x] Finish focused cleanup verification and review the diff (41 targeted tests, eight packaged smoke checks).
- [x] Reproduce setup on an independent clean machine (user-reported completion; not independently repeated in DEC-070).
- [x] Separate current questions from retrieval hints, prioritize selected pages, calibrate models/prompts and improve correction; run focused live regressions (DEC-069).
- [ ] Further reduce false semantic approvals, unsupported permissions/obligations and occasional irrelevant details; [current evidence](docs/QUALITY_IMPROVEMENT_RESULTS.md) records the unresolved cases.
- [x] Rerun all active live fixture suites and diagnose the supplied meal/expense conversation.
- [x] Obtain explicit instruction for the final commit/push (15 October 2026); Git history records the delivery outcome.
- [ ] Confirm private-repository access for ADC reviewers.

## Prototype presentation — 1–2 slides

- [x] Draft the [core architecture slide](docs/PROTOTYPE_ARCHITECTURE_SLIDE.md) showing inputs, interface, ingestion, retrieval, both prompts, generation, Python checks, verification and output.
- [ ] Summarize decisions, observed quality, trade-offs and known limitations.
- [ ] Rehearse upload, saved-chat restoration and citation inspection.

## Enterprise strategy presentation

- [ ] Show repository connectors, queued ingestion workers, authorized retrieval and serving.
- [ ] Select and justify cloud services, scaling, caching and operational targets.
- [ ] Explain data-quality ownership and handling of conflicts/stale policies.
- [ ] Define code/prompt/model/data versioning and evaluation/release gates.
- [ ] Cover feedback, monitoring, query drift, privacy, incidents and retention.
- [ ] Plan phased rollout and training for 10,000 employees.

## Final review

- [ ] Engineering: readable code, clear boundaries and evidence-backed checks.
- [ ] GenAI depth: explain chunking, embeddings, context and failure modes.
- [ ] Consulting: connect prototype choices to enterprise value and risk.
- [ ] Communication: concise documentation, accurate claims and a rehearsed demo.
