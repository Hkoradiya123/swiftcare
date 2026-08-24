# Folder Structure

### Har folder ka kaam ek line mein

| Folder/File | Kya karta hai |
| :--- | :--- |
| `swiftcare-contracts/events.py` | Dono services ke beech event schemas — ek jagah change karo, dono update |
| `swiftcare-core/app/core/` | Config, JWT, RBAC dependency, rate limiter — framework-independent |
| `swiftcare-core/app/db/` | Engine, session, Base, mixins — poora DB setup |
| `swiftcare-core/app/models/` | SQLAlchemy tables + domain behaviour (check_in, complete) |
| `swiftcare-core/app/schemas/` | Pydantic — Create/Update/Read teen alag classes |
| `swiftcare-core/app/repositories/` | Sirf queries — `if` bilkul nahi |
| `swiftcare-core/app/services/` | Business rules — `db.execute()` bilkul nahi |
| `swiftcare-core/app/api/v1/` | HTTP routers — dono nahi |
| `swiftcare-core/app/events/` | Redis `xadd` — sirf publish, subscribe nahi |
| `swiftcare-core/app/ai/` | RAG retriever + agent tool loop |
| `swiftcare-core/tests/` | Conflict + prescription + auth tests |
| `swiftcare-relay/app/consumers/` | Redis `xreadgroup` — events sunna |
| `swiftcare-relay/app/tasks/` | Celery Beat reminders |
| `swiftcare-relay/app/documents/` | Jinja2 HTML → WeasyPrint PDF |
| `swiftcare-relay/app/storage/` | S3 upload + pre-signed URL |
| `swiftcare-relay/app/mail/` | SMTP email + attachment |
| `swiftcare-relay/app/db/` | Relay ka apna DB — core se bilkul alag |
