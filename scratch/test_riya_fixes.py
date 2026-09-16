import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from voice_agent.ai.conversation_manager import (
    find_doctor_in_text,
    find_partial_doctor,
    ConversationManager
)
from voice_agent.ai.session_manager import Session
from voice_agent.services.appointment_service import (
    is_matched_doctor,
    ALL_CERTIFIED_DOCTORS
)
from voice_agent.ai.prompt_builder import get_system_prompt

def test_extract_dental_concern():
    print("\n--- TEST 1: extract_dental_concern ---")
    session = Session()
    cm = ConversationManager(session=session, send_json_callback=None, gemini_client=None)
    
    # We can test extract_dental_concern via update_session_memory
    test_cases = [
        ("मैंने नाक में दुख हुआ था नाक में।", ""),
        ("મને નાકમાં દુઃખાવો થાય છે", ""),
        ("मेरा सिर दर्द कर रहा है", ""),
        ("fat burner karwana hai", ""),
        ("दांत में दर्द है", "pain in teeth"),
        ("દાંતમાં દુખાવો છે", "pain in teeth"),
        ("મારા દાંત પીળા થઈ ગયા છે", "yellow stains / discoloration"),
        ("missing teeth", "missing teeth"),
        ("દાંતમાં સડો અને કાણું છે", "dental cavity and decay"),
        ("teeth problem", "dental issue/ teeth problem "),
    ]
    
    for text, expected in test_cases:
        test_session = Session()
        test_cm = ConversationManager(session=test_session, send_json_callback=None, gemini_client=None)
        test_cm.update_session_memory(user_text=text, history=[])
        res = test_session.user_concern or ""
        print(f"Input: '{text}' => Concern: '{res}'")
        if expected == "":
            assert res == "", f"Expected empty concern for '{text}', got '{res}'"
        else:
            assert expected in res, f"Expected '{expected}' in '{res}' for '{text}'"
    print("PASS: extract_dental_concern accurately rejects non-dental pain and accepts real dental symptoms!")

def test_city_doctor_restrictions():
    print("\n--- TEST 2: City Doctor Restrictions ---")
    # Dr. Deepika Dalal is ONLY in Mumbai (and not Surat)
    surat_doc = find_doctor_in_text("दीपिका दलाल", city="Surat")
    print(f"Deepika Dalal in Surat: {surat_doc}")
    assert surat_doc is None, f"Expected None for Deepika Dalal in Surat, got {surat_doc}"

    mumbai_doc = find_doctor_in_text("दीपिका दलाल", city="Mumbai")
    print(f"Deepika Dalal in Mumbai: {mumbai_doc}")
    assert mumbai_doc == "Dr. Deepika Dalal", f"Expected Dr. Deepika Dalal in Mumbai, got {mumbai_doc}"

    # Bharat Patel in Surat
    surat_bharat = find_doctor_in_text("Bharat Patel", city="Surat")
    print(f"Bharat Patel in Surat: {surat_bharat}")
    assert surat_bharat == "Dr. Bharat R. Patel", f"Expected Dr. Bharat R. Patel in Surat, got {surat_bharat}"

    # Bharat Patel in Mumbai
    mumbai_bharat = find_doctor_in_text("Bharat Patel", city="Mumbai")
    print(f"Bharat Patel in Mumbai: {mumbai_bharat}")
    assert mumbai_bharat is None, f"Expected None for Bharat Patel in Mumbai, got {mumbai_bharat}"
    print("PASS: City doctor restrictions strictly validated!")

def test_city_change_doctor_invalidation():
    print("\n--- TEST 3: City Change Doctor Invalidation ---")
    session = Session()
    cm = ConversationManager(session=session, send_json_callback=None, gemini_client=None)
    
    # Patient starts in Surat with Dr. Bharat R. Patel
    cm.update_session_memory(user_text="I am in Surat", history=[])
    assert session.booking_slots.get("city") == "Surat"
    
    cm.update_session_memory(user_text="Bharat Patel", history=[])
    assert session.booking_slots.get("doctor_name") == "Dr. Bharat R. Patel"
    print(f"Initial: City={session.booking_slots.get('city')}, Doctor={session.booking_slots.get('doctor_name')}")
    
    # Patient now changes city to Ahmedabad
    cm.update_session_memory(user_text="મારા જે અક્ષર છે સુરત લખાયેલી હતી ને એની જગ્યા ઉપર અમદાવાદ લખાવવું છે", history=[])
    print(f"After update to Ahmedabad: City={session.booking_slots.get('city')}, Doctor={session.booking_slots.get('doctor_name')}, asking_for_field={session.asking_for_field}")
    assert session.booking_slots.get("city") == "Ahmedabad", f"Expected Ahmedabad, got {session.booking_slots.get('city')}"
    assert session.booking_slots.get("doctor_name") == "", f"Expected cleared doctor, got {session.booking_slots.get('doctor_name')}"
    assert session.asking_for_field == "doctor", f"Expected asking_for_field='doctor', got {session.asking_for_field}"
    assert session.slot_just_updated == False, f"Expected slot_just_updated=False, got {session.slot_just_updated}"
    print("PASS: City change successfully voids doctor and demands new doctor selection!")

def test_prompt_compilation():
    print("\n--- TEST 4: Prompt Compilation & Verification ---")
    prompt = get_system_prompt(force_reload=True)
    assert "SPEECH-TO-SPEECH AUDIO LANGUAGE LOYALTY" in prompt
    assert "LOCAL DENTIST COMPARISON & TRANSPARENCY PROTOCOL" in prompt
    assert "Step 2.5. MANDATORY CONSULTATION PERMISSION GATE" in prompt
    assert "RULE FOR CITY CHANGE (MANDATORY DOCTOR VOIDING & RE-SELECTION)" in prompt
    print(f"PASS: System prompt compiled successfully! Length: {len(prompt)} characters.")

if __name__ == "__main__":
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    test_extract_dental_concern()
    test_city_doctor_restrictions()
    test_city_change_doctor_invalidation()
    test_prompt_compilation()
    print("\n==========================================")
    print("ALL TESTS PASSED WITH 100% SUCCESS!")
    print("==========================================")
