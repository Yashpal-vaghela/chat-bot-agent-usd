import asyncio
import websockets
import json

async def test_live_profession_flow():
    uri = 'ws://127.0.0.1:8000/ws/voice-agent/'
    async with websockets.connect(uri) as ws:
        print("Connected to Live WebSocket!")
        history = []
        
        # Turn 1 (Message 1): User introduces name
        print("\n--- TURN 1 (Message 1): Greeting & Name ---")
        history.append({"role": "user", "parts": [{"text": "Hello, my name is Yashpal"}]})
        await ws.send(json.dumps({
            "type": "text_input",
            "text": "Hello, my name is Yashpal",
            "history": history[:-1],
            "isVoiceMode": False
        }))
        bot_t1 = ""
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
            data = json.loads(msg)
            if data.get("type") == "reply_complete":
                bot_t1 = data.get("botText")
                break
        print(f"Riya Turn 1: '{bot_t1}'")
        history.append({"role": "model", "parts": [{"text": bot_t1}]})
        
        # Turn 2 (Message 2): User confirms name
        print("\n--- TURN 2 (Message 2): Name Confirmation ---")
        history.append({"role": "user", "parts": [{"text": "Yes, my name is Yashpal"}]})
        await ws.send(json.dumps({
            "type": "text_input",
            "text": "Yes, my name is Yashpal",
            "history": history[:-1],
            "isVoiceMode": False
        }))
        bot_t2 = ""
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
            data = json.loads(msg)
            if data.get("type") == "reply_complete":
                bot_t2 = data.get("botText")
                break
        print(f"Riya Turn 2: '{bot_t2}'")
        history.append({"role": "model", "parts": [{"text": bot_t2}]})
        
        # Turn 3 (Message 3): User states dental concern -> RIYA SHOULD ASK FOR PROFESSION
        print("\n--- TURN 3 (Message 3): Dental Concern & Profession Inquiry ---")
        history.append({"role": "user", "parts": [{"text": "I have gaps between my teeth"}]})
        await ws.send(json.dumps({
            "type": "text_input",
            "text": "I have gaps between my teeth",
            "history": history[:-1],
            "isVoiceMode": False
        }))
        bot_t3 = ""
        while True:
            msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
            data = json.loads(msg)
            if data.get("type") == "reply_complete":
                bot_t3 = data.get("botText")
                break
        print(f"Riya Turn 3: '{bot_t3}'")
        
        print("\nChecking Turn 3 response for profession inquiry...")
        prof_words = ["profession", "work", "do for work", "काम", "કામ", "વ્યવસાય", "પ્રોફેશન", "पेशा"]
        has_prof = any(w in bot_t3.lower() for w in prof_words)
        print(f"Profession inquiry detected in 3rd message: {has_prof}")
        assert has_prof, f"Profession was expected in 3rd message, but got: {bot_t3}"
        print("✅ LIVE MULTI-TURN PROFESSION TEST PASSED PERFECTLY!")

asyncio.run(test_live_profession_flow())
