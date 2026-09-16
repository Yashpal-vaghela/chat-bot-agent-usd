import os
import sys
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
import django
django.setup()

from voice_agent.ai.session_manager import Session
from voice_agent.ai.conversation_manager import ConversationManager, get_review_summary_prompt

async def test_genuine_booking():
    session = Session()
    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)

    cm = ConversationManager(session=session, send_json_callback=mock_send_json, gemini_client=None)

    print("=== Step 1: Name ===")
    cm.update_session_memory("I am Bhavin Parmar")
    assert session.user_name == "Bhavin Parmar"

    print("=== Step 2: Explicit booking intent ===")
    cm.update_session_memory("I want to book an appointment")
    assert session.consultation_agreed == True
    assert session.booking_slots["is_booking_active"] == True

    print("=== Step 3: City ===")
    cm.update_session_memory("Surat")
    assert session.booking_slots["city"] == "Surat"

    print("=== Step 4: Concern ===")
    cm.update_session_memory("teeth spacing")
    assert session.booking_slots["message"] == "gap between teeth"

    print("=== Step 5: Doctor ===")
    cm.update_session_memory("Dr. Purvi Patel")
    assert session.booking_slots["doctor_name"] == "Dr. Purvi Patel"

    print("=== Step 6: Phone ===")
    cm.update_session_memory("9876543210")
    assert session.booking_slots["phone"] == "9876543210"

    print("=== Step 7: All 5 slots complete -> Review Summary ===")
    slots = session.booking_slots
    has_fn = bool(slots.get("first_name"))
    has_city = bool(slots.get("city"))
    has_doc = bool(slots.get("doctor_name"))
    has_concern = bool(slots.get("message"))
    has_phone = bool(slots.get("phone"))
    assert has_fn and has_city and has_doc and has_concern and has_phone, "All 5 slots must be complete"

    rev_prompt = get_review_summary_prompt(
        "en", session.user_name, slots["phone"], slots["city"], slots["message"], slots["doctor_name"]
    )
    assert "Bhavin Parmar" in rev_prompt
    assert "9876543210" in rev_prompt
    assert "Surat" in rev_prompt
    assert "Dr. Purvi Patel" in rev_prompt
    assert "-" not in [slots["first_name"], slots["phone"], slots["city"], slots["message"], slots["doctor_name"]]

    print("[PASS] Genuine booking flow works seamlessly end-to-end!")

if __name__ == "__main__":
    asyncio.run(test_genuine_booking())
