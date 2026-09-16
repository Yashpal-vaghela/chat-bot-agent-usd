import os
import sys
import django

sys.path.insert(0, r"d:\media")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hm.settings")
django.setup()

from voice_agent.ai.conversation_manager import extract_certified_city_from_text, find_doctor_in_text, ConversationManager
from voice_agent.ai.session_manager import Session

turns = [
    'my name is sardaar vallabh bhai patel',
    'do you know me i m steel man of india',
    'do you know iron man',
    'do you marvel charecter also have iron m an',
    'maare enhanch smile joti se',
    'haan',
    'tamane to khabar hovi joi ne',
    'enhanch karvi se smile',
    'haan',
    'dalal saathe',
    'deepika dalal saathe',
    'dr dipika dalal'
]

async def main():
    session = Session()
    async def dummy_send_json(data):
        pass
    mgr = ConversationManager(session=session, send_json_callback=dummy_send_json, gemini_client=None)

    history = []
    for i, t in enumerate(turns):
        c = extract_certified_city_from_text(t)
        d = find_doctor_in_text(t)
        mgr.update_session_memory(t, history=history)
        print(f"Turn {i+1}: '{t}'")
        print(f"  -> Extracted City: {c}, Doctor: {d}")
        print(f"  -> Session User Name: {mgr.session.user_name}")
        print(f"  -> Session Slots: {mgr.session.booking_slots}")
        print(f"  -> Asking Field: {getattr(mgr.session, 'asking_for_field', None)}")
        print(f"  -> City Doctor Mismatch: {getattr(mgr.session, 'city_doctor_mismatch', None)}")
        print(f"  -> Last Uncertified Doctor: {getattr(mgr.session, 'last_uncertified_doctor', None)}")
        print("-" * 50)
        history.append({"role": "user", "parts": [{"text": t}]})
        history.append({"role": "model", "parts": [{"text": "dummy response"}]})

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
