import os
import sys
import asyncio
import django

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, r"d:\media")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hm.settings')
django.setup()

from voice_agent.services.appointment_service import submit_consultation_appointment
from account.models import UserSubmission

async def test_submission():
    print("\n--- Testing submit_consultation_appointment with Amit Bhai Details ---")
    data = {
        "first_name": "Amit",
        "last_name": "Bhai",
        "phone": "7984256299",
        "city": "Rajkot",
        "doctor_name": "Dr. Margie I Aghera",
        "message": "દાંતમાં દુખાવો",
        "user_concern": "દાંતમાં દુખાવો",
        "is_submitted": True
    }
    res = await submit_consultation_appointment(data)
    print(f"Result status: {res.get('status')}")
    print(f"Result details: {res.get('details')}")

    # Check local database
    last_sub = UserSubmission.objects.filter(phone__endswith="7984256299").order_by('-id').first()
    assert last_sub is not None, "Submission not found in local DB!"
    print(f"✓ Found in local SQLite UserSubmission (ID={last_sub.id}): Name={last_sub.first_name} {last_sub.last_name}, Phone={last_sub.phone}, City={last_sub.city}, Doctor={last_sub.doctor_name}, Message={last_sub.message}")
    assert "Amit" in last_sub.first_name
    assert last_sub.city == "Rajkot"
    assert "Margie" in last_sub.doctor_name

if __name__ == "__main__":
    asyncio.run(test_submission())
