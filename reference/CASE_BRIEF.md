# ADC Case: GenAI Engineer

## Transcription note

This is a faithful Markdown transcription of `project description/ADC_Case_-_GenAI_Engineer.pdf`, dated 10 March 2026. Wording, numbering, requirements, recommendations, examples, and deliverables are preserved. Line wrapping, bullet glyphs, indentation, and page breaks have been normalized for Markdown. The PDF has six readable, unencrypted pages. Raw and layout-preserving text extractions were compared against each other and the PDF during the initial pass; no unresolved wording uncertainty was found.

---

10 Mar 2026

ADC

Case: GenAI Engineer

# Interview Case: GenAI Engineer

## 1.1 Context

You have been engaged by "Apex Global," a major financial services firm with 10,000 employees. They currently have thousands of internal PDF policy documents scattered across SharePoint and local drives. Employees waste hours searching for answers to simple questions like "What is the travel reimbursement limit for Asia?"

The Goal: Apex Global wants to build an internal AI assistant including RAG (Retrieval Augmented Generation). You have been tasked with two deliverables:

1. The Prototype: A working "Walking Skeleton" API to prove the concept.
2. The Strategy: A production roadmap for scaling this to the entire organization.

You will be asked to present both deliverables during the interview.

## 1.2 Part 1: The Prototype

Develop a robust, minimal REST API using Python that demonstrates the core mechanics of RAG: Ingestion and Chat. A sample set of policy PDFs to be ingested is provided. The chat response must include a citation to the PDF answering the question, for example “The travel reimbursement limit for Asia is 200 USD. [1] (reimbursement_policy.pdf)”.

### 1.2.1 Minimal Functional Requirements

Your API must expose two endpoints:

1. POST /upload

   - Input: conversation_id, file (PDF).
   - Process:
     - Retrieves/creates a conversation_id.
     - Ingest and parse PDF text.
     - Split the text into logical chunks.
     - Generate vector embeddings for these chunks.
     - Index them in a vector store.
     - Persist metadata (filename, upload timestamp) in a database.
   - Output: Confirmation of successful indexing.

2. POST /chat

   - Input: conversation_id, message.
   - Process:
     - Retrieve the recent conversation history (last 5 messages).
     - Perform a semantic search to retrieve relevant chunks from the vector store.
     - Construct a context-aware prompt (System Prompt + History + Context + User Question).
     - Call an LLM to generate a response
     - Persist the interaction (User Query + AI Response) in the database.
   - Output: The assistant's JSON response.

### 1.2.2 Technical Recommendations

We recommend using the following components. However, you are free to choose your own preferred stack. The only requirement is to use Python.

- Framework: FastAPI (highly recommended) or Flask.
- Database: SQLite/Postgres for relational data; FAISS or ChromaDB for vectors.
- Model: For model calls to an embedding and chat model, you may stub this call or use a real (free) API like Mistral AI API on Experimental tier https://docs.mistral.ai/getting-started/quickstart. Other options may be found here https://github.com/cheahjs/free-llm-api-resources.

Note: you may add additional components & functionality to demonstrate your skills / level of expertise.

### 1.2.3 Deliverables for Part 1

- A link to a private GitHub repository or a zipped folder, including
  - Source code
  - Readme.md containing:
    - Instructions to run the application locally
    - "Design Decisions": A short section explaining your key design decisions and trade-offs. You will be asked to present these.
- You will be asked questions on your approach during the presentation so prepare 1-2 slides on what you did.

## 1.3 Part 2: The Strategy

Objective: The CIO has approved the project for a global rollout. You must design the ecosystem that turns your prototype into an enterprise platform. You may assume live document upload is not required in the Enterprise solution. Integration with internal document storing systems is expected.

Deliverable: A presentation covering the following three pillars, which is suitable to present to the client’s business stakeholders.

### 1.3.1 1. Enterprise Architecture

- Task: Draw a high-level system architecture diagram. What are the components of the architecture and how do they communicate?
- Requirements:
  - How will you decouple document ingestion (slow) from chat (fast)?
  - How will you handle latency and caching?
  - You are encouraged to demonstrate your cloud knowledge by deciding which cloud-native components (AWS/Azure/GCP) you would select for this.

### 1.3.2 2. LLMOps & CI/CD Pipeline

- Task: Define a deployment and evaluation strategy.
- Requirements:
  - How do you mitigate poor data quality (i.e. contradicting statements across documents)?
  - How do you prevent regressions? (e.g., If the prompt is changed, how do you know the bot didn't get ‘dumber’?)
  - Describe an automated evaluation pipeline
  - How do you manage versioning for Code vs. Prompts vs. Data?
  - Once the bot is live, how do you capture user feedback and turn it into improved performance?

### 1.3.3 3. Trust & Governance

The client is risk averse. They fear "hallucinations" (the bot inventing facts).

- Task: Propose a monitoring and guardrail framework.
- Requirements:
  - Technically, how will you detect or prevent the model from answering questions outside of the provided context?
  - How will you monitor "Data Drift" or "Concept Drift" in user queries over time?
  - Apex Global employees are used to 'keyword search.' How will you onboard 10,000 people to 'semantic chat'? What does your user-training program look like?

## 1.4 Evaluation Criteria

We are not looking for a perfect, feature-complete product. We are evaluating:

1. Engineering: Is the code clean, readable, and structured for extensibility? Are best practices implemented?
2. GenAI Depth: Do you understand the nuances of chunking strategies, embedding limitations, and context windows?
3. Consulting Aptitude: Can you translate technical choices into business value? Is your architecture pragmatic and scalable?
4. Communication: Is your documentation clear, concise, and professional?

Good luck! We look forward to seeing your solution.

Copyright 2026, ADC

Contact: Recruitment Team
recruitment@adc-consulting.com

Amsterdam
De Ruijterkade 7
1013AA Amsterdam, NL

Copenhagen
Overgaden Oven Vandet 58A
1415 Copenhagen, DK

Stockholm
Götgatan 22A
118 46 Stockholm, SE

CLEVER°FRANKE
Catharijnekade 11
3511 RT Utrecht, NL
