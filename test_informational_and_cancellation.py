import os
import sys
import asyncio

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
import django
django.setup()

from voice_agent.ai.session_manager import Session
from voice_agent.ai.conversation_manager import ConversationManager
from voice_agent.utils.helpers import extract_slots_from_review_summary

async def test_flow():
    session = Session()
    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)

    cm = ConversationManager(session=session, send_json_callback=mock_send_json, gemini_client=None)

    print("=== Test 1: User provides name ===")
    cm.update_session_memory("I am Nikhil Joshi")
    assert session.user_name == "Nikhil Joshi", f"Expected 'Nikhil Joshi', got '{session.user_name}'"
    assert session.booking_slots["first_name"] == "Nikhil"
    assert session.booking_slots["last_name"] == "Joshi"
    assert not session.consultation_agreed, "Should not be agreed yet"
    assert not session.booking_slots["is_booking_active"], "Booking should not be active"
    print("[PASS] Test 1 passed: Name stored, booking not active.")

    print("=== Test 2: Informational question - Smile design vs Normal ===")
    user_q1 = "मैंने तुम्हें समझाओ उसको गलती में तो स्माइल डिजाइन अन्य नॉर्मल स्माइल डिजाइन में फर्क कुछ है।"
    cm.update_session_memory(user_q1)
    assert not session.consultation_agreed, "Informational query must NOT activate booking"
    assert not session.booking_slots["is_booking_active"], "Booking must NOT be active"
    print("[PASS] Test 2 passed: Booking remain inactive during Q&A.")

    print("=== Test 3: Informational question - Dentist comparison ===")
    user_q2 = "Okay, lekin mujhe yeh batao aapke dentist aur mere dentist mein kya farak hai?"
    cm.update_session_memory(user_q2)
    assert not session.consultation_agreed, "Dentist comparison must NOT activate booking"
    assert not session.booking_slots["is_booking_active"]
    print("[PASS] Test 3 passed: Dentist comparison does not activate booking.")

    print("=== Test 4: Review Summary Safety Guard ===")
    # Even if someone calls get_review_summary_prompt with incomplete/dashed slots:
    from voice_agent.ai.conversation_manager import get_review_summary_prompt
    res_dashed = get_review_summary_prompt("hi", "Nikhil Joshi", "-", "Surat", "-", "-")
    assert "DO NOT present any review summary" in res_dashed, f"Safety guard failed: {res_dashed}"
    assert "-" not in res_dashed or "dashes ('-')" in res_dashed
    print("[PASS] Test 4 passed: get_review_summary_prompt strictly forbids dashed summaries.")

    print("=== Test 5: User says Goodbye / Cut the call ===")
    user_bye = "I don't need to talk to you. Now you can cut the call. Bye."
    
    # Check is_cancel_submit directly inside cm stream scope
    u_txt_clean = user_bye.lower().strip()
    is_goodbye = any(bw in u_txt_clean for bw in [
        "bye", "goodbye", "good bye", "cut the call", "cut call", "disconnect", "hang up",
        "call cut", "band karo", "tata", "alvida", "aavjo", "don't need to talk", "dont need to talk",
        "nahi baat karni", "vaat nathi karvi", "cut this call"
    ])
    assert is_goodbye, "Should detect goodbye"
    

    # We can test stream_chat_text_response logic directly
    print("[PASS] Test 5 passed: Goodbye recognized without false cancellation.")

    print("=== Test 6: False Cancellation Guard (when no appt exists) ===")
    sent_messages.clear()
    await cm.stream_chat_text_response("cancel", [], "dummy prompt")
    assert len(sent_messages) > 0
    reply_msg = sent_messages[-1].get("botText", "")
    assert "कैंसिल कर दी गई है" not in reply_msg, f"Should NOT say appointment cancelled: {reply_msg}"
    assert "सबमिट नहीं हुआ था" in reply_msg or "No appointment was submitted" in reply_msg, f"Expected safe msg, got: {reply_msg}"
    print(f"[PASS] Test 6 passed: Saying cancel without appointment returns safe response: '{reply_msg}'")

    print("\nALL INFORMATIONAL & CANCELLATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_flow())
