import os
import sys
import asyncio
import django

sys.path.insert(0, r'd:\media')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

from voice_agent.consumers import VoiceAgentConsumer

class MockConsumer(VoiceAgentConsumer):
    def __init__(self):
        super().__init__()
        self.scope = {'type': 'websocket', 'path': '/ws/voice-agent/'}
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True
        print('MockConsumer accepted!')

    async def send_json(self, data):
        t = data.get('type')
        txt = data.get('text', '')
        print(f'[OUT] send_json: type={t}, text={txt[:50]}')
        self.sent.append(data)

    async def close(self, code=1000):
        print('MockConsumer closed:', code)

async def run_test():
    c = MockConsumer()
    print('Calling connect()...')
    try:
        await c.connect()
        print('Connect completed!')
    except Exception as e:
        print('Connect ERROR:', type(e), e)
        return

    await asyncio.sleep(2.0)
    print('\n--- Sending Voice Starter ---')
    try:
        await c.receive(text_data='{"type": "text_input", "text": "SYSTEM INSTRUCTION: Start the conversation", "isVoiceMode": true}')
    except Exception as e:
        print('Receive voice error:', type(e), e)

    await asyncio.sleep(6.0)

    print('\n--- Sending Chat Text Input ---')
    try:
        await c.receive(text_data='{"type": "text_input", "text": "My name is Rahul Patel and I need veneers in Surat", "isVoiceMode": false}')
    except Exception as e:
        print('Receive chat error:', type(e), e)

    await asyncio.sleep(6.0)
    print('\nTest finished!')

if __name__ == '__main__':
    asyncio.run(run_test())
