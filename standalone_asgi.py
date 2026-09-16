import os
import json
import base64
import threading
import django
from django.conf import settings
from channels.routing import ProtocolTypeRouter, URLRouter
import voice_agent.routing

if not settings.configured:
    settings.configure(
        SECRET_KEY="voice-agent-cloud-run-production-secret-key",
        DEBUG=False,
        ALLOWED_HOSTS=["*"],
        INSTALLED_APPS=[
            "daphne",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "channels",
            "voice_agent",
        ],
        ASGI_APPLICATION="standalone_asgi.application",
        TIME_ZONE="Asia/Kolkata",
        USE_TZ=True,
    )
    django.setup()

from voice_agent.views import dispatch_feedback_email

async def http_app(scope, receive, send):
    if scope['type'] == 'http':
        path = scope.get('path', '')
        method = scope.get('method', 'GET')
        
        # Handle CORS OPTIONS pre-flight
        if method == 'OPTIONS':
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-type', b'application/json'),
                    (b'access-control-allow-origin', b'*'),
                    (b'access-control-allow-methods', b'POST, GET, OPTIONS'),
                    (b'access-control-allow-headers', b'Content-Type, X-CSRFToken'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"status":"ok"}',
            })
            return

        # Handle Submit Feedback API on Cloud Run
        if '/voice-agent/api/submit-feedback' in path:
            body_bytes = bytearray()
            more_body = True
            while more_body:
                message = await receive()
                body_bytes.extend(message.get('body', b''))
                more_body = message.get('more_body', False)
                
            rating_label = 'Call Completed'
            transcript = 'No transcript provided.'
            audio_bytes = None
            audio_filename = 'voice_recording.webm'
            try:
                if body_bytes:
                    body_data = json.loads(body_bytes.decode('utf-8'))
                    rating_label = body_data.get('rating', 'Call Completed')
                    transcript = body_data.get('transcript', 'No transcript provided.')
                    audio_b64 = body_data.get('audio_base64')
                    if audio_b64:
                        if ',' in audio_b64:
                            audio_b64 = audio_b64.split(',', 1)[1]
                        audio_bytes = base64.b64decode(audio_b64)
                        audio_filename = body_data.get('audio_filename', 'voice_recording.webm')
            except Exception as parse_err:
                print(f"[WARN] Error parsing submit_feedback body on Cloud Run ASGI: {parse_err}")

            # threading.Thread(
            #     target=dispatch_feedback_email,
            #     args=(rating_label, transcript, audio_bytes, audio_filename),
            #     daemon=False
            # ).start()

            resp_payload = json.dumps({
                "status": "success",
                "rating": rating_label,
                "audio_attached": bool(audio_bytes)
            }).encode('utf-8')

            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-type', b'application/json'),
                    (b'access-control-allow-origin', b'*'),
                ],
            })
            await send({
                'type': 'http.response.body',
                'body': resp_payload,
            })
            return

        # Default Health Check Response
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                (b'content-type', b'text/plain'),
                (b'access-control-allow-origin', b'*'),
            ],
        })
        await send({
            'type': 'http.response.body',
            'body': b'Voice Agent Cloud Run Service is Active and Healthy',
        })

application = ProtocolTypeRouter({
    "http": http_app,
    "websocket": URLRouter(
        voice_agent.routing.websocket_urlpatterns
    ),
})
