#!/usr/bin/env python3
"""
SwiftCare Provider CLI
All provider-facing API operations from the command line.
Note: provider accounts are created by an admin — use Login, not Register.
"""

import json
import sys
import requests

BASE_URL = "http://localhost:8000/api/v1"
_token = None
_provider_id = None  # resolved from /me after login

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ── helpers ──────────────────────────────────────────────────────────────────

def _headers():
    return {"Authorization": f"Bearer {_token}"} if _token else {}


def _print(data):
    print(json.dumps(data, indent=2, default=str))


def _post(path, data=None, auth=True):
    r = requests.post(f"{BASE_URL}{path}", json=data, headers=_headers() if auth else {})
    if r.status_code in (200, 201, 204):
        return r.json() if r.content else {}
    print(f"  Error {r.status_code}: {r.text}")
    return None


def _get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", params=params, headers=_headers())
    if r.status_code == 200:
        return r.json()
    print(f"  Error {r.status_code}: {r.text}")
    return None


def _patch(path, data):
    r = requests.patch(f"{BASE_URL}{path}", json=data, headers=_headers())
    if r.status_code == 200:
        return r.json()
    print(f"  Error {r.status_code}: {r.text}")
    return None


def _delete(path):
    r = requests.delete(f"{BASE_URL}{path}", headers=_headers())
    if r.status_code in (200, 204):
        return True
    print(f"  Error {r.status_code}: {r.text}")
    return False


def _input(prompt, default=None):
    val = input(f"  {prompt}{f' [{default}]' if default else ''}: ").strip()
    return val if val else default


def _required(prompt):
    while True:
        val = input(f"  {prompt}: ").strip()
        if val:
            return val
        print("  This field is required.")


# ── auth ─────────────────────────────────────────────────────────────────────

def login():
    print("\n── Login ──")
    data = {"email": _required("Email"), "password": _required("Password")}
    res = _post("/auth/login", data, auth=False)
    if res:
        _set_token(res)
        print("  Logged in.")


def logout():
    _post("/auth/logout")
    global _token, _provider_id
    _token = None
    _provider_id = None
    print("  Logged out.")


def me():
    res = _get("/auth/me")
    if res:
        _print(res)


def change_password():
    print("\n── Change Password ──")
    data = {
        "current_password": _required("Current password"),
        "new_password": _required("New password"),
    }
    res = _post("/auth/change-password", data)
    if res is not None:
        print("  Password changed.")


def forgot_password():
    print("\n── Forgot Password ──")
    email = _required("Email")
    res = _post("/auth/forgot-password", {"email": email}, auth=False)
    if res is not None:
        print("  Reset email sent (check your inbox).")


def reset_password():
    print("\n── Reset Password ──")
    data = {
        "token": _required("Reset token (from email)"),
        "new_password": _required("New password"),
    }
    res = _post("/auth/reset-password", data, auth=False)
    if res is not None:
        print("  Password reset successfully. Please login again.")


def _set_token(res):
    global _token, _provider_id
    _token = res.get("access_token")
    me_res = _get("/auth/me")
    if me_res:
        _provider_id = me_res.get("profile_id")
        if me_res.get("role") != "provider":
            print(f"  Warning: logged in as role={me_res.get('role')}, not provider.")


# ── provider profile ──────────────────────────────────────────────────────────

def get_profile():
    print("\n── My Provider Profile ──")
    res = _get("/providers/me")
    if res:
        _print(res)


def update_profile():
    print("\n── Update Profile ──")
    print("  Leave blank to keep current value.")
    data = {}
    spec = _input("Specialization")
    fee = _input("Consultation fee")
    slot = _input("Default slot minutes")
    bio = _input("Bio")
    if spec:
        data["specialization"] = spec
    if fee:
        data["consultation_fee"] = fee
    if slot:
        data["default_slot_minutes"] = int(slot)
    if bio:
        data["bio"] = bio
    if not data:
        print("  Nothing to update.")
        return
    res = _patch("/providers/me", data)
    if res:
        print("  Profile updated.")
        _print(res)


# ── schedule / availability ───────────────────────────────────────────────────

def _weekday_name(n):
    return WEEKDAYS[n] if 0 <= n <= 6 else str(n)


def list_availability():
    print("\n── My Schedule ──")
    slots = _get("/providers/me/availability")
    if slots is None:
        return
    if not slots:
        print("  No availability slots set.")
        return
    for s in slots:
        print(f"  [{s['id']}] {_weekday_name(s['weekday'])}  {s['start_time']}  →  {s['end_time']}")


def add_availability():
    print("\n── Add Availability Slot ──")
    print("  Weekdays: 0=Mon  1=Tue  2=Wed  3=Thu  4=Fri  5=Sat  6=Sun")
    weekday = int(_required("Weekday (0-6)"))
    start = _required("Start time (HH:MM)")
    end = _required("End time (HH:MM)")
    data = {"weekday": weekday, "start_time": start, "end_time": end}
    res = _post("/providers/me/availability", data)
    if res:
        print(f"  Slot added — ID: {res['id']}")


def update_availability():
    print("\n── Update Availability Slot ──")
    list_availability()
    slot_id = _required("\n  Slot ID to update")
    data = {}
    start = _input("New start time (HH:MM)")
    end = _input("New end time (HH:MM)")
    if start:
        data["start_time"] = start
    if end:
        data["end_time"] = end
    if not data:
        print("  Nothing to update.")
        return
    res = _patch(f"/providers/me/availability/{slot_id}", data)
    if res:
        print("  Slot updated.")


def delete_availability():
    print("\n── Delete Availability Slot ──")
    list_availability()
    slot_id = _required("\n  Slot ID to delete")
    confirm = input(f"  Delete slot #{slot_id}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        return
    if _delete(f"/providers/me/availability/{slot_id}"):
        print("  Slot deleted.")


# ── appointments ──────────────────────────────────────────────────────────────

def list_appointments():
    print("\n── My Appointments ──")
    params = {}
    status_f = _input("Filter by status (scheduled/checked_in/in_progress/completed/cancelled/no_show)")
    date_f = _input("Filter by date (YYYY-MM-DD)")
    page = _input("Page", "1")
    if status_f:
        params["status"] = status_f
    if date_f:
        params["date"] = date_f
    params["page"] = page
    res = _get("/appointments", params)
    if res is None:
        return
    if not res:
        print("  No appointments found.")
        return
    for a in res:
        print(f"\n  Appointment ID : {a['id']}")
        print(f"  Time           : {a['scheduled_start']}  →  {a['scheduled_end']}")
        print(f"  Status         : {a['status']}  |  {a['appointment_type']}")
        print(f"  Patient ID     : {a['patient_id']}")
        print(f"  Reason         : {a['reason']}")


def get_appointment():
    print("\n── Appointment Detail ──")
    appt_id = _required("Appointment ID")
    res = _get(f"/appointments/{appt_id}")
    if res:
        _print(res)


def check_in_appointment():
    print("\n── Check In Patient ──")
    appt_id = _required("Appointment ID")
    res = _post(f"/appointments/{appt_id}/check-in")
    if res:
        print(f"  Status → {res['status']}")


def complete_appointment():
    print("\n── Complete Appointment ──")
    appt_id = _required("Appointment ID")
    res = _post(f"/appointments/{appt_id}/complete")
    if res:
        print(f"  Appointment #{appt_id} completed. Status → {res['status']}")


def cancel_appointment():
    print("\n── Cancel Appointment ──")
    appt_id = _required("Appointment ID to cancel")
    confirm = input(f"  Cancel appointment #{appt_id}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        return
    res = _post(f"/appointments/{appt_id}/cancel")
    if res:
        print(f"  Appointment cancelled. Status → {res['status']}")


# ── patients ──────────────────────────────────────────────────────────────────

def list_patients():
    print("\n── My Patients ──")
    params = {"page": _input("Page", "1"), "size": _input("Page size", "20")}
    from_d = _input("From date (YYYY-MM-DD, optional)")
    to_d = _input("To date (YYYY-MM-DD, optional)")
    if from_d:
        params["from_date"] = from_d
    if to_d:
        params["to_date"] = to_d
    res = _get("/patients", params)
    if res is None:
        return
    items = res.get("items", [])
    if not items:
        print("  No patients found.")
        return
    for p in items:
        print(f"\n  [{p['id']}]  {p['full_name']}  DOB: {p.get('date_of_birth','—')}  Blood: {p.get('blood_group','—')}")
        if p.get("appointments"):
            latest = p["appointments"][0]
            print(f"       Last appt: {latest['scheduled_start']}  ({latest['status']})")


def get_patient():
    print("\n── Patient Detail ──")
    patient_id = _required("Patient ID")
    res = _get(f"/patients/{patient_id}")
    if res:
        _print(res)


# ── prescriptions ─────────────────────────────────────────────────────────────

def create_prescription():
    print("\n── Create Prescription ──")
    patient_id = int(_required("Patient ID"))
    appt_id = _input("Appointment ID (optional)")

    items = []
    print("  Add medications (blank drug name to finish):")
    while True:
        drug = _input("  Drug name (blank to finish)")
        if not drug:
            break
        amount   = float(_required("  Dosage amount (e.g. 500)"))
        unit     = _required("  Unit (mg / ml / tablet)")
        freq     = int(_required("  Frequency per day (e.g. 2)"))
        days     = int(_required("  Duration in days (e.g. 7)"))
        instr    = _input("  Instructions (optional)")
        items.append({
            "drug_name":         drug,
            "dosage_amount":     amount,
            "dosage_unit":       unit,
            "frequency_per_day": freq,
            "duration_days":     days,
            "instructions":      instr or None,
        })
        print(f"  Added: {drug} {amount}{unit} {freq}×/day for {days}d")

    if not items:
        print("  No drugs added. Cancelled.")
        return

    notes = _input("Notes")
    data = {
        "patient_id": patient_id,
        "items": items,
    }
    if appt_id:
        data["appointment_id"] = int(appt_id)
    if notes:
        data["notes"] = notes

    res = _post("/prescriptions", data)
    if res:
        print(f"\n  Prescription created! ID: {res['id']}  Status: {res['status']}")


def list_prescriptions():
    print("\n── Prescriptions ──")
    params = {}
    patient_id = _input("Filter by patient ID")
    status_f = _input("Filter by status (active/cancelled/filled)")
    page = _input("Page", "1")
    if patient_id:
        params["patient_id"] = patient_id
    if status_f:
        params["status"] = status_f
    params["page"] = page
    res = _get("/prescriptions", params)
    if res is None:
        return
    if not res:
        print("  No prescriptions found.")
        return
    for rx in res:
        print(f"\n  [{rx['id']}]  Patient: {rx['patient_id']}  Status: {rx['status']}")
        for item in rx.get("items", []):
            print(f"       • {item['drug_name']} {item['dosage']} {item['dosage_unit']} — {item['instructions']}")


def get_prescription():
    print("\n── Prescription Detail ──")
    rx_id = _required("Prescription ID")
    res = _get(f"/prescriptions/{rx_id}")
    if res:
        _print(res)


def cancel_prescription():
    print("\n── Cancel Prescription ──")
    rx_id = _required("Prescription ID to cancel")
    confirm = input(f"  Cancel prescription #{rx_id}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        return
    res = _post(f"/prescriptions/{rx_id}/cancel")
    if res:
        print(f"  Prescription cancelled. Status → {res['status']}")


# ── allergies ─────────────────────────────────────────────────────────────────

def record_allergy():
    print("\n── Record Patient Allergy ──")
    if not _provider_id:
        print("  No provider profile loaded. Please login first.")
        return
    patient_id = int(_required("Patient ID"))
    allergen = _required("Allergen (e.g. Penicillin)")
    print("  Types: drug / food / environmental / other")
    allergy_type = _input("Allergy type", "drug")
    print("  Severity: mild / moderate / severe / life_threatening")
    severity = _input("Severity", "moderate")
    reaction = _input("Reaction description")

    data = {
        "patient_id": patient_id,
        "allergen": allergen,
        "allergy_type": allergy_type,
        "severity": severity,
        "recorded_by_id": _provider_id,
    }
    if reaction:
        data["reaction"] = reaction

    res = _post("/allergies", data)
    if res:
        print(f"  Allergy recorded. ID: {res['id']}")


def list_allergies():
    print("\n── Patient Allergies ──")
    patient_id = _required("Patient ID")
    res = _get(f"/patients/{patient_id}/allergies")
    if res is None:
        return
    if not res:
        print("  No allergies on record.")
        return
    for a in res:
        print(f"\n  [{a['id']}]  {a['allergen']}  ({a['allergy_type']})  —  Severity: {a['severity']}")
        if a.get("reaction"):
            print(f"       Reaction: {a['reaction']}")


def delete_allergy():
    print("\n── Delete Allergy Record ──")
    patient_id = _required("Patient ID")
    list_allergies_for_patient(patient_id)
    allergy_id = _required("\n  Allergy ID to delete")
    confirm = input(f"  Delete allergy #{allergy_id}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        return
    if _delete(f"/patients/{patient_id}/allergies/{allergy_id}"):
        print("  Allergy deleted.")


def list_allergies_for_patient(patient_id):
    res = _get(f"/patients/{patient_id}/allergies")
    if res is None:
        return
    if not res:
        print("  No allergies on record.")
        return
    for a in res:
        print(f"  [{a['id']}]  {a['allergen']}  ({a['allergy_type']})  —  Severity: {a['severity']}")


# ── menu ──────────────────────────────────────────────────────────────────────

MENU = {
    "Auth": {
        "1": ("Login",            login),
        "2": ("Logout",           logout),
        "3": ("Who am I (/me)",   me),
        "4": ("Change password",  change_password),
        "5": ("Forgot password",  forgot_password),
        "6": ("Reset password",   reset_password),
    },
    "Provider Profile": {
        "7":  ("View my profile",    get_profile),
        "8":  ("Update my profile",  update_profile),
    },
    "Schedule": {
        "9":  ("List my availability",    list_availability),
        "10": ("Add availability slot",   add_availability),
        "11": ("Update availability slot", update_availability),
        "12": ("Delete availability slot", delete_availability),
    },
    "Appointments": {
        "13": ("List appointments",   list_appointments),
        "14": ("View appointment",    get_appointment),
        "15": ("Check in patient",    check_in_appointment),
        "16": ("Complete appointment", complete_appointment),
        "17": ("Cancel appointment",  cancel_appointment),
    },
    "Patients": {
        "18": ("List my patients",  list_patients),
        "19": ("View patient",      get_patient),
    },
    "Prescriptions": {
        "20": ("Create prescription", create_prescription),
        "21": ("List prescriptions",  list_prescriptions),
        "22": ("View prescription",   get_prescription),
        "23": ("Cancel prescription", cancel_prescription),
    },
    "Allergies": {
        "24": ("Record allergy",      record_allergy),
        "25": ("List patient allergies", list_allergies),
        "26": ("Delete allergy record",  delete_allergy),
    },
}


def _print_menu():
    print("\n" + "═" * 46)
    print("  SwiftCare Provider CLI")
    pid = f"  provider_id={_provider_id}" if _provider_id else ""
    status = f"Logged in{pid}" if _token else "Not logged in"
    print(f"  {status}")
    print("═" * 46)
    for section, items in MENU.items():
        print(f"\n  {section}")
        for key, (label, _) in items.items():
            print(f"    {key:>2}. {label}")
    print("\n   0. Exit")
    print("═" * 46)


def main():
    print("\nWelcome to SwiftCare Provider CLI")
    print(f"Connecting to: {BASE_URL}")
    print("  (Providers are onboarded by admin — use Login, not Register)")

    all_options = {}
    for items in MENU.values():
        all_options.update(items)

    while True:
        _print_menu()
        choice = input("\nChoice: ").strip()
        if choice == "0":
            print("Goodbye.")
            break
        if choice in all_options:
            try:
                all_options[choice][1]()
            except KeyboardInterrupt:
                print("\n  Cancelled.")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
