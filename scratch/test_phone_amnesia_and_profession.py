import os
import sys
import django

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# Setup Django environment
sys.path.insert(0, r"d:\media")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from voice_agent.ai.session_manager import Session
from voice_agent.ai.conversation_manager import ConversationManager
from voice_agent.ai.prompt_builder import get_system_prompt

class MockGeminiClient:
    pass

async def dummy_send_json(data):
    pass

def test_system_prompt_rules():
    print("\n--- TEST 1: System Prompt Rules Verification ---")
    sys_prompt = get_system_prompt()
    
    # 1. Check Phone Amnesia & Step 5 progression rule
    assert "If 10-digit mobile number is ALREADY in memory" in sys_prompt or "ALREADY in memory" in sys_prompt, "Missing already in memory rule in prompt!"
    assert "I ALREADY GAVE YOU MY NUMBER" in sys_prompt or "मैंने बता दिया है" in sys_prompt, "Missing handling for 'already told you'!"
    assert "ક્ષમા કરેં, મુઝે આપકા મોબાઈલ નંબર નહીં મિલા" not in sys_prompt
    print("✓ Phone Amnesia rules present in System Prompt.")
    
    # 2. Check Proactive Profession Inquiry
    assert "PROACTIVE" in sys_prompt or "proactively and naturally ask about their work/profession" in sys_prompt, "Missing proactive profession rule in prompt!"
    print("✓ Proactive Profession Inquiry rules present in System Prompt.")

def test_phone_retention_and_step_progression():
    print("\n--- TEST 2: Phone Retention & Doctor Resolution Simulation ---")
    session = Session()
    cm = ConversationManager(session, dummy_send_json, MockGeminiClient())
    
    # Turn 1: User introduces name and phone
    cm.update_session_memory("नमस्ते, मेरा नाम अलख है और मेरा फोन 7798452100 है", [])
    assert session.user_name == "Alakh"
    assert session.booking_slots.get("phone") == "7798452100"
    print(f"✓ Turn 1: Name={session.user_name}, Phone={session.booking_slots.get('phone')}")
    
    # Turn 2: User states dental concern
    cm.update_session_memory("मुझे स्माइल डिज़ाइन करवानी है", [{"role": "user", "parts": [{"text": "मुझे स्माइल डिज़ाइन करवानी है"}]}])
    assert session.user_concern is not None
    print(f"✓ Turn 2: Concern={session.user_concern}")
    
    # Turn 3: User mentions doctor in Pune while in Mumbai (creating mismatch)
    cm.update_session_memory("मुझे मुंबई में डॉक्टर आरती के साथ करानी है", [])
    # Dr. Aarti Bhatewara is in Pune, user said Mumbai
    assert session.city_doctor_mismatch is not None
    assert session.city_doctor_mismatch.get("doctor") == "Dr. Aarti Bhatewara"
    assert session.city_doctor_mismatch.get("doctor_city") == "Pune"
    print("✓ Turn 3: city_doctor_mismatch created for Dr. Aarti Bhatewara in Pune.")
    
    # Turn 4: User agrees to switch to Pune ("मैं पुणे में ही कराना चाहता हूं")
    cm.update_session_memory("मैं पुणे में ही कराना चाहता हूं।", [])
    assert session.booking_slots.get("city") == "Pune"
    assert session.booking_slots.get("doctor_name") == "Dr. Aarti Bhatewara"
    assert session.booking_slots.get("phone") == "7798452100"
    print(f"✓ Turn 4: Resolved City={session.booking_slots.get('city')}, Doctor={session.booking_slots.get('doctor_name')}, Phone={session.booking_slots.get('phone')}")
    
    # Turn 5: User says "मैंने ऑलरेडी तुम्हें बता दिया है"
    cm.update_session_memory("मैंने ऑलरेडी तुम्हें बता दिया है।", [])
    assert session.asking_for_field is None
    assert session.booking_slots.get("phone") == "7798452100"
    print("✓ Turn 5: 'already told you' preserved phone and did not enter phone re-ask state.")

def test_pending_doctor_with_known_phone():
    print("\n--- TEST 3: Pending Doctor with Known Phone ---")
    session = Session()
    session.booking_slots["city"] = "Ahmedabad"
    session.booking_slots["phone"] = "9876543210"
    session.user_name = "Nikhil"
    session.user_concern = "smile makeover"
    session.pending_doctor_candidate = "Dr. Janu Shah"
    
    cm = ConversationManager(session, dummy_send_json, MockGeminiClient())
    # User confirms doctor
    cm.update_session_memory("haan doctor janu shah", [])
    assert session.booking_slots.get("doctor_name") == "Dr. Janu Shah"
    assert session.booking_slots.get("phone") == "9876543210"
    print("✓ Turn: Doctor assigned and phone preserved without re-asking.")

import asyncio

async def main():
    test_system_prompt_rules()
    test_phone_retention_and_step_progression()
    test_pending_doctor_with_known_phone()
    print("\n=========================================")
    print("🎉 ALL UNIT TESTS PASSED SUCCESSFULLY! 🎉")
    print("=========================================\n")

if __name__ == "__main__":
    asyncio.run(main())

