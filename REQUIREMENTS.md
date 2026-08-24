# Patient Care Assistant Platform — Requirements

> **Data policy:** Use only made-up/sample patient data at every stage. No real patient information.

## Overview

A system for managing patients, providers, appointments, and prescriptions, with automated reminders, document generation, and a smart AI assistant.

---

## Requirements

### Data & Storage

1. Maintain records for patients, providers, appointments, and prescriptions — including their details and status.
2. Store all data in **Supabase (PostgreSQL)** with proper relationships (e.g. a provider has many appointments; a patient can see many providers).
3. Support schema migrations — update the data structure later without losing existing data (e.g. adding an `allergies` record type).
4. Any generated document (visit summary, prescription, lab report) must be uploaded to S3; return/share a link, not the file itself.

### Appointments

5. Support multiple appointment types (in-person, telehealth) with type-specific check-in and completion behaviour.
6. Allow searching and filtering appointments by date, provider, or status.
7. Paginate all list results.

### CRUD

8. Provide create, view, update, and delete operations for patients, providers, appointments, and prescriptions.

### Auth & Access Control

9. Require users to log in. Support three roles: **provider**, **patient**, **admin** — each with different access.
10. Restrict prescription creation to providers only.

### Validation & Safety

11. Validate all user input. Rate-limit and protect endpoints against abuse, especially around prescriptions.

### Testing

12. Include tests covering core logic — appointment conflict detection and prescription validation at minimum.

### Notifications & Documents

13. Automatically send appointment reminder emails to patients on a recurring schedule before their visit.
14. Generate a visit-summary document after an appointment is completed.
15. Generate a prescription document.
16. Email the visit summary to the patient as an attachment.

### Infrastructure

17. Package the system to run consistently on any machine (containerised).
18. Split the system into two independent services: one for appointment/patient data, one for notifications/documents — communicating via a defined interface.

### AI Features

19. **Q&A:** A provider can ask a natural-language question about a patient's history (e.g. "summarise this patient's last 3 visits") and receive an answer grounded in actual sample visit records, with source references.
20. **Smart assistant:** Given a high-level task (e.g. a symptom description), the assistant autonomously checks provider availability, suggests the earliest matching slot, and drafts a confirmation message — without step-by-step instructions.
