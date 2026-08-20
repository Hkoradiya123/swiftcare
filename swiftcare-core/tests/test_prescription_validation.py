import pytest
from decimal import Decimal
from pydantic import ValidationError

from app.schemas.prescription import PrescriptionCreate, PrescriptionItemCreate


def item(**kwargs):
    defaults = dict(drug_name="Amoxicillin", dosage_amount=Decimal("500"), dosage_unit="mg", frequency_per_day=3, duration_days=7)
    return PrescriptionItemCreate(**{**defaults, **kwargs})


_SENTINEL = object()


def rx(items=_SENTINEL, **kwargs):
    resolved = [item()] if items is _SENTINEL else items
    defaults = dict(appointment_id=1, patient_id=1, items=resolved)
    return PrescriptionCreate(**{**defaults, **kwargs})


def test_valid_prescription():
    r = rx()
    assert len(r.items) == 1


def test_empty_items_rejected():
    with pytest.raises(ValidationError):
        rx(items=[])


def test_too_many_items_rejected():
    with pytest.raises(ValidationError):
        rx(items=[item(drug_name=f"Drug{i}") for i in range(11)])


def test_max_items_allowed():
    r = rx(items=[item(drug_name=f"Drug{i}") for i in range(10)])
    assert len(r.items) == 10


def test_zero_dosage_rejected():
    with pytest.raises(ValidationError):
        item(dosage_amount=Decimal("0"))


def test_negative_dosage_rejected():
    with pytest.raises(ValidationError):
        item(dosage_amount=Decimal("-1"))


def test_zero_frequency_rejected():
    with pytest.raises(ValidationError):
        item(frequency_per_day=0)


def test_zero_duration_rejected():
    with pytest.raises(ValidationError):
        item(duration_days=0)


def test_negative_duration_rejected():
    with pytest.raises(ValidationError):
        item(duration_days=-5)


def test_optional_instructions_none():
    i = item()
    assert i.instructions is None


def test_optional_notes_none():
    r = rx()
    assert r.notes is None
