import os
import sys
import django
import asyncio

sys.path.insert(0, os.path.abspath("."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from asgiref.sync import sync_to_async
from account.models import UserSubmission
from voice_agent.services.appointment_service import save_lead_to_local_db, submit_consultation_appointment
from voice_agent.gemini.client import is_cancel_submit, is_affirmative_submit

@sync_to_async
def get_lead(lead_id):
    return UserSubmission.objects.get(id=lead_id)

@sync_to_async
def clean_test_leads(phone):
    UserSubmission.objects.filter(phone__endswith=phone).delete()

@sync_to_async
def get_lead_count():
    return UserSubmission.objects.count()

async def run_tests():
    print("\n=======================================================")
    print("TEST 1: In-Place Update on Same Submission ID & Cancellation")
    print("=======================================================\n")

    test_phone = "9988776655"
    # Clean up any previous test leads with this phone
    await clean_test_leads(test_phone)

    initial_count = await get_lead_count()

    # Step 1: Initial Booking
    booking_payload = {
        "first_name": "Rajesh",
        "last_name": "Patel",
        "phone": test_phone,
        "city": "Ahmedabad",
        "doctor_name": "Dr. Neerav Jhaveri",
        "message": "Gap between front teeth",
        "email": "rajesh@example.com",
        "is_cancel": False,
        "is_update": False
    }

    res1 = await submit_consultation_appointment(booking_payload)
    print(f"Step 1 (Booking) Response: status={res1.get('status')}, id={res1.get('details', {}).get('id')}")
    assert res1.get("status") == "success", "Step 1 failed"
    lead_id_1 = res1.get("details", {}).get("id")
    assert lead_id_1 is not None, "Lead ID not returned"

    lead_obj_1 = await get_lead(lead_id_1)
    assert lead_obj_1.doctor_name == "Dr. Neerav Jhaveri"
    assert lead_obj_1.is_cancel == False
    new_count_1 = await get_lead_count()
    assert new_count_1 == initial_count + 1, "Expected exactly 1 new lead"
    print(f"[PASS] Step 1 Passed: Created Lead ID {lead_id_1}")

    # Step 2: Update Doctor on same submission ID
    update_payload = {
        "submission_id": lead_id_1,
        "id": lead_id_1,
        "first_name": "Rajesh",
        "last_name": "Patel",
        "phone": test_phone,
        "city": "Surat",
        "doctor_name": "Dr. Purvi Patel",
        "message": "Gap between front teeth",
        "email": "rajesh@example.com",
        "is_cancel": False,
        "is_update": True
    }

    res2 = await submit_consultation_appointment(update_payload)
    print(f"Step 2 (Update Doctor) Response: status={res2.get('status')}, id={res2.get('details', {}).get('id') if isinstance(res2.get('details'), dict) else None}, message={res2.get('message')}")
    assert res2.get("status") == "success", "Step 2 failed"
    lead_id_2 = res2.get("details", {}).get("id")
    assert lead_id_2 == lead_id_1, f"Expected same ID {lead_id_1}, got {lead_id_2}"

    lead_obj_2 = await get_lead(lead_id_1)
    assert lead_obj_2.doctor_name == "Dr. Purvi Patel", f"Doctor not updated: {lead_obj_2.doctor_name}"
    assert lead_obj_2.city == "Surat", f"City not updated: {lead_obj_2.city}"
    assert lead_obj_2.is_cancel == False
    new_count_2 = await get_lead_count()
    assert new_count_2 == initial_count + 1, "Expected NO duplicate rows created!"
    print(f"[PASS] Step 2 Passed: Updated Lead ID {lead_id_1} in-place (Doctor is now Dr. Purvi Patel in Surat)")

    # Step 3: Cancellation on same submission ID
    cancel_payload = {
        "submission_id": lead_id_1,
        "id": lead_id_1,
        "phone": test_phone,
        "is_cancel": True,
        "is_update": True
    }

    res3 = await submit_consultation_appointment(cancel_payload)
    print(f"Step 3 (Cancellation) Response: status={res3.get('status')}, id={res3.get('details', {}).get('id') if isinstance(res3.get('details'), dict) else None}, message={res3.get('message')}")
    assert res3.get("status") == "success", "Step 3 failed"
    lead_id_3 = res3.get("details", {}).get("id")
    assert lead_id_3 == lead_id_1, f"Expected same ID {lead_id_1}, got {lead_id_3}"

    lead_obj_3 = await get_lead(lead_id_1)
    assert lead_obj_3.is_cancel == True, "is_cancel should be True!"
    new_count_3 = await get_lead_count()
    assert new_count_3 == initial_count + 1, "Expected NO duplicate rows created during cancellation!"
    print(f"[PASS] Step 3 Passed: Cancelled Lead ID {lead_id_1} in-place (is_cancel is now True)")

    # Step 4: Test is_cancel_submit keyword detection
    print("\n=======================================================")
    print("TEST 2: Multilingual Cancellation Detection")
    print("=======================================================\n")

    test_phrases = [
        ("Cancel my appointment", True),
        ("Please cancel it", True),
        ("mari appointment cancel kari nakho", True),
        ("appointment cancel karo", True),
        ("nathi karvu, cancel karo", True),
        ("cancel it please", True),
        ("meri booking cancel kar do", True),
        ("yes submit", False),
        ("Dr. Haresh Savani", False)
    ]

    for phrase, expected in test_phrases:
        detected = is_cancel_submit(phrase)
        print(f"Phrase: '{phrase}' -> is_cancel: {detected} (Expected: {expected})")
        assert detected == expected, f"Failed for phrase: {phrase}"

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    asyncio.run(run_tests())
