import os
import sys
import django

# Setup Django environment
sys.path.append(r'd:\media')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

from voice_agent.views import dispatch_feedback_email, SENDER_GMAIL, FEEDBACK_RECIPIENT_EMAILS
from voice_agent.services.appointment_service import send_appointment_email

print("=== VOICE AGENT EMAIL CONFIGURATION CHECK ===")
print(f"Feedback Email FROM: {SENDER_GMAIL}")
print(f"Feedback Email TO  : {FEEDBACK_RECIPIENT_EMAILS}")

# Test dispatch_feedback_email (Dry-run or live send test)
print("\n[TEST 1] Dispatching test feedback email...")
success_feedback = dispatch_feedback_email(
    rating_label="[TEST VERIFICATION] Voice Agent Email Flow Check",
    transcript="User: Test conversation transcript.\nRiya: Hello! Checking email routing from vaghela to marketing.",
    audio_bytes=b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00",
    audio_filename="test_voice.wav"
)
print(f"Feedback Email Result: {'SUCCESS' if success_feedback else 'FAILED'}")

# Test send_appointment_email
print("\n[TEST 2] Dispatching test appointment lead email...")
test_payload = {
    "first_name": "Test",
    "last_name": "Lead",
    "phone": "9876543210",
    "city": "Surat",
    "doctor_name": "Dr. Pratik Patel",
    "message": "Routine dental checkup test",
    "email": "patient_test@example.com",
    "submission_id": "TEST-9999",
    "transcript": "User: Book my appointment.\nRiya: Confirmed with Dr. Pratik Patel."
}

try:
    send_appointment_email(test_payload)
    print("Appointment Email Result: DISPATCHED SUCCESSFULLY")
except Exception as e:
    print(f"Appointment Email Result: FAILED ({e})")
