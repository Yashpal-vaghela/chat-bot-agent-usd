import sys
import os

# Add workspace to path
sys.path.insert(0, r"d:\media")
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from voice_agent.utils.helpers import is_cancel_submit, is_cancel_response_text
from voice_agent.ai.session_manager import Session

def test_cancel_spelling_variants():
    print("=== TESTING CANCEL TYPOS & SPELLING VARIANTS ===")
    
    session = Session()
    
    # 1. Test specific user-mentioned typos: cancsal, cencil
    user_typos = [
        "cancsal", "cencil", "cancle", "cansal", "cansel", "cancl", "cancil", "cencel", "cencle", "cencal",
        "kancel", "kancle", "kansal", "kansel", "kencil", "cacel", "cncel", "cncil", "cncl", "canel",
        "cancal", "camcel", "cnacel", "cancelling", "canceld", "cancled", "cancelled", "cancelation",
        "cancellation", "censal", "censel", "cancell", "cencill", "cancsl", "cancsel", "cancles",
        "cancels", "cancele", "canclled", "cancield", "cancellled", "kensil", "kensal", "kencl",
        "kensel", "kancil", "kencle", "kencal", "cancul", "cencul", "cansul", "kensul", "cance",
        "casel", "canxcel", "canxel", "cenceld", "kanseld", "cencild", "kancelled", "cancledd", "cancelld"
    ]
    
    for typo in user_typos:
        assert is_cancel_submit(typo, session), f"Failed to detect cancel for typo: '{typo}'"
        print(f" [PASS] '{typo}' -> Detected as Cancel")
        
    # 2. Test multi-word combinations with typos
    phrases = [
        "cancsal karo", "cancsal kar do", "cancsal kardo", "cancsal karvi", "cancsal karvu",
        "cencil karo", "cencil kar do", "cencil kardo", "cencil karvi", "cencil karvu",
        "cancle karo", "cancle kar do", "cancle kardo", "cancle karvi", "cancle karvu",
        "cansal karo", "cansal kar do", "cansal kardo", "cansal karvi", "cansal karvu",
        "kancel karo", "kancel kar do", "kancel kardo", "kancel karvi", "kancel karvu",
        "cancsal kari dyo", "cancsal kari do", "cencil kari dyo", "cencil kari do",
        "cancle kari nakho", "cancsal kari nakho", "cencil kari nakho",
        "please cancsal", "please cencil", "cancsal appointment", "cencil appointment",
        "cancsal my booking", "cencil my booking", "drop appointment", "stop booking",
        "નથી કરવું", "ના કરશો", "કેન્સલ કરો", "રદ કરો", "कैंसिल करो", "रद्द करो"
    ]
    
    for p in phrases:
        assert is_cancel_submit(p, session), f"Failed to detect cancel for phrase: '{p}'"
        print(f" [PASS] '{p}' -> Detected as Cancel")
        
    # 3. Test negative cases (should NOT be detected as cancel)
    neg_cases = [
        "don't cancel", "dont cancel", "not cancel",
        "change phone number", "update city", "mare city badalvi chhe",
        "my name is Bhavin", "I want smile design", "submit", "yes", "okay",
        "कैंसिल मत करो", "કેન્સલ નથી કરવું"
    ]
    
    for n in neg_cases:
        assert not is_cancel_submit(n, session), f"Falsely detected cancel for: '{n}'"
        print(f" [PASS] Negative case '{n}' correctly NOT detected as cancel")
        
    # 4. Test cancel response text detection
    bot_responses = [
        "Your appointment request has been cancelled.",
        "તમારી અપૉઇન્ટમેન્ટ રિક્વેસ્ટ કેન્સલ કરવામાં આવી છે.",
        "आपका अपॉइंटमेंट अनुरोध रद्द कर दिया गया है।",
        "तुमची अपॉइंटमेंट विनंती रद्द करण्यात आली आहे.",
        "আপনার অ্যাপয়েন্টমেন্টের অনুরোধ বাতিল করা হয়েছে।"
    ]
    for br in bot_responses:
        assert is_cancel_response_text(br), f"Failed to detect bot cancel response: '{br}'"
        print(f" [PASS] Bot response '{br[:30]}...' -> Detected")
        
    print("\n✅ ALL CANCEL TYPOS & SPELLING TESTS PASSED (100% RELIABILITY)!")

if __name__ == "__main__":
    test_cancel_spelling_variants()
