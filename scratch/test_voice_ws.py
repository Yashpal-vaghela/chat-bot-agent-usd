import asyncio
import websockets
import json

async def test_voice_mode():
    uri = 'ws://127.0.0.1:8000/ws/voice-agent/'
    async with websockets.connect(uri) as ws:
        print('Connected to Voice Mode WS!')
        # Send initial text_input greeting as done by frontend
        await ws.send(json.dumps({
            'type': 'text_input',
            'text': "SYSTEM INSTRUCTION: Start the conversation by warmly saying EXACTLY this specific phrase and absolutely nothing else: 'Namaste! I am Riya USD Consultant, How can we assist you today? Let\'s start with your beautiful name, what is your name?'",
            'history': [],
            'isVoiceMode': True
        }))
        print('Sent initial greeting in Voice Mode')
        chunks = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=12.0)
                data = json.loads(msg)
                mtype = data.get('type')
                print('RECV:', mtype, (data.get('text') or data.get('botText') or '')[:50])
                if mtype in ['bot_text_chunk', 'audio_chunk']:
                    chunks += 1
                if mtype == 'reply_complete' or chunks >= 5:
                    print('Voice mode test successful!')
                    break
            except asyncio.TimeoutError:
                print('Timeout in voice mode')
                break

asyncio.run(test_voice_mode())
