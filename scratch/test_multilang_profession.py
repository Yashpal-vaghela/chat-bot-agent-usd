import sys
import asyncio
import websockets
import json

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

async def test_all_languages_profession_flow():
    uri = 'ws://127.0.0.1:8000/ws/voice-agent/'
    
    test_cases = [
        {
            "lang": "English",
            "t1": "Hello, my name is Yashpal",
            "t2": "Yes, my name is Yashpal",
            "t3": "I have gaps between my teeth",
            "check": ["what do you do for work", "what is your profession", "may i ask"]
        },
        {
            "lang": "Gujarati",
            "t1": "મારું નામ યશપાલ છે",
            "t2": "હા મારું નામ યશપાલ છે",
            "t3": "મને દાંત વચ્ચે જગ્યા છે",
            "check": ["તમે શું કામ કરો છો", "કામ કરો", "વ્યવસાય", "પ્રોફેશન"]
        },
        {
            "lang": "Hindi",
            "t1": "मेरा नाम यशपाल है",
            "t2": "हाँ मेरा नाम यशपाल है",
            "t3": "मेरे दाँतों में गैप है",
            "check": ["आप क्या काम करते हैं", "काम करते", "पेशा", "प्रोफेशन"]
        }
    ]
    
    for tc in test_cases:
        print(f"\n==========================================")
        print(f"Testing {tc['lang']} Profession Flow")
        print(f"==========================================")
        async with websockets.connect(uri) as ws:
            history = []
            
            # Turn 1
            history.append({"role": "user", "parts": [{"text": tc['t1']}]})
            await ws.send(json.dumps({
                "type": "text_input", "text": tc['t1'], "history": history[:-1], "isVoiceMode": False
            }))
            bot_t1 = ""
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                data = json.loads(msg)
                if data.get("type") == "reply_complete":
                    bot_t1 = data.get("botText")
                    break
            print(f"Turn 1 ({tc['lang']}): {bot_t1}")
            history.append({"role": "model", "parts": [{"text": bot_t1}]})
            
            # Turn 2
            history.append({"role": "user", "parts": [{"text": tc['t2']}]})
            await ws.send(json.dumps({
                "type": "text_input", "text": tc['t2'], "history": history[:-1], "isVoiceMode": False
            }))
            bot_t2 = ""
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                data = json.loads(msg)
                if data.get("type") == "reply_complete":
                    bot_t2 = data.get("botText")
                    break
            print(f"Turn 2 ({tc['lang']}): {bot_t2}")
            history.append({"role": "model", "parts": [{"text": bot_t2}]})
            
            # Turn 3
            history.append({"role": "user", "parts": [{"text": tc['t3']}]})
            await ws.send(json.dumps({
                "type": "text_input", "text": tc['t3'], "history": history[:-1], "isVoiceMode": False
            }))
            bot_t3 = ""
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                data = json.loads(msg)
                if data.get("type") == "reply_complete":
                    bot_t3 = data.get("botText")
                    break
            print(f"Turn 3 ({tc['lang']}): {bot_t3}")
            
            has_match = any(w in bot_t3.lower() for w in tc['check'])
            assert has_match, f"Failed profession inquiry for {tc['lang']}: {bot_t3}"
            print(f" [PASS] {tc['lang']} 3rd message asked profession!")

    print("\n✅ ALL 3 LANGUAGES (EN, GU, HI) ASKED PROFESSION IN 3RD MESSAGE!")

asyncio.run(test_all_languages_profession_flow())
