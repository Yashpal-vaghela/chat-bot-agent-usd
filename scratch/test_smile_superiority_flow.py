import os
import sys
import asyncio
import django

sys.path.insert(0, os.path.abspath("."))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

from voice_agent.ai.conversation_manager import ConversationManager
from voice_agent.ai.prompt_builder import get_system_prompt
from voice_agent.retrieval.knowledge_loader import get_compiled_knowledge

class MockSession:
    def __init__(self):
        self.user_name = None
        self.user_concern = None
        self.consultation_agreed = False
        self.consultation_refused = False
        self.booking_slots = {"first_name": None, "last_name": None, "city": None, "doctor_name": None, "message": None, "phone": None}
        self.submission_id = None
        self.last_review_summary = None
        self.asking_for_field = None
        self.missing_field_reprompts = 0
        self.last_asked_field = None
        self.is_client_connected = True
        self.is_speaking = False

def test_smile_superiority_knowledge_and_prompts():
    print("=== TEST 1: Verify Knowledge Base Content ===")
    kb = get_compiled_knowledge(force_reload=True)
    assert "intent: smile_superiority" in kb
    assert "Beyond Good Smile - Good vs Superior Smile Philosophy" in kb
    assert "Just open your phone, take a photo of your smile" in kb
    assert "Could my smile look even more natural?" in kb
    assert "I completely understand, and I’m not saying your smile is bad." in kb
    assert "At USD, we believe there is a difference between good and superior." in kb
    assert "With more than 1 lakh smiles designed and over two decades of experience" in kb
    assert "1 लाख से अधिक स्माइल डिज़ाइन्स और दो दशकों" in kb
    assert "gums, your teeth, how much of your teeth are visible" in kb
    assert "Would you like to know how our philosophy works" in kb
    print("PASS: Knowledge base contains complete Beyond Good Smile structure.")

    print("=== TEST 2: Verify Master System Prompt Integration ===")
    prompt = get_system_prompt(force_reload=True)
    assert "SMILE SUPERIORITY & BEYOND GOOD SMILE" in prompt
    assert "ZERO-JUDGMENT MANDATE" in prompt
    assert "difference between good and superior" in prompt.lower()
    assert "1 लाख से अधिक स्माइल डिज़ाइन्स और दो दशकों" in prompt
    assert "photo of your smile" in prompt
    assert "NO DIRECT JUDGMENT ON USER SMILE" in prompt
    print("PASS: Master System Prompt and Safety Rules incorporate Smile Superiority.")

    print("=== TEST 3: Conversational Memory with Smile Superiority Statements ===")
    session = MockSession()
    manager = ConversationManager(session, None, None)

    # Turn 1: User gives their name
    manager.update_session_memory("नमस्ते, मेरा नाम आशीष है।")
    assert session.user_name in ["Ashish", "Asheesh"]

    # Turn 2: User says their smile is already good
    manager.update_session_memory("मेरी स्माइल तो पहले से ही अच्छी है, मुझे स्माइल डिजाइन की क्या जरूरत?")
    assert session.consultation_agreed is False, "Should not prematurely trigger consultation agree"
    assert session.asking_for_field is None or session.asking_for_field != "city"

    # Turn 3: User asks what superiority means
    manager.update_session_memory("superiority se aapka kya matlab hai?")
    assert session.user_name in ["Ashish", "Asheesh"], "User name must be retained"
    assert session.consultation_agreed is False, "Still in conversational education phase"

    print("PASS: Conversational session memory behaves correctly during Smile Superiority dialogue.")

    print("=== TEST 4: Verify Profession & Smile Connection Knowledge & Prompt ===")
    kb = get_compiled_knowledge(force_reload=True)
    assert "intent: profession_smile_connection" in kb
    assert "Profession and Smile Connection - Personalized Smile Design Philosophy" in kb
    assert "receptionist:" in kb and "welcome sign" in kb
    assert "salesperson:" in kb and "presentation" in kb
    assert "teacher:" in kb and "communication" in kb
    assert "doctor:" in kb and "trust and reassurance" in kb
    assert "lawyer:" in kb and "professional presence" in kb
    assert "architect:" in kb and "proportion + balance" in kb
    assert "engineer:" in kb and "engineered system" in kb
    assert "software_developer:" in kb and "complete system" in kb
    assert "founder:" in kb and "founder's personal brand" in kb

    prompt = get_system_prompt(force_reload=True)
    assert "PROFESSION & SMILE CONNECTION" in prompt
    assert "DENTIST PARTNER RECRUITMENT VS PATIENT MEDICAL PROFESSION" in prompt
    assert "DOCTOR AS A PATIENT PROFESSION" in prompt
    assert "PHILOSOPHY & EDUCATIONAL CONVERSATION PROGRESSION" in prompt
    assert "By the way, what do you do for work?" in prompt
    print("PASS: Profession, Doctor/Dentist distinction, and Philosophy rules verified in prompt.")

    print("=== TEST 5: Verify Language Detection Loyalty on Short Inputs ===")
    from voice_agent.ai.conversation_manager import detect_user_language
    
    # English conversation history with greeting containing "Namaste"
    history = [
        {"role": "model", "parts": [{"text": "Namaste! I am Riya USD Consultant, How can we assist you today? Let's start with your beautiful name, what is your name?"}]},
        {"role": "user", "parts": [{"text": "my name is nikhil"}]},
        {"role": "model", "parts": [{"text": "Hello Nikhil! What specific concern or issue are you experiencing with your teeth or smile?"}]},
        {"role": "user", "parts": [{"text": "i m experiance nothing i have good smile"}]},
        {"role": "model", "parts": [{"text": "I completely understand, Nikhil, and I’m not saying your smile is bad... Would you like to know how our philosophy works?"}]}
    ]
    
    assert detect_user_language("YES", history) == "en", "Short affirmation in English conversation must stay English"
    assert detect_user_language("yes", history) == "en"
    assert detect_user_language("ENGLISH PLEASE", history) == "en"
    assert detect_user_language("i m doctor", history) == "en"
    assert detect_user_language("i m an lawyer", history) == "en"
    assert detect_user_language("I want to know how your philosophy works", history) == "en"
    
    # Regional language tests
    assert detect_user_language("મારું નામ ભાવિન છે") == "gu"
    assert detect_user_language("હું સુરતમાં રહું છું") == "gu"
    assert detect_user_language("मेरा नाम राहुल है") == "hi"
    assert detect_user_language("माझे नाव सचिन आहे") == "mr"
    print("PASS: Language detection loyalty stays robust and never drifts into Marathi/Hindi on English inputs.")

    print("=== TEST 6: Verify Doctor and Lawyer Profession Handling in Session Memory ===")
    session = MockSession()
    manager = ConversationManager(session, None, None)
    
    # Patient Nikhil जोशी
    manager.update_session_memory("my name is nikhil")
    assert session.user_name == "Nikhil"
    
    # Patient shares profession
    manager.update_session_memory("i m doctor")
    assert session.user_name == "Nikhil", "Profession 'doctor' must not overwrite patient name"
    assert session.booking_slots["doctor_name"] in [None, ""], "Profession 'doctor' must not set doctor booking slot"
    assert session.consultation_agreed is False, "Profession sharing must not force consultation agree"
    
    # Patient changes profession statement
    manager.update_session_memory("oh sorry i write doctor i m an lawyer")
    assert session.user_name == "Nikhil", "Profession 'lawyer' must not overwrite patient name"
    assert session.consultation_agreed is False, "Lawyer profession must not force consultation agree"
    print("PASS: Doctor and Lawyer professions are cleanly handled without polluting booking slots or patient name.")

    print("\nALL SMILE SUPERIORITY, PROFESSION, AND LANGUAGE TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_smile_superiority_knowledge_and_prompts()

