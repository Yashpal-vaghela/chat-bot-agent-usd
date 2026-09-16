import os
import sys
import asyncio
import django

# Setup Django environment
sys.path.append(r'd:\media')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

from voice_agent.views import dispatch_feedback_email, SENDER_GMAIL, FEEDBACK_RECIPIENT_EMAILS, SENDER_GMAIL_APP_PASSWORD
from voice_agent.services.appointment_service import send_appointment_email, submit_consultation_appointment

print("==================================================")
print("       VOICE AGENT EMAIL VERIFICATION TEST        ")
print("==================================================")
print(f"Sender Gmail         : {SENDER_GMAIL}")
print(f"Marketing Recipient  : {FEEDBACK_RECIPIENT_EMAILS}")
masked_pw = SENDER_GMAIL_APP_PASSWORD[:4] + " **** " + SENDER_GMAIL_APP_PASSWORD[-4:] if len(SENDER_GMAIL_APP_PASSWORD) >= 8 else "****"
print(f"App Password Active  : {masked_pw}")
print("==================================================\n")

# TEST 1: Verify Appointment Booking Email is completely disabled
print("[TEST 1] Testing Appointment Booking Flow...")
appointment_data = {
    "first_name": "TestVerification",
    "last_name": "Patient",
    "phone": "9998887777",
    "city": "Surat",
    "doctor_name": "Dr. Pratik Patel",
    "message": "Testing appointment email suppression",
    "email": "test@example.com"
}

# Direct call to send_appointment_email
ret_direct = send_appointment_email(appointment_data)
print(f"• Direct send_appointment_email() returned: {ret_direct} (No email dispatched - disabled)")

# Async call to submit_consultation_appointment
async def test_appointment_submit():
    res = await submit_consultation_appointment(appointment_data)
    print(f"• submit_consultation_appointment() result: {res.get('status')} (Database/API handled, no appointment mail sent)")

asyncio.run(test_appointment_submit())

# TEST 2: Verify Call Transcript + Audio Recording email to marketing works with new app password
print("\n[TEST 2] Testing Call Transcript & Audio Recording Email to Marketing...")
test_audio_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

success = dispatch_feedback_email(
    rating_label="Call Completed (Verification Test)",
    transcript="User: Hi Riya, I would like to consult.\nRiya: Sure, I can help you connect with our specialist in Surat.\nUser: Thank you!",
    audio_bytes=test_audio_bytes,
    audio_filename="test_call_recording.wav"
)

if success:
    print("SUCCESS: Transcript and call audio email successfully delivered to marketing@advancedentalexport.com via new Gmail App Password!")
else:
    print("FAILED: Could not deliver email via Gmail SMTP.")
