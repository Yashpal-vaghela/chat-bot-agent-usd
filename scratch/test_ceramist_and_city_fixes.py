import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.abspath("."))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from voice_agent.utils.helpers import (
    is_submit_review_summary,
    extract_slots_from_review_summary,
    ALL_CERTIFIED_DOCTORS_LIST,
    DOCTOR_HOME_CITIES
)
from voice_agent.services.appointment_service import is_matched_doctor
from voice_agent.ai.conversation_manager import (
    find_doctor_in_text,
    detect_uncertified_doctor,
    ConversationManager
)
from voice_agent.ai.prompt_builder import get_system_prompt

class MockSession:
    def __init__(self):
        self.user_name = ""
        self.user_concern = ""
        self.consultation_agreed = False
        self.booking_slots = {
            "first_name": "", "last_name": "", "email": "--",
            "phone": "", "city": "", "message": "", "doctor_name": "",
            "is_booking_active": False, "is_submitted": False
        }
        self.unsupported_city = None
        self.slot_just_updated = False
        self.city_just_changed = False
        self.asking_for_field = None
        self.pending_doctor_candidate = None
        self.last_uncertified_doctor = None
        self.city_doctor_mismatch = None
        self.last_invalid_phone_input = None
        self.last_review_summary_slots = {}
        self.last_review_summary_text = ""

def test_ceramist_and_city_fixes():
    print("=== TEST 1: is_matched_doctor placeholder & ceramist rejection ===")
    assert is_matched_doctor("मुंबई में हमारे डॉक्टर हैं", city="Mumbai") == "", "Should reject placeholder"
    assert is_matched_doctor("Dr. मुंबई में हमारे डॉक्टर हैं", city="Mumbai") == "", "Should reject placeholder with Dr."
    assert is_matched_doctor("हमारे डॉक्टर", city="Mumbai") == "", "Should reject 'हमारे डॉक्टर'"
    assert is_matched_doctor("Master Ceramist", city="Mumbai") == "", "Should reject 'Master Ceramist'"
    assert is_matched_doctor("Haresh Savani", city="Surat") == "", "Should reject 'Haresh Savani'"
    assert is_matched_doctor("हरेश सवाणी", city="Surat") == "", "Should reject 'हरेश सवाणी'"
    assert is_matched_doctor("Dr. Vinita Tekchandani", city="Mumbai") == "Dr. Vinita Tekchandani", "Should match Dr. Vinita in Mumbai"
    print("PASS: Test 1")

    print("=== TEST 2: is_submit_review_summary rejects placeholder doctor ===")
    summary_with_placeholder = """
बहुत बढ़िया! आपके सभी विवरण दर्ज कर लिए गए हैं:
- नाम: Nikhil Joshi
- फ़ोन: 9876543210
- शहर: Mumbai
- समस्या: smile makeover
- डॉक्टर: मुंबई में हमारे डॉक्टर हैं

कृपया इस अपॉइंटमेंट अनुरोध को भेजने के लिए 'submit' कहें या रद्द करने के लिए 'cancel' कहें।
"""
    assert not is_submit_review_summary(summary_with_placeholder), "Summary with placeholder doctor should NOT be valid submit summary"

    valid_summary = """
बहुत बढ़िया! आपके सभी विवरण दर्ज कर लिए गए हैं:
- नाम: Nikhil Joshi
- फ़ोन: 9876543210
- शहर: Mumbai
- समस्या: smile makeover
- डॉक्टर: Dr. Vinita Tekchandani

कृपया इस अपॉइंटमेंट अनुरोध को भेजने के लिए 'submit' कहें या रद्द करने के लिए 'cancel' कहें।
"""
    assert is_submit_review_summary(valid_summary), "Valid summary should be accepted"
    print("PASS: Test 2")

    print("=== TEST 3: extract_slots_from_review_summary drops placeholder doctor ===")
    extracted = extract_slots_from_review_summary(summary_with_placeholder)
    assert extracted.get("city") == "Mumbai", f"City should be Mumbai, got {extracted.get('city')}"
    assert extracted.get("phone") == "9876543210", f"Phone should be 9876543210, got {extracted.get('phone')}"
    assert "doctor_name" not in extracted or not extracted["doctor_name"], f"doctor_name should be absent or empty, got {extracted.get('doctor_name')}"
    print(f"Extracted slots: {extracted}")
    print("PASS: Test 3")

    print("=== TEST 4: find_doctor_in_text with ceramist phrases ===")
    assert find_doctor_in_text("Master Ceramist", city="Mumbai") is None, "Ceramist should not match doctor"
    assert find_doctor_in_text("क्या आप मास्टर सिरामिस्ट से मिलना चाहते हैं", city="Mumbai") is None, "Hindi ceramist should not match doctor"
    assert find_doctor_in_text("Haresh Savani", city="Surat") is None, "Haresh Savani should not match Dr. Viren K Savani"
    assert find_doctor_in_text("Dr. Vinita Tekchandani", city="Mumbai") == "Dr. Vinita Tekchandani", "Dr. Vinita should match"
    print("PASS: Test 4")

    print("=== TEST 5: update_session_memory city retention & ceramist ===")
    session = MockSession()
    manager = ConversationManager(session, None, None)

    # Turn 1: User gives name and city
    manager.update_session_memory("हमारा नाम निखिल जोशी है और मैं अभी मुंबई में हूं")
    assert session.user_name in ["Nikhil Joshi", "Nikhil Joshee"], f"Expected Nikhil Joshi, got {session.user_name}"
    assert session.booking_slots["city"] == "Mumbai", f"Expected Mumbai, got {session.booking_slots.get('city')}"

    # Turn 2: User asks about ceramist
    manager.update_session_memory("Ha bhai batao na Mumbai mein ceramist kaun hai")
    assert session.booking_slots["city"] == "Mumbai", f"City must be retained as Mumbai, got {session.booking_slots.get('city')}"
    assert not session.booking_slots.get("doctor_name"), f"Doctor should not be set, got {session.booking_slots.get('doctor_name')}"

    # Turn 3: User confirms general response
    manager.update_session_memory("Haa bilkul bhai batao")
    assert session.booking_slots["city"] == "Mumbai", f"City must remain Mumbai, got {session.booking_slots.get('city')}"

    print("PASS: Test 5")

    print("=== TEST 6: Prompt Master Directive contains all required mandates ===")
    sys_prompt = get_system_prompt(force_reload=True)
    assert "MASTER CERAMIST VS USD CERTIFIED SMILE DESIGNER" in sys_prompt
    assert "AI SMILE CONSULTANT FIRST" in sys_prompt
    assert "STRICT BAN ON PLACEHOLDER DOCTORS" in sys_prompt
    assert "ZERO RE-ASKING & PERMANENT CITY MEMORY" in sys_prompt
    assert "SURNAME AND SECOND NAME ARE STRICTLY NOT COMPULSORY (JUST LIKE EMAIL)" in sys_prompt
    print("PASS: Test 6")

    print("=== TEST 7: Surname / Second name is NOT compulsory (like email) ===")
    # 7a: Single name input to session memory
    s_single = MockSession()
    mgr_single = ConversationManager(s_single, None, None)
    mgr_single.update_session_memory("हमारा नाम निखिल है")
    assert s_single.booking_slots["first_name"] == "Nikhil", f"Expected first_name 'Nikhil', got {s_single.booking_slots.get('first_name')}"
    assert s_single.booking_slots["last_name"] == "-", f"Expected last_name '-', got {s_single.booking_slots.get('last_name')}"
    assert s_single.user_name == "Nikhil", f"Expected user_name 'Nikhil', got {s_single.user_name}"
    assert s_single.asking_for_field != "name", f"Asking for field should not be 'name', got {s_single.asking_for_field}"

    # 7b: Single name extraction from review summary
    single_name_summary = """
    - દર્દીનું નામ: નિખિલ
    - શહેર: Mumbai
    - ડૉક્ટર: Dr. Vinita Tekchandani
    - ફોન: 9876543210
    - સમસ્યા: Smile makeover
    """
    extracted_single = extract_slots_from_review_summary(single_name_summary)
    assert extracted_single.get("first_name") == "Nikhil", f"Expected 'Nikhil', got {extracted_single.get('first_name')}"
    assert extracted_single.get("last_name") == "-", f"Expected '-', got {extracted_single.get('last_name')}"
    assert extracted_single.get("user_name") == "Nikhil", f"Expected 'Nikhil', got {extracted_single.get('user_name')}"
    print("PASS: Test 7")

    print("=== TEST 8: Consultation Permission Gate & In-Place ID Updates/Cancels ===")
    # 8a: Permission gate behavior
    s_gate = MockSession()
    mgr_gate = ConversationManager(s_gate, None, None)
    mgr_gate.update_session_memory("मेरा नाम आशुतोष है")
    assert s_gate.user_name == "Ashutosh"
    assert s_gate.consultation_agreed is False

    mgr_gate.update_session_memory("मुझे स्माइल डिजाइन करवानी है")
    assert s_gate.user_concern is not None
    assert s_gate.consultation_agreed is False, "Must not agree until user affirms"

    mgr_gate.update_session_memory("हाँ")
    assert s_gate.consultation_agreed is True, "Must agree after affirmation"

    # 8b: Prompt checks
    sys_p = get_system_prompt(force_reload=True)
    assert "MANDATORY CONSULTATION PERMISSION GATE" in sys_p
    assert "STRICT BAN ON BUNDLING" in sys_p
    assert "SAME SUBMISSION ID ON EDIT / CANCEL" in sys_p or "SAME SUBMISSION ID FOR EDITS & CANCELLATIONS" in sys_p

    # 8c: Async in-place DB edit & cancellation on same ID
    import asyncio
    from voice_agent.services.appointment_service import submit_consultation_appointment

    async def run_submission_test():
        # First submission
        res1 = await submit_consultation_appointment({
            "first_name": "Ashutosh",
            "last_name": "-",
            "phone": "7984256299",
            "city": "Gurugram",
            "doctor_name": "Dr. Amit Kr. Agrawal",
            "message": "smile design",
        })
        sub_id = res1.get("details", {}).get("id") or res1.get("details", {}).get("submission_id")
        assert sub_id, f"Expected submission ID, got {res1}"

        # Second submission (Update doctor/message)
        res2 = await submit_consultation_appointment({
            "first_name": "Ashutosh",
            "last_name": "-",
            "phone": "7984256299",
            "city": "Gurugram",
            "doctor_name": "Dr. Amit Kr. Agrawal",
            "message": "smile design updated",
            "submission_id": sub_id,
            "id": sub_id
        })
        sub_id2 = res2.get("details", {}).get("id") or res2.get("details", {}).get("submission_id")
        assert sub_id2 == sub_id, f"Expected same ID {sub_id}, got {sub_id2}"

        # Third submission (Cancellation)
        res3 = await submit_consultation_appointment({
            "first_name": "Ashutosh",
            "last_name": "-",
            "phone": "7984256299",
            "city": "Gurugram",
            "doctor_name": "Dr. Amit Kr. Agrawal",
            "message": "smile design",
            "submission_id": sub_id,
            "id": sub_id,
            "is_cancel": True
        })
        sub_id3 = res3.get("details", {}).get("id") or res3.get("details", {}).get("submission_id")
        assert sub_id3 == sub_id, f"Expected same ID {sub_id} on cancel, got {sub_id3}"
        assert res3.get("details", {}).get("is_cancel") is True
        assert res3.get("details", {}).get("is_cancel") is True

    asyncio.run(run_submission_test())
    print("PASS: Test 8")

    print("=== TEST 9: Smile Superiority Intent & Beyond Good Smile Knowledge Base ===")
    from voice_agent.retrieval.knowledge_loader import get_compiled_knowledge
    compiled_kb = get_compiled_knowledge(force_reload=True)
    assert "intent: smile_superiority" in compiled_kb, "intent: smile_superiority must be in compiled KB"
    assert "Beyond Good Smile" in compiled_kb, "Beyond Good Smile must be in compiled KB"
    assert "Could my smile look even more natural?" in compiled_kb
    assert "difference between good and superior" in compiled_kb
    assert "more than 1 lakh smiles designed and over two decades of experience" in compiled_kb
    assert "proportions and alignment" in compiled_kb
    assert "Would you like to know how our philosophy works" in compiled_kb

    sys_p2 = get_system_prompt(force_reload=True)
    assert "SMILE SUPERIORITY & BEYOND GOOD SMILE" in sys_p2
    assert "Could my smile look even more natural?" in sys_p2
    assert "ZERO-JUDGMENT" in sys_p2
    assert "more than 1 lakh smiles designed and over two decades of experience" in sys_p2
    assert "gums, your teeth" in sys_p2
    print("PASS: Test 9")

    print("\nALL CERAMIST, CITY RETENTION, PERMISSION GATE, SAME-ID & SMILE SUPERIORITY TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_ceramist_and_city_fixes()



