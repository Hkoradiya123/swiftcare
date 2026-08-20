# TODO — Patient Care Assistant Platform

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

---

## Setup & Infrastructure

- [ ] Initialise project structure and repo
- [ ] Dockerise the app (Dockerfile + docker-compose)
- [ ] Set up environment config (`.env`, secrets management)
- [ ] Configure S3 bucket and credentials
- [ ] Split into two services: **core** (data) and **notify** (notifications/documents)
- [ ] Define inter-service communication interface (REST or message queue)

---

## Database & Migrations

> **DB:** Supabase (PostgreSQL)

- [ ] Create Supabase project and grab connection string + anon/service keys
- [ ] Configure ORM / migration tool (e.g. Prisma or SQLAlchemy) against Supabase Postgres
- [ ] Schema: `patients`, `providers`, `users`
- [ ] Schema: `appointments` (with type field for in-person / telehealth)
- [ ] Schema: `prescriptions`
- [ ] Schema: `documents` (S3 links)
- [ ] Write initial migration
- [ ] Verify migration rollback works

---

## Auth & Roles

- [ ] User registration and login (JWT or session)
- [ ] Role model: `provider`, `patient`, `admin`
- [ ] Role-based access middleware
- [ ] Restrict prescription creation to providers only

---

## Core CRUD

- [ ] Patients — create, read, update, delete
- [ ] Providers — create, read, update, delete
- [ ] Appointments — create, read, update, delete
- [ ] Prescriptions — create, read, update, delete

---

## Appointment Logic

- [ ] In-person check-in / completion flow
- [ ] Telehealth check-in / completion flow
- [ ] Conflict detection (overlapping slots for same provider)
- [ ] Filter appointments by date, provider, status
- [ ] Paginate appointment list results

---

## Validation & Safety

- [ ] Input validation on all endpoints
- [ ] Rate limiting (especially prescription endpoints)
- [ ] Sanitise and reject malformed requests

---

## Notifications & Documents (notify service)

- [ ] Appointment reminder emails — scheduled job (cron)
- [ ] Generate visit-summary document (PDF or similar)
- [ ] Generate prescription document
- [ ] Email visit summary to patient as attachment
- [ ] Upload all generated documents to S3
- [ ] Return S3 link instead of file in API response

---

## Testing

- [ ] Test: appointment conflict detection
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

- [ ] API documentation (OpenAPI / Swagger)
- [ ] Seed script with sample/made-up patient data
- [ ] README with setup and run instructions
