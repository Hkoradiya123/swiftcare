#!/usr/bin/env python3
"""
SwiftCare Patient CLI
All patient-facing API operations from the command line.
"""

import json
import sys
import requests

BASE_URL = "http://localhost:8000/api/v1"
_token = None
_profile_id = None  # patient_id or provider_id


# ── helpers ──────────────────────────────────────────────────────────────────

def _headers():
    return {"Authorization": f"Bearer {_token}"} if _token else {}


def _print(data):
    print(json.dumps(data, indent=2, default=str))


def _post(path, data=None, auth=True):
    r = requests.post(f"{BASE_URL}{path}", json=data, headers=_headers() if auth else {})
    if r.status_code in (200, 201, 204):
        return r.json() if r.content else {}
    print(f"Error {r.status_code}: {r.text}")
    return None


def _get(path, params=None):
    r = requests.get(f"{BASE_URL}{path}", params=params, headers=_headers())
    if r.status_code == 200:
        return r.json()
    print(f"Error {r.status_code}: {r.text}")
    return None


def _patch(path, data):
    r = requests.patch(f"{BASE_URL}{path}", json=data, headers=_headers())
    if r.status_code == 200:
        return r.json()
    print(f"Error {r.status_code}: {r.text}")
    return None


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

def register():
    print("\n── Register ──")
    data = {
        "email": _required("Email"),
        "password": _required("Password"),
        "full_name": _required("Full name"),
    }
    res = _post("/auth/register", data, auth=False)
    if res:
        print("Registered and logged in.")
        _set_token(res)


def login():
    print("\n── Login ──")
    data = {"email": _required("Email"), "password": _required("Password")}
    res = _post("/auth/login", data, auth=False)
    if res:
        _set_token(res)
        print("Logged in.")


def logout():
    _post("/auth/logout")
    global _token
    _token = None
    print("Logged out.")


def me():
    res = _get("/auth/me")
    if res:
        _print(res)


def change_password():
    print("\n── Change Password ──")
    data = {
        "old_password": _required("Current password"),
        "new_password": _required("New password"),
    }
    res = _post("/auth/change-password", data)
    if res is not None:
        print("Password changed.")


def forgot_password():
    print("\n── Forgot Password ──")
    email = _required("Email")
    res = _post("/auth/forgot-password", {"email": email}, auth=False)
    if res is not None:
        print("Reset email sent (check your inbox).")


def reset_password():
    print("\n── Reset Password ──")
    data = {
        "token": _required("Reset token (from email)"),
        "new_password": _required("New password"),
    }
    res = _post("/auth/reset-password", data, auth=False)
    if res is not None:
        print("Password reset successfully. Please login.")


def _set_token(res):
    global _token, _profile_id
    _token = res.get("access_token")
    # fetch profile_id from /me so it's available without extra steps
    me_res = _get("/auth/me")
    if me_res:
        _profile_id = me_res.get("profile_id")


# ── patient profile ───────────────────────────────────────────────────────────

def create_profile():
    print("\n── Create Patient Profile ──")
    data = {
        "date_of_birth": _required("Date of birth (YYYY-MM-DD)"),
        "phone": _required("Phone number"),
        "blood_group": _input("Blood group (A+/B-/O+/etc.)"),
        "address": _input("Address"),
    }
    data = {k: v for k, v in data.items() if v}
    res = _post("/patients/me", data)
    if res:
        print("Profile created.")
        _print(res)


def get_profile():
    res = _get("/patients/me")
    if res:
        _print(res)


def update_profile():
    print("\n── Update Profile ──")
    print("  Leave blank to keep current value.")
    data = {}
    phone = _input("New phone")
    blood = _input("New blood group")
    addr = _input("New address")
    if phone:
        data["phone"] = phone
    if blood:
        data["blood_group"] = blood
    if addr:
        data["address"] = addr
    if not data:
        print("Nothing to update.")
        return
    res = _patch("/patients/me", data)
    if res:
        print("Profile updated.")
        _print(res)


# ── appointments ──────────────────────────────────────────────────────────────

def _fetch_providers(spec=None):
    params = {"page": 1, "size": 50}
    if spec:
        params["specialization"] = spec
    res = _get("/providers", params)
    return res.get("items", []) if res else []


def list_providers():
    print("\n── Available Providers ──")
    spec = _input("Filter by specialization (leave blank for all)")
    items = _fetch_providers(spec)
    if not items:
        print("  No providers found.")
        return
    print()
    for i, p in enumerate(items, 1):
        print(f"  {i:>2}. {p['full_name']}  —  {p['specialization']}")
        print(f"       Fee: ${p['consultation_fee']}  |  Slot: {p['default_slot_minutes']} min")


def book_appointment():
    print("\n── Book Appointment ──")

    # 1. Patient ID (auto from login)
    patient_id = _profile_id
    if not patient_id:
        print("  No patient profile found. Create one first (option 8).")
        return

    # 2. Pick provider
    print("\n  Step 1: Choose a provider")
    spec = _input("  Filter by specialization (leave blank for all)")
    providers = _fetch_providers(spec)
    if not providers:
        print("  No providers found.")
        return

    print()
    for i, p in enumerate(providers, 1):
        print(f"  {i:>2}. {p['full_name']}  —  {p['specialization']}  |  ${p['consultation_fee']}  |  {p['default_slot_minutes']} min/slot")

    while True:
        choice = input("\n  Pick provider number: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(providers):
            provider = providers[int(choice) - 1]
            break
        print("  Invalid choice.")

    print(f"\n  Selected: {provider['full_name']} ({provider['specialization']})")

    # 3. Pick date and show open slots
    print("\n  Step 2: Choose a date")
    while True:
        date_str = _required("  Date (YYYY-MM-DD)")
        slots = _get(f"/providers/{provider['id']}/slots", {"date": date_str})
        if slots is None:
            continue
        if not slots:
            print(f"  No open slots on {date_str} for this provider. Try another date.")
            continue
        break

    print(f"\n  Open slots on {date_str}:")
    for i, s in enumerate(slots, 1):
        start_t = s['start'].split('T')[1][:5]
        end_t = s['end'].split('T')[1][:5]
        print(f"  {i:>2}. {start_t}  →  {end_t}")

    while True:
        slot_choice = input("\n  Pick slot number: ").strip()
        if slot_choice.isdigit() and 1 <= int(slot_choice) <= len(slots):
            slot = slots[int(slot_choice) - 1]
            break
        print("  Invalid choice.")

    # 4. Appointment details
    print("\n  Step 3: Appointment details")
    print("  Types: in_person, telehealth")
    appt_type = _input("  Appointment type", "in_person")
    reason = _required("  Reason for visit")
    notes = _input("  Additional notes")

    data = {
        "patient_id": int(patient_id),
        "provider_id": provider["id"],
        "appointment_type": appt_type,
        "scheduled_start": slot["start"],
        "scheduled_end": slot["end"],
        "reason": reason,
    }
    if appt_type == "telehealth":
        link = _input("  Meeting link (optional)")
        if link:
            data["meeting_link"] = link
    else:
        room = _input("  Room number (optional)")
        if room:
            data["room_number"] = room
    if notes:
        data["notes"] = notes

    # 5. Confirm
    print(f"\n  Booking with {provider['full_name']} on {date_str} {slot['start'].split('T')[1][:5]}–{slot['end'].split('T')[1][:5]}")
    confirm = input("  Confirm? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("  Cancelled.")
        return

    res = _post("/appointments", data)
    if res:
        print(f"\n  ✓ Appointment booked! ID: {res['id']}")
        print(f"  {res['scheduled_start']}  →  {res['scheduled_end']}")
        print(f"  Status: {res['status']}")


def list_appointments():
    print("\n── My Appointments ──")
    params = {}
    status_f = _input("Filter by status (scheduled/checked_in/completed/cancelled/no_show)")
    date_f = _input("Filter by date (YYYY-MM-DD)")
    page = _input("Page", "1")
    if status_f:
        params["status"] = status_f
    if date_f:
        params["date"] = date_f
    params["page"] = page
    res = _get("/appointments", params)
    if res:
        if not res:
            print("No appointments found.")
        for a in res:
            print(f"\n  [{a['id']}] {a['scheduled_start']} → {a['scheduled_end']}")
            print(f"       Status: {a['status']}  Type: {a['appointment_type']}")
            print(f"       Reason: {a['reason']}")


def get_appointment():
    print("\n── Appointment Detail ──")
    appt_id = _required("Appointment ID")
    res = _get(f"/appointments/{appt_id}")
    if res:
        _print(res)


def cancel_appointment():
    print("\n── Cancel Appointment ──")
    appt_id = _required("Appointment ID to cancel")
    confirm = input(f"  Cancel appointment #{appt_id}? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Cancelled.")
        return
    res = _post(f"/appointments/{appt_id}/cancel")
    if res:
        print("Appointment cancelled.")
        _print(res)


# ── prescriptions ─────────────────────────────────────────────────────────────

def list_prescriptions():
    print("\n── My Prescriptions ──")
    patient_id = _profile_id or _required("Your patient profile ID")
    res = _get(f"/patients/{patient_id}/prescriptions")
    if res:
        if not res:
            print("No prescriptions found.")
        for rx in res:
            print(f"\n  [{rx['id']}] Status: {rx['status']}")
            for item in rx.get("items", []):
                print(f"       • {item['drug_name']} {item['dosage']} {item['dosage_unit']} — {item['instructions']}")


def get_prescription():
    print("\n── Prescription Detail ──")
    rx_id = _required("Prescription ID")
    res = _get(f"/prescriptions/{rx_id}")
    if res:
        _print(res)


# ── allergies ─────────────────────────────────────────────────────────────────

def list_allergies():
    print("\n── My Allergies ──")
    patient_id = _profile_id or _required("Your patient profile ID")
    res = _get(f"/patients/{patient_id}/allergies")
    if res:
        if not res:
            print("No allergies on record.")
        for a in res:
            print(f"\n  [{a['id']}] {a['allergen']} ({a['allergy_type']}) — Severity: {a['severity']}")
            if a.get("reaction"):
                print(f"       Reaction: {a['reaction']}")


# ── menu ──────────────────────────────────────────────────────────────────────

MENU = {
    "Auth": {
        "1": ("Register",         register),
        "2": ("Login",            login),
        "3": ("Logout",           logout),
        "4": ("Who am I (/me)",   me),
        "5": ("Change password",  change_password),
        "6": ("Forgot password",  forgot_password),
        "7": ("Reset password",   reset_password),
    },
    "Patient Profile": {
        "8":  ("Create profile",  create_profile),
        "9":  ("View profile",    get_profile),
        "10": ("Update profile",  update_profile),
    },
    "Appointments": {
        "11": ("List providers",        list_providers),
        "12": ("Book appointment",      book_appointment),
        "13": ("List my appointments",  list_appointments),
        "14": ("View appointment",      get_appointment),
        "15": ("Cancel appointment",    cancel_appointment),
    },
    "Prescriptions": {
        "16": ("List my prescriptions", list_prescriptions),
        "17": ("View prescription",     get_prescription),
    },
    "Allergies": {
        "18": ("List my allergies",     list_allergies),
    },
}


def _print_menu():
    print("\n" + "═" * 44)
    print("  SwiftCare Patient CLI")
    pid = f"  patient_id={_profile_id}" if _profile_id else ""
    status = f"Logged in{pid}" if _token else "Not logged in"
    print(f"  {status}")
    print("═" * 44)
    for section, items in MENU.items():
        print(f"\n  {section}")
        for key, (label, _) in items.items():
            print(f"    {key:>2}. {label}")
    print("\n   0. Exit")
    print("═" * 44)


def main():
    print("\nWelcome to SwiftCare Patient CLI")
    print(f"Connecting to: {BASE_URL}")

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
