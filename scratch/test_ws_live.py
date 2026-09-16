import asyncio
import websockets
import json
import sys

async def test():
    uri = "ws://127.0.0.1:8000/ws/voice-agent/"
    print(f"Connecting to {uri} ...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected to WebSocket successfully!")
            
            # Send initial text_input as the frontend does
            greeting_prompt = "SYSTEM INSTRUCTION: Start the conversation by warmly saying EXACTLY this specific phrase and absolutely nothing else: 'Namaste! I am Riya USD Consultant, How can we assist you today? Let\'s start with your beautiful name, what is your name?'"
            payload = {
                "type": "text_input",
                "text": greeting_prompt,
                "history": [],
                "isVoiceMode": True
            }
            print("Sending text_input...")
            await ws.send(json.dumps(payload))
            
            start_time = asyncio.get_event_loop().time()
            total_audio_bytes = 0
            total_text = ""
            
            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=8.0)
                    msg = json.loads(raw)
                    msg_type = msg.get("type")
                    print(f"[{asyncio.get_event_loop().time() - start_time:.2f}s] Received frame: {msg_type}")
                    
                    if msg_type == "bot_text_chunk":
                        chunk = msg.get("text", "")
                        total_text += chunk
                        print(f"   [bot_text_chunk]: {chunk!r}")
                    elif msg_type == "audio_chunk":
                        b64 = msg.get("audioBase64", "")
                        total_audio_bytes += len(b64)
                        print(f"   [audio_chunk]: index={msg.get('index')} len={len(b64)}")
                    elif msg_type == "bot_spoken_text":
                        print(f"   [bot_spoken_text]: {msg.get('text')!r}")
                    elif msg_type == "reply_complete":
                        print(f"   [reply_complete]: botText={msg.get('botText')!r}")
                        print(f"Total Text received: {total_text!r}")
                        print(f"Total Audio Base64 length: {total_audio_bytes}")
                        break
                    elif msg_type == "error":
                        print(f"   [ERROR]: {msg}")
                        break
                except asyncio.TimeoutError:
                    print("Timeout waiting for more frames!")
                    break
    except Exception as e:
        print(f"Exception during test: {e}")

if __name__ == "__main__":
    asyncio.run(test())
