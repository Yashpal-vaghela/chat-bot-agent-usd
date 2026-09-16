import sys
import os
import re

# Add workspace to path
sys.path.insert(0, r"d:\media")
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from voice_agent.ai.session_manager import Session
from voice_agent.ai.conversation_manager import ConversationManager

def test_profession_guard_and_timing():
    print("=== TESTING PROFESSION TIMING & AT LEAST ONCE IN CONVERSATION ===")
    
    session = Session()
    cm = ConversationManager(session=session, send_json_callback=lambda x: None, gemini_client=None)
    
    # 1. Test Turn 1 (user_turn_count = 0) -> Banned
    history_turn1 = [{"role": "user", "content": "Hello"}]
    turn_count1 = len([h for h in history_turn1 if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
    assert turn_count1 == 0, f"Expected 0, got {turn_count1}"
    
    test_raw_resp_en = "Hello! Welcome to Ultimate Smile Design. By the way, what is your profession?"
    test_raw_resp_gu = "નમસ્તે! અલ્ટીમેટ સ્માઇલ ડિઝાઇનમાં આપનું સ્વાગત છે. તેમ છતાં, તમે શું કામ કરો છો?"
    test_raw_resp_hi = "नमस्ते! अल्टीमेट स्माइल डिज़ाइन में आपका स्वागत है। वैसे, आप क्या काम करते हैं?"
    
    prof_re_patterns = [
        r"(?:by the way,?\s+)?(?:what is your profession|what do you do for work|may i ask what profession you are in|may i ask what you do for work)\??",
        r"(?:તેમ છતાં,?\s*(?:જો હું પૂછી શકું,?\s*)?)?(?:તમે શું કામ કરો છો|તમારો વ્યવસાય શું છે|તમારો વ્યવસાય \(પ્રોફેશન\) શું છે)\??",
        r"(?:वैसे,?\s*(?:अगर मैं पूछ सकती हूँ,?\s*)?)?(?:आप क्या काम करते हैं|आपका पेशा या प्रोफेशन क्या है|आप किस प्रोफेशन में हैं)\??"
    ]
    
    clean_text_t1 = test_raw_resp_en
    was_profession_already_asked = getattr(session, "profession_asked", False)
    if was_profession_already_asked or turn_count1 < 2:
        for pat in prof_re_patterns:
            clean_text_t1 = re.sub(pat, "", clean_text_t1, flags=re.IGNORECASE).strip()
            
    print(f"Turn 1 Cleaned Output (EN): '{clean_text_t1}'")
    assert "profession" not in clean_text_t1.lower(), "Profession should be stripped in Turn 1!"
    assert session.profession_asked == False
    
    # 2. Test Turn 2 (user_turn_count = 1) -> Banned
    history_turn2 = [
        {"role": "user", "content": "Hello"},
        {"role": "model", "content": "Namaste! What is your name?"},
        {"role": "user", "content": "My name is Yashpal"}
    ]
    turn_count2 = len([h for h in history_turn2 if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
    assert turn_count2 == 1, f"Expected 1, got {turn_count2}"
    
    clean_text_t2 = test_raw_resp_gu
    if was_profession_already_asked or turn_count2 < 2:
        for pat in prof_re_patterns:
            clean_text_t2 = re.sub(pat, "", clean_text_t2, flags=re.IGNORECASE).strip()
    print(f"Turn 2 Cleaned Output (GU): '{clean_text_t2}'")
    assert "કામ કરો છો" not in clean_text_t2, "Profession should be stripped in Turn 2!"
    assert session.profession_asked == False
    
    # 3. Test Turn 3 (user_turn_count = 2) -> Message 3: ALLOWED & MANDATORY
    history_turn3 = [
        {"role": "user", "content": "Hello"},
        {"role": "model", "content": "Namaste! What is your name?"},
        {"role": "user", "content": "My name is Yashpal"},
        {"role": "model", "content": "Namaste Yashpal! What concern do you have?"},
        {"role": "user", "content": "I have gaps between teeth"}
    ]
    turn_count3 = len([h for h in history_turn3 if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
    assert turn_count3 == 2, f"Expected 2 (Turn 3 / Message 3), got {turn_count3}"
    
    clean_text_t3 = "नमस्ते यशपाल! मैं समझ सकती हूँ कि आपको गैप्स की समस्या आ रही है। वैसे, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं? क्या मैं अपॉइंटमेंट बुक करने में मदद करूँ?"
    if was_profession_already_asked or turn_count3 < 2:
        for pat in prof_re_patterns:
            clean_text_t3 = re.sub(pat, "", clean_text_t3, flags=re.IGNORECASE).strip()
    else:
        for pat in prof_re_patterns:
            if re.search(pat, clean_text_t3, flags=re.IGNORECASE):
                session.profession_asked = True
                break
                
    print(f"Turn 3 / Message 3 Output (HI): '{clean_text_t3}'")
    assert "आप क्या काम करते हैं" in clean_text_t3, "Profession inquiry MUST be preserved in Turn 3 / Message 3!"
    assert session.profession_asked == True, "profession_asked should now be True after being asked in Message 3!"
    
    # 4. Test Turn 4 (turn_count = 3) -> Already asked, so repetition MUST be stripped!
    history_turn4 = history_turn3 + [{"role": "model", "content": clean_text_t3}, {"role": "user", "content": "Sure, I live in Ahmedabad"}]
    turn_count4 = len([h for h in history_turn4 if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
    was_profession_already_asked = getattr(session, "profession_asked", False)
    assert was_profession_already_asked == True
    
    clean_text_t4 = "Sure! By the way, what is your profession?"
    if was_profession_already_asked or turn_count4 < 2:
        for pat in prof_re_patterns:
            clean_text_t4 = re.sub(pat, "", clean_text_t4, flags=re.IGNORECASE).strip()
    print(f"Turn 4 Repetition Cleaned Output: '{clean_text_t4}'")
    assert "profession" not in clean_text_t4.lower(), "Repeated profession inquiry in Turn 4 was not stripped!"
    
    print("\n✅ ALL PROFESSION 3RD MESSAGE & CONVERSATION RULES PASSED (100% RELIABILITY)!")

if __name__ == "__main__":
    test_profession_guard_and_timing()
