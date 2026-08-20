# TODO — Patient Care Assistant Platform

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Setup & Infrastructure

- [x] Initialise project structure and repo
- [ ] Dockerise the app (Dockerfile + docker-compose)
- [x] Set up environment config (`.env`, secrets management)
- [ ] Configure S3 bucket and credentials
- [x] Split into two services: **core** (data) and **notify** (notifications/documents)
- [x] Define inter-service communication interface (Redis Streams)
- [x] Root `main.py` to start all services with one command

---

## Database & Migrations

> **DB:** Supabase (PostgreSQL)

- [x] Create Supabase project and grab connection string
- [x] Configure Alembic + SQLAlchemy against Supabase Postgres
- [x] Schema: `users`, `patients`, `providers`, `provider_availabilities`
- [x] Schema: `refresh_tokens`
- [x] Schema: `appointments` (with type field for in-person / telehealth)
- [x] Schema: `notify.reminder_logs`, `notify.task_logs` (relay schema)
- [ ] Schema: `prescriptions`, `prescription_items`
- [ ] Schema: `visit_summaries`
- [ ] Schema: `allergies`
- [ ] Schema: `visit_embeddings` (pgvector)
- [x] Initial migration applied to Supabase
- [ ] Verify migration rollback works

---

## Auth & Roles

- [x] User registration and login (JWT)
- [x] Refresh token — stored as SHA-256 hash, rotated on use
- [x] `/auth/refresh` and `/auth/logout` endpoints
- [x] Role model: `provider`, `patient`, `admin`
- [x] Role-based access middleware (`require_role`)
- [ ] Restrict prescription creation to providers only

---

## Core CRUD

- [x] Patients — create, read, update, delete
- [x] Providers — create, read, update, delete
- [x] Appointments — create, read, update, delete
- [ ] Prescriptions — create, read, update, delete

---

## Appointment Logic

- [x] In-person check-in / completion flow
- [x] Telehealth check-in → in_progress flow
- [x] Conflict detection — app-level overlap check
- [x] Conflict detection — DB-level `gist` exclusion constraint
- [x] Filter appointments by date, provider, status
- [x] Paginate appointment list results
- [x] Redis Stream event publish on appointment completion

---

## Validation & Safety

- [ ] Input validation on all endpoints
- [ ] Rate limiting (especially prescription endpoints)
- [ ] Sanitise and reject malformed requests

---

## Notifications & Documents (notify service)

- [ ] Appointment reminder emails — scheduled job (Celery Beat)
- [ ] Generate visit-summary document (WeasyPrint PDF)
- [ ] Generate prescription document
- [ ] Email visit summary to patient as attachment
- [ ] Upload all generated documents to S3
- [ ] Return S3 link instead of file in API response
- [ ] Redis Stream consumer in swiftcare-notify

---

## Testing

- [x] Test: appointment conflict detection (14 tests passing)
- [x] Test: state machine transitions (check-in, complete, cancel)
- [ ] Test: prescription validation rules
- [ ] Test: role-based access (provider-only actions)
- [ ] Test: reminder scheduler triggers correctly
- [ ] Test: document upload returns S3 link

---

## AI Features

- [ ] Q&A endpoint — accept natural-language question about a patient
- [ ] Retrieve relevant sample visit records for context
- [ ] Return answer with source record references
- [ ] Smart assistant — accept symptom/task description
- [ ] Check provider availability autonomously
- [ ] Suggest earliest matching appointment slot
- [ ] Draft confirmation message
- [ ] Wire assistant steps into a single agentic flow

---

## Polish

- [x] API documentation (OpenAPI / Swagger via FastAPI)
- [ ] Seed script with sample/made-up patient data
- [ ] README with setup and run instructions
