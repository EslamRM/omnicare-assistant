# OmniCare GenAI Customer Assistant

A submission-ready prototype for the OmniCare Financial GenAI Engineer
assessment.

OmniCare is a customer-facing insurance assistant that can:

-   Answer policy coverage questions using Retrieval-Augmented
    Generation (RAG) with source citations.
-   Look up claim status through a validated backend tool.
-   Prepare and submit new claims through a two-step confirmation
    workflow.
-   Enforce policy ownership and claim authorization server-side.
-   Reject prompt-injection and tool-abuse attempts deterministically.
-   Run locally with Docker using FastAPI, LangGraph, Chroma, and
    Streamlit.

## Architecture

``` text
[ Streamlit UI ]
       |
       v
[ FastAPI: auth / chat / health ]
       |
       v
[ AssistantService / LangGraph DAG ]
       |
       +--> deterministic router
       |
       +--> injection refusal
       +--> claim status -> get_claim_status
       +--> claim submission -> LLM extraction -> Pydantic -> authorization
       |                       -> confirmation -> submit_claim -> JSON
       +--> policy question -> TF-IDF retrieval -> grounded LLM synthesis
                                      |
                                      v
                              sample_policy.md
```

The LangGraph workflow is intentionally a flat DAG with no cycles:

``` text
route -> exactly one action -> END
```

This provides predictable termination, straightforward testing, and a
maximum of one LLM call per user turn.

## Main Components

  -----------------------------------------------------------------------
  Component                           Purpose
  ----------------------------------- -----------------------------------
  Streamlit                           Customer chat UI, history,
                                      citations, authentication,
                                      confirmation

  FastAPI                             HTTP API, authentication, request
                                      handling

  LangGraph                           Deterministic assistant
                                      orchestration

  Chroma                              Local vector-store interface

  scikit-learn TF-IDF                 Network-free policy representation

  Groq                                Free-tier LLM inference

  Ollama                              Optional local LLM provider

  Pydantic                            Input and tool validation

  JSON                                Assessment-specified claim storage
  -----------------------------------------------------------------------

## Core Flows

### Policy questions

1.  Route the request deterministically.
2.  Retrieve relevant sections from `sample_policy.md`.
3.  If relevant content exists, synthesize an answer from that content.
4.  Attach the retrieved section as a deterministic citation.
5.  If the policy does not contain enough information, do not guess.

### Claim status

1.  Identify and validate the claim ID.
2.  Verify authenticated user identity.
3.  Verify policy ownership.
4.  Execute `get_claim_status`.
5.  Return the authorized customer-facing result.

### Claim submission

``` text
User request
 -> LLM structured extraction
 -> Pydantic validation
 -> policy ownership authorization
 -> pending draft + short-lived confirmation token
 -> explicit confirmation
 -> authorization re-check
 -> submit_claim
 -> atomic JSON write
 -> confirmation ID
```

The LLM never has direct write access to the claim store.

## Security Model

Defense in depth is used rather than relying on a single filter.

1.  Deterministic prompt-injection and tool-abuse patterns are rejected
    before an LLM or business tool is called.
2.  Retrieved RAG content is explicitly treated as untrusted data, not
    instructions.
3.  Pydantic validates every tool argument independently of the router.
4.  Claim types use a closed enumeration; IDs use format validation;
    amounts are bounded.
5.  The LLM only proposes structured arguments. Backend tools perform
    the actual operations.
6.  Policy ownership is checked server-side.
7.  Claim submission requires explicit customer confirmation.
8.  Unexpected server errors are converted to client-safe responses
    without stack traces or infrastructure details.

## Demo Authentication

The prototype includes lightweight assessment/demo authentication.

  User ID       Demo PIN Authorized policy
  ----------- ---------- -------------------
  `usr_123`       `1234` `POL-1092`
  `usr_456`       `4567` `POL-3341`

The UI receives a short-lived signed session token and sends it as a
Bearer token. The backend verifies the token, checks that its identity
matches the request `user_id`, and then applies policy ownership rules.

This is intentionally assessment/demo authentication, not production
identity management. Production should use OIDC/OAuth and durable
authorization data.

## Setup

### Docker

``` bash
git clone <this-repository>
cd omnicare-assistant
cp .env.example .env
```

Set:

``` text
GROQ_API_KEY=<your-free-groq-api-key>
AUTH_SECRET=<long-random-secret>
```

Then:

``` bash
docker compose up --build
```

Open the Streamlit UI at:

``` text
http://localhost:8501
```

API documentation:

``` text
http://localhost:8000/docs
```

Health endpoint:

``` text
http://localhost:8000/api/v1/health
```

### Without Docker

``` bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

In another terminal:

``` bash
cd frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
BACKEND_URL=http://localhost:8000 streamlit run app.py
```

## Environment Variables

  ----------------------------------------------------------------------------------
  Variable            Required          Default                    Description
  ------------------- ----------------- -------------------------- -----------------
  `GROQ_API_KEY`      Yes for Groq      ---                        Groq API key

  `LLM_PROVIDER`      No                `groq`                     `groq` or
                                                                   `ollama`

  `LLM_MODEL`         No                `openai/gpt-oss-20b`       Selected model

  `OLLAMA_BASE_URL`   No                `http://localhost:11434`   Ollama endpoint

  `AUTH_SECRET`       Recommended       development default        Session-token
                                                                   signing secret

  `LOG_LEVEL`         No                `INFO`                     Logging level
  ----------------------------------------------------------------------------------

Never commit `.env` or API keys.

## API Examples

### Health

``` bash
curl http://localhost:8000/api/v1/health
```

### Login

``` bash
curl -X POST http://localhost:8000/api/v1/auth/login   -H "Content-Type: application/json"   -d '{"user_id":"usr_123","pin":"1234"}'
```

Copy the returned `access_token`.

### Policy question

``` bash
curl -X POST http://localhost:8000/api/v1/chat   -H "Authorization: Bearer <access_token>"   -H "Content-Type: application/json"   -d '{"user_id":"usr_123","message":"Is water damage covered?"}'
```

Expected: grounded answer with a policy citation and no tool call.

### Claim status

``` bash
curl -X POST http://localhost:8000/api/v1/chat   -H "Authorization: Bearer <access_token>"   -H "Content-Type: application/json"   -d '{"user_id":"usr_123","message":"What is the status of claim CLM-8821?"}'
```

### Claim submission draft

``` bash
curl -X POST http://localhost:8000/api/v1/chat   -H "Authorization: Bearer <access_token>"   -H "Content-Type: application/json"   -d '{"user_id":"usr_123","message":"I want to submit a water damage claim for policy POL-1092 for $3,500 because a pipe leaked and damaged my kitchen."}'
```

The first request creates a pending draft. It does not write the claim.

Confirm with the returned token:

``` bash
curl -X POST http://localhost:8000/api/v1/chat   -H "Authorization: Bearer <access_token>"   -H "Content-Type: application/json"   -d '{"user_id":"usr_123","message":"confirm <confirmation-token>"}'
```

## API Contract

### `GET /api/v1/health`

Returns service health.

### `POST /api/v1/auth/login`

Request:

``` json
{"user_id":"usr_123","pin":"1234"}
```

Returns a short-lived signed Bearer token and authorized policy list.

### `POST /api/v1/chat`

Request:

``` json
{"user_id":"usr_123","message":"Is water damage covered?"}
```

Response:

``` json
{
  "response": "...",
  "sources": [],
  "tool_calls": []
}
```

`tool_calls` is API-level trace information for evaluation/debugging.
The Streamlit UI does not expose internal tool arguments to the
customer.

## Why This Architecture?

### LangGraph instead of an autonomous agent loop

The assessment use cases map to controlled actions rather than
open-ended planning. A flat DAG provides orchestration and
agent-workflow structure while guaranteeing termination and avoiding
runaway tool/LLM loops.

### Deterministic routing

Claim IDs and explicit submission language can be detected without an
LLM. This reduces latency, cost, and unnecessary model calls.

### Chroma + TF-IDF

Chroma provides the local vector-store abstraction. TF-IDF avoids
downloading an embedding model and is deterministic and sufficient for
the small assessment policy corpus. A production implementation could
swap in a semantic embedding model behind the same retriever interface.

### Groq

Groq provides fast free-tier inference with minimal setup. The LLM
integration is isolated so the provider can be switched to Ollama.

### JSON storage

The assessment specifies `mock_claims.json`. Atomic writes and an
in-process lock are appropriate for this small prototype. Production
should use transactional database storage.

### Streamlit

Streamlit is recommended by the assessment and lets implementation
effort focus on backend, RAG, tools, validation, authorization, and
safety.

## Token Efficiency

  Intent                          LLM calls
  ----------------------------- -----------
  Prompt injection                        0
  Claim status                            0
  Unsupported policy question             0
  Grounded policy question                1
  Claim submission extraction             1

Maximum: **one LLM call per user turn**.

## Testing

Run from the repository root:

``` bash
docker compose exec backend pytest -q
```

Compilation check:

``` bash
docker compose exec backend python -m compileall -q app tests
```

The suite covers health, tools, validation, persistence, idempotency,
RAG retrieval, citation provenance, chat scenarios, prompt injection,
authorization, confirmation, graph structure, and error leakage.

The final README should not hard-code a pytest pass count. Record the
actual result from the final Docker build in `WALKTHROUGH.md`.

## Demo Scenarios

  --------------------------------------------------------------------------------------
                            \# Input / action                      Expected result
  ---------------------------- ----------------------------------- ---------------------
                             1 `Is water damage covered?`          Grounded answer +
                                                                   Section 1 citation

                             2 `Are gradual leaks covered?`        Exclusion answer +
                                                                   citation

                             3 `What is the status of CLM-8821?`   Authorized status

                             4 Submit water-damage claim for       Validated draft +
                               `POL-1092`                          confirmation token

                             5 Confirm the draft                   Claim written +
                                                                   confirmation ID

                             6 Prompt injection                    Safe refusal, no tool
                                                                   call

                             7 Unsupported question                No hallucinated
                                                                   policy answer

                             8 Cross-user policy attempt           Authorization
                                                                   rejection
  --------------------------------------------------------------------------------------

## Walkthrough and Screenshots

See [`WALKTHROUGH.md`](WALKTHROUGH.md) for the end-to-end reviewer
walkthrough.

Recommended screenshots:

1.  Authenticated session showing the authorized policy.
2.  RAG answer showing the Sources section.
3.  Claim-status response.
4.  Claim submission draft and confirmation action.
5.  Successful submission with confirmation ID.
6.  Prompt-injection refusal.
7.  Cross-user authorization rejection.

Screenshots should be captured from the final running Docker stack.

## Project Structure

``` text
omnicare-assistant/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── data/
│   ├── mock_claims.json
│   └── sample_policy.md
├── screenshots/
├── .env.example
├── docker-compose.yml
├── README.md
└── WALKTHROUGH.md
```

## Prototype Limitations

-   Claims use `mock_claims.json`; this is not a multi-replica
    transactional store.
-   Idempotency uses content-based duplicate detection; production
    should use a client-supplied idempotency key and database
    constraint.
-   Demo authentication should be replaced by OIDC/OAuth in production.
-   The small policy index is rebuilt at process startup.
-   TF-IDF is appropriate for this tiny corpus but not a large/diverse
    policy library.
-   Chat requests are independent; there is no unbounded conversation
    history.
-   The current JSON lock is process-local.

## Production Evolution

``` text
Load Balancer
     |
FastAPI replicas
     |
AssistantService
   /          RAG      Tools
   |          |
Vector DB  PostgreSQL
   |
Real embeddings

Redis: rate limiting / cache
OIDC/OAuth: authentication
OpenTelemetry: tracing
```

Production upgrades would include PostgreSQL transactions, durable
idempotency keys, persisted vector storage, semantic embeddings,
OIDC/OAuth, durable policy entitlements, Redis rate limiting/caching,
observability, and horizontal scaling.

## Assessment Alignment

  Requirement            Implementation
  ---------------------- ------------------------------------------------
  Full-stack prototype   FastAPI + LangGraph + Streamlit
  Policy RAG             `sample_policy.md` + Chroma + TF-IDF
  Citations              Deterministic source metadata
  Claim status           `get_claim_status`
  Claim submission       `submit_claim`
  Validation             Pydantic
  Safety                 Deterministic injection filter + RAG isolation
  Authorization          Signed session + server-side policy ownership
  Confirmation           Pending draft + explicit confirmation
  Chat UI                Streamlit history + citations
  API                    `/health`, `/auth/login`, `/chat`
  Docker                 Dockerfiles + Compose
  Testing                Pytest
  Documentation          README + walkthrough

## Submission Checklist

``` text
[ ] docker compose up --build succeeds
[ ] Streamlit UI loads
[ ] /api/v1/health returns healthy
[ ] Demo login works
[ ] usr_123 shows POL-1092
[ ] usr_456 shows POL-3341
[ ] Policy RAG answer includes correct source
[ ] Gradual-leak exclusion works
[ ] Authorized claim status works
[ ] Unauthorized claim access is rejected
[ ] Incomplete claim request is validated
[ ] Complete claim creates a pending draft
[ ] Confirmation submits the claim
[ ] Confirmation ID is returned
[ ] New claim is persisted
[ ] Prompt injection is refused
[ ] Unsupported questions do not hallucinate
[ ] Final pytest result is recorded
[ ] compileall succeeds
[ ] Final screenshots are captured
[ ] WALKTHROUGH.md is updated
[ ] No API keys or .env files are committed
```

**Assessment demo:** `usr_123` / `1234` → `POL-1092`.

The demo authentication is intentionally designed for reproducible
assessment evaluation and is not production identity management.
