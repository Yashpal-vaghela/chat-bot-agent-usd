import sys
import re
from voice_agent.utils.helpers import clean_assistant_text
from voice_agent.ai.prompt_builder import get_system_prompt

def test_terminology_cleanup():
    # 1. Gujarati: સ્મિત -> Smile, પ્રયોગશાળા -> Laboratory
    text_gu = "તમારી સ્મિત અને અમારી પ્રયોગશાળા ખૂબ સુંદર છે."
    cleaned_gu = clean_assistant_text(text_gu)
    print("GU Input :", text_gu)
    print("GU Output:", cleaned_gu)
    assert "Smile" in cleaned_gu, "Smile should replace સ્મિત"
    assert "Laboratory" in cleaned_gu, "Laboratory should replace પ્રયોગશાળા"
    assert "સ્મિત" not in cleaned_gu
    assert "પ્રયોગશાળા" not in cleaned_gu

    # 2. Hindi: मुस्कान -> Smile, प्रयोगशाला -> Laboratory
    text_hi = "आपकी मुस्कान बहुत प्यारी है, हमारी प्रयोगशाला में हर वेनियर तैयार होता है।"
    cleaned_hi = clean_assistant_text(text_hi)
    print("HI Input :", text_hi)
    print("HI Output:", cleaned_hi)
    assert "Smile" in cleaned_hi, "Smile should replace मुस्कान"
    assert "Laboratory" in cleaned_hi, "Laboratory should replace प्रयोगशाला"
    assert "मुस्कान" not in cleaned_hi
    assert "प्रयोगशाला" not in cleaned_hi

    # 3. Patient Name Preservation (ਨਾਮ / નામ: સ્મિત)
    text_name = "- નામ: સ્મિત પટેલ\n- ફોન: 9876543210"
    cleaned_name = clean_assistant_text(text_name)
    print("Name Output:", cleaned_name)
    assert "સ્મિત પટેલ" in cleaned_name, "Name should be preserved"

    print("✅ All terminology tests passed!")

def test_system_prompt_rules():
    sys_prompt = get_system_prompt(force_reload=True)
    # Check that fixed English terms are mentioned
    assert "FIXED IN ENGLISH: ALWAYS say \"Smile\"" in sys_prompt or "Smile" in sys_prompt
    assert "Laboratory" in sys_prompt
    assert "PRAYOGSHALA" in sys_prompt
    assert "SMIT" in sys_prompt
    assert "MUSKAAN" in sys_prompt
    # Check that one-time profession rule is in prompt
    assert "STRICTLY ONLY ONE TIME IN THE WHOLE CONVERSATION" in sys_prompt
    print("✅ All system prompt rules tests passed!")

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    test_terminology_cleanup()
    test_system_prompt_rules()
