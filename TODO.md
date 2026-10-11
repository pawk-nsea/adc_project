# ADC case checklist

Use this as the main checklist. `[x]` means ready; `[ ]` still needs work.

## Deliverable 1 — Prototype repository

### Required API

- [x] Python REST API using FastAPI.
- [x] `POST /upload` accepts `conversation_id` and a PDF.
- [x] Create or reuse the conversation.
- [x] Parse PDF text and split it into logical chunks.
- [x] Create embeddings and store them in Chroma.
- [x] Save filename and upload time in SQLite.
- [x] Return successful indexing as JSON.
- [x] `POST /chat` accepts `conversation_id` and `message`.
- [x] Load the last five messages.
- [x] Retrieve relevant chunks with semantic search.
- [x] Build the prompt from instructions, history, context, and question.
- [x] Call Gemini and save the user and assistant messages.
- [x] Return JSON with PDF/page citations.

### Quality and demo

- [x] Handle missing, invalid, empty, encrypted, large, and duplicate PDFs.
- [x] Keep workspaces separate.
- [x] Handle older and conflicting policies.
- [x] Abstain when the documents do not support an answer.
- [x] Provide a browser demo and saved chats.
- [x] Add unit, integration, retrieval, and answer-quality tests.
- [x] Document known limits honestly.
- [ ] Re-test from a clean clone.
- [ ] Run the final live demo with all eight PDFs.

### Repository submission

- [x] Include source code, tests, evaluation cases, and sample policies.
- [x] Add local setup and run instructions to `README.md`.
- [x] Add a short Design Decisions section to `README.md`.
- [x] Keep secrets and generated files out of Git.
- [x] Create the private GitHub repository `adc_project`.
- [x] Push the reviewed `main` branch.
- [ ] Give the ADC reviewers access.
- [ ] Check the repository link in a private/incognito window.

### Prototype presentation — 1–2 slides

- [ ] Slide 1: problem, user flow, and prototype architecture.
- [ ] Slide 2: key decisions, test evidence, limits, and next steps.
- [ ] Prepare a short live demo: upload, ask, inspect citation, show conflict.

## Deliverable 2 — Enterprise strategy presentation

The audience is business stakeholders. Keep the story clear and practical.

### Pillar 1 — Enterprise architecture

- [ ] Draw the high-level architecture and communication flows.
- [ ] Connect SharePoint and other internal document stores.
- [ ] Separate slow ingestion jobs from fast chat requests.
- [ ] Explain queues, retries, failures, latency, and caching.
- [ ] Choose and justify Azure, AWS, or GCP services.
- [ ] Show security, identity, access control, and data boundaries.

### Pillar 2 — LLMOps and CI/CD

- [ ] Show development, test, staging, and production deployment.
- [ ] Explain how conflicting or poor-quality documents are handled.
- [ ] Define automated retrieval and answer evaluations.
- [ ] Add quality gates, comparison with the current version, and rollback.
- [ ] Version code, prompts, models, evaluation data, and source documents.
- [ ] Turn user feedback into reviewed test cases and improvements.

### Pillar 3 — Trust and governance

- [ ] Explain grounded answers, citations, abstention, and guardrails.
- [ ] Define quality, safety, latency, cost, and failure monitoring.
- [ ] Explain query/data drift detection and the response process.
- [ ] Define owners, audit logs, retention, privacy, and incident handling.
- [ ] Create a rollout and training plan for 10,000 employees.
- [ ] Measure adoption, trust, helpfulness, and support needs.

## What I must understand for the interview

- [ ] Explain the complete upload-to-answer flow without notes.
- [ ] Explain chunk size, overlap, page boundaries, and their trade-offs.
- [ ] Explain embeddings, cosine similarity, top-k, and retrieval failures.
- [ ] Explain Chroma versus a production vector database.
- [ ] Explain context windows, token limits, and prompt construction.
- [ ] Explain RAG, hallucinations, citations, conflicts, and abstention.
- [ ] Defend FastAPI, SQLite, Chroma, MiniLM, and Gemini choices.
- [ ] Explain the main failure paths and HTTP responses.
- [ ] Explain what the tests prove—and what they do not prove.
- [ ] Separate prototype choices from production architecture.
- [ ] Link technical choices to accuracy, latency, cost, scale, and risk.

## Final evaluation check

- [ ] **Engineering:** code is readable, structured, tested, and extensible.
- [ ] **GenAI depth:** explain chunking, embeddings, retrieval, and context limits.
- [ ] **Consulting:** connect the design to business value and risk.
- [ ] **Communication:** repository and slides are concise and professional.
- [ ] Remove secrets, stale claims, broken links, and unnecessary files.
- [ ] Rehearse expected questions and keep a backup demo/video.

## Best next order

1. Finish the enterprise strategy and diagrams.
2. Create the prototype and strategy slides.
3. Clean-clone test the repository.
4. Push the final version and invite the reviewers.
5. Rehearse the presentation and demo.
