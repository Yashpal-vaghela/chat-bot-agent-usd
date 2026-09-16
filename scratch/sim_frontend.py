import asyncio
import websockets
import json

async def test_frontend_sim():
    uri = 'ws://127.0.0.1:8000/ws/voice-agent/'
    print('Connecting to', uri)
    async with websockets.connect(uri) as ws:
        print('Connected!')
        
        # Test 1: Starter message in voice mode (like chat_bot.html does on open)
        starter = {
            'type': 'text_input',
            'text': "SYSTEM INSTRUCTION: Start the conversation by warmly saying EXACTLY this specific phrase and absolutely nothing else: 'Namaste! I am Riya USD Consultant, How can we assist you today? Let's start with your beautiful name, what is your name?'",
            'history': [],
            'isVoiceMode': True
        }
        await ws.send(json.dumps(starter))
        print('Sent starter message in voice mode')
        
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                if isinstance(msg, bytes):
                    print(f'Received binary PCM chunk: {len(msg)} bytes')
                else:
                    data = json.loads(msg)
                    m_type = data.get('type')
                    txt = data.get('text', '')
                    print(f'Received JSON: type={m_type}, text={txt[:60]}')
                    if m_type == 'reply_complete':
                        break
        except asyncio.TimeoutError:
            print('Voice mode listen timed out!')
            
        print('--- NOW TESTING CHAT MODE ---')
        chat_msg = {
            'type': 'text_input',
            'text': 'My name is Rahul Patel and I need veneers in Surat',
            'history': [],
            'isVoiceMode': False
        }
        await ws.send(json.dumps(chat_msg))
        print('Sent chat mode text message')
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=8.0)
                if isinstance(msg, bytes):
                    print(f'Received binary PCM chunk: {len(msg)} bytes')
                else:
                    data = json.loads(msg)
                    m_type = data.get('type')
                    txt = data.get('text', '')
                    print(f'Chat JSON: type={m_type}, text={txt[:60]}')
                    if m_type == 'reply_complete':
                        break
        except asyncio.TimeoutError:
            print('Chat mode listen timed out!')

if __name__ == '__main__':
    asyncio.run(test_frontend_sim())
