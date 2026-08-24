# Prescriptions & Rate Limiting

Prescription management requires strict validation and security controls to prevent medical errors and prescription abuse. Prahar Care implements business-level validation rules and Redis-based rate limiting to enforce these controls.

---

## Prescription Creation Rules

A prescription can only be created if it meets the following business rules:

1. **Completed Appointment**: A prescription must be linked to an appointment that has a status of `COMPLETED`. Prescriptions cannot be written for scheduled, cancelled, or in-progress appointments.
2. **Matching Provider**: The provider writing the prescription must be the same provider who conducted the appointment.
3. **Active Patient**: The patient receiving the prescription must match the patient on the appointment record.

### Implementation in Service Layer

```python
# app/services/prescription.py
async def create_prescription(self, provider_id: int, data: PrescriptionCreate) -> Prescription:
    # 1. Fetch the appointment
    appointment = await self.appointment_repo.get_by_id(data.appointment_id)
    if not appointment:
        raise NotFoundError("Appointment not found")
        
    # 2. Validate appointment status
    if appointment.status != AppointmentStatus.COMPLETED.value:
        raise DomainError("Prescriptions can only be written for completed appointments")
        
    # 3. Validate provider matching
    if appointment.provider_id != provider_id:
        raise PermissionDeniedError("You can only write prescriptions for your own appointments")
        
    # 4. Validate patient matching
    if appointment.patient_id != data.patient_id:
        raise DomainError("Patient ID does not match the appointment record")
        
    # 5. Run clinical safety checks (e.g., allergies)
    await self.check_patient_allergies(data.patient_id, data.items)
    
    # 6. Create prescription
    return await self.prescription_repo.create(data)
```

---

## Clinical Safety Checks (Allergies)

Before a prescription is saved, the system checks the patient's active allergies against the ingredients of the prescribed items. If a conflict is detected, the system raises a validation error.

```python
async def check_patient_allergies(self, patient_id: int, items: list[PrescriptionItemCreate]) -> None:
    patient_allergies = await self.allergy_repo.get_active_by_patient(patient_id)
    allergy_names = {allergy.allergen.lower() for allergy in patient_allergies}
    
    for item in items:
        if item.drug_name.lower() in allergy_names:
            raise AllergyConflictError(
                f"Patient is allergic to {item.drug_name}. Prescription blocked."
            )
```

---

## Redis-Based Rate Limiting (Abuse Prevention)

To prevent prescription abuse (e.g., a compromised provider account writing hundreds of prescriptions in a short period), the system enforces a rate limit of **20 prescriptions per provider per hour**.

### Why Redis?
* **Distributed State**: If the API is scaled horizontally across multiple containers/servers, an in-memory dictionary would allow 20 prescriptions *per container*. Redis provides a single, shared state.
* **Atomic Operations**: We use Redis's atomic `INCR` and `EXPIRE` commands to prevent race conditions (check-then-set bugs).

### Implementation

We implement this as a reusable FastAPI dependency:

```python
# app/core/rate_limit.py
import redis.asyncio as redis
from fastapi import Depends, HTTPException, status

async def get_redis():
    # Injected via dependency
    yield redis.from_url("redis://redis:6379/0")

def rate_limit(key_prefix: str, limit: int, window_seconds: int):
    async def dependency(
        provider_id: int = Depends(get_current_provider_id),
        redis_client: redis.Redis = Depends(get_redis)
    ):
        key = f"rate_limit:{key_prefix}:{provider_id}"
        
        # Increment the counter
        current_count = await redis_client.incr(key)
        
        # If it's a new key, set the expiration window
        if current_count == 1:
            await redis_client.expire(key, window_seconds)
            
        # Check if limit is exceeded
        if current_count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Prescription rate limit exceeded. Please try again later."
            )
    return dependency
```

### Usage in Router
```python
@router.post(
    "/prescriptions",
    dependencies=[
        Depends(require_role(UserRole.PROVIDER)),
        Depends(rate_limit(key_prefix="prescription", limit=20, window_seconds=3600))
    ]
)
async def create_prescription(data: PrescriptionCreate):
    ...
```

---

## Testing Strategy

We use `pytest` and `pytest-mock` to test prescription validation and rate limiting:

1. **Validation Tests**:
   * Verify prescription creation succeeds for completed appointments.
   * Verify prescription creation fails for scheduled/in-progress appointments.
   * Verify prescription creation fails if the provider ID does not match the appointment.
   * Verify prescription creation fails if the patient has an active allergy to the prescribed drug.
2. **Rate Limiting Tests**:
   * Mock the Redis client.
   * Simulate 20 successful prescription requests.
   * Verify that the 21st request throws a `429 Too Many Requests` exception.
   * Verify that the Redis key expires after 1 hour.
