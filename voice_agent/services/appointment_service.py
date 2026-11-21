import os
import time
import httpx
import logging
import asyncio
import smtplib
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

# Consultation API endpoint
CONSULT_API_ENDPOINT = os.getenv(
    "CONSULT_API_ENDPOINT",
    os.getenv("LOCAL_API_ENDPOINT", "https://ultimatesmiledesign.com/api/consult-with-dentist/")
)
LOCAL_API_ENDPOINT = CONSULT_API_ENDPOINT

# GoDaddy lightweight internal endpoint (Disabled for now - local database only)
ENABLE_GODADDY_SYNC = os.getenv("ENABLE_GODADDY_SYNC", "false").lower() in ("true", "1")
GODADDY_SYNC_URL = os.getenv("GODADDY_SYNC_URL") or os.getenv("INTERNAL_SYNC_URL") or "api/internal/save-lead/"
INTERNAL_SYNC_SECRET = os.getenv("INTERNAL_SYNC_SECRET", "usd-secret-sync-token-2026")

AUTHORISED_CITIES = CERTIFIED_CITIES = {
    "Ahmedabad", "Surat", "Mumbai", "Pune", "Vadodara", "Rajkot", "Jamnagar",
    "Bharuch", "Halvad", "Dhrangadhra", "New Delhi", "Delhi", "Gurugram", "Gurgaon",
    "Indore", "Gwalior", "Bangalore", "Bengaluru", "Hyderabad", "Chennai", "Guntur",
    "Sangli", "Guwahati", "Faridkot", "Sri Ganganagar", "Malda"
}

ALL_AUTHORISED_DOCTORS = ALL_CERTIFIED_DOCTORS = [
    "Dr. Rakesh Patel", "Dr. Jigar P. Thakkar", "Dr. Ankit Mataliya", "Dr. Neerav Jhaveri", "Dr. Alap D Shah", "Dr. Abbas Noorani", "Dr. Purvesh Chauhan", "Dr. Ravi Shah", "Dr. Janu Shah",
    "Dr. Bharat R. Patel", "Dr. Parita Shah", "Dr. Viren K Savani", "Dr. Purvi Patel", "Dr. Priyanka Kathiriya", "Dr. Jay Patel",
    "Dr. Vinita Tekchandani", "Dr. Deepika Dalal", "Dr. Nikita Motwani", "Dr. Rohan Bandi", "Dr. Moez Khakiani",
    "Dr. Aarti Bhatewara", "Dr. Kaveena Parikh", "Dr. Khushbu Patel",
    "Dr. Margie I Aghera", "Dr. Pagisha Sojitra", "Dr. Vishvaraj Agravat", "Dr. Hetal Buch",
    "Dr. D. J. Chetariya", "Dr. Prasanna Patel", "Dr. Bharat Katarmal",
    "Dr. Hafsha Saiyed", "Dr. Pankaj Patel", "Dr. Dilip J Parejiya",
    "Dr. Sanjit Singh", "Dr. Minu Arora", "Dr. Amit Kr. Agrawal",
    "Dr. Surangana Gupta", "Dr. Jaydev Roy", "Dr. Himanshu Sharma",
    "Dr. Aman Singhal", "Dr. Mohammed Issak", "Dr. Srilakshmi CH", "Dr. M Jaydev",
    "Dr. Reuben Joseph", "Dr. Praneeth Kumar", "Dr. Kalyani Jagdale", "Dr. Digvijay Deshpande",
    "Dr. Adil Lyngdoh", "Dr. Asmita Sodhi", "Dr. Neetu Jindal", "Dr. A K Saha", "Dr. Chinar Patel"
]

_RECENT_SUBMISSIONS_CACHE = {}

def transliterate_to_english(text: str) -> str:
    if not text:
        return ""
    
    COMMON_MAP = {
        'ભવિન': 'Bhavin', 'ભાવિન': 'Bhavin', 'પરમાર': 'Parmar',
        'ગુરપ્રીત': 'Gurpreet', 'ਸਿੰਘ': 'Singh', 'ગੁਰਪ੍ਰੀਤ ਸਿੰਘ': 'Gurpreet Singh',
        'राहुल': 'Rahul', 'शर्मा': 'Sharma', 'राहुल शर्मा': 'Rahul Sharma',
        'સચિન': 'Sachin', 'સાવંત': 'Sawant', 'सचिन': 'Sachin', 'सावंत': 'Sawant',
        'সৌমেন': 'Soumen', 'ব্যানার্জি': 'Banerjee',
        'கார்த்திக்': 'Karthik', 'ராஜா': 'Raja',
        'రవి': 'Ravi', 'తేజ': 'Teja',
        'ಸುರೇಶ್': 'Suresh', 'ಕುಮಾರ್': 'Kumar',
        'അനൂപ്': 'Anoop', 'കുമാർ': 'Kumar',
        'ਦੇਵਾਸ਼ੀਸ਼': 'Debashish', 'ਪੰਡਾ': 'Panda', 'ଦେବାଶିଷ': 'Debashish', 'ପଣ୍ଡା': 'Panda'
    }
    
    if text.strip() in COMMON_MAP:
        return COMMON_MAP[text.strip()]

    BRAHMIC_CONSONANTS = {
        0x15: 'k', 0x16: 'kh', 0x17: 'g', 0x18: 'gh', 0x19: 'ng',
        0x1A: 'ch', 0x1B: 'chh', 0x1C: 'j', 0x1D: 'jh', 0x1E: 'ny',
        0x1F: 't', 0x20: 'th', 0x21: 'd', 0x22: 'dh', 0x23: 'n',
        0x24: 't', 0x25: 'th', 0x26: 'd', 0x27: 'dh', 0x28: 'n',
        0x2A: 'p', 0x2B: 'ph', 0x2C: 'b', 0x2D: 'bh', 0x2E: 'm',
        0x2F: 'y', 0x30: 'r', 0x31: 'r', 0x32: 'l', 0x33: 'l', 0x34: 'l',
        0x35: 'v', 0x36: 'sh', 0x37: 'sh', 0x38: 's', 0x39: 'h',
        0x58: 'q', 0x59: 'kh', 0x5A: 'gh', 0x5B: 'z', 0x5C: 'r', 0x5D: 'rh', 0x5E: 'f', 0x5F: 'y',
        0x70: 't', 0x71: 'n'
    }
    BRAHMIC_VOWELS = {
        0x04: 'a', 0x05: 'a', 0x06: 'a', 0x07: 'i', 0x08: 'ee', 0x09: 'u', 0x0A: 'oo',
        0x0B: 'ri', 0x0E: 'e', 0x0F: 'e', 0x10: 'ai', 0x12: 'o', 0x13: 'o', 0x14: 'au'
    }
    BRAHMIC_MATRAS = {
        0x3E: 'a', 0x3F: 'i', 0x40: 'ee', 0x41: 'u', 0x42: 'oo', 0x43: 'ri',
        0x46: 'e', 0x47: 'e', 0x48: 'ai', 0x4A: 'o', 0x4B: 'o', 0x4C: 'au',
        0x55: 'e', 0x56: 'ai', 0x57: 'au'
    }
    SCRIPT_BASES = [0x0900, 0x0980, 0x0A00, 0x0A80, 0x0B00, 0x0B80, 0x0C00, 0x0C80, 0x0D00]
    
    words = text.split()
    out_words = []
    for w in words:
        if w in COMMON_MAP:
            out_words.append(COMMON_MAP[w])
            continue
        res = []
        i = 0
        chars = list(w)
        n = len(chars)
        while i < n:
            c = chars[i]
            code = ord(c)
            base = None
            for b in SCRIPT_BASES:
                if b <= code < b + 0x80:
                    base = b
                    break
            if base is None:
                res.append(c)
                i += 1
                continue
            
            offset = code - base
            if offset in [0x01, 0x02, 0x70, 0x71]:
                res.append('n')
                i += 1
                continue
            if offset == 0x03:
                res.append('h')
                i += 1
                continue
            if offset in BRAHMIC_VOWELS:
                res.append(BRAHMIC_VOWELS[offset])
                i += 1
                continue
            if offset in BRAHMIC_CONSONANTS:
                cons = BRAHMIC_CONSONANTS[offset]
                if i + 1 < n:
                    next_c = chars[i + 1]
                    next_code = ord(next_c)
                    next_base = None
                    for b in SCRIPT_BASES:
                        if b <= next_code < b + 0x80:
                            next_base = b
                            break
                    if next_base is not None:
                        next_offset = next_code - next_base
                        if next_offset == 0x4D:
                            res.append(cons)
                            i += 2
                            continue
                        elif next_offset in BRAHMIC_MATRAS:
                            res.append(cons + BRAHMIC_MATRAS[next_offset])
                            i += 2
                            continue
                res.append(cons)
                if i + 1 < n:
                    next_code = ord(chars[i+1])
                    for b in SCRIPT_BASES:
                        if b <= next_code < b + 0x80:
                            if (next_code - b) in BRAHMIC_CONSONANTS:
                                res.append('a')
                            break
                i += 1
                continue
            res.append(c)
            i += 1
        
        w_str = ''.join(res)
        out_words.append(w_str.capitalize())
        
    return ' '.join(out_words)

def is_duplicate_submission(phone: str, doctor_name: str) -> bool:
    now = time.time()
    expired = [k for k, v in _RECENT_SUBMISSIONS_CACHE.items() if now - v > 60]
    for k in expired:
        _RECENT_SUBMISSIONS_CACHE.pop(k, None)
        
    key = ("".join(filter(str.isdigit, str(phone))), str(doctor_name).lower().strip())
    if key in _RECENT_SUBMISSIONS_CACHE and (now - _RECENT_SUBMISSIONS_CACHE[key]) < 30:
        return True
    _RECENT_SUBMISSIONS_CACHE[key] = now
    return False

def is_matched_doctor(doc_str: str, city: str = None) -> str:
    if not doc_str:
        return ""
    import re
    d_clean = doc_str.lower().strip()
    if d_clean in ["none", "null", "usd certified smile designer", "usd authorised smile designer", "usd authorized smile designer", "doctor", "dentist", "any", "not provided", ""]:
        return ""

    placeholder_words = [
        "हमारे डॉक्टर", "અમારા ડૉક્ટર", "our doctor", "doctor in", "ડોક્ટર છે", "डॉक्टर हैं",
        "select doctor", "choose doctor", "કોઈ પણ", "कोई भी", "ceramist", "सिरामिस्ट", "સેરેમિસ્ટ", "haresh savani", "हरेश सवाणी", "હરેશ સવાણી",
        "not selected", "pending", "પસંદ કરેલ નથી", "ચયનિત નહીં", "चयनित नहीं", "निवडले नाही"
    ]
    if any(pw in d_clean for pw in placeholder_words):
        return ""
        
    try:
        from voice_agent.ai.conversation_manager import CITY_DOCTORS
        primary_docs = CITY_DOCTORS.get(city, []) if (city and city in CITY_DOCTORS) else ALL_CERTIFIED_DOCTORS
    except Exception:
        primary_docs = ALL_CERTIFIED_DOCTORS

    for doc_candidates in [primary_docs, ALL_CERTIFIED_DOCTORS]:
        # 1. Exact or direct substring match in doctor candidate list
        for full_doc in doc_candidates:
            raw_name = full_doc.lower().replace("dr.", "").replace("dr", "").strip()
            if raw_name in d_clean or d_clean in full_doc.lower():
                return full_doc
                
        # 2. Try find_doctor_in_text directly
        try:
            from voice_agent.ai.conversation_manager import find_doctor_in_text
            doc = find_doctor_in_text(doc_str, city=city if doc_candidates is primary_docs else None)
            if doc and doc in doc_candidates:
                return doc
        except Exception:
            pass

        # 3. Transliterate non-ascii and match again
        eng_doc = transliterate_to_english(doc_str) if any(ord(c) > 127 for c in doc_str) else d_clean
        try:
            from voice_agent.ai.conversation_manager import find_doctor_in_text
            doc = find_doctor_in_text(eng_doc, city=city if doc_candidates is primary_docs else None)
            if doc and doc in doc_candidates:
                return doc
        except Exception:
            pass
        for full_doc in doc_candidates:
            raw_name = full_doc.lower().replace("dr.", "").replace("dr", "").strip()
            if raw_name in eng_doc.lower() or eng_doc.lower() in full_doc.lower():
                return full_doc

        # 4. Token / Root match for doctors in candidate list
        eng_clean = re.sub(r"^dr\.?\s*", "", eng_doc, flags=re.IGNORECASE).strip().lower()
        for full_doc in doc_candidates:
            parts = [p.lower() for p in full_doc.replace("Dr.", "").split() if len(p) >= 3 and p.lower() not in ["shah", "patel", "kumar", "singh", "sharma"]]
            for p in parts:
                p_short = p[:4]  # e.g. 'marg' for 'margie'
                if p in eng_clean or p_short in eng_clean:
                    return full_doc
    return ""

from channels.db import database_sync_to_async

_GODADDY_LEAD_MAP = {}  # In-memory cache mapping phone (10-digits) -> GoDaddy lead_id

@database_sync_to_async
def fetch_existing_lead_data(sub_id, phone_val):
    """Fetches an existing lead record safely from the database in an async-safe context."""
    from account.models import UserSubmission
    lead = None
    if sub_id:
        try:
            lead = UserSubmission.objects.filter(id=sub_id).first()
        except Exception:
            lead = None
    if not lead and phone_val:
        digits = "".join(filter(str.isdigit, str(phone_val)))
        if len(digits) >= 10:
            try:
                lead = UserSubmission.objects.filter(phone__endswith=digits[-10:]).order_by('-id').first()
            except Exception:
                lead = None
    # (No "latest lead of the last 30 minutes" fallback: that could be ANOTHER patient's lead)
    if lead:
        return {
            "id": lead.id,
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "city": lead.city,
            "pincode": getattr(lead, "pincode", "") or "",
            "country_code": getattr(lead, "country_code", "") or "IN",
            "doctor_name": lead.doctor_name,
            "message": lead.message,
            "email": lead.email,
            "phone": lead.phone,
            "is_cancel": bool(getattr(lead, "is_cancel", False)),
        }
    return None

@database_sync_to_async
def save_lead_to_local_db(payload: dict):
    """Saves or updates lead directly into local UserSubmission table asynchronously for Daphne/Channels."""
    from account.models import UserSubmission
    lead_id = payload.get('id') or payload.get('lead_id') or payload.get('submission_id')
    is_cancel = bool(payload.get('is_cancel', False))
    phone_val = str(payload.get('phone', '')).strip()
    old_phone_val = str(payload.get('old_phone', '')).strip()

    lead = None
    if lead_id:
        try:
            lead = UserSubmission.objects.get(id=lead_id)
        except (UserSubmission.DoesNotExist, ValueError):
            lead = None

    # A NEW booking always creates a new row (newest at the top). Only an update/cancel of the lead THIS
    # conversation created (lead_id) changes an existing row. Matching by phone is allowed only for a cancellation
    # without a lead id (patient calls back to cancel); never "the latest lead of the last 30 minutes", which
    # could be another patient's lead.
    if not lead and is_cancel:
        for ph in (old_phone_val, phone_val):
            digits = "".join(filter(str.isdigit, ph))
            if len(digits) >= 10:
                lead = UserSubmission.objects.filter(phone__endswith=digits[-10:]).order_by('-id').first()
                if lead:
                    break

    city_val = str(payload.get('city') or '').strip()
    pin_val = str(payload.get('pincode') or '').strip()
    if pin_val and str(payload.get('country_code') or 'IN').upper() == 'IN':
        try:
            from voice_agent.services.dentist_service import get_pincode_canonical_city
            canon_c = get_pincode_canonical_city(pin_val)
            if canon_c:
                city_val = canon_c
        except Exception:
            pass
    if not city_val and payload.get('city'):
        city_val = str(payload.get('city')).strip()
    if "," in city_val:
        city_val = city_val.split(",")[-1].strip()

    if lead:
        if 'is_cancel' in payload:
            lead.is_cancel = is_cancel
        if payload.get('doctor_name') is not None:
            lead.doctor_name = payload.get('doctor_name')
        if payload.get('first_name'):
            lead.first_name = payload.get('first_name')
        if payload.get('last_name'):
            lead.last_name = payload.get('last_name')
        if phone_val and len("".join(filter(str.isdigit, phone_val))) >= 10:
            lead.phone = "".join(filter(str.isdigit, phone_val))[-10:]
        if city_val:
            lead.city = city_val
        if hasattr(lead, 'pincode') and pin_val:
            lead.pincode = pin_val
        if hasattr(lead, 'country_code') and payload.get('country_code'):
            lead.country = payload.get('country') or lead.country
            lead.country_code = payload.get('country_code')
        if payload.get('message'):
            lead.message = payload.get('message')
        if payload.get('email') and payload.get('email') not in ['no-reply@ultimatesmiledesign.com', '--', '-']:
            lead.email = payload.get('email')
        lead.save()
        print(f"[SUCCESS] Updated local UserSubmission lead ID {lead.id}! (City: {lead.city}, Pincode: {getattr(lead, 'pincode', '-')} Doctor: {lead.doctor_name}, Phone: {lead.phone}, is_cancel={lead.is_cancel})")
        return lead.id

    create_kwargs = {
        "first_name": payload.get('first_name', ''),
        "last_name": payload.get('last_name', '-'),
        "phone": phone_val,
        "email": payload.get('email') or 'no-reply@ultimatesmiledesign.com',
        "city": city_val,
        "message": payload.get('message', ''),
        "doctor_name": payload.get('doctor_name', ''),
        "is_cancel": is_cancel,
        "agree_to_terms": True
    }
    if hasattr(UserSubmission, 'pincode'):
        create_kwargs['pincode'] = pin_val
    if hasattr(UserSubmission, 'country_code'):
        create_kwargs['country'] = payload.get('country') or 'India'
        create_kwargs['country_code'] = payload.get('country_code') or 'IN'
    lead = UserSubmission.objects.create(**create_kwargs)
    print(f"[SUCCESS] Saved directly to local UserSubmission table! (ID: {lead.id}, City: {lead.city}, Pincode: {getattr(lead, 'pincode', '-')}, Name: {lead.first_name} {lead.last_name}, is_cancel={lead.is_cancel})")
    return lead.id

def sync_lead_to_godaddy_sqlite(payload: dict) -> int:
    """Remote GoDaddy HTTP sync to update the admin dashboard on ultimatesmiledesign.com."""
    if not ENABLE_GODADDY_SYNC:
        return 0
    try:
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Secret": INTERNAL_SYNC_SECRET
        }
        phone_raw = str(payload.get("phone", "")).strip()
        # Indian numbers stay 10 digits; international ones keep their '+<dial code>' (never cut to the last 10)
        phone_digits = phone_raw if phone_raw.startswith("+") else "".join(filter(str.isdigit, phone_raw))[-10:]
        sync_payload = {
            "first_name": payload.get("first_name", ""),
            "last_name": payload.get("last_name", "-"),
            "phone": phone_digits,
            "email": payload.get("email") or "no-reply@ultimatesmiledesign.com",
            "city": payload.get("city", ""),
            "pincode": payload.get("pincode", ""),
            "country": payload.get("country", "India"),
            "country_code": payload.get("country_code", "IN"),
            "message": payload.get("message", ""),
            "doctor_name": payload.get("doctor_name", ""),
            "is_cancel": bool(payload.get("is_cancel", False)),
            "is_update": bool(payload.get("is_update", False))
        }

        # For updates or cancellations, pass the GoDaddy lead ID (NEVER pass local SQLite ID)
        godaddy_id = payload.get("godaddy_id") or payload.get("godaddy_lead_id") or _GODADDY_LEAD_MAP.get(phone_digits)
        if godaddy_id:
            sync_payload["id"] = godaddy_id

        sync_url = GODADDY_SYNC_URL.strip()
        if not sync_url.startswith("http://") and not sync_url.startswith("https://"):
            sync_url = f"http://127.0.0.1:8000/{sync_url.lstrip('/')}"

        with httpx.Client(timeout=8.0) as client:
            resp = client.post(sync_url, json=sync_payload, headers=headers)
            print(f"[INFO] GoDaddy/Internal Admin Dashboard Sync response: {resp.status_code}")
            if resp.status_code == 200:
                res_data = resp.json()
                ret_id = res_data.get("lead_id")
                print(f"[SUCCESS] Lead synced to GoDaddy Admin Dashboard: ID {ret_id} (is_cancel={res_data.get('is_cancel')})")
                if ret_id:
                    payload["godaddy_id"] = ret_id
                    payload["godaddy_lead_id"] = ret_id
                    if phone_digits:
                        _GODADDY_LEAD_MAP[phone_digits] = ret_id
                return ret_id
            elif resp.status_code == 404:
                print("[WARN] GoDaddy returned 404. Make sure 'home/urls.py' and 'home/views.py' are deployed/reloaded on GoDaddy cPanel.")
    except Exception as e:
        print(f"[WARN] Failed to sync lead to GoDaddy SQLite: {e}")
    return 0

_API_LEAD_MAP = {}  # local UserSubmission id -> the consultation API's lead id
_API_SYNC_TASKS = {}  # local UserSubmission id -> in-flight consultation API task
# Submit waits for the API's full answer (its own timeout is 10 s); the UI shows "Riya is submitting..." meanwhile.
# Only a call that is still hanging after this finishes in the background.
API_SYNC_WAIT_SECONDS = float(os.getenv("CONSULT_API_WAIT_SECONDS", "12"))
_LOCAL_API_LEAD_MAP = _API_LEAD_MAP

def sync_lead_to_api_endpoint(payload: dict) -> int:
    """Dispatches consultation appointment lead directly to the consultation API endpoint."""
    from voice_agent.utils.country_utils import format_phone_for_display

    try:
        api_url = os.getenv("CONSULT_API_ENDPOINT") or os.getenv("LOCAL_API_ENDPOINT") or "https://ultimatesmiledesign.com/api/consult-with-dentist/"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        phone_raw = str(payload.get("phone", "")).strip()
        # This endpoint supplies the external lead list. Local records keep the compact number.
        if phone_raw.startswith("+"):
            api_phone = format_phone_for_display(phone_raw)
        else:
            national = "".join(filter(str.isdigit, phone_raw))[-10:]
            api_phone = format_phone_for_display(national, payload.get("country_code") or "IN")
        is_cancel = bool(payload.get("is_cancel", False))
        is_update = bool(payload.get("is_update", False))

        city_name = (payload.get("city") or "").strip().title()
        city_pincodes = {
            "Ahmedabad": "380001", "Surat": "395001", "Vadodara": "390001", "Rajkot": "360001",
            "Mumbai": "400001", "Pune": "411001", "Delhi": "110001", "New Delhi": "110001",
            "Gurugram": "122001", "Gurgaon": "122001", "Bangalore": "560001", "Bengaluru": "560001",
            "Hyderabad": "500001", "Chennai": "600001", "Indore": "452001", "Gwalior": "474001",
            "Jamnagar": "361001", "Bharuch": "392001"
        }
        pincode_val = str(payload.get("pincode") or "").strip()

        # Build exact fields matching the specification:
        # first_name, last_name, email, phone, city, message, doctor_name, source, pincode
        # NOTE: message must contain ONLY the patient's dental concern — never append pincode here.
        msg_text = payload.get("message", "") or "."

        api_payload = {
            "first_name": payload.get("first_name", "") or "",
            "last_name": payload.get("last_name", "-") or "-",
            "email": payload.get("email") or "no-reply@ultimatesmiledesign.com",
            "phone": api_phone or str(payload.get("phone", "")),
            "city": payload.get("city", "") or "",
            "pincode": pincode_val,
            "pin_code": pincode_val,
            "postal_code": pincode_val,
            "country": payload.get("country") or "India",
            "country_code": payload.get("country_code") or "IN",
            "message": msg_text,
            "doctor_name": payload.get("doctor_name", "") or "",
            "source": "voice_agent",
            "is_cancel": is_cancel,
            "is_update": is_update,
        }

        # Only an update/cancel of the lead THIS conversation created carries the API's own lead id. A new booking
        # never sends an id (it must become a new lead at the top), and the LOCAL db id is never sent: the API
        # treated local id 273 as its own (old, June) lead 273 and kept overwriting it.
        api_lead_id = None
        if is_cancel or is_update:
            api_lead_id = payload.get("api_id") or payload.get("local_api_id")

        if api_lead_id:
            api_payload["id"] = api_lead_id
            api_payload["submission_id"] = api_lead_id

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(api_url, json=api_payload, headers=headers)
            print(f"[INFO] Consultation API Endpoint ({api_url}) Response: {resp.status_code}")
            if resp.status_code in (200, 201):
                res_data = resp.json()
                ret_id = res_data.get("data", {}).get("id") or res_data.get("id")
                print(f"[SUCCESS] Lead posted to Consultation API endpoint: ID {ret_id} (is_cancel={is_cancel}, is_update={is_update})")
                if ret_id:
                    payload["api_id"] = ret_id
                    payload["local_api_id"] = ret_id
                    if payload.get("id"):
                        _API_LEAD_MAP[payload["id"]] = ret_id  # keyed by OUR lead id, never by phone
                return ret_id
            else:
                print(f"[WARN] Consultation API endpoint returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"[WARN] Failed to post lead to Consultation API endpoint ({api_url}): {e}")
    return 0

# def sync_to_zoho_crm(payload: dict):
#     """Syncs lead to Zoho CRM directly from Cloud Run."""
#     try:
#         zoho_url = "https://flow.zoho.in/60070945438/flow/webhook/incoming?zapikey=1001.a119cd21b36db26402ffe013750915ad.885b5855c0af73a633e0a39a93142bcd&isdebug=false"
#         zoho_payload = {
#             "Name": f"{payload.get('first_name', '')} {payload.get('last_name', '')}".strip(),
#             "Email": payload.get('email', ''),
#             "Phone": payload.get('phone', ''),
#             "City": payload.get('city', ''),
#             "Message": payload.get('message', ''),
#             "DoctorName": payload.get('doctor_name', ''),
#             "Website": "Ultimate Smile Design",
#             "FormName": "Patient appointment Form",
#         }
#         with httpx.Client(timeout=10.0) as client:
#             client.post(zoho_url, json=zoho_payload)
#             print("[INFO] Zoho CRM sync completed via Cloud Run.")
#     except Exception as e:
#         print(f"[WARN] Zoho CRM sync failed: {e}")

# def sync_to_bikayi_crm(payload: dict):
#     """Syncs lead to Bikayi CRM directly from Cloud Run."""
#     try:
#         bikai_url = "https://bikapi.bikayi.app/chatbot/webhook/N8eHI9BWzqVPK7RnXu2xs5qIQt23?flow=webpatient3834"
#         now_str = datetime.datetime.now().strftime("%d-%m-%Y %I:%M %p")
#         bikai_payload = {
#             "First_name": payload.get("first_name"),
#             "Last_name": payload.get("last_name"),
#             "Email": payload.get("email"),
#             "Phone": payload.get("phone"),
#             "City": payload.get("city"),
#             "Message": payload.get("message"),
#             "Doctor_name": payload.get("doctor_name"),
#             "DateTime": now_str,
#         }
#         with httpx.Client(timeout=10.0) as client:
#             client.post(bikai_url, json=bikai_payload)
#             print("[INFO] Bikayi CRM sync completed via Cloud Run.")
#     except Exception as e:
#         print(f"[WARN] Bikayi CRM sync failed: {e}")

def send_appointment_email(payload: dict):
    """(Disabled) Appointment booking/update/cancel emails have been completely discontinued."""
    return


async def submit_consultation_appointment(data: dict) -> dict:
    """
    Submits a confirmed dental consultation appointment request.
    Handles all CRM webhooks (Zoho & Bikayi) and Email notifications directly on Cloud Run,
    and performs a lightweight 2ms background sync to GoDaddy's SQLite database.
    """
    is_cancel = bool(data.get("is_cancel", False))
    sub_id = data.get("id") or data.get("submission_id")
    phone = str(data.get("phone", "")).strip()
    digits_only = "".join(filter(str.isdigit, phone))

    # A lead is only ever updated when THIS conversation created it (sub_id). Without one, a booking is new;
    # a cancellation may still find the patient's latest lead by phone.
    if not sub_id:
        data["is_update"] = False
        for k in ("api_id", "local_api_id", "godaddy_id", "godaddy_lead_id"):
            data.pop(k, None)

    # If this is an existing lead or cancellation, prefill missing fields from existing lead
    if (sub_id and (is_cancel or data.get("is_update"))) or (is_cancel and digits_only):
        try:
            lead_info = await fetch_existing_lead_data(sub_id, phone if is_cancel else None)
            if lead_info and not is_cancel and lead_info.get("is_cancel"):
                # Booking again after cancelling: that is a NEW request (new row at the top), not a revival of
                # the cancelled one
                print(f"[INFO] Lead {lead_info['id']} was cancelled -> this booking is saved as a new lead")
                for k in ("id", "submission_id", "api_id", "local_api_id", "godaddy_id", "godaddy_lead_id"):
                    data.pop(k, None)
                data["is_update"] = False
                sub_id = None
                lead_info = None
            if lead_info:
                if not data.get("first_name"):
                    data["first_name"] = lead_info["first_name"]
                if not data.get("last_name"):
                    data["last_name"] = lead_info["last_name"]
                if not data.get("city"):
                    data["city"] = lead_info["city"]
                if not data.get("country_code") and lead_info.get("country_code"):
                    data["country_code"] = lead_info["country_code"]
                if not data.get("pincode") and lead_info.get("pincode"):
                    data["pincode"] = lead_info["pincode"]
                if not data.get("doctor_name"):
                    data["doctor_name"] = lead_info["doctor_name"]
                if not data.get("message"):
                    data["message"] = lead_info["message"]
                if not data.get("email") or data.get("email") == "no-reply@ultimatesmiledesign.com":
                    data["email"] = lead_info["email"]
                if not sub_id:
                    data["submission_id"] = lead_info["id"]
                    data["id"] = lead_info["id"]
                    sub_id = lead_info["id"]
        except Exception as e:
            print(f"[INFO] Existing lead prefill skipped: {e}")

    # Fallback for cancellations where user only requests cancellation without repeating all slots
    if is_cancel:
        if not data.get("first_name"):
            data["first_name"] = "Patient"
        if not data.get("city"):
            data["city"] = "India"
        if not data.get("message"):
            data["message"] = "Appointment cancellation request"

    raw_first_name = str(data.get("first_name", "")).strip()
    if not is_cancel and (not raw_first_name or raw_first_name.lower() in ["none", "null", "user", "patient", "not provided", ""]):
        return {
            "status": "error",
            "missing_field": "first_name",
            "message": "Cannot submit appointment: Patient name is missing. Please ask the patient for their name before submitting."
        }
    if is_cancel and (not raw_first_name or raw_first_name.lower() in ["none", "null", "user", "not provided", ""]):
        raw_first_name = "Patient"

    raw_last_name = str(data.get("last_name", "")).strip()
    if not raw_last_name or raw_last_name.lower() in ["none", "null", "not provided", ""]:
        raw_last_name = "-"

    # Transliterate to English / Latin script
    first_name = transliterate_to_english(raw_first_name)
    last_name = transliterate_to_english(raw_last_name) if raw_last_name != "-" else "-"

    # Exactly a 10-digit mobile (a '0' / '91' prefix is fine); a longer number is never cut down to 10 digits
    from voice_agent.utils.helpers import normalize_mobile
    from voice_agent.utils import country_utils as cu
    country_code = str(data.get("country_code") or "IN").upper()
    is_intl = cu.is_international(country_code)
    phone = str(data.get("phone", "")).strip()
    if is_intl:
        # International: stored/sent with its dial code, e.g. '+971501234567' (never cut to 10 digits)
        digits_only = cu.format_e164(cu.normalize_phone(phone, country_code), country_code)
    else:
        digits_only = normalize_mobile(phone) or ""
    if not digits_only and is_intl:
        return {
            "status": "error",
            "missing_field": "phone",
            "message": f"Cannot submit appointment: a valid {cu.country_name(country_code)} mobile number ({cu.phone_digits_hint(country_code)} digits) is compulsory. Please ask the patient for it again."
        }
    if not digits_only:
        return {
            "status": "error",
            "missing_field": "phone",
            "message": "Cannot submit appointment: A valid 10-digit mobile number (exactly 10 digits, starting with 6-9) is compulsory. Please ask the patient for their 10-digit mobile number again before submitting."
        }

    city = str(data.get("city", "")).strip()
    if not is_cancel and (not city or city.lower() in ["none", "null", "not provided", "india", ""]):
        return {
            "status": "error",
            "missing_field": "city",
            "message": "Cannot submit appointment: City is missing. Please ask the patient which city they are located in."
        }
    if is_cancel and (not city or city.lower() in ["none", "null", "not provided", ""]):
        city = "India"

    matched_c = next((c for c in CERTIFIED_CITIES if c.lower() == city.lower()), None)
    if matched_c:
        city = matched_c
    else:
        city = city.title()
    data["city"] = city

    raw_pincode = str(data.get("pincode", "")).strip()
    digits_pin = "".join(filter(str.isdigit, raw_pincode))
    if is_intl:
        # Postal codes abroad can be alphanumeric (UK 'SW1A 1AA') or absent (UAE, Qatar): keep as given
        digits_pin = cu.validate_postal(raw_pincode, country_code) or ""
        if country_code == "BR" and not digits_pin and not is_cancel:
            return {"status": "error", "missing_field": "pincode", "message": cu.intl_text("ask_postal", "en", "BR")}
    elif not is_cancel and len(digits_pin) != 6:
        return {
            "status": "error",
            "missing_field": "pincode",
            "message": "Cannot submit appointment: Area pincode is missing. Please ask the patient for their 6-digit area pincode before submitting."
        }
    if is_cancel and not is_intl and len(digits_pin) != 6:
        digits_pin = digits_pin if len(digits_pin) == 6 else "380001"
    data["pincode"] = digits_pin

    raw_message = str(data.get("message", "")).strip()
    if not is_cancel and (not raw_message or raw_message.lower() in ["none", "null", "not provided", "dental consultation appointment request", ""]):
        return {
            "status": "error",
            "missing_field": "message",
            "message": "Cannot submit appointment: Patient's dental concern is missing. Please ask what dental issue they would like to consult about."
        }
    if is_cancel and (not raw_message or raw_message.lower() in ["none", "null", "not provided", ""]):
        raw_message = "Appointment cancellation request"
    
    # Ensure message is in English
    message = transliterate_to_english(raw_message) if any(ord(c) > 127 for c in raw_message) else raw_message

    # Doctor is strictly optional: anyone can book with or without doctor name
    raw_doc = str(data.get("doctor_name", "")).strip()
    if raw_doc and raw_doc.lower() not in ["none", "null", "not provided", "--", "-", "not selected", "pending", "પસંદ કરેલ નથી", "ચયનિત નહીં", "चयनित नहीं", "निवडले नाही"]:
        matched_doc = is_matched_doctor(raw_doc, city=city)
        if not matched_doc:
            matched_doc = is_matched_doctor(raw_doc, city=None)
        doctor_name = matched_doc if matched_doc else raw_doc
    else:
        doctor_name = ""
    data["doctor_name"] = doctor_name

    # ⚡ Duplicate Submission Guard: Ignore identical duplicate in-flight requests within 30s ⚡
    if not data.get("submission_id") and not data.get("is_update") and not data.get("is_cancel") and is_duplicate_submission(digits_only, doctor_name):
        print(f"[INFO] Deduplication guard: Submission for {digits_only} with {doctor_name} already in progress. Ignoring duplicate.")
        return {
            "status": "success",
            "message": "Appointment request has already been submitted.",
            "details": {"duplicate_prevented": True}
        }

    raw_email = str(data.get("email", "")).strip()
    if not raw_email or "@" not in raw_email or raw_email in ["--", "-", "none", "null", "not provided"]:
        valid_email = "no-reply@ultimatesmiledesign.com"
    else:
        valid_email = raw_email

    is_cancel = bool(data.get("is_cancel", False))
    if is_cancel and "[request cancel]" not in str(message):
        message = f"{message} [request cancel]".strip()

    sub_id = data.get("id") or data.get("submission_id")
    # Update only when there is a lead of this conversation to update; otherwise it is a new lead
    is_update = bool(sub_id)

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        "email": valid_email,
        "phone": digits_only,
        "city": city,
        "pincode": digits_pin,
        "country": cu.country_name(country_code),
        "country_code": country_code,
        "message": message,
        "doctor_name": doctor_name,
        "is_cancel": is_cancel,
        "is_update": is_update,
        "submission_id": sub_id,
        "id": sub_id
    }
    if data.get("api_id"):
        payload["api_id"] = data["api_id"]
    if data.get("local_api_id"):
        payload["local_api_id"] = data["local_api_id"]
    if data.get("godaddy_id"):
        payload["godaddy_id"] = data["godaddy_id"]
    
    action_str = "Cancellation" if is_cancel else "Booking"
    print(f"[INFO] Processing appointment {action_str} for: {payload['first_name']} {payload['last_name']} ({payload['city']}, Pincode: {payload.get('pincode', '-')}) with {payload['doctor_name']}")
    
    # ⚡ 1. Direct local database save (Primary local SQLite UserSubmission table) ⚡
    try:
        saved_id = await save_lead_to_local_db(payload)
        if saved_id:
            payload["id"] = saved_id
            payload["submission_id"] = saved_id
            data["submission_id"] = saved_id
            data["id"] = saved_id
    except Exception as db_err:
        print(f"[INFO] Local DB save skipped: {db_err}")

    # ⚡ 2. Direct POST to Consultation API endpoint ⚡
    # Waits for the API's answer (up to API_SYNC_WAIT_SECONDS; the voice UI shows "Riya is submitting..."), so the
    # lead is really saved before Riya says it is submitted. The API's lead id is
    # remembered per LOCAL lead id (_API_LEAD_MAP), and a later update/cancel of that same lead first waits for
    # the in-flight call, so it targets the API lead this conversation created - never another (old) lead.
    lead_key = payload.get("id")
    try:
        if is_update or is_cancel:
            prev_task = _API_SYNC_TASKS.get(lead_key) if lead_key else None
            if prev_task and not prev_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(prev_task), timeout=10.0)
                except Exception:
                    pass
            if not payload.get("api_id") and lead_key and _API_LEAD_MAP.get(lead_key):
                payload["api_id"] = _API_LEAD_MAP[lead_key]
        else:
            payload.pop("api_id", None)
            payload.pop("local_api_id", None)
        api_task = asyncio.create_task(asyncio.to_thread(sync_lead_to_api_endpoint, payload))
        if lead_key:
            _API_SYNC_TASKS[lead_key] = api_task
        try:
            api_id = await asyncio.wait_for(asyncio.shield(api_task), timeout=API_SYNC_WAIT_SECONDS)
        except asyncio.TimeoutError:
            api_id = 0
            print(f"[INFO] Consultation API slower than {API_SYNC_WAIT_SECONDS}s; finishing in the background")
        if api_id:
            payload["api_id"] = api_id
            data["api_id"] = api_id
            payload["local_api_id"] = api_id
            data["local_api_id"] = api_id
    except Exception as api_err:
        print(f"[WARN] Consultation API endpoint error: {api_err}")

    # ⚡ 2. Dispatch GoDaddy SQLite sync task in background (disabled for now - local database only) ⚡
    if ENABLE_GODADDY_SYNC:
        try:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, sync_lead_to_godaddy_sqlite, payload)
        except Exception as exec_err:
            print(f"[WARN] Error scheduling background tasks: {exec_err}")

    # ⚡ 3. Appointment email notification disabled ⚡


    msg = "Appointment request has been cancelled." if is_cancel else "Appointment request submitted successfully to Ultimate Smile Design team."
    return {
        "status": "success",
        "message": msg,
        "details": payload
    }
