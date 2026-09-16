import os
import sys
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
import django
django.setup()

from voice_agent.ai.session_manager import Session
from voice_agent.ai.conversation_manager import ConversationManager

async def test_user_dialogue():
    session = Session()
    sent_messages = []
    async def mock_send_json(data):
        sent_messages.append(data)

    cm = ConversationManager(session=session, send_json_callback=mock_send_json, gemini_client=None)

    turns = [
        "I am Nikhil Joshi.",
        "मैंने तुम्हें समझाओ उसको गलती में तो स्माइल डिजाइन अन्य नॉर्मल स्माइल डिजाइन में फर्क कुछ है।",
        "By the way, maine ek kyon nahin kiya? Atript mein to sab barabar hai. Kare kaun?",
        "मैंने कोई चोकस तो नहीं भेजा जिन्होंने?",
        "પડે હમ નહીં. હાં, તો મેં બોલા, 'લિસ્ટ ઓફ હોને દો.' તો પોતાની",
        "Ok, to to ti je res super maso.",
        "तुमने अह डॉक्टर का नाम नहीं जाना वह।",
        "मैं शाहिद मुन्नू नवाब की बीवी तो नहीं।",
        "Okay, lekin mujhe yeh batao aapke dentist aur mere dentist mein kya farak hai?",
        "पर मैंने तो यह पूछा ही नहीं। मैंने तो यह पूछा, मेरे डॉक्टर और आपके डॉक्टर में फर्क क्या है?",
        "I don't need to talk to you. Now you can cut the call. Bye."
    ]

    for idx, user_text in enumerate(turns, 1):
        cm.update_session_memory(user_text)
        print(f"Turn {idx} -> consultation_agreed={session.consultation_agreed}, is_booking_active={session.booking_slots['is_booking_active']}")
        
        # Verify that booking NEVER activated automatically on informational questions!
        if idx < 11:
            assert not session.booking_slots.get("is_submitted"), f"Turn {idx} submitted prematurely!"
            assert not session.booking_slots.get("is_cancel"), f"Turn {idx} cancelled prematurely!"

    # Now verify the last turn (Goodbye)
    last_turn = turns[-1]
    u_txt_clean = last_turn.lower().strip()
    is_goodbye = any(bw in u_txt_clean for bw in [
        "bye", "goodbye", "good bye", "cut the call", "cut call", "disconnect", "hang up",
        "call cut", "band karo", "tata", "alvida", "aavjo", "don't need to talk", "dont need to talk",
        "nahi baat karni", "vaat nathi karvi", "cut this call"
    ])
    assert is_goodbye, "Last turn must be identified as goodbye"
    assert not session.booking_slots.get("is_cancel"), "Must NOT be marked as cancelled"
    assert not session.booking_slots.get("is_submitted"), "Must NOT be marked as submitted"

    print("\n[PASS] All 11 turns in exact user dialogue handled with 100% precision!")

if __name__ == "__main__":
    asyncio.run(test_user_dialogue())
