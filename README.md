# SwiftCare

SwiftCare is an event-driven healthcare backend built with FastAPI, PostgreSQL, Redis Streams, and Celery. It manages patient records, provider schedules, appointment lifecycles, and prescriptions, while offloading document generation, automated reminders, and email delivery to a background relay worker. It also includes clinical AI tools for patient history Q&A (pgvector RAG) and autonomous appointment booking (LangGraph ReAct agent).

---

## Architecture Overview

The system is split into two independent services connected by Redis Streams and a shared event contract package:

```
                    ┌─────────────────────────┐
                    │       HTTP Clients      │
                    │  (Web, Mobile, CLIs)    │
                    └────────────┬────────────┘
                                 │
                                 ▼ :8000
                    ┌─────────────────────────┐
                    │      swiftcare-core     │
                    │  (FastAPI + PostgreSQL) │
                    └──────┬───────────┬──────┘
                           │           │
            Event Stream   │           │ pgvector
             (Redis)       ▼           ▼
      ┌─────────────────────────┐   ┌─────────────────────────┐
      │     swiftcare-notify    │   │      Clinical AI        │
      │  (Consumer + Celery)    │   │  (RAG + LangGraph Agent)│
      └──────┬───────────┬──────┘   └─────────────────────────┘
             │           │
             ▼           ▼
        S3 / MinIO     SMTP / MailHog
       (PDF Storage)  (Email Delivery)
```

### Services & Components

- **`swiftcare-core/`** (Port `8000`): Primary API handling authentication, role-based access control, appointment state transitions, prescription validation, and AI endpoints.
- **`swiftcare-notify/`**: Asynchronous worker consuming Redis Stream events to generate PDFs (prescriptions and visit summaries), store them in S3/MinIO, send transactional emails, and run recurring Celery Beat appointment reminders.
- **`swiftcare-contracts/`**: Shared Python library defining versioned Pydantic event payloads (`AppointmentCompletedEvent`, `PrescriptionCreatedEvent`, `AppointmentScheduledEvent`, `PasswordResetRequestedEvent`).
- **Interactive CLIs**: Terminal interfaces for patient booking (`patient_cli.py`) and clinical provider workflows (`provider_cli.py`).

---

## Tech Stack

| Domain | Technologies |
| :--- | :--- |
| **Core API** | Python 3.12, FastAPI, Pydantic v2, Starlette |
| **Databases** | PostgreSQL 16 (Async via `asyncpg`), SQLite (in-memory test suite) |
| **Vector Engine** | `pgvector` (HNSW index, 1536-dim embeddings) |
| **ORM & Migrations** | SQLAlchemy 2.0 (Async), Alembic |
| **Event Bus & Cache** | Redis 7 (Redis Streams, Pipelines, Fixed/Sliding Window counters) |
| **Task Queue** | Celery + Celery Beat (Redis broker) |
| **Object Storage** | AWS S3 / MinIO (via `boto3`) |
| **Document Engine** | `xhtml2pdf`, Jinja2 HTML templates |
| **AI / Agent** | LangGraph, LangChain, OpenAI (`gpt-4o-mini`, `text-embedding-ada-002`) |
| **Auth & Security** | JWT (access tokens), SHA-256 hashed refresh tokens, Argon2/Bcrypt |
| **Email** | `aiosmtplib`, MailHog (local SMTP trap) |
| **Testing** | `pytest`, `pytest-asyncio`, `httpx` (ASGITransport), `fakeredis` |

---

## Repository Structure

```
swiftcare/
├── swiftcare-core/               # Primary API service
│   ├── alembic/                  # Core database migrations
│   ├── app/
│   │   ├── ai/                   # RAG retriever, embedder, and LangGraph agent
│   │   ├── api/v1/               # HTTP route handlers (auth, patients, appointments, etc.)
│   │   ├── core/                 # Config, security, rate limit middleware, dependencies
│   │   ├── db/                   # Async session maker, base ORM classes
│   │   ├── events/               # Redis stream event publisher
│   │   ├── models/               # SQLAlchemy ORM models & state transitions
│   │   ├── repositories/         # Database access layer (queries only)
│   │   ├── schemas/              # Pydantic request/response validation
│   │   └── services/             # Core business logic & transactions
│   └── tests/                    # Async unit and integration test suite
│
├── swiftcare-notify/             # Background notification & document service
│   ├── alembic/                  # Relay database migrations
│   ├── app/
│   │   ├── celery_app.py         # Celery beat configuration
│   │   ├── consumers/            # Redis stream consumer loop & event handlers
│   │   ├── db/                   # Relay idempotency models (ProcessedEvent, DocumentRecord)
│   │   ├── documents/            # PDF rendering engine & Jinja2 templates
│   │   ├── mail/                 # Async SMTP email sender
│   │   ├── storage/              # S3 / MinIO client wrapper
│   │   └── tasks/                # Scheduled reminder tasks (24h and 2h alerts)
│   └── tests/                    # Consumer idempotency and worker tests
│
├── swiftcare-contracts/          # Shared Pydantic event schemas
├── docs/                         # Technical specifications and architectural references
├── docker-compose.dev.yml        # Dev: hot-reload, MailHog, MinIO (local mocks)
├── docker-compose.prod.yml       # Prod: real SMTP, real S3, secrets via env vars
├── main.py                       # Local multi-process runner (Core + Notify)
├── patient_cli.py                # Patient terminal client
├── provider_cli.py               # Provider terminal client
├── create_admin.py               # Admin account provisioner
├── create_provider.py            # Provider onboarding and schedule generator
└── test_email.py                 # SMTP verification script
```

---

## Core System Features

### 1. Layered Architecture inside Core
Every domain inside `swiftcare-core` enforces strict separation of concerns:
```
HTTP Request ──> api/v1/<domain>.py
                    │ (routes & params)
                    ▼
                 services/<domain>.py
                    │ (business rules & transactions)
                    ▼
                 repositories/<domain>.py
                    │ (database queries)
                    ▼
                 models/<domain>.py
                   (SQLAlchemy state models)
```

### 2. Authentication & Access Control (RBAC + OLAC)
- Three explicit roles: `patient`, `provider`, and `admin`.
- Role guards using FastAPI dependency injection (`require_role(...)`).
- Owner-Level Access Control (OLAC): Patients access only their own medical history; providers access only patients with whom they share scheduled appointments.
- SHA-256 hashed refresh tokens rotated on every renewal; automated password-reset flow backed by Redis and email tokens.

### 3. Dual-Layer Sliding Window Rate Limiting
Global protection via `DualLayerRateLimitMiddleware`:
- **Server-wide capacity ceiling:** Caps aggregate requests across the entire application (e.g. 5,000 req/60s).
- **Per-client sliding window:** Keyed by JWT user ID or client IP, preventing boundary bursts using a hybrid weighted calculation over Redis pipelines.
- Configurable per-path overrides for `/health` and OpenAPI documentation routes (`/docs`, `/redoc`).

### 4. Polymorphic Appointments & Pure State Transitions
- Single base table with polymorphic discriminators (`IN_PERSON` vs `TELEHEALTH`).
- Lifecycle transitions (`SCHEDULED` ➔ `CONFIRMED` ➔ `CHECKED_IN` ➔ `COMPLETED` or `CANCELLED`) executed via pure module-level state transition functions to allow deterministic unit testing without database locks.

### 5. Clinical AI Subsystems
- **History Q&A (RAG):** Cosine similarity vector search over patient visit records stored in `pgvector` (`Vector(1536)`), feeding context to `gpt-4o-mini` with exact citation back-links.
- **Autonomous Booking Agent:** LangGraph ReAct agent with tools to inspect doctor availability, find open slots, verify schedule conflicts, and draft appointment bookings.

### 6. Asynchronous Document & Email Pipeline
- When an appointment is marked completed, `swiftcare-core` commits the transaction and publishes `AppointmentCompletedEvent` to Redis Streams.
- `swiftcare-notify` reads the message with consumer group acknowledgment (`XREADGROUP` + `XACK`), renders a PDF with `xhtml2pdf`, uploads the file to S3/MinIO, and delivers the document via SMTP.
- Processed message IDs are recorded in an idempotency table (`processed_events`) to prevent duplicate email delivery.

---

## Quickstart

### Option A: Running with Docker Compose (Recommended)

Two compose files — pick one based on your environment:

#### Development (`docker-compose.dev.yml`)
Uses local mocks — MailHog for email, MinIO for S3, hot-reload enabled. No real credentials needed except OpenAI.

```bash
# Optional: set your OpenAI key in .env first
echo "OPENAI_API_KEY=sk-..." >> .env

docker compose -f docker-compose.dev.yml up --build
```

| Service | URL | Credentials |
| :--- | :--- | :--- |
| Core API & Swagger | http://localhost:8000/docs | — |
| MailHog (caught emails) | http://localhost:8025 | — |
| MinIO Console | http://localhost:9001 | `swiftcare` / `swiftcare123` |

#### Production (`docker-compose.prod.yml`)
Uses real SMTP, real AWS S3, and strong secrets — all supplied via environment variables. Create a `.env` file with the following before running:

```bash
# Database
CORE_DB_USER=core
CORE_DB_PASSWORD=<strong-password>
NOTIFY_DB_USER=notify
NOTIFY_DB_PASSWORD=<strong-password>

# Security
SECRET_KEY=<random-64-char-string>

# OpenAI
OPENAI_API_KEY=sk-...

# Email (real SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your-app-password
MAIL_FROM=noreply@yourdomain.com

# S3 (real AWS — leave S3_ENDPOINT empty for AWS)
S3_ENDPOINT=
S3_ACCESS_KEY=<aws-access-key>
S3_SECRET_KEY=<aws-secret-key>
S3_BUCKET=swiftcare-docs
```

```bash
docker compose -f docker-compose.prod.yml up --build
```

---

### Option B: Running Locally (Manual Setup)

#### 1. Setup Environment
Clone the repository and create a Python 3.12 virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

Install contracts and service dependencies:

```bash
pip install -e swiftcare-contracts
pip install -r swiftcare-core/requirements.txt
pip install -r swiftcare-notify/requirements.txt
```

#### 2. Configure Environment Variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Ensure your PostgreSQL databases, Redis instance, and SMTP servers are running locally or through Docker.

#### 3. Run Database Migrations

Apply migrations to both databases:

```bash
# Core database
cd swiftcare-core
alembic upgrade head
cd ..

# Relay database
cd swiftcare-notify
alembic upgrade head
cd ..
```

#### 4. Start Services

To launch both Core and Relay concurrently:

```bash
python main.py
```

To run individual services manually:

```bash
# Terminal 1: Core API
cd swiftcare-core
uvicorn app.main:app --reload --port 8000

# Terminal 2: Notification Stream Consumer
cd swiftcare-notify
python -m app.main

# Terminal 3: Celery Beat Reminders
cd swiftcare-notify
celery -A app.celery_app.celery beat --loglevel=info
```

---

## Provisioning & Seed Scripts

Run these helper scripts from the repository root:

1. **Create an Admin User:**
   ```bash
   python create_admin.py
   ```
2. **Onboard a Doctor & Default Shift Schedules:**
   ```bash
   python create_provider.py
   ```
3. **Verify SMTP Configuration:**
   ```bash
   python test_email.py
   ```

---

## Interactive CLIs

SwiftCare includes two complete terminal interfaces for testing and manual workflows:

- **Patient Portal CLI:**
  ```bash
  python patient_cli.py
  ```
  *Features: Registration, login, profile view, appointment booking with open slot discovery, medical history review, active prescriptions, and logged allergies.*

- **Provider Portal CLI:**
  ```bash
  python provider_cli.py
  ```
  *Features: Schedule and shift management (single & bulk availability), checking in appointments, completing visits, issuing prescriptions with dosage validation, and recording patient drug allergies.*

---

## Testing

Tests run against an in-memory SQLite database and isolated Redis mocks. No external services are required to run the test suites.

Run all tests in `swiftcare-core`:

```bash
cd swiftcare-core
pytest
```

Run specific test suites:

```bash
# Appointment conflict checks
pytest tests/test_appointment_conflict.py

# Prescription allergy cross-checks and dosage validation
pytest tests/test_prescription_validation.py

# Owner-level and role-based security boundaries
pytest tests/test_security_olac.py
```

Run notification and consumer idempotency tests:

```bash
cd swiftcare-notify
pytest
```

---

## Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/swiftcare_core` | Core database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis instance for streams, rate limiting, and celery broker |
| `SECRET_KEY` | `dev-secret-key-change-in-production-1234567890!` | JWT signing secret key |
| `ALGORITHM` | `HS256` | JWT cryptographic algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Lifespan of access tokens |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Lifespan of refresh tokens |
| `S3_ENDPOINT` | `http://localhost:9000` | S3 API endpoint (MinIO or AWS) |
| `S3_ACCESS_KEY` | `swiftcare` | S3 access key |
| `S3_SECRET_KEY` | `swiftcare123` | S3 secret key |
| `S3_BUCKET` | `swiftcare-docs` | S3 target bucket for generated PDFs |
| `SMTP_HOST` | `localhost` | Outgoing SMTP host (MailHog: `localhost` / port `1025`) |
| `SMTP_PORT` | `1025` | Outgoing SMTP port |
| `MAIL_FROM` | `noreply@swiftcare.io` | Sender email address |
| `MOCK_SMTP` | `false` | When `true`, logs emails to console instead of sending |
| `OPENAI_API_KEY` | `""` | OpenAI API key for embeddings and clinical assistant |
| `OPENAI_MODEL` | `gpt-4o-mini` | LLM model name for RAG and tool agent |

---

## License

This project is licensed under the MIT License. Sample patient data is used throughout for testing and development purposes.
