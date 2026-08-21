from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "swiftcare_notify",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.reminders"],
)

celery.conf.beat_schedule = {
    "send-appointment-reminders": {
        "task": "app.tasks.reminders.send_reminders",
        "schedule": 300.0,  # every 5 minutes
    },
}
celery.conf.timezone = "UTC"
