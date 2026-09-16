import os
import sys
import django

# Setup Django environment
sys.path.insert(0, r"d:\media")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from voice_agent.utils.helpers import clean_assistant_text, extract_slots_from_review_summary
from voice_agent.services.appointment_service import is_matched_doctor
from voice_agent.ai.conversation_manager import find_doctor_in_text, get_city_for_doctor
from voice_agent.ai.prompt_builder import get_system_prompt

def test_disclaimer_removal():
    print("--- Test 1: Medical Disclaimer Scrubbing ---")
    
    # 1. Gujarati disclaimer from user prompt transcript
    guj_input = "હું સમજી શકું છું કે તમને વાંકાચૂંકા દાંતની સમસ્યા છે, નિખિલ. શું હું આના માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું? અમે તમને કોઈ તબીબી સલાહ કે નિદાન આપતા નથી. કૃપા કરીને કોઈ મદદ માટે ડૉક્ટરને મળો."
    cleaned_guj = clean_assistant_text(guj_input)
    assert "તબીબી સલાહ" not in cleaned_guj, f"Failed: Gujarati disclaimer still present! Output: {cleaned_guj}"
    assert "નિદાન આપતા નથી" not in cleaned_guj, f"Failed: Gujarati disclaimer still present! Output: {cleaned_guj}"
    print("[PASS] Gujarati disclaimer scrubbed cleanly.")

    # 2. Hindi disclaimer
    hin_input = "नमस्ते निखिल! हम आपको कोई चिकित्सीय सलाह या निदान नहीं दे रहे हैं। कृपया डॉक्टर से संपर्क करें। क्या हम आपकी अपॉइंटमेंट बुक करें?"
    cleaned_hin = clean_assistant_text(hin_input)
    assert "चिकित्सीय सलाह" not in cleaned_hin, f"Failed: Hindi disclaimer still present! Output: {cleaned_hin}"
    assert "डॉक्टर से संपर्क करें" not in cleaned_hin, f"Failed: Hindi disclaimer still present! Output: {cleaned_hin}"
    print("[PASS] Hindi disclaimer scrubbed cleanly.")

    # 3. English disclaimer
    eng_input = "I can definitely help book your consultation. Please note that I do not provide medical advice or diagnosis. Please consult a qualified dentist for diagnosis. May I have your phone number?"
    cleaned_eng = clean_assistant_text(eng_input)
    assert "medical advice" not in cleaned_eng.lower(), f"Failed: English disclaimer still present! Output: {cleaned_eng}"
    assert "May I have your phone number?" in cleaned_eng, f"Failed: Good text was lost! Output: {cleaned_eng}"
    print("[PASS] English disclaimer scrubbed cleanly.")

def test_system_prompts():
    print("\n--- Test 2: System Prompts & Mandates ---")
    prompt = get_system_prompt(force_reload=True)
    
    # Check Zero-Disclaimer Mandate
    assert "ABSOLUTE ZERO-DISCLAIMER MANDATE" in prompt, "Failed: Zero-Disclaimer Mandate missing from system prompt!"
    print("[PASS] Absolute Zero-Disclaimer Mandate present in prompt.")

    # Check Dynamic Workflow Entry Point
    assert "DYNAMIC WORKFLOW ENTRY POINT" in prompt, "Failed: Dynamic Workflow Entry Point missing from system prompt!"
    print("[PASS] Dynamic Workflow Entry Point present in prompt.")

    # Check Step 4 Immediate Doctor-City Validation
    assert "CRITICAL IMMEDIATE DOCTOR-CITY VALIDATION" in prompt or "REFUSE IMMEDIATELY AT STEP 4" in prompt, "Failed: Step 4 Doctor-City validation mandate missing!"
    print("[PASS] Step 4 Doctor-City Immediate Validation present in prompt.")

def test_doctor_city_validation():
    print("\n--- Test 3: Doctor-City Validation & Mismatch Protection ---")

    # Janu Shah is in Ahmedabad ONLY
    assert get_city_for_doctor("Dr. Janu Shah") == "Ahmedabad", "Janu Shah home city mismatch"
    
    # 1. Searching for Janu Shah in Mumbai MUST return None
    doc_mumbai = find_doctor_in_text("I want Dr. Janu Shah", city="Mumbai")
    assert doc_mumbai is None, f"Expected None for Janu Shah in Mumbai, got: {doc_mumbai}"
    print("[PASS] find_doctor_in_text correctly refused Dr. Janu Shah for Mumbai.")

    # 2. Searching in Ahmedabad returns Dr. Janu Shah
    doc_ahmedabad = find_doctor_in_text("I want Dr. Janu Shah", city="Ahmedabad")
    assert doc_ahmedabad == "Dr. Janu Shah", f"Expected Dr. Janu Shah, got: {doc_ahmedabad}"
    print("[PASS] find_doctor_in_text correctly matched Dr. Janu Shah for Ahmedabad.")

    # 3. Hindi/Devanagari search for Dr. Janu Shah in Mumbai
    doc_hin_mumbai = find_doctor_in_text("मुझे जानू शाह से ट्रीटमेंट करवानी है", city="Mumbai")
    assert doc_hin_mumbai is None, f"Expected None for Devanagari Janu Shah in Mumbai, got: {doc_hin_mumbai}"
    print("[PASS] Devanagari Janu Shah refused for Mumbai.")

    # 4. Hindi/Devanagari search for Dr. Janu Shah in Ahmedabad
    doc_hin_ahm = find_doctor_in_text("मुझे जानू शाह से ट्रीटमेंट करवानी है", city="Ahmedabad")
    assert doc_hin_ahm == "Dr. Janu Shah", f"Expected Dr. Janu Shah, got: {doc_hin_ahm}"
    print("[PASS] Devanagari Janu Shah accepted for Ahmedabad.")

    # 5. Doctor in Mumbai (Dr. Vinita Tekchandani)
    doc_vinita_mum = find_doctor_in_text("Dr. Vinita Tekchandani", city="Mumbai")
    assert doc_vinita_mum == "Dr. Vinita Tekchandani", f"Expected Dr. Vinita Tekchandani for Mumbai, got: {doc_vinita_mum}"
    print("[PASS] Dr. Vinita Tekchandani accepted for Mumbai.")

    # 6. Extract slots from review summary: Janu Shah in Mumbai must be dropped
    summary_mismatch = """
    Patient Name: Nikhil Joshi
    City: Mumbai
    Doctor: Dr. Janu Shah
    Phone: 9876543210
    Concern: Crooked teeth
    """
    slots = extract_slots_from_review_summary(summary_mismatch)
    assert "doctor_name" not in slots or not slots.get("doctor_name"), f"Doctor should be stripped from mismatched summary, but found: {slots.get('doctor_name')}"
    assert slots.get("city") == "Mumbai", f"City should be Mumbai, got: {slots.get('city')}"
    print("[PASS] extract_slots_from_review_summary stripped mismatched doctor.")

def test_session_memory_flow():
    print("\n--- Test 4: ConversationManager Session Memory & Mismatch Flow ---")
    from voice_agent.ai.conversation_manager import ConversationManager

    class MockSession:
        def __init__(self):
            self.user_name = ""
            self.user_concern = ""
            self.booking_slots = {"first_name": "", "last_name": "", "city": "", "doctor_name": "", "phone": "", "message": ""}
            self.city_doctor_mismatch = None
            self.pending_doctor_candidate = None
            self.unsupported_city = None
            self.last_uncertified_doctor = None
            self.last_invalid_phone_input = None
            self.slot_just_updated = False
            self.city_just_changed = False
            self.asking_for_field = None
            self.latest_client_history = []

    cm = ConversationManager(MockSession(), lambda x: None, None)

    # Turn 1: User says name
    cm.update_session_memory("Nikhil Joshi", [])
    assert cm.session.user_name == "Nikhil Joshi", f"Expected Nikhil Joshi, got {cm.session.user_name}"
    assert cm.session.booking_slots["first_name"] == "Nikhil"
    assert cm.session.booking_slots["last_name"] == "Joshi"
    print("[PASS] Name remembered: Nikhil Joshi.")

    # Turn 2: User says dental concern in Gujarati
    cm.update_session_memory("I just too many koi mara daat se nibha chuka hai vanka chuka", [])
    assert cm.session.user_concern is not None, "Expected user concern to be extracted"
    print(f"[PASS] Concern remembered: {cm.session.user_concern}.")

    # Turn 3: User picks city Mumbai
    cm.update_session_memory("Mumbai", [])
    assert cm.session.booking_slots.get("city") == "Mumbai", f"Expected Mumbai, got {cm.session.booking_slots.get('city')}"
    print("[PASS] City remembered: Mumbai.")

    # Turn 4: User asks for Dr. Janu Shah (Ahmedabad only!)
    cm.update_session_memory("Dr. Janu Shah", [])
    assert cm.session.city_doctor_mismatch is not None, "Expected city_doctor_mismatch to be set!"
    assert cm.session.city_doctor_mismatch["doctor"] == "Dr. Janu Shah"
    assert cm.session.city_doctor_mismatch["doctor_city"] == "Ahmedabad"
    assert cm.session.city_doctor_mismatch["user_city"] == "Mumbai"
    assert not cm.session.booking_slots.get("doctor_name"), f"Doctor should be empty string on mismatch, got {cm.session.booking_slots.get('doctor_name')}"
    print("[PASS] Doctor-City mismatch caught immediately: Janu Shah (Ahmedabad) refused for Mumbai.")

    # Turn 5: User picks Mumbai certified doctor (Dr. Vinita Tekchandani)
    cm.update_session_memory("Dr. Vinita Tekchandani", [])
    assert cm.session.booking_slots.get("doctor_name") == "Dr. Vinita Tekchandani"
    assert cm.session.city_doctor_mismatch is None
    print("[PASS] Local doctor accepted: Dr. Vinita Tekchandani for Mumbai.")

if __name__ == "__main__":
    test_disclaimer_removal()
    test_system_prompts()
    test_doctor_city_validation()
    test_session_memory_flow()
    print("\nALL TESTS PASSED SUCCESSFULLY!")

