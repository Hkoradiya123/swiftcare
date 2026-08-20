import enum


class UserRole(str, enum.Enum):
    PATIENT = "patient"
    PROVIDER = "provider"
    ADMIN = "admin"


class AppointmentStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    CHECKED_IN = "checked_in"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentType(str, enum.Enum):
    IN_PERSON = "in_person"
    TELEHEALTH = "telehealth"
