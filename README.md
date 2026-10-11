# Apex Global RAG Interview Case

## Purpose and current status

This repository is being prepared for ADC’s GenAI Engineer interview case: a minimal Python RAG API for Apex Global policy documents plus an enterprise-scale strategy and presentation.

**Current status:** The local prototype through Stage 5 is implemented and fully retested. The FastAPI application ingests policy PDFs, retrieves conversation-scoped evidence, and uses Gemini Flash to return grounded answers with application-verified PDF/page citations. The complete deterministic suite passes 124/124, real-embedding retrieval passes 12/12 direct cases and 22/22 conversation turns, and exact policy evidence passes 33/33 scenarios. A complete live Gemini run passed 33/33 automated checks; manual review produced additional guards that also pass focused live regressions.

## Documentation

- [Submission and presentation checklist](TODO.md)
- [Verified case transcription](reference/CASE_BRIEF.md)
- [Requirements and acceptance tracker](docs/REQUIREMENTS.md)
- [Staged plan and progress](docs/PLAN.md)
- [Initial prototype blueprint (historical plan)](docs/PROTOTYPE_BLUEPRINT.md)
- [Stage 2 ingestion and indexing plan](docs/STAGE_2_PLAN.md)
- [Stage 3 retrieval plan](docs/STAGE_3_PLAN.md)
- [Stage 3 retrieval results](docs/STAGE_3_RESULTS.md)
- [Stage 4 grounded chat plan](docs/STAGE_4_PLAN.md)
- [Stage 4 implementation results](docs/STAGE_4_RESULTS.md)
- [Stage 4.5 usable web demo plan](docs/STAGE_4_5_WEB_UI_PLAN.md)
- [Stage 4.5 implementation results](docs/STAGE_4_5_RESULTS.md)
- [Stage 5 robustness and answer-quality plan](docs/STAGE_5_PLAN.md)
- [Stage 5 retrieval and answer-contract results](docs/STAGE_5_RESULTS.md)
- [Complete testing report](docs/TESTING_REPORT.md)
- [Implemented solution blueprint and flow diagrams](docs/SOLUTION_BLUEPRINT.md)
- [Decision log](docs/DECISIONS.md)
- [Conceptual enterprise architecture](docs/ARCHITECTURE.md)
- [Permanent repository working instructions](AGENTS.md)

The supplied source PDF remains authoritative. The supplied policy PDFs under `data/sampleset_policies/sampleset_policies/` are application data and include intentionally useful version, freshness, and contradiction cases.

## Intended deliverables

- A robust, minimal Python REST API with `POST /upload` and `POST /chat`.
- PDF parsing, logical chunking, embeddings, vector retrieval, relational metadata/conversation persistence, recent conversation history, LLM generation, and PDF citations.
- A private repository link or ZIP containing source and verified local run guidance.
- One or two prototype-approach slides.
- A business-stakeholder presentation covering enterprise architecture, LLMOps/CI/CD, and trust/governance including adoption for 10,000 employees.

## Design decisions

The local prototype uses FastAPI, SQLAlchemy/SQLite, `pypdf`, Chroma, the small `sentence-transformers/all-MiniLM-L6-v2` embedding model through CPU ONNX Runtime, and Gemini Flash for answer generation. Chunks remain inside page boundaries and retain conversation, document, filename, page, and position metadata. Conflicting policies are preserved and surfaced instead of resolving authority from dates alone. Validated inline source markers must reference retrieved evidence; the application canonicalizes redundant model metadata and constructs the public filename/page citations.

This keeps ingestion and retrieval local, but live chat requires a Gemini credential and sends the bounded recent history plus retrieved policy text to that hosted service. Google states that free-tier content may be used to improve its products, so this path is suitable for the artificial case corpus but not automatically for confidential enterprise data. The prototype also requires a one-time embedding-model download, uses two persistence systems without a shared transaction, and is not an enterprise deployment architecture. Trade-offs, alternatives, and revisit conditions are in the [detailed decision log](docs/DECISIONS.md).

## Run instructions

These commands were verified with Python 3.13. Python 3.11–3.13 is supported.

### Fastest setup on a new computer

Install Python 3.11–3.13, download or clone this repository, and run:

```bash
./setup_and_run.sh
```

This creates `.venv`, installs the application, asks for a Gemini API key, saves the key only in the Git-ignored local `.env`, starts the server, and opens the app. The first policy upload also downloads the local embedding model. Internet access is therefore required during first setup.

The Gemini key is deliberately not included in the repository. Every user must supply their own key; committing a shared key would expose a reusable credential.

### Normal use after setup

After the one-time setup, launch the complete local application with:

```bash
./run_app.sh
```

The launcher uses `.venv`, lets the application load `.env`, initializes local storage during FastAPI startup, enables code reload, and opens the employee-facing web application in the default browser once the health endpoint is ready. Stop it with `Ctrl+C`.

### Manual development setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q
python -m uvicorn app.main:app
```

The direct Uvicorn command remains available for debugging. Optional launcher overrides are `ADC_APP_HOST`, `ADC_APP_PORT`, `ADC_APP_RELOAD=false`, and `ADC_APP_OPEN_BROWSER=false`.

The employee-facing application is at `http://127.0.0.1:8000/`. Swagger remains available at `http://127.0.0.1:8000/docs` for generated API documentation. You can also check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The default SQLite file is created under `data/runtime/`. To enable real chat, copy the ignored example file and add your own Gemini key locally:

```bash
cp .env.example .env
```

Set `ADC_GEMINI_API_KEY` in `.env`. Do not paste the key into source code, tests, chat messages, or commits. Upload and health checks work without it; `/chat` returns `503` until it is configured.

Open `http://127.0.0.1:8000/`, then drag in or browse for one or more supplied policy PDFs. The web application creates and remembers the workspace ID automatically, uploads files sequentially into that workspace, and enables chat after the first successful index. The first real upload downloads the 79.3 MiB compressed embedding model into the ignored `data/model-cache/`; later uploads reuse it.

Ask a policy question in the chat composer. A grounded answer shows filename/page citation chips beneath the response. The application always opens with a fresh empty chat; prior conversations remain available under **Saved chats** and can be reopened or permanently deleted. Use **New workspace** when you want another separate document set and conversation without reloading.

For direct API inspection, open `http://127.0.0.1:8000/docs`, expand `POST /upload`, choose **Try it out**, enter a conversation ID, select a PDF, and execute. A successful response is `201` and contains `status: "indexed"` plus the stored chunk count.

The same flow can be checked from a terminal:

```bash
curl -X POST http://127.0.0.1:8000/upload \
  -F conversation_id=demo \
  -F 'file=@data/sampleset_policies/sampleset_policies/reimbursement_2025.pdf;type=application/pdf'
```

Then expand `POST /chat` in the API documentation. Enter the **same** `conversation_id` used for the upload and a policy question. A successful response has this shape:

```json
{
  "conversation_id": "demo",
  "status": "answered",
  "answer": "... [1]",
  "citations": [{"id": 1, "filename": "reimbursement_2025.pdf", "page": 1}]
}
```

`status` can also be `insufficient_context` or `conflicting_sources`. An insufficient-context answer has no citations; grounded and conflict responses require citations verified against retrieved evidence.

The prototype uses `gemini-3.5-flash-lite`, selected by a real same-context latency check: it answered in 1.69 seconds while `gemini-3.8-flash` was intermittently taking 79–120+ seconds. Requests have a 60-second safety deadline. The API returns a specific `504` timeout message or `503` rate-limit message, and failed turns are not added to conversation history.

To rerun the real Stage 2 corpus check separately from the fast automated suite:

```bash
python scripts/verify_stage2.py
```

To rebuild the temporary corpus and run the labeled Stage 3 retrieval evaluation:

```bash
python scripts/evaluate_retrieval.py
```

After configuring a key, run one isolated real-provider Stage 4 check with temporary storage:

```bash
python scripts/verify_stage4_live.py
```

The automated tests use an explicit deterministic fake provider so they remain fast and reproducible. Runtime never silently substitutes that fake for Gemini.

The complete local verification commands and their assurance boundaries are in the [testing report](docs/TESTING_REPORT.md).

For the Stage 5 conflict and edge-case checks:

```bash
python scripts/evaluate_policy_answers.py
python scripts/evaluate_policy_answers.py --live
```

The first command checks retrieved supporting text locally. `--live` additionally
calls Gemini with the sample policies and synthetic test history in temporary
storage; it prints actual answers for review and stops live requests on rate
limits or other provider outages. See [the conflict board](docs/POLICY_CONFLICT_BOARD.md) for source findings
and expected handling. Pattern checks are regression signals, not proof of answer
correctness.
