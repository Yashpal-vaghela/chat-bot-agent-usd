import os
import json
import base64
import binascii
import uuid
import datetime
import threading
import httpx
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.core.files.base import ContentFile
from voice_agent.audio.transcoder import wrap_pcm_to_wav_base64
from voice_agent.models import VoiceRecordingLog
from voice_agent.utils.constants import GEMINI_VOICE_NAME

def chat_bot(request):
    return render(request, 'chat_bot.html')

@csrf_exempt
def api_tts(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body.decode('utf-8'))
        text = data.get('text', 'Okay.')
    except Exception as e:
        return JsonResponse({'error': 'Invalid JSON body'}, status=400)
    
    api_key = os.getenv('GEMINI_API_KEY_NEW') or os.getenv('GEMINI_API_KEY')
    if not api_key:
        return JsonResponse({'error': 'GEMINI_API_KEY is not set'}, status=500)
    
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-tts-preview:generateContent"
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "maxOutputTokens": 2048,
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {
                        "voiceName": os.getenv("GEMINI_VOICE_NAME") or GEMINI_VOICE_NAME or "Aoede"
                    }
                }
            }
        }
    }
    
    try:
        response = httpx.post(url, headers={"x-goog-api-key": api_key}, json=payload, timeout=20.0)
        if response.status_code != 200:
            return JsonResponse({'error': f'Speech provider returned HTTP {response.status_code}'}, status=502)
        
        result = response.json()
        for candidate in result.get('candidates', []):
            audio = bytearray()
            for part in candidate.get('content', {}).get('parts', []):
                inline = part.get('inlineData', {})
                if inline.get('data') and inline.get('mimeType', 'audio/L16').lower().startswith('audio/'):
                    audio.extend(base64.b64decode(inline['data'], validate=True))
            if audio:
                return JsonResponse({'audioBase64': wrap_pcm_to_wav_base64(audio, 24000)})
        return JsonResponse({'error': 'Speech provider returned no audio'}, status=502)
    except httpx.TimeoutException:
        return JsonResponse({'error': 'Speech provider timed out'}, status=504)
    except (httpx.RequestError, binascii.Error, ValueError):
        return JsonResponse({'error': 'Unable to read speech provider response'}, status=502)

# ==============================================================================
# Voice Agent Independent Email Configuration (ONLY Voice Agent - not other mails)
# FROM (Sender)   : vaghela9632@gmail.com
# TO (Destination): marketing@advancedentalexport.com
# ==============================================================================
SENDER_GMAIL = os.getenv('SENDER_GMAIL', 'vaghela9632@gmail.com')
SENDER_GMAIL_APP_PASSWORD = os.getenv('SENDER_GMAIL_APP_PASSWORD', 'oobystkwcvknwzwy')
FEEDBACK_RECIPIENT_EMAILS = [
    os.getenv('MARKETING_EMAIL', 'marketing@advancedentalexport.com'),
]

def dispatch_feedback_email(rating_label='Call Completed', transcript='No transcript provided.', audio_bytes=None, audio_filename='voice_recording.webm'):
    return True

@csrf_exempt
def submit_feedback(request):
    """
    Receives transcript, rating, and optional raw recorded audio file.
    Saves recording file (.mp3/.webm) and transcript (.txt) into VoiceRecordingLog table in DB.
    Supports save_type tags: 'submit_feedback' (way 1) and 'without_submit' (way 2, on close).
    """
    if request.method == 'OPTIONS':
        response = JsonResponse({'status': 'ok'})
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return response
        
    if request.method != 'POST':
        response = JsonResponse({'error': 'Only POST method is allowed'}, status=405)
        response['Access-Control-Allow-Origin'] = '*'
        return response
    
    try:
        rating_label = 'Call Completed'
        transcript = 'No transcript provided.'
        audio_bytes = None
        audio_filename = 'voice_recording.webm'
        save_type = 'without_submit'
        conversation_type = 'voice_agent'
        
        # Check if request body contains JSON (handles fetch, sendBeacon, etc.)
        body_data = None
        if request.body:
            try:
                parsed = json.loads(request.body.decode('utf-8'))
                if isinstance(parsed, dict):
                    body_data = parsed
            except Exception:
                pass

        if body_data is not None:
            rating_label = body_data.get('rating', 'Call Completed')
            transcript = body_data.get('transcript', 'No transcript provided.')
            save_type = body_data.get('save_type') or body_data.get('tag') or ('submit_feedback' if ('Stars' in rating_label or 'Submit' in rating_label or 'feedback' in rating_label.lower()) else 'without_submit')
            conversation_type = body_data.get('conversation_type') or body_data.get('agent_type') or 'voice_agent'
            audio_b64 = body_data.get('audio_base64')
            if audio_b64:
                if ',' in audio_b64:
                    audio_b64 = audio_b64.split(',', 1)[1]
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    audio_filename = body_data.get('audio_filename', 'voice_recording.webm')
                except Exception as b64_err:
                    print(f"[WARN] Error decoding audio base64: {b64_err}")
        else:
            rating_label = request.POST.get('rating', 'Call Completed')
            transcript = request.POST.get('transcript', 'No transcript provided.')
            save_type = request.POST.get('save_type') or request.POST.get('tag') or ('submit_feedback' if ('Stars' in rating_label or 'Submit' in rating_label or 'feedback' in rating_label.lower()) else 'without_submit')
            conversation_type = request.POST.get('conversation_type') or request.POST.get('agent_type') or 'voice_agent'
            audio_file = request.FILES.get('audio') or request.FILES.get('file')
            if audio_file:
                audio_filename = audio_file.name or 'voice_recording.webm'
                audio_bytes = audio_file.read()
            audio_b64 = request.POST.get('audio_base64')
            if not audio_bytes and audio_b64:
                if ',' in audio_b64:
                    audio_b64 = audio_b64.split(',', 1)[1]
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    audio_filename = request.POST.get('audio_filename', 'voice_recording.webm')
                except Exception as b64_err:
                    print(f"[WARN] Error decoding audio base64 from POST: {b64_err}")
        
        # Determine call_id
        call_id = None
        if body_data:
            call_id = body_data.get('call_id')
        if not call_id:
            call_id = request.POST.get('call_id') or f"call_{uuid.uuid4().hex[:10]}"

        # ⚡ SAVE OR UPDATE TO DATABASE (VoiceRecordingLog) ⚡
        log_id = None
        try:
            log_record, created = VoiceRecordingLog.objects.get_or_create(
                call_id=call_id,
                defaults={
                    'rating': rating_label,
                    'transcript': transcript,
                    'save_type': save_type,
                    'conversation_type': conversation_type
                }
            )
            if not created:
                if transcript and transcript != "No transcript provided.":
                    curr_len = len((log_record.transcript or "").strip())
                    if len(transcript.strip()) >= curr_len:
                        log_record.transcript = transcript
                if save_type == 'submit_feedback' or log_record.save_type != 'submit_feedback':
                    log_record.rating = rating_label
                    log_record.save_type = save_type
                if conversation_type:
                    log_record.conversation_type = conversation_type

            if audio_bytes and len(audio_bytes) > 0:
                has_valid_file = False
                try:
                    has_valid_file = bool(log_record.audio_file and log_record.audio_file.name and os.path.exists(log_record.audio_file.path))
                except Exception:
                    has_valid_file = False
                if not has_valid_file:
                    unique_filename = f"rec_{uuid.uuid4().hex[:8]}_{audio_filename}"
                    log_record.audio_file.save(unique_filename, ContentFile(audio_bytes), save=False)
            log_record.save()
            log_id = log_record.id
            print(f"[INFO] Saved VoiceRecordingLog #{log_id} in DB (created={created}, conv_type={conversation_type}, save_type={save_type}, audio={bool(audio_bytes)})")
        except Exception as db_err:
            print(f"[ERROR] Failed to save VoiceRecordingLog in DB: {db_err}")

        response = JsonResponse({
            'status': 'success',
            'record_id': log_id,
            'conversation_type': conversation_type,
            'save_type': save_type,
            'rating': rating_label,
            'audio_attached': bool(audio_bytes)
        })
        response['Access-Control-Allow-Origin'] = '*'
        return response
        
    except Exception as e:
        print(f"[ERROR] submit_feedback failed: {e}")
        response = JsonResponse({'error': str(e)}, status=500)
        response['Access-Control-Allow-Origin'] = '*'
        return response
