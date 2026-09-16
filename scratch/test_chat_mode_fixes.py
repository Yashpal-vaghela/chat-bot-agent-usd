import os
import sys
import django
import asyncio

# Setup django environment
sys.path.insert(0, r"d:\media")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from voice_agent.ai.conversation_manager import (
    detect_user_language,
    extract_certified_city_from_text,
    find_doctor_in_text,
    CONFIRMATION_MESSAGES_11,
    ConversationManager
)
from voice_agent.utils.helpers import is_submit_review_summary, extract_slots_from_review_summary
from voice_agent.services.appointment_service import save_lead_to_local_db, submit_consultation_appointment
from account.models import UserSubmission

def test_language_detection():
    print("\n--- Testing Language Detection ---")
    gu_samples = [
        "maaru naam amitaabh bacchan se",
        "maari smit to akdummast se",
        "to maari smile haji enhaanch thai sake?",
        "hu kaya saher ma ravsu ?",
        "hu ahmedabad ma rav su",
        "maare edit karvi se request",
        "haan to surat ma purvi patel saathe",
        "cancel kari naakho",
        "cancel kari naakho maari appointment request ne"
    ]
    for s in gu_samples:
        lang = detect_user_language(s)
        print(f"Sample: '{s}' -> Detected: {lang}")
        assert lang == "gu", f"Expected 'gu' for '{s}', got '{lang}'"
    print("Language detection tests PASSED!")

def test_simultaneous_city_and_doctor():
    print("\n--- Testing Simultaneous City and Doctor Extraction ---")
    from voice_agent.ai.session_manager import Session
    session = Session()
    session.booking_slots["city"] = "Ahmedabad"
    session.booking_slots["first_name"] = "Amitaabh"
    session.booking_slots["last_name"] = "Bacchan"
    session.booking_slots["phone"] = "7984265299"
    session.booking_slots["message"] = "Smile Makeover & Enhancement"
    session.booking_slots["doctor_name"] = "Dr. Janu Shah"

    async def dummy_send_json(data):
        pass

    mgr = ConversationManager(session=session, send_json_callback=dummy_send_json, gemini_client=None)

    # Now user says: "haan to surat ma purvi patel saathe"
    mgr.update_session_memory("haan to surat ma purvi patel saathe", history=[])
    
    print(f"Updated City: {mgr.session.booking_slots.get('city')}")
    print(f"Updated Doctor: {mgr.session.booking_slots.get('doctor_name')}")
    assert mgr.session.booking_slots.get("city") == "Surat", "City should be Surat"
    assert mgr.session.booking_slots.get("doctor_name") == "Dr. Purvi Patel", "Doctor should be Dr. Purvi Patel"
    print("Simultaneous City and Doctor extraction test PASSED!")

async def test_lead_save_and_cancel_in_db():
    print("\n--- Testing Local DB Save, In-Place Update and Cancellation ---")
    payload = {
        "first_name": "Amitaabh",
        "last_name": "Bacchan",
        "phone": "7984265299",
        "city": "Ahmedabad",
        "doctor_name": "Dr. Janu Shah",
        "message": "Smile Makeover & Enhancement",
        "email": "no-reply@ultimatesmiledesign.com",
        "is_cancel": False,
        "is_update": False
    }
    
    # 1. First submission
    sub_id = await save_lead_to_local_db(payload)
    print(f"Saved initial lead ID: {sub_id}")
    assert sub_id is not None
    
    lead = await asyncio.to_thread(UserSubmission.objects.get, id=sub_id)
    assert lead.city == "Ahmedabad"
    assert lead.doctor_name == "Dr. Janu Shah"
    assert lead.is_cancel is False

    # 2. Update to Surat with Dr. Purvi Patel
    update_payload = dict(payload)
    update_payload["id"] = sub_id
    update_payload["submission_id"] = sub_id
    update_payload["city"] = "Surat"
    update_payload["doctor_name"] = "Dr. Purvi Patel"
    update_payload["is_update"] = True
    
    updated_id = await save_lead_to_local_db(update_payload)
    print(f"Updated lead ID: {updated_id}")
    assert updated_id == sub_id, f"ID changed! Expected {sub_id}, got {updated_id}"
    
    lead_up = await asyncio.to_thread(UserSubmission.objects.get, id=sub_id)
    assert lead_up.city == "Surat"
    assert lead_up.doctor_name == "Dr. Purvi Patel"
    assert lead_up.is_cancel is False

    # 3. Cancel the appointment
    cancel_payload = dict(update_payload)
    cancel_payload["is_cancel"] = True
    
    cancelled_id = await save_lead_to_local_db(cancel_payload)
    print(f"Cancelled lead ID: {cancelled_id}")
    assert cancelled_id == sub_id, f"ID changed on cancel! Expected {sub_id}, got {cancelled_id}"
    
    lead_cancel = await asyncio.to_thread(UserSubmission.objects.get, id=sub_id)
    assert lead_cancel.is_cancel is True
    print("Database in-place save, update, and cancellation tests PASSED!")

async def main():
    test_language_detection()
    test_simultaneous_city_and_doctor()
    await test_lead_save_and_cancel_in_db()

if __name__ == "__main__":
    asyncio.run(main())
