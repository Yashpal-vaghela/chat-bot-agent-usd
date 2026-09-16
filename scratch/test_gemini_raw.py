import asyncio
import websockets
import json
import os
import sys

from dotenv import load_dotenv
load_dotenv(r'd:\media\.env')

api_key = os.getenv("GEMINI_API_KEY_NEW") or os.getenv("GEMINI_API_KEY")
print("API Key found:", bool(api_key))

GEMINI_LIVE_MODEL = "models/gemini-3.1-flash-live-preview"
ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

async def test_live_raw():
    async with websockets.connect(ws_url) as ws:
        print("Connected to Gemini Live raw WS")
        setup_message = {
            "setup": {
                "model": GEMINI_LIVE_MODEL,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Despina"
                            }
                        }
                    }
                },
                "outputAudioTranscription": {},
                "systemInstruction": {"parts": [{"text": "You are Riya, helpful dental assistant."}]}
            }
        }
        await ws.send(json.dumps(setup_message))
        res = await ws.recv()
        print("Setup response:", res)

        # Test sending realtimeInput with text:
        test_payload = {
            "realtimeInput": {
                "text": "Hello, how are you?"
            }
        }
        print("Sending realtimeInput with text...")
        await ws.send(json.dumps(test_payload))

        for i in range(10):
            try:
                frame = await asyncio.wait_for(ws.recv(), timeout=5.0)
                data = json.loads(frame)
                print(f"Frame {i}: keys={list(data.keys())}")
                if "serverContent" in data:
                    sc = data["serverContent"]
                    print("  sc keys:", list(sc.keys()))
                    if "outputTranscription" in sc:
                        print("  transcription:", sc["outputTranscription"])
                    if "modelTurn" in sc:
                        parts = sc["modelTurn"].get("parts", [])
                        print("  modelTurn parts count:", len(parts))
                        for p in parts:
                            if "inlineData" in p:
                                print("    part has inline audio data len=", len(p["inlineData"]["data"]))
                            if "text" in p:
                                print("    part has text:", p["text"])
                    if sc.get("turnComplete"):
                        print("  turnComplete! Done.")
                        break
            except Exception as e:
                print("Recv exception:", e)
                break

asyncio.run(test_live_raw())
