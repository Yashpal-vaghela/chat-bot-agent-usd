import os
import re
import json
import base64
import asyncio
import httpx
import websockets
from websockets.exceptions import ConnectionClosed
from voice_agent.utils.constants import GEMINI_LIVE_MODEL, GEMINI_TEXT_MODEL, GEMINI_VOICE_NAME, get_live_model_name
from voice_agent.utils.helpers import clean_assistant_text, clean_hallucinations, extract_slots_from_review_summary
from voice_agent.navigation.commands import detect_best_tag, detect_best_tag_with_fallback
from voice_agent.audio.transcoder import wrap_pcm_to_wav_base64
from voice_agent.utils.ios_debug import ios_debug_log
from voice_agent.audio.transcriber import transcribe_voice_data
from voice_agent.services.appointment_service import submit_consultation_appointment, CERTIFIED_CITIES

from voice_agent.utils.helpers import is_cancel_submit, is_explicit_submit_command, is_affirmative_submit, is_cancel_response_text, is_submit_response_text
from voice_agent.utils.helpers import is_submit_review_summary, is_valid_indian_mobile, get_review_summary_problem
from voice_agent.utils.helpers import normalize_mobile, phone_from_user_turns


def build_summary_correction_note(problem, bad_phone=""):
    """Instruction for Gemini to speak a correction itself (same voice, same language) instead of the server
    appending a silent text bubble in a guessed language."""
    if problem == "phone_invalid":
        ask = (f"The phone number {bad_phone} is NOT a valid Indian mobile number (it must be exactly 10 digits and start with 6, 7, 8 or 9). "
               "Briefly apologise, say that number is not valid, and ask the patient to say their 10-digit mobile number again.")
    elif problem == "phone_mismatch":
        said_wrong, _, said_right = (bad_phone or "").partition("|")
        return (
            "[BACKEND NOTE - not spoken by the patient. Do not read this note aloud.] "
            f"Your summary used mobile number {said_wrong}, but the patient said {said_right}. The summary must NOT be submitted. "
            f"Briefly apologise and recite the COMPLETE review summary again with mobile number {said_right}, ending with the "
            "full sentence asking the patient to say 'submit' or 'cancel'. Use exactly the same language as your previous reply."
        )
    elif problem == "phone_unheard":
        ask = (f"The patient never actually said the number {bad_phone} - you may have guessed it. Ask the patient to say "
               "their 10-digit mobile number again slowly. NEVER invent or guess a phone number.")
    elif problem == "city_mismatch":
        pin, _, pin_city = (bad_phone or "").partition("|")
        ask = (f"The city in the summary does not match pincode {pin}, which belongs to {pin_city}. "
               f"Ask ONLY: 'Based on your pincode {pin}, you reside in {pin_city} area, right?' After the patient says yes, "
               f"use {pin_city} as the city and recite the corrected summary.")
    elif problem == "phone_missing":
        ask = "No valid 10-digit mobile number has been given yet. Ask the patient for their 10-digit mobile number."
    elif problem == "not_submitted":
        return (
            "[BACKEND NOTE - not spoken by the patient. Do not read this note aloud.] "
            "The appointment has NOT been submitted yet: submission only happens after the patient says 'submit' to a complete review summary. "
            "Briefly correct yourself, then recite the complete review summary (name, phone, city, pincode, concern, doctor) "
            "and ask the patient to say 'submit' or 'cancel'. Use exactly the same language you used in your previous reply."
        )
    else:
        field = {"name": "name", "pincode": "6-digit area pincode", "city": "city", "concern": "dental concern"}.get(problem, problem)
        ask = f"The patient's {field} is missing or unclear. Ask the patient only for their {field}."
    return (
        "[BACKEND NOTE - not spoken by the patient. Do not read this note aloud.] "
        "Your last review summary is NOT valid and must NOT be submitted. "
        f"{ask} Do NOT recite the summary or ask to submit in this reply. "
        "Reply in one or two short sentences, in exactly the same language you used in your previous reply."
    )


# Voice only, appended LAST to the system prompt so it overrides the shared prompt's Step 6 template and its many
# "re-recite the full review summary" instructions (those made Riya build the summary herself and only correct the
# phone number afterwards). The gatekeeper runs BEFORE any summary is spoken.
VOICE_REVIEW_GATEKEEPER_RULE = (
    "\n\n=========================================\n"
    "VOICE REVIEW SUMMARY GATEKEEPER (FINAL RULE - OVERRIDES EVERY OTHER INSTRUCTION ABOVE):\n"
    "- In this voice call you NEVER compose an appointment review summary yourself. Wherever the instructions above say "
    "'present', 'recite' or 're-recite' the review summary (Step 6, Step 7, after any update), do this instead: call the "
    "prepare_review_summary tool FIRST, before you say anything, and then speak ONLY what it returns.\n"
    "- As soon as the patient says their mobile number (or any number when you asked for it - even if it sounds too long "
    "or too short), call prepare_review_summary with the number exactly as you heard it, BEFORE replying. Do not judge "
    "or fix the number yourself; the backend checks it against the patient's own words (exactly 10 digits).\n"
    "- Pass name and concern as YOU understood them from the patient (you hear the patient directly; the backend's "
    "speech transcript is often wrong). The concern is the dental problem the patient described - never a yes/no reply.\n"
    "- status 'ok': speak 'say_exactly' word for word and COMPLETELY, to the last word of the sentence asking to say "
    "'submit' or 'cancel'. It is deliberately short: do NOT read out the details (they are shown on screen).\n"
    "- status 'ask_again': speak ONLY 'say_now' - no summary, no details, no submit/cancel line.\n"
    "- NEVER call prepare_review_summary before the patient has said their mobile number. Before that, follow the normal "
    "booking steps (concern -> consultation offer -> pincode -> doctor -> mobile number). Call it again only if the patient "
    "changes a detail AFTER the summary was shown.\n"
    "=========================================\n"
    "STAY ON TOPIC (FINAL RULE): you are ONLY Ultimate Smile Design's smile & dental consultant. Talk only about teeth, "
    "smiles, dental treatments, Ultimate Smile Design and the appointment. If the patient's words are about anything else "
    "(weather, clouds, rain, vehicles, their business, news, general knowledge...), do NOT explain, discuss or ask "
    "questions about that topic - not even one sentence. Acknowledge in a few words and bring the talk back, e.g. ask "
    "whether they have any question about their teeth/smile or the appointment. If you simply did not understand the "
    "patient (speech is often misheard), politely ask them to repeat - never invent a topic from a misheard word. The "
    "profession answer gets one short 'thank you' - never follow-up questions about their work."
)


APPOINTMENT_TOOL_DECLARATION = {
    "functionDeclarations": [
        {
            "name": "submit_appointment_booking",
            "description": "Submits a finalized patient dental consultation appointment booking to the Ultimate Smile Design clinic team after details (first_name, last_name, email, phone, city, pincode, message, doctor_name) have been verified with the patient.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "first_name": {"type": "STRING", "description": "Patient's confirmed first name"},
                    "last_name": {"type": "STRING", "description": "Patient's last name (or empty if not provided)"},
                    "email": {"type": "STRING", "description": "Patient's email address (optional, leave empty string if not provided)"},
                    "phone": {"type": "STRING", "description": "Patient's confirmed 10-digit Indian mobile number (must start with 6, 7, 8 or 9)"},
                    "city": {"type": "STRING", "description": "Patient's confirmed residence city (MUST be the patient's residence city where they live, e.g. Bhavnagar, NEVER the doctor's clinic city)"},
                    "pincode": {"type": "STRING", "description": "Patient's confirmed 6-digit area pincode / postal code"},
                    "message": {"type": "STRING", "description": "Patient's dental concern or consultation request notes"},
                    "doctor_name": {"type": "STRING", "description": "USD Authorised Dentist/Doctor name requested for the consultation (must be a verified USD authorised smile designer)"},
                    "is_cancel": {"type": "BOOLEAN", "description": "Whether the user requested to cancel the booking (true) or submit it (false)"}
                },
                "required": ["first_name", "phone", "city", "pincode", "message", "doctor_name"]
            }
        },
        {
            "name": "prepare_review_summary",
            "description": "GATEKEEPER - call it ONLY at the last booking step: right after the patient tells you their mobile number (call it even if the number sounds too long or too short), and again if the patient changes a detail AFTER the summary was shown. NEVER call it earlier (not after the name, concern, pincode or doctor) - it must be called BEFORE you speak the appointment review summary. NEVER recite a review summary yourself. The backend checks the mobile number against what the patient actually said and checks every detail. Pass name and concern as YOU understood them from the patient. If status is 'ok', speak 'say_exactly' word for word and COMPLETELY up to the last word of the sentence asking the patient to say submit or cancel; do NOT read out the details (they are shown on screen). If status is 'ask_again', do NOT speak any summary: say ONLY the 'say_now' text and wait.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "phone": {"type": "STRING", "description": "The patient's 10-digit mobile number exactly as you heard it"},
                    "doctor_name": {"type": "STRING", "description": "The USD doctor the patient chose, or empty if our team should guide them"},
                    "name": {"type": "STRING", "description": "Patient's name as YOU understood it from the patient (the backend transcript is unreliable), in the patient's language/script"},
                    "concern": {"type": "STRING", "description": "Patient's dental problem as YOU understood it, short, in the patient's language (e.g. 'દાંતમાં દુખાવો'). It is the problem they described - NEVER a yes/no answer like 'હા' / 'करू ने' / 'ok'"},
                    "name_english": {"type": "STRING", "description": "The patient's name in English letters (e.g. 'Nikhil'), for the clinic CRM"},
                    "concern_english": {"type": "STRING", "description": "The same dental problem in short plain English (e.g. 'Tooth pain', 'Gaps between teeth'), for the clinic CRM"}
                },
                "required": ["phone"]
            }
        },
        {
            "name": "find_dentists_in_city",
            "description": "Finds the USD Authorised Smile Designers in ANOTHER city the patient wants a doctor in (e.g. 'I am going to Bharuch tomorrow, give me a Bharuch doctor'), nearest to the patient's own pincode / travel route first. Call it whenever the patient asks for a doctor in a city other than the one you listed doctors for. It does NOT change the patient's residence city or pincode. Speak the doctors it returns with their clinic city.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "city": {"type": "STRING", "description": "The city the patient wants a doctor in, in English letters (e.g. 'Bharuch')"}
                },
                "required": ["city"]
            }
        },
        {
            "name": "check_doctor",
            "description": "Only for a DOCTOR'S NAME (for a city name use find_dentists_in_city). Checks whether a doctor the patient names is a USD Authorised Smile Designer (in ANY city - the patient may choose a doctor in another city, e.g. Bharuch while living in Surat). ALWAYS call this when the patient names a doctor that is not one of the nearest doctors you just told them, BEFORE you reply. NEVER say a doctor is not authorised / not ours without calling it - the nearest-doctor list only shows 3 doctors near the pincode, not all of them.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "doctor_name": {"type": "STRING", "description": "The doctor's name as the patient said it, in English letters if you can (e.g. 'Hafsha Saiyed')"}
                },
                "required": ["doctor_name"]
            }
        },
        {
            "name": "find_nearest_dentists",
            "description": "Finds and returns the nearest USD Authorised Smile Designer dentists based on the patient's confirmed 6-digit area pincode. STRICT MANDATE: You are strictly forbidden from calling this tool unless the patient has explicitly and genuinely provided a 6-digit area postal pincode in the conversation. NEVER guess, assume, or auto-pick a pincode from city name! If patient only gave a city, ask for their 6-digit area pincode first. As soon as the patient gives a 6-digit pincode you MUST call this tool before replying: NEVER name doctors from memory or from the city list - doctor names (and each doctor's clinic city) may only come from this tool's result (sorted by road distance) or from check_doctor, which verifies any other doctor the patient names. Follow the tool result's 'say_now' / 'say_exactly' texts. A NEW pincode first returns only the area question ('need_city_confirmation'); after the patient answers it (yes), call this tool AGAIN with the same pincode to get the doctor list - never ask the area question twice.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "pincode": {"type": "STRING", "description": "Patient's confirmed 6-digit area postal pincode provided explicitly by the user"},
                    "offset": {"type": "INTEGER", "description": "Starting offset for pagination (0 for first 3, 3 for next 3, 6 for next 3)"}
                },
                "required": ["pincode"]
            }
        }
    ]
}

def log_live_voice_conversation(user_text, bot_text, slots):
    import sys
    fn = slots.get('first_name') or '-'
    ln = slots.get('last_name') or '-'
    name_str = f"{fn} {ln}".strip() if ln != '-' else fn
    city_str = slots.get('city') or '-'
    pin_str = slots.get('pincode') or '-'
    doc_str = slots.get('doctor_name') or '-'
    msg_str = slots.get('message') or '-'
    phone_str = slots.get('phone') or '-'
    sub_str = "YES (Submitted to CRM)" if slots.get('is_submitted') else "No"

    sep = "=" * 70
    log_msg = (
        f"\n{sep}\n"
        f"⚡ [VOICE MODE - GEMINI LIVE]\n"
        f"👤 USER : {user_text}\n"
        f"🤖 RIYA : {bot_text}\n"
        f"📋 SLOTS: Name: {name_str} | City: {city_str} | Pincode: {pin_str} | Doctor: {doc_str} | Concern: {msg_str} | Phone: {phone_str} | Submitted: {sub_str}\n"
        f"{sep}\n"
    )
    try:
        print(log_msg, flush=True)
    except Exception:
        try:
            sys.stdout.buffer.write(log_msg.encode('utf-8', errors='replace') + b'\n')
            sys.stdout.buffer.flush()
        except Exception:
            pass

def append_to_live_log(msg):
    pass

def sanitize_gemini_history(history, max_turns=12):
    if not isinstance(history, list):
        return []
    sliced = history[-max_turns:] if len(history) > max_turns else history
    sanitized = []
    current_role = None
    current_parts = []
    
    for turn in sliced:
        r = 'model' if turn.get('role') == 'model' else 'user'
        t = turn.get('parts', [{}])[0].get('text', "")
        if not t:
            continue
        if r == current_role:
            current_parts.append(t)
        else:
            if current_role is not None:
                sanitized.append({"role": current_role, "parts": [{"text": " \n ".join(current_parts)}]})
            current_role = r
            current_parts = [t]
            
    if current_role is not None:
        sanitized.append({"role": current_role, "parts": [{"text": " \n ".join(current_parts)}]})
        
    if sanitized and sanitized[0]["role"] == 'model':
        sanitized.insert(0, {"role": "user", "parts": [{"text": "Hello"}]})
        
    return sanitized

def get_gemini_api_key():
    key = os.getenv("GEMINI_API_KEY_NEW") or os.getenv("GEMINI_API_KEY", "")
    return key.strip()

class GeminiClient:
    def __init__(self, session, send_json_callback, transcribe_bot_audio_callback):
        self.session = session
        self.send_json = send_json_callback
        self.transcribe_bot_audio = transcribe_bot_audio_callback
        
        api_key = get_gemini_api_key()
        self.gemini_ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"

    async def connect_and_loop(self, system_prompt):
        while self.session.is_client_connected:
            recv_task = None
            resumption_config = {}
            try:
                api_key = get_gemini_api_key()
                ws_url = f"wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={api_key}"
                live_model = get_live_model_name()
                print(f"[INFO] Connecting to Native Gemini Live API ({live_model})...")
                async with websockets.connect(ws_url) as ws:
                    self.session.gemini_ws = ws
                    print(f"[INFO] Connected to Native Gemini Live API (v1beta) - Model: {live_model}")
                    
                    self.session.setup_complete_event.clear()
                    
                    # Session Resumption: Seamlessly preserve conversation context across reconnects
                    resumption_config = {}
                    # latest_client_history is cleared after every turn, so it must not gate resumption.
                    # The handle lives on this browser connection's Session and is reset when a new call starts.
                    resumption_handle = getattr(self.session, 'gemini_resumption_handle', None)
                    if resumption_handle:
                        print(f"[INFO] Resuming Gemini Live Session with handle: {resumption_handle[:20]}...")
                        resumption_config = {"handle": resumption_handle}
                    else:
                        self.session.gemini_resumption_handle = None

                    live_system_prompt = system_prompt
                    active_mem = []
                    if self.session.user_name:
                        active_mem.append(f"- CURRENT CONFIRMED PATIENT NAME: {self.session.user_name}")
                    if self.session.booking_slots.get("city"):
                        active_mem.append(f"- CURRENT CONFIRMED PATIENT CITY: {self.session.booking_slots.get('city')}")
                    if self.session.booking_slots.get("phone"):
                        active_mem.append(f"- CURRENT CONFIRMED 10-DIGIT PHONE: {self.session.booking_slots.get('phone')}")
                    if self.session.booking_slots.get("doctor_name"):
                        active_mem.append(f"- CURRENT CONFIRMED DOCTOR: {self.session.booking_slots.get('doctor_name')}")
                    if self.session.user_concern:
                        active_mem.append(f"- CURRENT CONFIRMED DENTAL CONCERN: {self.session.user_concern}")
                    if self.session.booking_slots.get("pincode"):
                        active_mem.append(f"- CURRENT CONFIRMED AREA PINCODE: {self.session.booking_slots.get('pincode')}")
                    if getattr(self.session, 'recommended_dentists', None):
                        from voice_agent.services.dentist_service import format_dentist_recommendation_prompt
                        active_mem.append(format_dentist_recommendation_prompt(
                            self.session.recommended_dentists,
                            self.session.booking_slots.get("pincode", ""),
                            getattr(self.session, "dentist_page_offset", 0)
                        ))
                    active_mem.append("- COMPLETE BUT SHORT SENTENCES: Every response must consist of full, well-formed sentences and must never be cut off mid-sentence (e.g. '. કૃપા કરીને તમારો—'). Keep each spoken reply short: 1-3 sentences with at most ONE question. Only the final review summary may be longer.")
                    if self.session.booking_slots.get("is_submitted"):
                        active_mem.append("- APPOINTMENT ALREADY SUBMITTED: Do NOT re-ask for booking details.")

                    # Language guidance
                    if getattr(self.session, 'has_user_spoken', False) and getattr(self.session, 'is_language_established', False) and getattr(self.session, 'current_language', None):
                        active_mem.append(f"- MANDATORY LANGUAGE: The user's active language is {self.session.current_language}. You MUST respond in {self.session.current_language} beginning with [{self.session.current_language}]! However, if the user switches to another Indian language (e.g. Hindi, Gujarati, Marathi, English), immediately switch with them to that language!")
                    else:
                        active_mem.append("- STARTING LANGUAGE & DYNAMIC MATCHING: Start with greeting in Indian English beginning with [en-IN]. However, as soon as the user speaks in Hindi [hi-IN], Gujarati [gu-IN], Marathi [mr-IN], or any of the 11 supported Indian languages, YOU MUST IMMEDIATELY SWITCH YOUR RESPONSE to that same language and prefix with the appropriate language tag!")

                    # Sequential step-by-step appointment flow enforcement (STRICT ONE QUESTION AT A TIME)
                    if not self.session.user_name:
                        active_mem.append("- CURRENT SEQUENTIAL STEP (MANDATORY): Step 1 (Greeting & Patient Name). Ask warmly for their name. DO NOT ask for City, Concern, Doctor, Pincode, or Phone yet!")
                    elif not self.session.user_concern:
                        active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 1 done -> Step 2 (Dental Concern). Greet {self.session.user_name} by name and ask ONLY what specific dental concern or smile goal they have (do NOT ask them to confirm their name). YOU ARE STRICTLY FORBIDDEN from asking for City, Doctor, Pincode, or Phone!")
                    elif not getattr(self.session, "consultation_agreed", False) and not self.session.booking_slots.get("pincode"):
                        active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 2 confirmed -> Step 2.5 (Consultation Permission Gate). Acknowledge dental concern ({self.session.user_concern}), and ask ONLY: 'Would you like me to help book a consultation appointment with our USD Authorised Smile Designer for this?'. YOU MUST WAIT FOR PATIENT TO SAY YES before asking for Pincode! DO NOT ask about profession, city, or pincode in this turn!")
                    elif not self.session.booking_slots.get("pincode") and not getattr(self.session, "city_confirm_needed", False):
                        active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 3 (6-Digit Area Pincode FIRST). Ask ONLY for their 6-digit area pincode ('To help find your nearest USD Authorised Smile Designer, could you please tell me your 6-digit area pincode?'). YOU ARE STRICTLY FORBIDDEN from asking for city, doctor, or phone in this turn! DO NOT ask about profession!")
                    elif getattr(self.session, "city_confirm_needed", False) or (getattr(self.session, "pending_pincode", None) and not getattr(self.session, "city_pincode_locked", False)):
                        p_pin = getattr(self.session, "pending_pincode", "") or self.session.booking_slots.get("pincode", "")
                        p_cit = getattr(self.session, "pending_display_city", "") or getattr(self.session, "pending_city", "") or self.session.booking_slots.get("city", "")
                        if getattr(self.session, "asking_for_field", None) == "city_confirmation":
                            # Reconnect after the area question was already asked: asking it again started the loop
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 3.5 done. You ALREADY asked whether the patient lives in {p_cit} (pincode {p_pin}) - NEVER ask that again. If the patient says yes / anything but 'wrong', call find_nearest_dentists with pincode {p_pin} and tell the doctors it returns. Only if they say the area is wrong, ask for their correct 6-digit pincode.")
                        else:
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 3.5 (Confirm City from Pincode ONLY). Pincode {p_pin} is located in {p_cit} area. Ask ONLY this one single question to confirm if they reside in {p_cit} area: 'Based on your pincode {p_pin}, you reside in {p_cit} area, right?'. 🚨 ABSOLUTE PROHIBITION: DO NOT recommend doctors, DO NOT ask doctor guidance, and DO NOT ask for phone number! Output ONLY this single question and wait for the patient to say yes/right!")
                    elif getattr(self.session, "is_travel_booking_turn", False) or (getattr(self.session, "travel_destination_city", None) and not self.session.booking_slots.get("doctor_name")):
                        t_dest = getattr(self.session, "travel_destination_city", "") or self.session.booking_slots.get("clinic_city", "")
                        r_cit = self.session.booking_slots.get("city", "")
                        r_pin = self.session.booking_slots.get("pincode", "")
                        active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Travel Booking in {t_dest}. Patient resides in {r_cit} ({r_pin}) and wants appointment in {t_dest}. DO NOT change residence city or pincode! DO NOT ask for a pincode in {t_dest}! Recommend the 3 nearest dentists in {t_dest} closest to their arrival route.")
                    elif getattr(self.session, "consultation_declined", False):
                        active_mem.append("- CONSULTATION DECLINED: Patient previously declined consultation or appointment booking. Converse purely as a helpful smile consultant answering their dental/treatment questions. DO NOT push appointment booking or ask for doctor/phone!")
                    elif not self.session.booking_slots.get("doctor_name") and not getattr(self.session, "doctor_guidance_asked", False):
                        if getattr(self.session, "recommended_dentists_spoken", False):
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 4 (Doctor Choice Follow-up). The 3 nearest dentist names for pincode {self.session.booking_slots.get('pincode')} have ALREADY been spoken to the patient. 🚨 ABSOLUTE BAN: DO NOT repeat or speak the dentist names again! Ask if they prefer one of those doctors or want clinic team to guide them. If patient says 'no', 'nahi', 'nathi', accept gracefully without asking again!")
                        else:
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 4 (Doctor Guidance ONLY). Call find_nearest_dentists with pincode {self.session.booking_slots.get('pincode')} and speak the 3 nearest dentist names it returns, each with the doctor's clinic city (never names from memory), and ask if they prefer one or want clinic team to guide them. YOU ARE STRICTLY FORBIDDEN from asking for phone number in Step 4! Wait for their doctor response!")
                    elif not self.session.booking_slots.get("phone"):
                        bad_num = getattr(self.session, 'last_invalid_phone_input', '') or ''
                        if bad_num and len(bad_num) != 10:
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 5 (Phone Number ONLY). Patient provided an INVALID phone number ({bad_num}, {len(bad_num)} digits). An Indian mobile number MUST have exactly 10 digits. Tell them: 'You provided {len(bad_num)} digits ({bad_num}). A valid mobile number has 10 digits. Could you please provide your 10-digit mobile number?'. YOU ARE STRICTLY FORBIDDEN from reciting the review summary!")
                        else:
                            active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 5 (Phone Number ONLY). Doctor addressed. Ask ONLY for their 10-digit mobile number so clinic team can contact them ('Could you please provide your 10-digit mobile phone number?'). DO NOT recite review summary yet! DO NOT ask to submit yet! When they say it, call prepare_review_summary.")
                    elif not self.session.booking_slots.get("is_submitted"):
                        active_mem.append(f"- CURRENT SEQUENTIAL STEP (MANDATORY): Step 6 (Review Summary). Call prepare_review_summary and speak its 'say_exactly' text completely (it ends with: 'Please say submit to submit this appointment request to our clinic team, or say cancel to cancel it.').")

                    active_mem.append("- STRICT 10-DIGIT PHONE INTEGRITY: Indian mobile phone numbers have EXACTLY 10 digits AND start with 6, 7, 8 or 9 (e.g. a number starting with 1 or 0 is invalid - ask again). NEVER invent, add, or complete digits to an incomplete phone number (e.g. if the user says 9 digits like '984255299', NEVER add a 10th digit and DO NOT show review summary). If the phone number does not have exactly 10 digits, YOU MUST NOT recite the review summary under ANY circumstances! Tell the user that their number has fewer or more digits and ask for the complete 10-digit number.")
                    if getattr(self.session, "profession_asked", False) or getattr(self.session, "consultation_agreed", False) or self.session.booking_slots.get("pincode") or self.session.booking_slots.get("city"):
                        active_mem.append("- PROFESSION INQUIRY FORBIDDEN DURING BOOKING: Do NOT ask 'what is your profession?' while the booking is in progress." + ("" if getattr(self.session, "profession_done", False) else " EXCEPTION (mandatory, once): it has never been asked yet, so right after the appointment is submitted or cancelled, or when the patient declines the consultation/appointment, your reply MUST end with ONLY the profession question."))
                    active_mem.append("- ONE QUESTION PER REPLY (ABSOLUTE): Every reply may contain only ONE question. If you need several things, ask the single most important one now and the next one in a later reply. NEVER combine two asks, for example: name confirmation + dental concern, dental concern + consultation offer, pincode/city confirmation + profession or consultation offer, dentist names + phone number. The profession question is always its own reply.")
                    if active_mem:
                        live_system_prompt += f"\n\n=========================================\nACTIVE PATIENT MEMORY (HIGH PRIORITY OVERRIDE):\n" + "\n".join(active_mem) + "\n========================================="
                    live_system_prompt += VOICE_REVIEW_GATEKEEPER_RULE

                    live_voice = os.getenv("GEMINI_VOICE_NAME") or GEMINI_VOICE_NAME or "Aoede"
                    # All 11 supported Indian languages (keeps transcription away from Korean/Portuguese/etc.);
                    # the patient's language, once known (e.g. on a reconnect), goes first
                    input_lang_codes = [c.strip() for c in os.getenv(
                        "GEMINI_INPUT_LANGUAGE_CODES",
                        "en-IN,hi-IN,gu-IN,mr-IN,bn-IN,ta-IN,te-IN,kn-IN,ml-IN,pa-IN,or-IN").split(",") if c.strip()]
                    known_lang = getattr(self.session, "current_language", None)
                    if known_lang in input_lang_codes and getattr(self.session, "is_language_established", False):
                        input_lang_codes.remove(known_lang)
                        input_lang_codes.insert(0, known_lang)
                    setup_message = {
                        "setup": {
                            "model": live_model,
                            "generationConfig": {
                                "responseModalities": ["AUDIO"],
                                # Lower temperature keeps a reply from degenerating into a loop ("Dr. Dr. Pagisha ...");
                                # 2048 is needed: 1024 cut the Gujarati review summary off before "submit"
                                "temperature": 0.6,
                                "maxOutputTokens": 2048,
                                "speechConfig": {
                                    "voiceConfig": {
                                        "prebuiltVoiceConfig": {
                                            "voiceName": live_voice
                                        }
                                    }
                                }
                            },
                            "realtimeInputConfig": {
                                "automaticActivityDetection": {
                                    "disabled": False,
                                    "prefixPaddingMs": 300,
                                    "silenceDurationMs": 900
                                }
                            },
                            "tools": [APPOINTMENT_TOOL_DECLARATION],
                            "sessionResumption": resumption_config,
                            "contextWindowCompression": {
                                "slidingWindow": {}
                            },
                            "outputAudioTranscription": {},
                            # Language hints: with auto-detection the patient's Hindi/Gujarati was transcribed as
                            # Korean/Portuguese/Spanish, so the backend never read the name or concern
                            "inputAudioTranscription": {"languageCodes": input_lang_codes} if input_lang_codes else {},
                            "systemInstruction": {"parts": [{"text": live_system_prompt}]}
                        }
                    }
                    await ws.send(json.dumps(setup_message))
                    self.session.initial_greeting_sent = False
                    
                    # Start the receive loop task
                    recv_task = asyncio.create_task(self.gemini_recv_loop(ws))
                    
                    # Await setupComplete frame from Gemini Live with a timeout
                    try:
                        await asyncio.wait_for(self.session.setup_complete_event.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        print("[WARN] Timeout waiting for Gemini Live setupComplete!")
                    
                    # If this is a fresh connection with prior history, seed the context
                    if not resumption_handle and self.session.latest_client_history:
                        history_to_inject = sanitize_gemini_history(self.session.latest_client_history)
                        await ws.send(json.dumps({
                            "clientContent": {
                                "turns": history_to_inject,
                                "turnComplete": False
                            }
                        }))
                        self.session.initial_greeting_sent = True
                    
                    # Await the receive loop to finish cleanly when connection closes or GoAway occurs
                    await recv_task
                        
            except ConnectionClosed as e:
                print(f"[INFO] Gemini Live WS Connection closed: {e}")
            except Exception as e:
                print(f"[ERROR] Gemini Live WS Error: {e}")
            finally:
                self.session.gemini_ws = None
                if recv_task and not recv_task.done():
                    recv_task.cancel()
                # A stale/expired handle makes setup fail; drop it so the next attempt starts a fresh session
                if resumption_config and not self.session.setup_complete_event.is_set():
                    print("[WARN] Gemini Live resumption failed before setupComplete. Discarding handle.")
                    self.session.gemini_resumption_handle = None
                    
            if not self.session.is_client_connected:
                break
                
            print("[INFO] Gemini Live connection reset. Automatically reconnecting & resuming session...")
            ios_debug_log(self.session, "srv_gemini_reconnect")
            await asyncio.sleep(0.3)

    async def sync_slots_to_gemini(self):
        """The ACTIVE PATIENT MEMORY in the setup prompt is built once per connection, so mid-call Gemini never saw
        server-confirmed details (it recited Surat while the pincode said Rajkot). Push the current booking slots as
        silent context (turnComplete=False never triggers or interrupts a reply). Only sent when something changed."""
        ws = self.session.gemini_ws
        if not ws:
            return
        bs = self.session.booking_slots

        def _val(v, missing="not given yet"):
            v = str(v or "").strip()
            return v if v and v.lower() not in ["none", "null", "-", "--"] else missing

        # Name / concern parsed from the speech transcript are often wrong ("करू ने" stored as the concern), so they
        # are never pushed to Riya as verified: she uses what she understood, unless a summary already fixed them
        confirmed = getattr(self.session, "last_review_summary_slots", None) or getattr(self.session, "last_consumed_summary_slots", None) or {}
        heard_self = "use the name/problem exactly as the patient told you in this conversation (you heard them directly); do NOT ask again if already told"
        from voice_agent.services.dentist_service import get_doctor_city
        docs = getattr(self.session, "recommended_dentists", None) or []
        docs_txt = ", ".join(
            f"{d.get('name')} ({get_doctor_city(d) or d.get('city') or '?'})" for d in docs if d.get("name")
        )
        summary = (
            "[BACKEND NOTE - not spoken by the patient. Do not reply to this note or read it aloud. "
            "Use these verified booking details; never invent or change them unless the patient says so. "
            "Remember: ask only ONE question per reply. Stay on teeth / smile / appointment topics only - never discuss or "
            "ask about unrelated topics (weather, clouds, vehicles, work...); steer back to the patient's smile. NEVER name a doctor that the find_nearest_dentists or check_doctor tool "
            "did not return; if the patient names another doctor, call check_doctor before answering (never say a doctor is "
            "not ours without it); if the patient wants a doctor in another city (e.g. travelling to Bharuch), call "
            "find_dentists_in_city - never answer with the nearest list of their own pincode instead; when you name a doctor, also say the doctor's clinic city. NEVER speak the appointment review "
            "summary yourself: call prepare_review_summary first and speak its 'say_exactly' text completely.] "
            f"Name: {_val(confirmed.get('user_name'), heard_self)} | Concern: {_val(confirmed.get('user_concern'), heard_self)} | "
            f"City: {_val(bs.get('city'), (str(getattr(self.session, 'pending_display_city', '') or getattr(self.session, 'pending_city', '')) + ' (from the pincode; area question already asked - do NOT ask it again; when the patient says yes, call find_nearest_dentists again with the pincode and tell the doctors it returns)') if getattr(self.session, 'pending_city', None) else 'not given yet')} | "
            f"Pincode: {_val(bs.get('pincode') or getattr(self.session, 'pending_pincode', ''))} | "
            f"Phone: {_val(bs.get('phone')) if is_valid_indian_mobile(bs.get('phone')) else 'not given yet'} | "
            f"Nearest doctors already told to the patient: {docs_txt or 'none yet'} | "
            f"Doctor: {bs.get('doctor_name') or 'optional - use the doctor the patient chose in the conversation, if any'} | "
            f"Appointment submitted: {'yes' if bs.get('is_submitted') else 'no'}"
        )
        if getattr(self.session, "profession_done", False):
            summary += " | Profession question: ALREADY asked - NEVER ask it again (not even after a re-submission)."
        else:
            from voice_agent.ai.conversation_manager import profession_question_text
            summary += (
                " | Profession question: NOT asked yet. RULE: if the patient declines the consultation/appointment "
                "(says no / not now / not interested), or right after the appointment is submitted or cancelled, your reply "
                f"MUST end with ONLY this question in the patient's language: '{profession_question_text(self._voice_lang())}'. "
                "Do not ask it in the middle of the booking."
            )
        if summary == getattr(self.session, "last_synced_slot_summary", None):
            return
        try:
            await ws.send(json.dumps({
                "clientContent": {
                    "turns": [{"role": "user", "parts": [{"text": summary}]}],
                    "turnComplete": False
                }
            }))
            self.session.last_synced_slot_summary = summary
        except Exception as e:
            print(f"[WARN] Failed to sync slots to Gemini Live: {e}")

    def begin_residence_change(self, pin_val, canonical_city, display_city, sub_area):
        """A NEW pincode (different from the booked one) means the patient is moving residence: the city must be
        re-confirmed from that pincode before dentists are listed, and after the "yes" both city and pincode change.
        Returns True when it paused the flow for that confirmation."""
        booked_pin = re.sub(r"\D", "", str(self.session.booking_slots.get("pincode") or ""))
        pin_val = re.sub(r"\D", "", str(pin_val or ""))
        if not booked_pin or booked_pin == pin_val:
            return False
        self.session.pending_pincode = pin_val
        self.session.pending_city = canonical_city
        self.session.pending_display_city = display_city
        self.session.pending_area = sub_area
        self.session.city_confirm_needed = True
        self.session.asking_for_field = "city_confirmation"
        self.session.city_pincode_locked = False
        self.session.recommended_dentists = []
        print(f"[CITY-CHANGE] New pincode {pin_val} (was {booked_pin}) -> confirming city '{display_city}'")
        return True

    # ---------------------------------------------------------------------------------------------
    # Nearest-dentist step for voice mode. Chat mode builds the dentist reply on the server
    # (format_dentists_speech_text: road-distance order + each doctor's clinic city); voice mode
    # left the wording - and whether to fetch at all - to Gemini, which skipped the list after the
    # city confirmation, dropped the doctors' cities, or named doctors that were never fetched.
    # These helpers give Gemini the same server-built sentence chat mode sends.
    # ---------------------------------------------------------------------------------------------
    def _voice_lang(self):
        return getattr(self.session, "current_language", None) or "en-IN"

    @staticmethod
    def _dentist_entries(dentists):
        from voice_agent.services.dentist_service import get_doctor_city
        return [
            {
                "name": d.get("name"),
                "clinic_name": d.get("clinic_name"),
                "clinic_city": get_doctor_city(d) or d.get("city") or "",
                "pincode": d.get("pincode"),
                "address": d.get("address") or "",
            }
            for d in dentists
        ]

    def _dentist_speech(self, dentists, pin_val, offset_val=0, user_city=None, is_update=False, after_city_confirm=False):
        from voice_agent.services.dentist_service import format_dentists_speech_text
        return format_dentists_speech_text(
            dentists, pin_val, self._voice_lang(),
            is_more=offset_val > 0, is_update=is_update,
            user_city=user_city or self.session.booking_slots.get("city"),
            after_city_confirm=after_city_confirm,
        )

    def _mark_dentists_recommended(self, dentists, pin_val, offset_val):
        self.session.recommended_dentists = dentists
        self.session.recommended_dentists_spoken = True
        self.session.doctor_guidance_asked = True
        self.session.dentist_page_offset = offset_val
        self.session.last_recommended_pincode = pin_val
        self.session.pending_dentists = None

    def _lock_pending_city(self, pin_val=None):
        """The patient confirmed the area detected from their pincode: make it the booking city."""
        pin_val = pin_val or getattr(self.session, "pending_pincode", None) or self.session.booking_slots.get("pincode")
        if getattr(self.session, "pending_city", None):
            self.session.booking_slots["city"] = self.session.pending_city
        if pin_val:
            self.session.booking_slots["pincode"] = pin_val
        if getattr(self.session, "pending_area", None):
            self.session.booking_slots["area"] = self.session.pending_area
        self.session.city_pincode_locked = True
        self.session.city_manually_confirmed = True
        self.session.city_confirm_needed = False
        self.session.pending_city = None
        self.session.pending_display_city = None
        self.session.pending_area = None
        self.session.pending_pincode = None
        self.session.city_confirm_turn_id = None
        self.session.asking_for_field = "doctor_selection"

    def _dentist_success_result(self, dentists, total_count, next_offset, pin_val, offset_val, speech):
        result = {
            "status": "success",
            "pincode": pin_val,
            "city": self.session.booking_slots.get("city") or "",
            "offset": offset_val,
            "next_offset": next_offset,
            "total_found": total_count,
            "dentists": self._dentist_entries(dentists),
        }
        if speech:
            result["say_exactly"] = speech
            result["instruction"] = (
                "Your reply MUST be the 'say_exactly' text, word for word. It already lists the nearest doctors "
                "(sorted by road distance) together with each doctor's clinic city. Do NOT change, reorder, add or "
                "drop any doctor name or city, and do NOT add another question. If the patient is speaking a "
                "different language, translate it faithfully but keep every doctor name and city. "
                "Do NOT ask for the phone number in this reply."
            )
        else:
            result["instruction"] = (
                "Speak all doctor names from 'dentists' together with their clinic_city, then ask ONLY whether they "
                "want one of these doctors or should our team guide them. Do NOT ask for the phone number in this reply."
            )
        return result

    # Words for "pincode" in the languages Riya speaks (used to know Riya actually asked for it)
    PINCODE_WORDS = ("pincode", "pin code", "postal code", "પિનકોડ", "પિન કોડ", "पिनकोड", "पिन कोड", "পিনকোড",
                     "பின்கோட்", "పిన్‌కోడ్", "పిన్ కోడ్", "ಪಿನ್‌ಕೋಡ್", "ಪಿನ್ ಕೋಡ್", "പിൻകോഡ്", "ਪਿਨਕੋਡ", "ପିନକୋଡ୍")

    @staticmethod
    def _ascii_digits(text):
        """Gujarati/Devanagari/other Indic digits -> 0-9, so '૩૮૦૦૦૧' / '३८०००१' match '380001'."""
        import unicodedata
        return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in str(text or ""))

    def _user_said_pincode(self, pin_val):
        """True when the patient's own words (this turn or an earlier one) contain this pincode."""
        texts = [getattr(self.session, "current_user_transcription", "") or "",
                 getattr(self.session, "latest_typed_user_text", "") or ""]
        texts += [t for role, t in (getattr(self.session, "transcript_history", None) or [])[-12:] if role == "user"]
        for t in texts:
            t = self._ascii_digits(t)
            if pin_val in t or pin_val in re.sub(r"\D", "", t):
                return True
        return False

    def track_pincode_request(self, bot_text):
        """Remember that Riya asked the patient for their pincode (a question without a 6-digit number in it)."""
        if not bot_text:
            return
        low = bot_text.lower()
        if any(w in low for w in self.PINCODE_WORDS) and not re.search(r"\d{6}", self._ascii_digits(bot_text)):
            self.session.pincode_asked_by_bot = True

    PHONE_UNHEARD_11 = {
        "gu": "માફ કરશો, મને તમારો મોબાઇલ નંબર બરાબર સંભળાયો નહીં. શું તમે તમારો 10 અંકનો મોબાઇલ નંબર ફરીથી ધીમેથી જણાવશો?",
        "hi": "माफ़ कीजिए, मुझे आपका मोबाइल नंबर ठीक से सुनाई नहीं दिया। क्या आप अपना 10 अंकों का मोबाइल नंबर फिर से धीरे-धीरे बताएंगे?",
        "mr": "माफ करा, मला तुमचा मोबाइल नंबर नीट ऐकू आला नाही. तुमचा 10 अंकी मोबाइल नंबर पुन्हा हळू सांगाल का?",
        "en": "Sorry, I could not hear your mobile number clearly. Could you please say your 10-digit mobile number again, slowly?",
    }

    PHONE_NOT_10 = {
        "gu": "માફ કરશો, તમે જણાવેલા નંબરમાં બરાબર 10 અંક નથી. કૃપા કરીને તમારો 10 અંકનો મોબાઇલ નંબર ફરીથી જણાવશો?",
        "hi": "माफ़ कीजिए, आपके बताए नंबर में पूरे 10 अंक नहीं हैं। कृपया अपना 10 अंकों का मोबाइल नंबर फिर से बताएंगे?",
        "mr": "माफ करा, तुम्ही सांगितलेल्या नंबरमध्ये बरोबर 10 अंक नाहीत. कृपया तुमचा 10 अंकी मोबाइल नंबर पुन्हा सांगाल का?",
        "en": "Sorry, the number you gave does not have exactly 10 digits. Could you please say your 10-digit mobile number again?",
    }

    def _user_turn_texts(self):
        """Everything the patient said in this call (transcript turns + the turn in progress)."""
        said = [t for role, t in (getattr(self.session, "transcript_history", None) or []) if role == "user"]
        for extra in (getattr(self.session, "current_user_transcription", "") or "",
                      getattr(self.session, "latest_typed_user_text", "") or ""):
            if extra and (not said or said[-1] != extra):
                said.append(extra)
        return said

    async def prepare_review_summary(self, args):
        """Server-checked review summary: Riya used to recite a summary with a number she never heard and only
        afterwards say the number was missing; and she sometimes cut the closing 'say submit or cancel' sentence."""
        from voice_agent.ai.conversation_manager import build_review_summary_text, get_missing_field_message
        from voice_agent.services.appointment_service import is_matched_doctor
        lang = self._voice_lang()[:2].lower()
        bs = self.session.booking_slots

        def ask(field, say_now=None):
            self.session.asking_for_field = field
            self.session.review_prepared_turn = None
            return {
                "status": "ask_again",
                "missing": field,
                "say_now": say_now or get_missing_field_message(lang, field),
                "message": "Do NOT speak any review summary. Say ONLY the 'say_now' text and wait for the patient.",
            }

        # Name and concern: what Riya understood (she hears the audio itself) wins over the backend's parse of the
        # speech transcript, which is random for Indian languages (the patient's "करू ने" = "yes, do it" was stored
        # as the concern and recited in the summary)
        def _arg(key):
            v = str(args.get(key) or "").strip()
            return "" if v.lower() in ("none", "null", "-", "--", "not provided", "unknown") else v
        name = (_arg("name") or self.session.user_name or "").strip()
        concern = (_arg("concern") or self.session.user_concern or bs.get("message") or "").strip()
        name_en = _arg("name_english")
        concern_en = _arg("concern_english")

        # Too early: the gatekeeper is only for the moment the patient has given their mobile number (the last
        # step). Called right after the concern it answered "pincode missing", so Riya skipped the consultation offer
        # and kept repeating "before submitting, tell me your pincode".
        pin_now = "".join(filter(str.isdigit, str(bs.get("pincode") or "")))
        number_said = phone_from_user_turns(self._user_turn_texts(), pin_now)[0] != "none"
        if not number_said and not normalize_mobile(bs.get("phone")):
            print("[REVIEW-SUMMARY] called before the patient gave a mobile number -> not_ready")
            return {
                "status": "not_ready",
                "message": "Ignore this call: the patient has not given their mobile number yet, so there is no summary. "
                           "Do NOT mention this check and do NOT recite any summary. Simply give the reply you would have given "
                           "to the patient's last message (if you were telling the nearest doctors, continue that). NEVER repeat "
                           "a question the patient has already answered (name, concern, consultation, pincode/area confirmation). "
                           "Call prepare_review_summary only after the patient says their mobile number.",
            }
        city = str(bs.get("city") or "").strip()
        pin = "".join(filter(str.isdigit, str(bs.get("pincode") or "")))
        # Exactly 10 digits only - never cut a longer number down to 10
        phone = normalize_mobile(args.get("phone")) or ""

        if not name:
            return ask("name")
        if not concern:
            return ask("concern")
        if len(pin) != 6:
            return ask("pincode")
        if not city:
            return ask("city")
        # The patient's own transcript is the source of truth for the number (what the screen shows is what is
        # submitted). Riya used to invent numbers ('9193862652') or keep 10 digits of a 12-digit answer.
        said = self._user_turn_texts()
        status, said_phone = phone_from_user_turns(said, pin)
        if status == "wrong_length":
            print(f"[REVIEW-SUMMARY] patient said {said_phone} ({len(said_phone)} digits), not a 10-digit mobile -> asking again")
            bs["phone"] = ""
            return ask("phone", self.PHONE_NOT_10.get(lang))
        if status == "ok":
            if phone and phone != said_phone:
                print(f"[REVIEW-SUMMARY] Gemini passed phone {phone}, transcript says {said_phone} -> using the transcript")
            phone = said_phone
        else:
            # Nothing usable in the transcript (spoken digits are often transcribed only partly): fall back to
            # Gemini's number, but only if 4+ of the patient's digits are inside it (or it is the stored number)
            if not phone and normalize_mobile(bs.get("phone")):
                phone = normalize_mobile(bs.get("phone"))
            if not is_valid_indian_mobile(phone):
                return ask("phone", self.PHONE_UNHEARD_11.get(lang))
            said_digits = [re.sub(r"\D", "", self._ascii_digits(t)) for t in said]
            heard = phone == normalize_mobile(bs.get("phone")) or \
                any(phone in d or (len(d) >= 4 and d in phone) for d in said_digits)
            if not heard:
                print(f"[REVIEW-SUMMARY] phone {phone} was never said by the patient -> asking again")
                return ask("phone", self.PHONE_UNHEARD_11.get(lang))
        if not is_valid_indian_mobile(phone):
            return ask("phone", self.PHONE_NOT_10.get(lang))

        doctor = str(args.get("doctor_name") or bs.get("doctor_name") or "").strip()
        if doctor:
            doctor = is_matched_doctor(doctor, city=None) or ""
        is_update = bool(bs.get("is_submitted") or bs.get("submission_id"))
        text = build_review_summary_text(lang, name, phone, city, pin, concern, doctor, is_update=is_update)

        # The CRM gets Riya's English version when she gives one (otherwise the service transliterates)
        crm_parts = (name_en or name).split()
        crm_message = concern_en or concern
        self.session.user_name = name
        self.session.user_concern = concern
        bs["phone"] = phone
        bs["doctor_name"] = doctor
        bs["message"] = crm_message
        self.session.last_review_summary_slots = {
            "first_name": crm_parts[0], "last_name": " ".join(crm_parts[1:]) if len(crm_parts) > 1 else "-",
            "user_name": name_en or name,
            "phone": phone, "city": city, "pincode": pin, "message": crm_message, "user_concern": crm_message,
            "doctor_name": doctor,
        }
        # Spoken: only the opening and the closing 'submit / cancel' sentence. A ~25 s recital of every detail was
        # often cut off before the closing sentence (echo / noise barge-in stops the rest of the audio). The full
        # summary with every detail is shown on screen and saved in the transcript (see the turn-complete handler).
        spoken, _ = self._short_spoken_summary(text)
        self.session.last_review_summary_text = text
        self.session.review_prepared_turn = self.session.current_voice_turn_id
        self.session.asking_for_field = None
        print(f"[REVIEW-SUMMARY] ok: name={name!r} concern={concern!r} crm_message={crm_message!r} phone={phone}")
        # Show the full summary on screen right now. Gemini's own speech transcript lags behind the audio and was
        # sometimes cut to just "Sure!", so the patient never saw the details (and had to ask for them).
        self.session.pending_summary_card = text
        try:
            await self.send_json({"type": "review_summary_card", "text": text, "turnId": self.session.current_voice_turn_id})
        except Exception as e:
            print(f"[WARN] Could not send review summary card: {e}")
        return {
            "status": "ok",
            "say_exactly": spoken,
            "instruction": "Speak 'say_exactly' word for word and COMPLETELY, to the very last word of the sentence asking "
                           "the patient to say 'submit' or 'cancel'. Do NOT read out the details (name, phone, city, pincode, "
                           "concern, doctor) - the full summary is shown to the patient on screen automatically. Do not add "
                           "anything else and do not ask another question.",
        }

    @staticmethod
    def _known_city(text):
        """The canonical USD city named in `text` ('Bharuch', 'ભરૂચ', 'भरूच', 'bharuch ma'), else ''."""
        from voice_agent.ai.conversation_manager import CITY_DOCTORS
        from voice_agent.services.appointment_service import transliterate_to_english
        from voice_agent.utils.helpers import MULTILINGUAL_CITY_MAP
        raw = str(text or "").strip()
        if not raw:
            return ""
        low = raw.lower()
        for alias, city in MULTILINGUAL_CITY_MAP.items():
            # Native-script names ('ભરૂચ' / 'भरूच') do not transliterate to the English spelling
            if city not in CITY_DOCTORS:
                continue
            a = alias.lower()
            hit = re.search(r"\b" + re.escape(a) + r"\b", low) if a.isascii() else (a in low)
            if hit:
                return city
        cands = [low]
        if any(ord(ch) > 127 for ch in raw):
            cands.append(transliterate_to_english(raw).lower())
        for cand in cands:
            cand = re.sub(r"[^a-z ]", " ", cand)
            for city in CITY_DOCTORS:
                if re.search(r"\b" + re.escape(city.lower()) + r"\b", cand):
                    return city
        return ""

    def find_dentists_in_city(self, args):
        """Doctors in another city the patient asked for (travel), nearest to their pincode / route first. The
        patient's residence city and pincode stay as they are. Chat mode already did this; voice only knew the
        nearest list of the patient's own pincode, so 'give me a Bharuch doctor' got Surat doctors again."""
        from voice_agent.ai.conversation_manager import CITY_DOCTORS
        from voice_agent.services.dentist_service import get_nearest_dentists_for_travel, get_doctor_city
        city = self._known_city(args.get("city")) or str(args.get("city") or "").strip().title()
        bs = self.session.booking_slots
        dentists = []
        try:
            dentists = get_nearest_dentists_for_travel(bs.get("pincode") or "", bs.get("city") or "", city) or []
        except Exception as e:
            print(f"[WARN] find_dentists_in_city failed for {city}: {e}")
        if not dentists and city in CITY_DOCTORS:
            dentists = [{"name": n, "city": city} for n in CITY_DOCTORS[city]]
        entries = [{"name": d.get("name"), "clinic_city": get_doctor_city(d) or d.get("city") or ""} for d in dentists]
        in_city = [e for e in entries if e["clinic_city"].lower() == city.lower()]
        if not in_city:
            # No USD doctor in that city: the lookup returns the nearest ones elsewhere - never present them as "in" it
            nearest = entries[:3]
            if nearest:
                self._mark_dentists_recommended(dentists[:3], bs.get("pincode") or "", 0)
            return {
                "status": "none_in_city",
                "city": city,
                "nearest_elsewhere": nearest,
                "message": f"There is no USD Authorised Smile Designer in {city}. Say that in one short sentence"
                           + (", then name the nearest ones from 'nearest_elsewhere' WITH their clinic city" if nearest else "")
                           + ", and ask whether the patient would like one of them or a doctor near their own pincode. "
                             "Do NOT invent doctors and do NOT change the patient's own city or pincode.",
            }
        entries = in_city[:3]
        self._mark_dentists_recommended([d for d in dentists if d.get("name") in {e["name"] for e in entries}],
                                        bs.get("pincode") or "", 0)
        return {
            "status": "ok",
            "city": city,
            "dentists": entries,
            "message": f"Tell the patient the USD Authorised Smile Designer(s) in {city} (nearest to them first), each with "
                       "the clinic city, and ask whether they would like to consult one of them. Do NOT change or re-confirm "
                       "the patient's own city or pincode. One question only.",
        }

    def check_doctor(self, args):
        """Any USD Authorised doctor in any city. Gemini only knew the 3 nearest doctors of the pincode, so when the
        patient asked for Dr. Hafsha Saiyed (Bharuch) while living in Surat, Riya said she was not a USD designer."""
        from voice_agent.services.appointment_service import is_matched_doctor
        from voice_agent.services.dentist_service import get_doctor_city
        from voice_agent.ai.conversation_manager import find_doctor_in_text
        raw = str(args.get("doctor_name") or "").strip()
        # A city is not a doctor: 'Bharuch' was loosely matched to 'Dr. Bharat R. Patel'
        if self._known_city(raw) and not re.search(r"\bdr\b|doctor|ડૉ|ડો\.|डॉ", raw, re.IGNORECASE):
            return self.find_dentists_in_city({"city": raw})
        doc = is_matched_doctor(raw, city=None) if raw else ""
        if not doc:
            # Gemini's spelling may be off: also try the patient's own last words
            for t in reversed(self._user_turn_texts()[-2:]):
                try:
                    doc = find_doctor_in_text(t, None) or ""
                except Exception:
                    doc = ""
                if doc:
                    break
        if not doc:
            return {
                "status": "not_found",
                "message": "No USD Authorised Smile Designer with that name was found - the name may have been misheard. "
                           "Politely ask the patient to say the doctor's name again (or the clinic city). Do NOT say the doctor "
                           "is not genuine, and do NOT repeat the earlier list unless the patient asks for it.",
            }
        clinic_city = get_doctor_city(doc) or ""
        bs = self.session.booking_slots
        if bs.get("doctor_name") != doc:
            bs["doctor_name"] = doc
            if bs.get("is_submitted") or bs.get("submission_id"):
                # A change after submission: the patient must re-confirm the updated summary
                bs["is_submitted"] = False
                self.session.slots_edited_after_submit = True
        return {
            "status": "authorised",
            "doctor_name": doc,
            "clinic_city": clinic_city,
            "message": f"YES - {doc} is a USD Authorised Smile Designer (clinic in {clinic_city}). Patients may choose any "
                       "authorised doctor, also in another city. Confirm the choice in one short sentence (say the clinic city), "
                       "then continue: if the review summary was already shown or the appointment was already submitted, call "
                       "prepare_review_summary for the updated summary; otherwise ask only the next missing detail.",
        }

    @staticmethod
    def _short_spoken_summary(text):
        """(spoken text, closing sentence): the summary's opening line + its closing 'submit / cancel' sentence."""
        lines = [l.strip() for l in str(text or "").splitlines() if l.strip()]
        if len(lines) < 3:
            return text, (lines[-1] if lines else "")
        opener = lines[0]
        if re.search(r"[:：]\s*$", opener):
            # "...અપડેટ કરી દીધી છે. તમારી અપડેટ કરેલી વિગતો:" -> drop the dangling "your details:" lead-in when a
            # full sentence (ending in . or ।) precedes it; otherwise end the line as a sentence
            m = re.match(r"^(.*[.।])\s+[^.।!?]+[:：]\s*$", opener)
            if m:
                opener = m.group(1)
            else:
                stop = "।" if re.search(r"[ऀ-ॿ]", opener) else "."
                opener = re.sub(r"\s*[:：]\s*$", stop, opener)
        return f"{opener} {lines[-1]}", lines[-1]

    def sync_pending_dentists_after_turn(self, bot_text):
        """After Gemini's turn: if it spoke the dentist list prepared during the city confirmation, the patient
        did not reject the area, so lock the city and record the dentists as recommended (as chat mode does)."""
        pending = getattr(self.session, "pending_dentists", None)
        if not pending or not bot_text:
            return
        low = bot_text.lower()
        # Gemini's speech transcript is often cut off ("તમારા પિનકોડ 394130 મુજબ, તમારા સૌથી નજીકના"), so the word
        # "nearest" is enough; the area question ("... વિસ્તારમાં રહો છો, બરાબર ને?") never contains it
        nearest_words = ("nearest", "નજીકના", "નજીકની", "नज़दीकी", "नजदीकी", "नजीकचे", "जवळचे", "ନିକଟତମ", "নিকটতম",
                         "அருகிலுள்ள", "సమీప", "ಹತ್ತಿರದ", "അടുത്തുള്ള", "ਨੇੜਲੇ")
        spoke_list = "smile designer" in low or any(w in low for w in nearest_words) or any(
            (d.get("name") or "").split()[-1].lower() in low for d in pending if (d.get("name") or "").split()
        )
        if not spoke_list:
            return
        pin_val = getattr(self.session, "pending_dentists_pincode", None) or self.session.booking_slots.get("pincode")
        # A rejected area clears pending_city, so a pending city for this same pincode means it was not rejected
        # (city_confirm_needed / asking_for_field are not reliable here: other slot parsing overwrites them)
        if getattr(self.session, "pending_city", None) and str(getattr(self.session, "pending_pincode", "") or "") == str(pin_val or ""):
            self._lock_pending_city(pin_val)
            print(f"[INFO] Voice city confirmed via dentist list: {pin_val} -> {self.session.booking_slots.get('city')}")
        self._mark_dentists_recommended(pending, pin_val, 0)
        print(f"[INFO] Voice dentists recommended for {pin_val}: {[d.get('name') for d in pending]}")

    def consume_review_summary(self):
        """A summary is good for exactly one submission. Afterwards neither a stray "yes" nor a later "book it" may
        re-submit it (or a pre-cancellation summary): the next submission needs a freshly recited summary."""
        txt = (getattr(self.session, "last_review_summary_text", "") or "").strip()
        if txt:
            self.session.consumed_summary_texts.add(txt)
        if self.session.last_review_summary_slots:
            # Kept so an explicit "re-submit my appointment" can reuse it
            self.session.last_consumed_summary_slots = dict(self.session.last_review_summary_slots)
        self.session.last_review_summary_slots = {}
        self.session.last_review_summary_text = ""

    async def request_spoken_correction(self, note):
        """Ask Gemini to speak a short correction as its next turn. At most one per patient turn: the reply to this
        note is flagged so it can never trigger another note."""
        ws = self.session.gemini_ws
        if not ws:
            return
        try:
            await ws.send(json.dumps({"realtimeInput": {"text": note}}))
            self.session.awaiting_correction_reply = True
        except Exception as e:
            print(f"[WARN] Failed to send correction note to Gemini Live: {e}")

    async def gemini_recv_loop(self, ws):
        try:
            async for raw_message in ws:
                if not self.session.is_client_connected:
                    break
                    
                response = json.loads(raw_message)
                
                # SESSION RESUMPTION UPDATES (Store fresh handle for zero-interruption reconnects)
                if "sessionResumptionUpdate" in response:
                    update = response["sessionResumptionUpdate"]
                    if update.get("resumable") and update.get("newHandle"):
                        # Updated many times per minute; not printed so the conversation log stays readable
                        self.session.gemini_resumption_handle = update["newHandle"]
                    continue

                # GOAWAY SIGNAL: Server signals upcoming connection closure. Cleanly close to trigger instant resumption
                if "goAway" in response:
                    go_away = response["goAway"]
                    time_left = go_away.get("timeLeft", "unknown")
                    print(f"[WARN] Gemini Live GoAway received (time left: {time_left}). Triggering clean session resumption...")
                    ios_debug_log(self.session, "srv_goaway", time_left=time_left)
                    await ws.close()
                    break

                if "setupComplete" in response:
                    print("[INFO] Gemini Live Setup Complete!")
                    ios_debug_log(self.session, "srv_setup_complete")
                    self.session.setup_complete_event.set()
                    continue

                # ⚡ TOOL CALL HANDLING (Direct Appointment Submission via Ultimate Smile Design API) ⚡
                if "toolCall" in response:
                    tool_call = response["toolCall"]
                    function_calls = tool_call.get("functionCalls", [])
                    ios_debug_log(self.session, "srv_tool_call", names=[fc.get("name") for fc in function_calls])
                    function_responses = []
                    for fc in function_calls:
                        func_name = fc.get("name")
                        func_id = fc.get("id")
                        args = fc.get("args", {})
                        print(f"[INFO] Gemini Live invoked Tool Call: {func_name} with args: {args}")
                        # Show "Riya is submitting / cancelling / checking" so the pause during the lookup is explained
                        if func_name == "submit_appointment_booking":
                            await self.send_json({"type": "status_update", "status": "cancelling" if args.get("is_cancel") else "submitting"})
                        elif func_name in ("find_nearest_dentists", "prepare_review_summary", "check_doctor", "find_dentists_in_city"):
                            await self.send_json({"type": "status_update", "status": "checking"})
                        if func_name == "submit_appointment_booking":
                            # ⚡ The last VALID review summary the patient heard is the source of truth ⚡
                            # (last_review_summary_slots only ever holds summaries whose every field passed validation)
                            sum_slots = dict(getattr(self.session, "last_review_summary_slots", {}) or {})
                            if sum_slots:
                                for k, v in sum_slots.items():
                                    if v and str(v).lower() not in ["none", "null", "-", "--"]:
                                        self.session.booking_slots[k] = v
                                if sum_slots.get("user_name"):
                                    self.session.user_name = sum_slots["user_name"]
                                    u_p = sum_slots["user_name"].split()
                                    self.session.booking_slots["first_name"] = u_p[0]
                                    self.session.booking_slots["last_name"] = " ".join(u_p[1:]) if len(u_p) > 1 else "-"
                                if sum_slots.get("user_concern") or sum_slots.get("message"):
                                    self.session.user_concern = sum_slots.get("user_concern") or sum_slots.get("message")
                                    self.session.booking_slots["message"] = self.session.user_concern

                            # 1. Base slots from booking_slots & sum_slots
                            full_args = dict(self.session.booking_slots)
                            # Cancellation comes only from THIS turn (tool arg or the patient's words), never from an
                            # earlier cancel still stored in the slots (that turned a re-booking into another cancel)
                            full_args.pop('is_cancel', None)
                            if sum_slots:
                                for k, v in sum_slots.items():
                                    if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                        if k not in full_args or not full_args[k]:
                                            full_args[k] = v
                            
                            # 2. Update with args from tool call
                            for k, v in args.items():
                                if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                    full_args[k] = v
                                    self.session.booking_slots[k] = v
                            
                            # 3. Check for explicitly updated slots in current user utterance
                            curr_u_text = str(getattr(self.session, 'current_user_transcription', '') or getattr(self.session, 'latest_typed_user_text', '') or '')
                            curr_u_lower = curr_u_text.lower().strip()
                            
                            user_phone_match = re.search(r'\b[6-9]\d{9}\b', curr_u_text)
                            if user_phone_match:
                                new_phone = user_phone_match.group(0)
                                if self.session.booking_slots.get('phone') and self.session.booking_slots['phone'] != new_phone:
                                    self.session.booking_slots['old_phone'] = self.session.booking_slots['phone']
                                full_args['phone'] = new_phone
                                self.session.booking_slots['phone'] = new_phone
                            elif args.get('phone'):
                                arg_phone = ''.join(filter(str.isdigit, str(args['phone'])))
                                if len(arg_phone) == 10:
                                    if self.session.booking_slots.get('phone') and self.session.booking_slots['phone'] != arg_phone:
                                        self.session.booking_slots['old_phone'] = self.session.booking_slots['phone']
                                    full_args['phone'] = arg_phone
                                    self.session.booking_slots['phone'] = arg_phone
                            
                            user_pin_match = re.search(r'\b[1-9]\d{5}\b', curr_u_text)
                            if user_pin_match:
                                new_pin = user_pin_match.group(0)
                                full_args['pincode'] = new_pin
                                self.session.booking_slots['pincode'] = new_pin
                            elif args.get('pincode'):
                                arg_pin = ''.join(filter(str.isdigit, str(args['pincode'])))
                                if len(arg_pin) == 6:
                                    full_args['pincode'] = arg_pin
                                    self.session.booking_slots['pincode'] = arg_pin
                            
                            if not full_args.get('message') and self.session.user_concern:
                                full_args['message'] = self.session.user_concern
                            # Ensure patient's confirmed residence city is NEVER overwritten by doctor's clinic city
                            if self.session.booking_slots.get('city') and getattr(self.session, 'city_manually_confirmed', False):
                                full_args['city'] = self.session.booking_slots['city']
                            if self.session.user_name:
                                u_p = self.session.user_name.split()
                                full_args['first_name'] = u_p[0]
                                full_args['last_name'] = ' '.join(u_p[1:]) if len(u_p) > 1 else '-'
                            # Guard against placeholder doctor phrases & canonicalize real doctor name
                            doc_val = str(full_args.get('doctor_name') or '').lower()
                            placeholder_words = ['हमारे डॉक्टर', 'અમારા ડૉક્ટર', 'our doctor', 'doctor in', 'ડોક્ટર છે', 'डॉक्टर हैं', 'ceramist', 'सिरामिस्ट', 'સેરેમિસ્ટ', 'haresh savani']
                            if any(pw in doc_val for pw in placeholder_words):
                                full_args['doctor_name'] = ''
                                self.session.booking_slots['doctor_name'] = ''
                            elif doc_val:
                                from voice_agent.services.appointment_service import is_matched_doctor
                                matched_d = is_matched_doctor(full_args['doctor_name'], city=self.session.booking_slots.get('clinic_city') or full_args.get('clinic_city'))
                                if not matched_d:
                                    matched_d = is_matched_doctor(full_args['doctor_name'], city=None)
                                if matched_d:
                                    full_args['doctor_name'] = matched_d
                                    self.session.booking_slots['doctor_name'] = matched_d
                            
                            sub_id = self.session.booking_slots.get('submission_id') or getattr(self.session, 'submitted_lead_id', None)
                            full_args['submission_id'] = sub_id
                            full_args['id'] = sub_id
                            if self.session.booking_slots.get('godaddy_id'):
                                full_args['godaddy_id'] = self.session.booking_slots.get('godaddy_id')
                            if self.session.booking_slots.get('api_id'):
                                full_args['api_id'] = self.session.booking_slots.get('api_id')
                            if self.session.booking_slots.get('old_phone'):
                                full_args['old_phone'] = self.session.booking_slots.get('old_phone')
                            if is_cancel_submit(curr_u_text):
                                full_args['is_cancel'] = True
                            full_args['is_update'] = bool(sub_id) or bool(self.session.booking_slots.get('is_submitted')) or bool(getattr(self.session, 'slots_edited_after_submit', False))
                            
                            # Guard: Check if user is actively requesting an edit/update without confirming submit
                            is_edit_request = any(ew in curr_u_lower for ew in [
                                'change', 'update', 'edit', 'instead', 'no my', 'no, my', 'spelling', 'mistake',
                                'wrong', 'incorrect', 'ખોટું', 'ખોટો', 'ખોટી', 'ખોટા', 'ખોટો છે', 'ખોટી છે', 'ખોટું છે',
                                'બદલ', 'બદલો', 'બદલવો', 'બદલવી', 'બદલવું', 'બદલવા', 'સુધાર', 'સુધારો', 'સુધારવો', 'સુધારવી', 'સુધારવું',
                                'ફેરફાર', 'ચેન્જ', 'ચેંજ', 'ચેંન્જ', 'અપડેટ', 'गलत', 'बदल', 'बदलो', 'बदलना', 'बदल दीजिए', 'बदल दो',
                                'सुधार', 'सुधारो', 'सुधारना', 'खो तो', 'खोटो', 'खोता', 'खोती', 'अपडेट', 'badlo', 'badlav', 'sudharo'
                            ])
                            is_explicit_sub = is_explicit_submit_command(curr_u_text)
                            is_user_affirmed = is_affirmative_submit(curr_u_text)
                            if any(w in curr_u_lower for w in ['sommeil', 'sommet', 'soit', 'somet', 'sammit', 'submarino']):
                                is_explicit_sub = True
                                is_user_affirmed = True
                            f_cancel = bool(full_args.get('is_cancel'))

                            # The summary the patient approved wins over tool args and transcript parsing
                            for k, v in sum_slots.items():
                                if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                    full_args[k] = v
                            if sum_slots.get('user_concern'):
                                full_args['message'] = sum_slots['user_concern']

                            # Mandatory fields check before calling submit_consultation_appointment
                            f_fn = bool(full_args.get('first_name') and full_args['first_name'].lower() not in ['', 'none', 'null', 'patient', 'user'])
                            f_city = bool(full_args.get('city') and len(str(full_args['city']).strip()) >= 2 and str(full_args['city']).lower() not in ['none', 'null', 'india', ''])
                            f_pin = bool(full_args.get('pincode') and len(''.join(filter(str.isdigit, str(full_args['pincode'])))) == 6)
                            f_msg = bool(full_args.get('message') and len(full_args['message'].strip()) >= 2 and full_args['message'].lower() not in ['none', 'null', 'dental consultation appointment request', ''])
                            f_phone = is_valid_indian_mobile(full_args.get('phone'))

                            # Already submitted and unchanged (e.g. the patient only ASKED 'is my appointment submitted?'):
                            # the consumed summary used to make this answer 'NOT submitted' and re-recite the summary
                            submitted_unchanged = bool(self.session.booking_slots.get("is_submitted")) and not bool(self.session.booking_slots.get("is_cancel")) \
                                and not getattr(self.session, "slots_edited_after_submit", False)
                            if not f_cancel and submitted_unchanged:
                                print("[GUARD] submit_appointment_booking on an already submitted, unchanged appointment -> already_submitted")
                                result = {"status": "already_submitted", "message": "This appointment request is ALREADY successfully submitted and nothing has changed since. Do NOT submit again, do NOT say it is not submitted and do NOT recite the summary. Tell the patient in one short sentence that their appointment request is already submitted and our team will contact them soon."}
                            elif not f_cancel and not sum_slots:
                                print("[GUARD] Gemini Live attempted submit_appointment_booking without a valid review summary. Blocking.")
                                result = {
                                    "status": "waiting_confirmation",
                                    "message": "NOT submitted. There is no valid review summary yet. If the 10-digit mobile number (starting with 6-9) or any other detail is missing or invalid, ask for it first. If the city does not match the pincode, confirm the city from the pincode first. NEVER repeat the same summary you just recited: fix the wrong detail, then recite the corrected summary and ask the patient to say 'submit' or 'cancel'."
                                }
                            elif is_edit_request and not (is_explicit_sub or is_user_affirmed) and not f_cancel:
                                print(f"[GUARD] Gemini Live attempted submit_appointment_booking while user requested edit without submitting ('{curr_u_text}'). Blocking submission.")
                                self.session.booking_slots["is_submitted"] = False
                                self.session.slots_edited_after_submit = True
                                result = {
                                    "status": "edit_in_progress",
                                    "message": "User is updating/changing details. DO NOT submit yet! Ask for the updated detail, update summary, and wait for confirmation."
                                }
                            elif not f_cancel and not (is_explicit_sub or is_user_affirmed):
                                print(f"[GUARD] Gemini Live attempted premature submit_appointment_booking without user confirmation ('{curr_u_text}'). Blocking.")
                                result = {
                                    "status": "waiting_confirmation",
                                    "message": "Appointment summary is prepared. Do NOT submit yet! Recite the full summary and ask patient to say 'submit' to confirm or 'cancel' to cancel."
                                }
                            elif not f_cancel and not (f_fn and f_city and f_pin and f_msg and f_phone):
                                missing_name = "phone"
                                if not f_fn: missing_name = "patient name"
                                elif not f_msg: missing_name = "dental concern"
                                elif not f_city: missing_name = "city"
                                elif not f_pin: missing_name = "6-digit area pincode"
                                result = {
                                    "status": "error",
                                    "missing_field": missing_name,
                                    "message": f"Cannot submit appointment! The required field '{missing_name}' has not been provided yet. Ask patient to provide their {missing_name} first."
                                }
                            else:
                                result = await submit_consultation_appointment(full_args)
                            if result.get("status") == "success" and not getattr(self.session, "profession_done", False):
                                from voice_agent.ai.conversation_manager import profession_question_text
                                result = dict(result)
                                result["next_step"] = (
                                    "Tell the patient the result in one short sentence, then end your reply with ONLY this "
                                    f"question, in the patient's language: '{profession_question_text(self._voice_lang())}'"
                                )
                            elif result.get("status") == "success":
                                result = dict(result)
                                result["next_step"] = ("Tell the patient the result in one short sentence. Do NOT ask about their "
                                                       "profession - it was already asked earlier in this conversation.")
                            if result.get("status") == "success":
                                self.session.booking_slots["is_submitted"] = True
                                self.session.slots_edited_after_submit = False
                                self.session.last_submit_turn_id = self.session.current_voice_turn_id
                                self.consume_review_summary()
                                if full_args.get("is_cancel"):
                                    self.session.booking_slots["is_cancel"] = True
                                    self.session.pending_cancellation = False
                                else:
                                    self.session.booking_slots["is_cancel"] = False
                                if isinstance(result.get("details"), dict):
                                    ret_id = result["details"].get("id") or result["details"].get("submission_id")
                                    if ret_id:
                                        self.session.booking_slots["submission_id"] = ret_id
                                        self.session.submitted_lead_id = ret_id
                                    if result["details"].get("godaddy_id"):
                                        self.session.booking_slots["godaddy_id"] = result["details"]["godaddy_id"]
                                    if result["details"].get("api_id"):
                                        self.session.booking_slots["api_id"] = result["details"]["api_id"]
                                for k, v in full_args.items():
                                    if v is not None:
                                        if k in ('is_submitted', 'is_cancel', 'is_update'):
                                            pass  # set from the backend result above; this pre-submit copy (is_submitted=False) must not undo it
                                        elif isinstance(v, bool):
                                            self.session.booking_slots[k] = v
                                        else:
                                            self.session.booking_slots[k] = str(v)
                                await self.send_json({
                                    "type": "sync_slots",
                                    "slots": self.session.booking_slots
                                })
                            function_responses.append({
                                "name": func_name,
                                "id": func_id,
                                "response": {"result": result}
                            })
                        elif func_name == "find_nearest_dentists":
                            pin_val = str(args.get("pincode") or "").strip()
                            if not pin_val and self.session.booking_slots.get("pincode"):
                                pin_val = self.session.booking_slots.get("pincode")
                            try:
                                offset_val = int(args.get("offset") or 0)
                            except (TypeError, ValueError):
                                offset_val = 0

                            actual_pincode = self.session.booking_slots.get("pincode", "")
                            curr_u_text = str(getattr(self.session, "current_user_transcription", "") or "")
                            latest_typed = str(getattr(self.session, "latest_typed_user_text", "") or "")
                            # Gemini passes the pincode the way the patient said it ("39 41 30", "394-130"): digits only.
                            # With the spaces it looked like a NEW pincode and the area question was asked again and again.
                            pin_val = re.sub(r"\D", "", self._ascii_digits(pin_val))
                            said_pin = bool(pin_val) and self._user_said_pincode(pin_val)
                            user_spoke_pin = bool(pin_val and len(pin_val) == 6 and pin_val.isdigit() and said_pin)

                            # Gemini invented pincodes (380001 / 390001) right after the concern and started the
                            # booking. Accept a pincode only if the patient said it, Riya asked for it (the transcript
                            # can garble the digits), or it is the booking's / pending pincode already.
                            known_pins = {str(actual_pincode or ""), str(getattr(self.session, "pending_pincode", "") or "")}
                            if pin_val and pin_val not in known_pins and not said_pin and not getattr(self.session, "pincode_asked_by_bot", False):
                                print(f"[GUARD] Gemini Live invented pincode '{pin_val}' (patient never said it, Riya never asked). Rejected.")
                                function_responses.append({
                                    "name": func_name,
                                    "id": func_id,
                                    "response": {"result": {
                                        "status": "pincode_not_given",
                                        "message": (
                                            f"REJECTED: the patient has NOT told you any pincode - '{pin_val}' was invented. Do NOT use it and do "
                                            "NOT name any city, area or doctor. Continue the normal flow from where it is: acknowledge the "
                                            "patient's dental concern if you have not yet, then ask whether they would like to book a "
                                            "consultation; only after they agree, ask ONLY for their 6-digit area pincode. Ask one question only."
                                        )
                                    }}
                                })
                                continue

                            from voice_agent.services.dentist_service import validate_pincode_online, get_pincode_city_info, get_nearest_dentists, format_city_confirm_speech
                            is_valid_pin, detected_pin_city, pin_err = await asyncio.to_thread(validate_pincode_online, pin_val)
                            city_info = (await asyncio.to_thread(get_pincode_city_info, pin_val)) if is_valid_pin else {}
                            canonical_city = city_info.get("canonical_city") or detected_pin_city or ""
                            display_city = city_info.get("display_city") or detected_pin_city or ""
                            sub_area = city_info.get("area") or ""

                            needs_city_confirmation = False
                            area_just_confirmed = False
                            # The area question for THIS pincode is already pending: a call in a LATER turn is the
                            # second call, made after the patient answered it -> lock the area and list the doctors.
                            # It must never ask the area question again (that was the "Sayan vistaar" loop; the
                            # residence-change check below re-asked it on every call while the old pincode was booked).
                            pending_same_pin = bool(getattr(self.session, "pending_city", None)) and \
                                str(getattr(self.session, "pending_pincode", "") or "") == pin_val
                            asked_turn = getattr(self.session, "city_confirm_turn_id", None)
                            waiting_for_answer = False
                            if not is_valid_pin:
                                print(f"[WARN] Gemini Live attempted find_nearest_dentists with invalid/unregistered pincode '{pin_val}': {pin_err}")
                                result = {
                                    "status": "error",
                                    "message": f"Pincode '{pin_val}' is invalid or not found in India Post records! You MUST NOT accept it and you MUST NOT name any doctor. Tell the patient that pincode {pin_val} was not found in postal records, and ask for their correct 6-digit area pincode."
                                }
                            elif pending_same_pin and asked_turn is not None and asked_turn == self.session.current_voice_turn_id:
                                # Called again in the same reply, before the patient could answer
                                print(f"[INFO] find_nearest_dentists called again before the patient answered the area question ({pin_val})")
                                waiting_for_answer = True
                                result = {
                                    "status": "wait_for_patient",
                                    "message": "The patient has NOT answered the area question yet. Do not call this tool again now and do "
                                               "not name any doctor. If you have not asked it yet, ask ONLY the area question, then wait.",
                                }
                            elif pending_same_pin and asked_turn is not None:
                                is_change = bool(actual_pincode and actual_pincode != pin_val)
                                self._lock_pending_city(pin_val)
                                if is_change:
                                    self.session.recommended_dentists = []
                                    if self.session.booking_slots.get("submission_id") or getattr(self.session, "submitted_lead_id", None):
                                        self.session.slots_edited_after_submit = True
                                        self.session.booking_slots["is_submitted"] = False
                                area_just_confirmed = True
                                print(f"[INFO] Gemini Live find_nearest_dentists area confirmed by patient: {pin_val} -> {self.session.booking_slots.get('city')}")
                            elif self.begin_residence_change(pin_val, canonical_city, display_city, sub_area):
                                needs_city_confirmation = True
                            elif not getattr(self.session, "city_pincode_locked", False) and not self.session.booking_slots.get("city"):
                                if getattr(self.session, "pending_city", None) and (not user_spoke_pin or getattr(self.session, "pending_pincode", "") == pin_val):
                                    # Second call after the patient confirmed the area
                                    self._lock_pending_city(pin_val)
                                    area_just_confirmed = True
                                    print(f"[INFO] Gemini Live find_nearest_dentists city confirmed: {pin_val} -> {self.session.booking_slots['city']}")
                                else:
                                    self.session.pending_pincode = pin_val
                                    self.session.pending_city = canonical_city
                                    self.session.pending_display_city = display_city
                                    self.session.pending_area = sub_area
                                    self.session.city_confirm_needed = True
                                    self.session.asking_for_field = "city_confirmation"
                                    needs_city_confirmation = True
                            elif user_spoke_pin and not actual_pincode:
                                self.session.booking_slots["pincode"] = pin_val

                            if not is_valid_pin or waiting_for_answer:
                                pass
                            elif needs_city_confirmation:
                                # Two separate calls: this one returns ONLY the area question. Giving Gemini the area
                                # question and the doctor list in one result made it speak the area question again
                                # after the patient's "yes" (over and over). The doctor list comes from the second call.
                                self.session.city_confirm_turn_id = self.session.current_voice_turn_id
                                self.session.pending_dentists = None
                                confirm_text = format_city_confirm_speech(pin_val, display_city, self._voice_lang())
                                print(f"[INFO] Gemini Live find_nearest_dentists paused for city confirmation: {pin_val} -> {display_city} (canonical: {canonical_city})")
                                result = {
                                    "status": "need_city_confirmation",
                                    "pincode": pin_val,
                                    "detected_city": display_city,
                                    "say_now": confirm_text,
                                    "message": (
                                        "Say ONLY the 'say_now' text (the area question) and stop. Do NOT name any doctor and do NOT ask anything else. "
                                        "This area question is asked ONLY ONCE. When the patient answers yes / haan / ha / barabar / right / correct "
                                        f"(or anything that does not say the area is wrong), call find_nearest_dentists again with pincode {pin_val} "
                                        "BEFORE you reply, and speak the doctor list it returns - NEVER ask the area question again. "
                                        "Only if the patient says the area is wrong, ask for their correct 6-digit pincode."
                                    ),
                                }
                            else:
                                dentists_slice, total_count, next_offset = await asyncio.to_thread(get_nearest_dentists, pin_val, offset_val, 3)
                                self._mark_dentists_recommended(dentists_slice, pin_val, offset_val)
                                speech = self._dentist_speech(dentists_slice, pin_val, offset_val, after_city_confirm=area_just_confirmed)
                                print(f"[INFO] Gemini Live find_nearest_dentists for {pin_val} (offset {offset_val}): {[d.get('name') for d in dentists_slice]}")
                                result = self._dentist_success_result(dentists_slice, total_count, next_offset, pin_val, offset_val, speech)
                            function_responses.append({
                                "name": func_name,
                                "id": func_id,
                                "response": {"result": result}
                            })
                        elif func_name == "prepare_review_summary":
                            result = await self.prepare_review_summary(args)
                            print(f"[INFO] prepare_review_summary -> {result.get('status')} {result.get('missing') or ''}")
                            function_responses.append({"name": func_name, "id": func_id, "response": {"result": result}})
                        elif func_name == "find_dentists_in_city":
                            result = await asyncio.to_thread(self.find_dentists_in_city, args)
                            print(f"[INFO] find_dentists_in_city {args.get('city')!r} -> {result.get('status')} {[d.get('name') for d in result.get('dentists', [])]}")
                            function_responses.append({"name": func_name, "id": func_id, "response": {"result": result}})
                        elif func_name == "check_doctor":
                            result = await asyncio.to_thread(self.check_doctor, args)
                            print(f"[INFO] check_doctor {args.get('doctor_name')!r} -> {result.get('status')} {result.get('doctor_name') or ''}")
                            function_responses.append({"name": func_name, "id": func_id, "response": {"result": result}})
                        else:
                            function_responses.append({
                                "name": func_name,
                                "id": func_id,
                                "response": {"result": {"status": "error", "message": f"Unknown tool: {func_name}"}}
                            })
                    
                    tool_response_message = {
                        "toolResponse": {
                            "functionResponses": function_responses
                        }
                    }
                    await ws.send(json.dumps(tool_response_message))
                    print("[INFO] Sent tool response back to Gemini Live WebSocket")
                    continue
                    
                server_content = response.get("serverContent", {})
                if not server_content:
                    continue
                    
                # OFFICIAL GEMINI VAD BARGE-IN / INTERRUPTION HANDLING
                if server_content.get("interrupted"):
                    print("[INFO] Gemini Official VAD Interruption / Barge-in Detected!")
                    ios_debug_log(self.session, "srv_interrupted")
                    self.session.is_interrupted = True
                    self.session.display_str = ""
                    self.session.full_bot_reply = ""
                    self.session.assistant_audio_buffer = bytearray()
                    self.session.live_pcm_buffer = bytearray()
                    
                    # Cut off assistant playback in frontend immediately
                    await self.send_json({
                        "type": "interrupted",
                        "turnId": self.session.current_voice_turn_id
                    })
                        
                    await asyncio.sleep(0.05)
                    if self.session.is_client_connected:
                        self.session.is_interrupted = False
                    else:
                        return
                
                if self.session.is_interrupted:
                    if server_content.get("turnComplete") or server_content.get("generationComplete") or "outputTranscription" in server_content or "modelTurn" in server_content:
                        self.session.is_interrupted = False
                    else:
                        return
                
                # NATIVE GEMINI LIVE REAL-TIME TRANSCRIPTIONS (REAL-TIME STREAMING SUBTITLES)
                if "outputTranscription" in server_content:
                    raw_chunk = server_content["outputTranscription"].get("text", "")
                    ios_debug_log(self.session, "srv_said", text=raw_chunk)
                    bot_chunk = re.sub(r"\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*-->\s*\d{1,2}:\d{2}(:\d{2})?(\.\d+)?", "", raw_chunk)
                    bot_chunk = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*$", "", bot_chunk)
                    if bot_chunk:
                        self.session.full_bot_reply += bot_chunk
                        self.session.display_str += bot_chunk
                        # The summary card is already on screen; Riya's spoken short version of it is not shown again
                        if getattr(self.session, "pending_summary_card", ""):
                            bot_chunk = ""
                        
                        # Update conversation language based on the bot's tag
                        lang_match = re.search(r"\[(hi|bn|ta|te|mr|gu|kn|ml|pa|or|en)-IN\]", self.session.full_bot_reply, re.IGNORECASE)
                        if lang_match:
                            bot_tag_lang = f"{lang_match.group(1).lower()}-IN"
                            if bot_tag_lang != "en-IN" or getattr(self.session, 'has_user_spoken', False):
                                self.session.current_language = bot_tag_lang
                                self.session.is_language_established = True
                        elif getattr(self, 'conversation_manager', None):
                            from voice_agent.ai.conversation_manager import detect_user_language
                            detected_bot_lang = detect_user_language(self.session.full_bot_reply)
                            if detected_bot_lang and detected_bot_lang != "en":
                                self.session.current_language = f"{detected_bot_lang}-IN"
                                self.session.is_language_established = True
                            
                        if bot_chunk:
                            best_tag = detect_best_tag(self.session.latest_typed_user_text, self.session.display_str)
                            await self.send_json({
                                "type": "bot_text_chunk",
                                "text": bot_chunk,
                                "tag": best_tag,
                                "turnId": self.session.current_voice_turn_id
                            })

                if "inputTranscription" in server_content:
                    raw_user_chunk = server_content["inputTranscription"].get("text", "")
                    ios_debug_log(self.session, "srv_heard", text=raw_user_chunk)
                    user_chunk = clean_hallucinations(raw_user_chunk)
                    if user_chunk:
                        self.session.full_bot_reply = ""
                        self.session.display_str = ""
                        self.session.current_user_transcription += user_chunk
                        self.session.has_user_spoken = True
                        # Slots are parsed once at turnComplete on the full utterance. Parsing every partial chunk
                        # turned half-spoken phone digits into fake pincodes and set stale invalid-input flags.
                        await self.send_json({
                            "type": "user_text_chunk",
                            "text": user_chunk,
                            "turnId": self.session.current_voice_turn_id,
                            "slots": dict(self.session.booking_slots),
                            "userName": self.session.user_name,
                            "userConcern": self.session.user_concern,
                            "userCity": self.session.booking_slots.get("city"),
                            "userDoctor": self.session.booking_slots.get("doctor_name"),
                            "userPhone": self.session.booking_slots.get("phone")
                        })

                if "modelTurn" in server_content:
                    parts = server_content["modelTurn"].get("parts", [])
                    for part in parts:
                        if "functionCall" in part:
                            fc = part["functionCall"]
                            func_name = fc.get("name")
                            args = fc.get("args", {})
                            if func_name == "submit_appointment_booking":
                                # ⚡ The last VALID review summary the patient heard is the source of truth ⚡
                                sum_slots = dict(getattr(self.session, "last_review_summary_slots", {}) or {})
                                if sum_slots:
                                    for k, v in sum_slots.items():
                                        if v and str(v).lower() not in ["none", "null", "-", "--"]:
                                            self.session.booking_slots[k] = v
                                    if sum_slots.get("user_name"):
                                        self.session.user_name = sum_slots["user_name"]
                                        u_p = sum_slots["user_name"].split()
                                        self.session.booking_slots["first_name"] = u_p[0]
                                        self.session.booking_slots["last_name"] = " ".join(u_p[1:]) if len(u_p) > 1 else "-"
                                    if sum_slots.get("user_concern") or sum_slots.get("message"):
                                        self.session.user_concern = sum_slots.get("user_concern") or sum_slots.get("message")
                                        self.session.booking_slots["message"] = self.session.user_concern
                                if not self.session.booking_slots.get("message") and self.session.user_concern:
                                    self.session.booking_slots["message"] = self.session.user_concern

                                # 1. Base slots from booking_slots & sum_slots
                                full_args = dict(self.session.booking_slots)
                                full_args.pop('is_cancel', None)  # cancellation only from this turn, see the toolCall path
                                if sum_slots:
                                    for k, v in sum_slots.items():
                                        if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                            if k not in full_args or not full_args[k]:
                                                full_args[k] = v
                                
                                # 2. Update with args from tool call
                                for k, v in args.items():
                                    if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                        full_args[k] = v
                                        self.session.booking_slots[k] = v
                                
                                # 3. Check for explicitly updated slots in current user utterance
                                curr_u_text = str(getattr(self.session, 'current_user_transcription', '') or getattr(self.session, 'latest_typed_user_text', '') or '')
                                curr_u_lower = curr_u_text.lower().strip()
                                
                                user_phone_match = re.search(r'\b[6-9]\d{9}\b', curr_u_text)
                                if user_phone_match:
                                    new_phone = user_phone_match.group(0)
                                    if self.session.booking_slots.get('phone') and self.session.booking_slots['phone'] != new_phone:
                                        self.session.booking_slots['old_phone'] = self.session.booking_slots['phone']
                                    full_args['phone'] = new_phone
                                    self.session.booking_slots['phone'] = new_phone
                                elif args.get('phone'):
                                    arg_phone = ''.join(filter(str.isdigit, str(args['phone'])))
                                    if len(arg_phone) == 10:
                                        if self.session.booking_slots.get('phone') and self.session.booking_slots['phone'] != arg_phone:
                                            self.session.booking_slots['old_phone'] = self.session.booking_slots['phone']
                                        full_args['phone'] = arg_phone
                                        self.session.booking_slots['phone'] = arg_phone
                                
                                user_pin_match = re.search(r'\b[1-9]\d{5}\b', curr_u_text)
                                if user_pin_match:
                                    new_pin = user_pin_match.group(0)
                                    full_args['pincode'] = new_pin
                                    self.session.booking_slots['pincode'] = new_pin
                                elif args.get('pincode'):
                                    arg_pin = ''.join(filter(str.isdigit, str(args['pincode'])))
                                    if len(arg_pin) == 6:
                                        full_args['pincode'] = arg_pin
                                        self.session.booking_slots['pincode'] = arg_pin
                                
                                if not full_args.get('message') and self.session.user_concern:
                                    full_args['message'] = self.session.user_concern
                                # Ensure patient's confirmed residence city is NEVER overwritten by doctor's clinic city
                                if self.session.booking_slots.get('city') and getattr(self.session, 'city_manually_confirmed', False):
                                    full_args['city'] = self.session.booking_slots['city']
                                if self.session.user_name:
                                    u_p = self.session.user_name.split()
                                    full_args['first_name'] = u_p[0]
                                    full_args['last_name'] = ' '.join(u_p[1:]) if len(u_p) > 1 else '-'
                                # Guard against placeholder doctor phrases & canonicalize real doctor name
                                doc_val = str(full_args.get('doctor_name') or '').lower()
                                placeholder_words = ['हमारे डॉक्टर', 'અમારા ડૉક્ટર', 'our doctor', 'doctor in', 'ડોક્ટર છે', 'डॉक्टर हैं', 'ceramist', 'सिरामिस्ट', 'સેરેમિસ્ટ', 'haresh savani']
                                if any(pw in doc_val for pw in placeholder_words):
                                    full_args['doctor_name'] = ''
                                    self.session.booking_slots['doctor_name'] = ''
                                elif doc_val:
                                    from voice_agent.services.appointment_service import is_matched_doctor
                                    matched_d = is_matched_doctor(full_args['doctor_name'], city=self.session.booking_slots.get('clinic_city') or full_args.get('clinic_city'))
                                    if not matched_d:
                                        matched_d = is_matched_doctor(full_args['doctor_name'], city=None)
                                    if matched_d:
                                        full_args['doctor_name'] = matched_d
                                        self.session.booking_slots['doctor_name'] = matched_d
                                
                                sub_id = self.session.booking_slots.get('submission_id') or getattr(self.session, 'submitted_lead_id', None)
                                full_args['submission_id'] = sub_id
                                full_args['id'] = sub_id
                                if self.session.booking_slots.get('godaddy_id'):
                                    full_args['godaddy_id'] = self.session.booking_slots.get('godaddy_id')
                                if self.session.booking_slots.get('api_id'):
                                    full_args['api_id'] = self.session.booking_slots.get('api_id')
                                if self.session.booking_slots.get('old_phone'):
                                    full_args['old_phone'] = self.session.booking_slots.get('old_phone')
                                if is_cancel_submit(curr_u_text):
                                    full_args['is_cancel'] = True
                                full_args['is_update'] = bool(sub_id) or bool(self.session.booking_slots.get('is_submitted')) or bool(getattr(self.session, 'slots_edited_after_submit', False))
                                
                                # Guard: Check if user is actively requesting an edit/update without confirming submit
                                is_edit_request = any(ew in curr_u_lower for ew in [
                                    'change', 'update', 'edit', 'instead', 'no my', 'no, my', 'spelling', 'mistake',
                                    'wrong', 'incorrect', 'ખોટું', 'ખોટો', 'ખોટી', 'ખોટા', 'ખોટો છે', 'ખોટી છે', 'ખોટું છે',
                                    'બદલ', 'બદલો', 'બદલવો', 'બદલવી', 'બદલવું', 'બદલવા', 'સુધાર', 'સુધારો', 'સુધારવો', 'સુધારવી', 'સુધારવું',
                                    'ફેરફાર', 'ચેન્જ', 'ચેંજ', 'ચેંન્જ', 'અપડેટ', 'गलत', 'बदल', 'बदलो', 'बदलना', 'बदल दीजिए', 'बदल दो',
                                    'सुधार', 'सुधारो', 'सुधारना', 'खो तो', 'खोटो', 'खोता', 'खोती', 'अपडेट', 'badlo', 'badlav', 'sudharo'
                                ])
                                is_explicit_sub = is_explicit_submit_command(curr_u_text)
                                is_user_affirmed = is_affirmative_submit(curr_u_text)
                                if any(w in curr_u_lower for w in ['sommeil', 'sommet', 'soit', 'somet', 'sammit', 'submarino']):
                                    is_explicit_sub = True
                                    is_user_affirmed = True
                                f_cancel = bool(full_args.get('is_cancel'))

                                # The summary the patient approved wins over tool args and transcript parsing
                                for k, v in sum_slots.items():
                                    if v and str(v).lower() not in ['none', 'null', '-', '--']:
                                        full_args[k] = v
                                if sum_slots.get('user_concern'):
                                    full_args['message'] = sum_slots['user_concern']

                                # Mandatory fields check before calling submit_consultation_appointment
                                f_fn = bool(full_args.get('first_name') and full_args['first_name'].lower() not in ['', 'none', 'null', 'patient', 'user'])
                                f_city = bool(full_args.get('city') and len(str(full_args['city']).strip()) >= 2 and str(full_args['city']).lower() not in ['none', 'null', 'india', ''])
                                f_pin = bool(full_args.get('pincode') and len(''.join(filter(str.isdigit, str(full_args['pincode'])))) == 6)
                                f_msg = bool(full_args.get('message') and len(full_args['message'].strip()) >= 2 and full_args['message'].lower() not in ['none', 'null', 'dental consultation appointment request', ''])
                                f_phone = is_valid_indian_mobile(full_args.get('phone'))

                                # Already submitted and unchanged (e.g. the patient only ASKED 'is my appointment submitted?'):
                                # the consumed summary used to make this answer 'NOT submitted' and re-recite the summary
                                submitted_unchanged = bool(self.session.booking_slots.get("is_submitted")) and not bool(self.session.booking_slots.get("is_cancel")) \
                                    and not getattr(self.session, "slots_edited_after_submit", False)
                                if not f_cancel and submitted_unchanged:
                                    print("[GUARD] submit_appointment_booking on an already submitted, unchanged appointment -> already_submitted")
                                    res = {"status": "already_submitted", "message": "This appointment request is ALREADY successfully submitted and nothing has changed since. Do NOT submit again, do NOT say it is not submitted and do NOT recite the summary. Tell the patient in one short sentence that their appointment request is already submitted and our team will contact them soon."}
                                elif not f_cancel and not sum_slots:
                                    print("[GUARD] Gemini Live modelTurn submit without a valid review summary. Blocking.")
                                    res = {
                                        "status": "waiting_confirmation",
                                        "message": "NOT submitted. There is no valid review summary yet. If the 10-digit mobile number (starting with 6-9) or any other detail is missing or invalid, ask for it first. If the city does not match the pincode, confirm the city from the pincode first. NEVER repeat the same summary you just recited: fix the wrong detail, then recite the corrected summary and ask the patient to say 'submit' or 'cancel'."
                                    }
                                elif is_edit_request and not (is_explicit_sub or is_user_affirmed) and not f_cancel:
                                    print(f"[GUARD] Gemini Live attempted submit_appointment_booking while user requested edit without submitting ('{curr_u_text}'). Blocking submission.")
                                    self.session.booking_slots["is_submitted"] = False
                                    self.session.slots_edited_after_submit = True
                                    res = {
                                        "status": "edit_in_progress",
                                        "message": "User is updating/changing details. DO NOT submit yet! Ask for the updated detail, update summary, and wait for confirmation."
                                    }
                                elif not f_cancel and not (is_explicit_sub or is_user_affirmed):
                                    print(f"[GUARD] Gemini Live attempted premature submit_appointment_booking without user confirmation ('{curr_u_text}'). Blocking.")
                                    res = {
                                        "status": "waiting_confirmation",
                                        "message": "Appointment summary is prepared. Do NOT submit yet! Recite the full summary and ask patient to say 'submit' to confirm or 'cancel' to cancel."
                                    }
                                elif not f_cancel and not (f_fn and f_city and f_pin and f_msg and f_phone):
                                    missing_name = "phone"
                                    if not f_fn: missing_name = "patient name"
                                    elif not f_msg: missing_name = "dental concern"
                                    elif not f_city: missing_name = "city"
                                    elif not f_pin: missing_name = "6-digit area pincode"
                                    res = {
                                        "status": "error",
                                        "missing_field": missing_name,
                                        "message": f"Cannot submit appointment! The required field '{missing_name}' has not been provided yet. Ask patient to provide their {missing_name} first."
                                    }
                                else:
                                    res = await submit_consultation_appointment(full_args)
                                if res.get("status") == "success":
                                    self.session.booking_slots["is_submitted"] = True
                                    self.session.slots_edited_after_submit = False
                                    self.session.last_submit_turn_id = self.session.current_voice_turn_id
                                    self.consume_review_summary()
                                    if full_args.get("is_cancel"):
                                        self.session.booking_slots["is_cancel"] = True
                                        self.session.pending_cancellation = False
                                    else:
                                        self.session.booking_slots["is_cancel"] = False
                                    if isinstance(res.get("details"), dict):
                                        ret_id = res["details"].get("id") or res["details"].get("submission_id")
                                        if ret_id:
                                            self.session.booking_slots["submission_id"] = ret_id
                                            self.session.submitted_lead_id = ret_id
                                        if res["details"].get("godaddy_id"):
                                            self.session.booking_slots["godaddy_id"] = res["details"]["godaddy_id"]
                                        if res["details"].get("api_id"):
                                            self.session.booking_slots["api_id"] = res["details"]["api_id"]
                                    for k, v in full_args.items():
                                        if v is not None:
                                            if k in ('is_submitted', 'is_cancel', 'is_update'):
                                                pass  # set from the backend result above; this pre-submit copy (is_submitted=False) must not undo it
                                            elif isinstance(v, bool):
                                                self.session.booking_slots[k] = v
                                            else:
                                                self.session.booking_slots[k] = str(v)
                                    await self.send_json({
                                        "type": "sync_slots",
                                        "slots": self.session.booking_slots
                                    })
                                print(f"[INFO] Gemini Live modelTurn part invoked submit_appointment_booking with args: {full_args}, result: {res}")
                            elif func_name == "find_nearest_dentists":
                                pin_val = re.sub(r"\D", "", self._ascii_digits(str(args.get("pincode") or "")))
                                if not pin_val and self.session.booking_slots.get("pincode"):
                                    pin_val = self.session.booking_slots.get("pincode")

                                actual_pincode = self.session.booking_slots.get("pincode", "")
                                curr_u_text = str(getattr(self.session, "current_user_transcription", "") or "")
                                latest_typed = str(getattr(self.session, "latest_typed_user_text", "") or "")
                                user_spoke_pin = bool(pin_val and len(pin_val) == 6 and pin_val.isdigit() and (pin_val in curr_u_text or pin_val in latest_typed))

                                from voice_agent.services.dentist_service import validate_pincode_online, get_pincode_city_info
                                is_valid_pin, detected_pin_city, pin_err = await asyncio.to_thread(validate_pincode_online, pin_val)
                                city_info = (await asyncio.to_thread(get_pincode_city_info, pin_val)) if is_valid_pin else {}
                                canonical_city = city_info.get("canonical_city") or detected_pin_city or ""
                                display_city = city_info.get("display_city") or detected_pin_city or ""
                                sub_area = city_info.get("area") or ""

                                if not is_valid_pin:
                                    print(f"[WARN] Gemini Live modelTurn part rejected invalid/unregistered pincode '{pin_val}': {pin_err}")
                                elif self.begin_residence_change(pin_val, canonical_city, display_city, sub_area):
                                    pass
                                elif not getattr(self.session, "city_pincode_locked", False) and not self.session.booking_slots.get("city"):
                                    if getattr(self.session, "pending_city", None) and (not user_spoke_pin or getattr(self.session, "pending_pincode", "") == pin_val):
                                        self.session.booking_slots["city"] = self.session.pending_city
                                        self.session.booking_slots["pincode"] = pin_val
                                        if getattr(self.session, "pending_area", None):
                                            self.session.booking_slots["area"] = self.session.pending_area
                                        self.session.city_pincode_locked = True
                                        self.session.city_confirm_needed = False
                                        self.session.pending_city = None
                                        self.session.pending_display_city = None
                                        self.session.pending_area = None
                                        self.session.pending_pincode = None
                                        self.session.asking_for_field = "doctor_selection"
                                        offset_val = int(args.get("offset") or 0)
                                        from voice_agent.services.dentist_service import get_nearest_dentists
                                        dentists_slice, total_count, next_offset = await asyncio.to_thread(get_nearest_dentists, pin_val, offset_val, 3)
                                        self.session.recommended_dentists = dentists_slice
                                        self.session.recommended_dentists_spoken = True
                                        self.session.doctor_guidance_asked = True
                                        self.session.dentist_page_offset = offset_val
                                        self.session.last_recommended_pincode = pin_val
                                        print(f"[INFO] Gemini Live modelTurn part confirmed city for pin: {pin_val}, found {len(dentists_slice)} dentists")
                                    else:
                                        self.session.pending_pincode = pin_val
                                        self.session.pending_city = canonical_city
                                        self.session.pending_display_city = display_city
                                        self.session.pending_area = sub_area
                                        self.session.city_confirm_needed = True
                                        self.session.asking_for_field = "city_confirmation"
                                        print(f"[INFO] Gemini Live modelTurn part paused for city confirmation: {pin_val} -> {display_city} (canonical: {canonical_city})")
                                else:
                                    if user_spoke_pin and not actual_pincode:
                                        self.session.booking_slots["pincode"] = pin_val
                                    offset_val = int(args.get("offset") or 0)
                                    from voice_agent.services.dentist_service import get_nearest_dentists
                                    dentists_slice, total_count, next_offset = await asyncio.to_thread(get_nearest_dentists, pin_val, offset_val, 3)
                                    self.session.recommended_dentists = dentists_slice
                                    self.session.recommended_dentists_spoken = True
                                    self.session.doctor_guidance_asked = True
                                    self.session.dentist_page_offset = offset_val
                                    self.session.last_recommended_pincode = pin_val
                                    print(f"[INFO] Gemini Live modelTurn part invoked find_nearest_dentists for pin: {pin_val}, offset: {offset_val}, found: {len(dentists_slice)}")

                        if "text" in part and part["text"]:
                            raw_txt = part["text"]
                            bot_chunk = re.sub(r"\d{1,2}:\d{2}(:\d{2})?(\.\d+)?\s*-->\s*\d{1,2}:\d{2}(:\d{2})?(\.\d+)?", "", raw_txt)
                            bot_chunk = re.sub(r"^\s*\d{1,2}:\d{2}(:\d{2})?\s*$", "", bot_chunk)
                            if bot_chunk and bot_chunk not in self.session.full_bot_reply:
                                self.session.full_bot_reply += bot_chunk
                                self.session.display_str += bot_chunk
                                if not getattr(self.session, "pending_summary_card", ""):
                                    best_tag = detect_best_tag(self.session.latest_typed_user_text, self.session.display_str)
                                    await self.send_json({
                                        "type": "bot_text_chunk",
                                        "text": bot_chunk,
                                        "tag": best_tag,
                                        "turnId": self.session.current_voice_turn_id
                                    })

                        if "inlineData" in part:
                            incoming_pcm = base64.b64decode(part["inlineData"]["data"])
                            self.session.live_pcm_buffer.extend(incoming_pcm)
                            self.session.assistant_audio_buffer.extend(incoming_pcm)
                            
                        # Stream audio chunks with smooth buffer alignment (9600 bytes = 200ms of 24kHz 16-bit PCM)
                        if len(self.session.live_pcm_buffer) >= 9600:
                            send_len = len(self.session.live_pcm_buffer) - (len(self.session.live_pcm_buffer) % 2)
                            send_bytes = self.session.live_pcm_buffer[:send_len]
                            self.session.live_pcm_buffer = self.session.live_pcm_buffer[send_len:]
                            wav_base64 = wrap_pcm_to_wav_base64(send_bytes, 24000)
                            await self.send_json({
                                "type": "audio_chunk",
                                "audioBase64": wav_base64,
                                "index": self.session.chunk_index
                            })
                            ios_debug_log(self.session, "srv_audio_out", i=self.session.chunk_index, ms=send_len // 48)
                            self.session.chunk_index += 1
                
                is_turn_finished = server_content.get("turnComplete") or server_content.get("generationComplete")
                if is_turn_finished:
                    if len(self.session.assistant_audio_buffer) == 0 and not self.session.full_bot_reply and not len(self.session.live_pcm_buffer):
                        continue
                    await self.send_json({"type": "user_speaking_status", "is_speaking": False})
                    ios_debug_log(self.session, "srv_turn_complete")
                    if len(self.session.live_pcm_buffer) > 0:
                        send_len = len(self.session.live_pcm_buffer) - (len(self.session.live_pcm_buffer) % 2)
                        if send_len > 0:
                            send_bytes = self.session.live_pcm_buffer[:send_len]
                            self.session.live_pcm_buffer = bytearray()
                            wav_base64 = wrap_pcm_to_wav_base64(send_bytes, 24000)
                            await self.send_json({
                                "type": "audio_chunk",
                                "audioBase64": wav_base64,
                                "index": self.session.chunk_index
                            })
                            ios_debug_log(self.session, "srv_audio_out", i=self.session.chunk_index, ms=send_len // 48, last=True)
                            self.session.chunk_index += 1
                    
                    current_assistant_audio = bytes(self.session.assistant_audio_buffer)
                    self.session.assistant_audio_buffer = bytearray()
                    
                    # Resolve user transcription with fallback
                    user_text = ""
                    if self.session.user_transcription_task:
                        try:
                            user_text = await asyncio.wait_for(asyncio.shield(self.session.user_transcription_task), timeout=0.6)
                        except Exception:
                            if self.session.user_transcription_task.done():
                                try:
                                    user_text = self.session.user_transcription_task.result()
                                except Exception:
                                    pass
                    if not user_text:
                        user_text = self.session.current_user_transcription or self.session.latest_typed_user_text or ""
                    # Frontend control prompts (greeting / reconnect / silence nudge) are not the patient's words.
                    # Treating them as speech made the reconnect message ("...appointment is already submitted")
                    # count as "submit" and re-submit (even un-cancel) the previous booking.
                    if user_text.strip().startswith("SYSTEM INSTRUCTION"):
                        user_text = ""

                    bot_text_to_send = self.session.full_bot_reply or ""
                    clean_text = clean_assistant_text(bot_text_to_send) if bot_text_to_send else ""


                    # 🚨 Track profession inquiry without destructive text stripping
                    was_prof_already_asked = getattr(self.session, "profession_asked", False)
                    prof_re_patterns = [
                        r"(?:profession|for work|do for work|regarding your work|about your work)",
                        r"(?:તમે શું કામ કરો છો|તમારો વ્યવસાય|પ્રોફેશન|કામ કરો છો)",
                        r"(?:आप क्या काम करते हैं|आपका पेशा|प्रोफेशन|काम करते हैं|काम करती हैं)"
                    ]
                    if not was_prof_already_asked and clean_text:
                        for pat in prof_re_patterns:
                            if re.search(pat, clean_text, flags=re.IGNORECASE):
                                self.session.profession_asked = True
                                break
                    if getattr(self.session, "consultation_agreed", False) or self.session.booking_slots.get("city"):
                        self.session.profession_asked = True
                    from voice_agent.ai.conversation_manager import text_asks_profession
                    if text_asks_profession(clean_text):
                        self.session.profession_done = True
                        self.session.profession_prompt_pending = False
                    
                    if getattr(self, 'conversation_manager', None):
                        # Worker thread: slot parsing can hit the postal/dentist APIs (blocking requests), which
                        # otherwise froze the event loop - and every caller's audio - for up to a second or more
                        if user_text and user_text != "Message":
                            await asyncio.to_thread(self.conversation_manager.update_session_memory, user_text, self.session.latest_client_history)
                        if clean_text:
                            temp_h = list(self.session.latest_client_history or []) + [{"role": "model", "parts": [{"text": clean_text}]}]
                            await asyncio.to_thread(self.conversation_manager.update_session_memory, "", temp_h)
                    # Gemini spoke the dentist list prepared at the city confirmation -> lock city, record dentists
                    self.sync_pending_dentists_after_turn(clean_text)
                    self.track_pincode_request(clean_text)

                    # 🚨 Check if user requested an edit/change after initial submission
                    curr_u_l = (user_text or "").lower().strip()
                    user_is_editing = any(ew in curr_u_l for ew in [
                        'change', 'update', 'edit', 'instead', 'no my', 'no, my', 'spelling', 'mistake',
                        'wrong', 'incorrect', 'ખોટું', 'ખોટો', 'ખોટી', 'ખોટા', 'ખોટો છે', 'ખોટી છે', 'ખોટું છે',
                        'બદલ', 'બદલો', 'બદલવો', 'બદલવી', 'બદલવું', 'બદલવા', 'સુધાર', 'સુધારો', 'સુધારવો', 'સુધારવી', 'સુધારવું',
                        'ફેરફાર', 'ચેન્જ', 'ચેંજ', 'ચેંન્જ', 'અપડેટ', 'गलत', 'बदल', 'बदलो', 'बदलना', 'बदल दीजिए', 'बदल दो',
                        'सुधार', 'सुधारो', 'सुधारना', 'खो तो', 'खोटो', 'खोता', 'खोती', 'अपडेट', 'badlo', 'badlav', 'sudharo'
                    ])
                    if user_is_editing and (self.session.booking_slots.get("is_submitted") or getattr(self.session, "submitted_lead_id", None)):
                        self.session.booking_slots["is_submitted"] = False
                        self.session.slots_edited_after_submit = True

                    # 🌐 Language follows what Gemini actually heard: its reply is in the patient's language, while the
                    # transcript of unclear audio is not (a Hindi speaker's garbled transcript was detected as Punjabi)
                    from voice_agent.ai.conversation_manager import detect_user_language
                    reply_lang = detect_user_language(clean_text, None, None) if clean_text else None
                    if reply_lang:
                        self.session.current_language = f"{reply_lang}-IN"
                        self.session.is_language_established = True
                    turn_lang = reply_lang or str(getattr(self.session, "current_language", "") or "en-IN").split("-")[0]

                    # A turn that answers our own correction note must not trigger another note (no correction loops)
                    is_correction_reply = getattr(self.session, "awaiting_correction_reply", False)
                    self.session.awaiting_correction_reply = False
                    correction_note = None

                    # Template placeholders spoken as if real ("Dr. [Name 1], Dr. [Name 2]"): make Riya fetch the real dentists
                    if not is_correction_reply and re.search(r"\[(?:name|doctor|નામ|नाम)\s*\d", clean_text or "", re.IGNORECASE):
                        pin_for_lookup = self.session.booking_slots.get("pincode") or getattr(self.session, "pending_pincode", "") or ""
                        correction_note = (
                            "[BACKEND NOTE - not spoken by the patient. Do not read this note aloud.] You just said placeholder "
                            "doctor names like '[Name 1]' instead of real names. Briefly apologise, call find_nearest_dentists"
                            f"{' with pincode ' + pin_for_lookup if pin_for_lookup else ''} now, and speak ONLY the real doctor names it "
                            "returns. If it returns none, say we will have our team guide them. Same language as your previous reply."
                        )

                    # ⚡ Review summary = the single source of truth for submission ⚡
                    # Only a summary whose every field is valid is remembered; submit sends exactly that summary.
                    summary_slots = extract_slots_from_review_summary(clean_text or bot_text_to_send)
                    is_review_summary = bool(summary_slots) and is_submit_review_summary(clean_text or bot_text_to_send)
                    if not is_review_summary:
                        # A normal reply that merely mentions details must never fill the booking: the extractor turned
                        # Riya's dentist list into a "chosen" doctor and her "you live in Surat, right?" into a confirmed city
                        summary_slots = {}
                    summary_problem = None
                    bad_summary_phone = ""
                    prepared_now = getattr(self.session, "review_prepared_turn", None) == self.session.current_voice_turn_id \
                        and bool(self.session.last_review_summary_slots)
                    if is_review_summary and prepared_now:
                        # Checked by prepare_review_summary before Riya spoke it; the transcript of her speech may differ
                        summary_slots = dict(self.session.last_review_summary_slots)
                    elif is_review_summary:
                        merged_for_check = {
                            "user_name": self.session.user_name,
                            "user_concern": self.session.user_concern,
                            **{k: v for k, v in self.session.booking_slots.items() if k != "phone"},
                            **summary_slots,
                        }
                        summary_problem = get_review_summary_problem(merged_for_check)
                        # Phone must be one the patient actually said: Riya invents a number when she did not hear it clearly
                        if not summary_problem:
                            sum_phone = normalize_mobile(merged_for_check.get("phone")) or ""
                            said = [text for role, text in self.session.transcript_history if role == "user"] + [user_text or ""]
                            said_digits = ["".join(filter(str.isdigit, self._ascii_digits(s))) for s in said]
                            # The patient's transcript decides the number: a 12-digit answer is never a mobile, and a
                            # summary with a number other than the one the patient clearly said is wrong
                            t_status, t_phone = phone_from_user_turns(said, merged_for_check.get("pincode"))
                            if t_status == "wrong_length":
                                summary_problem = "phone_invalid"
                                bad_summary_phone = t_phone
                            elif t_status == "ok" and sum_phone and sum_phone != t_phone:
                                summary_problem = "phone_mismatch"
                                bad_summary_phone = f"{sum_phone}|{t_phone}"
                            else:
                                # Spoken Gujarati/Hindi number words are transcribed only partly ("O Ganeshi ... 84 26 52 99"
                                # for 79 84 26 52 99), so a run of 4+ of the patient's digits inside the number counts as said
                                heard = any(sum_phone in d or (len(d) >= 4 and d in sum_phone) for d in said_digits)
                                if sum_phone and not heard:
                                    summary_problem = "phone_unheard"
                                    bad_summary_phone = sum_phone
                        # City must belong to the pincode (a summary said "Surat" with Rajkot's 360001)
                        sum_pin = "".join(filter(str.isdigit, str(merged_for_check.get("pincode") or "")))
                        sum_city = str(merged_for_check.get("city") or "").strip().lower()
                        if not summary_problem and len(sum_pin) == 6 and sum_city:
                            from voice_agent.services.dentist_service import get_pincode_canonical_city
                            pin_city = await asyncio.to_thread(get_pincode_canonical_city, sum_pin)
                            if pin_city and pin_city.lower() not in sum_city and sum_city not in pin_city.lower():
                                summary_problem = "city_mismatch"
                                bad_summary_phone = f"{sum_pin}|{pin_city}"
                    if summary_slots.get("phone") and not is_valid_indian_mobile(summary_slots["phone"]):
                        # An invalid or placeholder phone never reaches the booking slots
                        bad_summary_phone = summary_slots.pop("phone")
                    if is_review_summary:
                        if summary_problem:
                            self.session.last_review_summary_slots = {}
                            self.session.last_review_summary_text = ""
                            if summary_problem in ("phone_invalid", "phone_missing", "phone_unheard"):
                                self.session.asking_for_field = "phone"
                            if summary_problem == "city_mismatch":
                                self.session.asking_for_field = "city_confirmation"
                            if summary_problem == "phone_mismatch":
                                self.session.booking_slots["phone"] = bad_summary_phone.partition("|")[2]
                                summary_slots.pop("phone", None)  # the wrong spoken number never reaches the slots
                            correction_note = build_summary_correction_note(summary_problem, bad_summary_phone)
                            print(f"[SUMMARY-INVALID] Review summary rejected ({summary_problem}); asking Gemini to correct it.")
                        else:
                            self.session.last_review_summary_slots = dict(summary_slots)
                            self.session.last_review_summary_text = clean_text or bot_text_to_send

                    if summary_slots:

                        # Canonical city integrity: ensure city slot is strictly the canonical city (e.g. Surat, never Sayan)
                        active_pin = summary_slots.get("pincode") or self.session.booking_slots.get("pincode")
                        if active_pin:
                            from voice_agent.services.dentist_service import get_pincode_canonical_city
                            c_pin = await asyncio.to_thread(get_pincode_canonical_city, active_pin)
                            if c_pin:
                                summary_slots["city"] = c_pin
                        elif summary_slots.get("city") and "," in str(summary_slots["city"]):
                            summary_slots["city"] = str(summary_slots["city"]).split(",")[-1].strip()

                        for k, v in summary_slots.items():
                            if v and str(v).lower() not in ["none", "null", "-", "--"]:
                                old_v = self.session.booking_slots.get(k)
                                if old_v and str(old_v).strip() != str(v).strip():
                                    if self.session.booking_slots.get("is_submitted") or getattr(self.session, "submitted_lead_id", None):
                                        self.session.booking_slots["is_submitted"] = False
                                        self.session.slots_edited_after_submit = True
                                self.session.booking_slots[k] = v
                        if summary_slots.get("user_name"):
                            self.session.user_name = summary_slots["user_name"]
                            u_p = summary_slots["user_name"].split()
                            self.session.booking_slots["first_name"] = u_p[0]
                            self.session.booking_slots["last_name"] = " ".join(u_p[1:]) if len(u_p) > 1 else "-"
                        if summary_slots.get("user_concern") or summary_slots.get("message"):
                            self.session.user_concern = summary_slots.get("user_concern") or summary_slots.get("message")
                            self.session.booking_slots["message"] = self.session.user_concern
                        if not self.session.booking_slots.get("message") and self.session.user_concern:
                            self.session.booking_slots["message"] = self.session.user_concern
                        # Verify doctor-city consistency
                        if self.session.booking_slots.get("doctor_name") and self.session.booking_slots.get("city"):
                            try:
                                from voice_agent.services.appointment_service import is_matched_doctor
                                matched = is_matched_doctor(self.session.booking_slots["doctor_name"], city=self.session.booking_slots.get("clinic_city") or self.session.booking_slots.get("city"))
                                if not matched:
                                    matched = is_matched_doctor(self.session.booking_slots["doctor_name"], city=None)
                                if matched:
                                    self.session.booking_slots["doctor_name"] = matched
                                else:
                                    self.session.booking_slots["doctor_name"] = ""
                            except Exception:
                                pass
                        await self.send_json({
                            "type": "sync_slots",
                            "slots": self.session.booking_slots
                        })

                    # ⚡ Check for Step 3.5 Compulsory Single-Message City Confirmation Turn ⚡
                    if getattr(self.session, "city_confirm_needed", False):
                        self.session.city_confirm_needed = False
                        from voice_agent.services.dentist_service import format_city_confirm_speech
                        user_lang = turn_lang
                        p_pin = getattr(self.session, "pending_pincode", "") or self.session.booking_slots.get("pincode", "")
                        p_cit = getattr(self.session, "pending_display_city", "") or getattr(self.session, "pending_city", "") or self.session.booking_slots.get("city", "")
                        intercepted_msg = format_city_confirm_speech(p_pin, p_cit, user_lang)
                        self.session.asking_for_field = "city_confirmation"
                        if not clean_text or clean_text == "...":
                            clean_text = intercepted_msg
                            await self.send_json({
                                "type": "bot_text_chunk",
                                "text": intercepted_msg,
                                "tag": None,
                                "turnId": self.session.current_voice_turn_id
                            })

                    # ⚡ Check for Travel Booking Turn (e.g. Mumbai resident booking in Surat) ⚡
                    elif getattr(self.session, "is_travel_booking_turn", False):
                        from voice_agent.services.dentist_service import format_travel_dentists_speech_text, get_nearest_dentists_for_travel
                        user_lang = turn_lang
                        r_cit = self.session.booking_slots.get("city", "") or getattr(self.session, 'pending_city', '')
                        r_pin = self.session.booking_slots.get("pincode", "") or getattr(self.session, 'pending_pincode', '')
                        t_dest = getattr(self.session, "travel_destination_city", "") or self.session.booking_slots.get("clinic_city", "")
                        t_docs = getattr(self.session, "recommended_dentists", [])
                        if not t_docs:
                            t_docs = await asyncio.to_thread(get_nearest_dentists_for_travel, r_pin, r_cit, t_dest)
                            self.session.recommended_dentists = t_docs
                        intercepted_msg = format_travel_dentists_speech_text(t_docs, r_cit, t_dest, user_lang)
                        self.session.is_travel_booking_turn = False
                        self.session.asking_for_field = "doctor_selection"
                        self.session.recommended_dentists_spoken = True
                        # Gemini has already spoken its reply by turnComplete. Appending a second, different dentist
                        # list here showed two answers (often in another language) for one question, so only fill
                        # in when Gemini produced nothing.
                        if not clean_text or clean_text == "...":
                            clean_text = intercepted_msg
                            await self.send_json({
                                "type": "bot_text_chunk",
                                "text": intercepted_msg,
                                "tag": None,
                                "turnId": self.session.current_voice_turn_id
                            })

                    # (An invalid review summary is handled above: Gemini is asked to speak the correction itself
                    # instead of the server appending a second, silent bubble in a guessed language.)

                    # ⚡ Fast-path submission / cancellation in Voice Mode ⚡
                    bot_reply_lower = (self.session.full_bot_reply or "").lower()
                    clean_reply_lower = (clean_text or "").lower()
                    # Submit/cancel only ever happens in reply to something the patient actually said, and an
                    # already-cancelled booking is not cancelled again every time Riya mentions the cancellation
                    real_user_turn = bool(user_text.strip())
                    # Explicit "re-submit / submit again" may reuse the last submitted summary (a plain "yes" may not).
                    # Edits produce a fresh summary anyway, which the patient then confirms with "submit".
                    if real_user_turn and not self.session.last_review_summary_slots and getattr(self.session, "last_consumed_summary_slots", None) \
                            and re.search(r"(re-?submit|submit again|dobara|fir se|phir se|फिर से|दोबारा|ફરીથી|ફરી થી|pharithi|farithi)", user_text, re.IGNORECASE):
                        self.session.last_review_summary_slots = dict(self.session.last_consumed_summary_slots)
                        self.session.slots_edited_after_submit = True
                    already_cancelled = bool(self.session.booking_slots.get("is_cancel")) and bool(self.session.booking_slots.get("is_submitted")) \
                                        and not getattr(self.session, "slots_edited_after_submit", False)
                    if already_cancelled:
                        # The cancel request is fulfilled; a leftover flag re-cancelled on a later turn
                        self.session.pending_cancellation = False
                    is_cancel_req = real_user_turn and not already_cancelled and (
                                    is_cancel_submit(user_text, self.session) or
                                    is_cancel_response_text(bot_reply_lower) or
                                    is_cancel_response_text(clean_reply_lower) or
                                    bool(getattr(self.session, "pending_cancellation", False)))
                    is_model_confirmed = is_submit_response_text(bot_reply_lower) or any(w in bot_reply_lower for w in ["successfully submitted", "appointment request has been", "appointment has been submitted", "સફળતાપૂર્વક સબમિટ", "સબમિટ થઈ ગઈ છે", "સબમિટ કરવામાં આવી", "सफलतापूर्वक सबमिट", "सबमिट हो गई"])
                    is_user_affirmed = is_affirmative_submit(user_text)
                    is_explicit_sub = is_explicit_submit_command(user_text) or any(w in (user_text or "").lower() for w in ['sommeil', 'sommet', 'soit', 'somet', 'sammit', 'submarino'])
                    has_existing_lead = bool(self.session.booking_slots.get("submission_id") or getattr(self.session, "submitted_lead_id", None))

                    can_submit_booking = (not self.session.booking_slots.get("is_submitted")) or getattr(self.session, "slots_edited_after_submit", False) or (has_existing_lead and (is_explicit_sub or is_user_affirmed))

                    should_submit = real_user_turn and (is_cancel_req or
                                    ((is_model_confirmed or is_user_affirmed or is_explicit_sub) and can_submit_booking))
                    # The submit_appointment_booking tool may already have submitted during this same turn
                    if getattr(self.session, "last_submit_turn_id", None) == self.session.current_voice_turn_id:
                        should_submit = False

                    # Defaults for the confirmation guard below (it previously raised NameError when should_submit was False)
                    _bs = self.session.booking_slots
                    has_fn = bool(_bs.get("first_name") and str(_bs["first_name"]).lower() not in ["", "none", "null", "patient", "user"])
                    has_city = bool(_bs.get("city") and len(str(_bs["city"]).strip()) >= 2 and str(_bs["city"]).lower() not in ["none", "null", "india", ""])
                    has_msg = bool((_bs.get("message") or self.session.user_concern or "").strip())
                    has_pin = len("".join(filter(str.isdigit, str(_bs.get("pincode") or "")))) == 6

                    submitted_this_turn = False
                    if should_submit:
                        # The patient says "submit" to the summary they just heard, so the last VALID review summary
                        # is the source of truth: its values win over anything the server parsed from transcripts.
                        confirmed_slots = dict(getattr(self.session, "last_review_summary_slots", {}) or {})
                        slots_to_send = dict(self.session.booking_slots)
                        if self.session.user_name:
                            u_parts = self.session.user_name.split()
                            slots_to_send["first_name"] = u_parts[0]
                            slots_to_send["last_name"] = " ".join(u_parts[1:]) if len(u_parts) > 1 else "-"
                        if self.session.user_concern:
                            slots_to_send["message"] = self.session.user_concern
                        if not self.session.booking_slots.get("message") and self.session.user_concern:
                            self.session.booking_slots["message"] = self.session.user_concern
                        for k, v in confirmed_slots.items():
                            if v and str(v).lower() not in ["none", "null", "-", "--"]:
                                slots_to_send[k] = v
                        if confirmed_slots.get("user_concern"):
                            slots_to_send["message"] = confirmed_slots["user_concern"]

                        if slots_to_send.get("doctor_name"):
                            try:
                                from voice_agent.services.appointment_service import is_matched_doctor
                                matched = is_matched_doctor(slots_to_send["doctor_name"], city=slots_to_send.get("city"))
                                if not matched:
                                    matched = is_matched_doctor(slots_to_send["doctor_name"], city=None)
                                if matched:
                                    slots_to_send["doctor_name"] = matched
                                    self.session.booking_slots["doctor_name"] = matched
                                else:
                                    slots_to_send["doctor_name"] = ""
                                    self.session.booking_slots["doctor_name"] = ""
                            except Exception:
                                pass
                        
                        has_fn = bool(slots_to_send.get("first_name") and slots_to_send["first_name"].lower() not in ["", "none", "null", "patient", "user"])
                        has_city = bool(slots_to_send.get("city") and len(str(slots_to_send["city"]).strip()) >= 2 and str(slots_to_send["city"]).lower() not in ["none", "null", "india", ""])
                        has_msg = bool(slots_to_send.get("message") and len(slots_to_send["message"].strip()) >= 2)
                        has_pin = bool(slots_to_send.get("pincode") and len("".join(filter(str.isdigit, str(slots_to_send["pincode"])))) == 6)
                        has_phone = is_valid_indian_mobile(slots_to_send.get("phone"))

                        if is_cancel_req or (confirmed_slots and has_fn and has_city and has_pin and has_msg and has_phone):
                            sub_id = self.session.booking_slots.get("submission_id") or getattr(self.session, "submitted_lead_id", None)
                            slots_to_send["is_cancel"] = is_cancel_req
                            slots_to_send["is_update"] = bool(sub_id) or bool(self.session.booking_slots.get("is_submitted")) or bool(getattr(self.session, "slots_edited_after_submit", False))
                            slots_to_send["submission_id"] = sub_id
                            slots_to_send["id"] = sub_id
                            if self.session.booking_slots.get("old_phone"):
                                slots_to_send["old_phone"] = self.session.booking_slots.get("old_phone")
                            if self.session.booking_slots.get("godaddy_id"):
                                slots_to_send["godaddy_id"] = self.session.booking_slots.get("godaddy_id")
                            if self.session.booking_slots.get("api_id"):
                                slots_to_send["api_id"] = self.session.booking_slots.get("api_id")
                            await self.send_json({"type": "status_update", "status": "cancelling" if is_cancel_req else "submitting"})
                            res = await submit_consultation_appointment(slots_to_send)
                            if res.get("status") == "success":
                                submitted_this_turn = True
                                self.session.booking_slots["is_submitted"] = True
                                self.session.slots_edited_after_submit = False
                                self.session.last_submit_turn_id = self.session.current_voice_turn_id
                                self.consume_review_summary()
                                if is_cancel_req:
                                    self.session.booking_slots["is_cancel"] = True
                                    self.session.pending_cancellation = False
                                    self.session.consultation_declined = True
                                    self.session.asking_for_field = None
                                else:
                                    self.session.booking_slots["is_cancel"] = False
                                if isinstance(res.get("details"), dict):
                                    ret_id = res["details"].get("id") or res["details"].get("submission_id")
                                    if ret_id:
                                        self.session.booking_slots["submission_id"] = ret_id
                                        self.session.submitted_lead_id = ret_id
                                    if res["details"].get("godaddy_id"):
                                        self.session.booking_slots["godaddy_id"] = res["details"]["godaddy_id"]
                                    if res["details"].get("api_id"):
                                        self.session.booking_slots["api_id"] = res["details"]["api_id"]
                                for k, v in slots_to_send.items():
                                    if v is not None:
                                        if k in ('is_submitted', 'is_cancel', 'is_update'):
                                            pass  # set from the backend result above; this pre-submit copy (is_submitted=False) must not undo it
                                        elif isinstance(v, bool):
                                            self.session.booking_slots[k] = v
                                        else:
                                            self.session.booking_slots[k] = str(v)
                                await self.send_json({
                                    "type": "sync_slots",
                                    "slots": self.session.booking_slots
                                })
                                act_type = "cancelled" if is_cancel_req else ("updated" if slots_to_send["is_update"] else "submitted")
                                print(f"[INFO] Fast-path appointment {act_type} in Voice Mode: {slots_to_send}")

                    # ⚡ Patient asked to submit / Gemini claimed "submitted", but nothing valid was submitted ⚡
                    # Gemini already spoke its reply, so it corrects itself out loud (same voice, same language)
                    # instead of the server appending a silent text bubble.
                    if real_user_turn and not is_cancel_req and not submitted_this_turn and correction_note is None and \
                            getattr(self.session, "last_submit_turn_id", None) != self.session.current_voice_turn_id:
                        gemini_claimed_submitted = (not self.session.booking_slots.get("is_submitted") or getattr(self.session, "slots_edited_after_submit", False)) and (
                            is_submit_response_text(clean_text) or any(w in clean_text.lower() for w in ["સફળતાપૂર્વક સબમિટ", "સબમિટ થઈ ગઈ છે", "સબમિટ કરવામાં આવી", "सफलतापूर्वक सबमिट", "सबमिट हो गई", "successfully submitted"])
                        )
                        # Only when Riya claims it was submitted. A "submit"/"book it" before a valid summary needs no note:
                        # nothing gets submitted and Riya is already asking for what is missing (a note only doubled her question)
                        if gemini_claimed_submitted:
                            check_slots = {
                                "user_name": self.session.user_name,
                                "user_concern": self.session.user_concern,
                                **self.session.booking_slots,
                                **(getattr(self.session, "last_review_summary_slots", {}) or {}),
                            }
                            missing = get_review_summary_problem(check_slots)
                            if missing in ("phone_invalid", "phone_missing"):
                                self.session.asking_for_field = "phone"
                            correction_note = build_summary_correction_note(missing or "not_submitted", check_slots.get("phone") or "")
                            print(f"[SUBMIT-BLOCKED] No valid review summary to submit ({missing or 'summary not confirmed'}); asking Gemini to correct.")

                    # Submitted / cancelled this turn but Riya did not ask the profession question (the server-side
                    # submit paths never told her to): have her ask ONLY that question now - once per conversation
                    submit_done_now = getattr(self.session, "last_submit_turn_id", None) == self.session.current_voice_turn_id
                    if submit_done_now and correction_note is None and not is_correction_reply \
                            and self.session.booking_slots.get("is_submitted") \
                            and not getattr(self.session, "profession_done", False) and not text_asks_profession(clean_text):
                        from voice_agent.ai.conversation_manager import profession_question_text
                        correction_note = (
                            "[BACKEND NOTE - not spoken by the patient. Do not read this note aloud.] The appointment request is "
                            "done. Now ask ONLY this one question, in the patient's language, nothing before or after it: "
                            f"'{profession_question_text(self._voice_lang())}'"
                        )
                        self.session.profession_done = True  # asked exactly once, never again
                        print("[PROFESSION] not asked after submit -> asking Riya to ask it now")

                    if len(current_assistant_audio) > 0 or len(clean_text) > 0:
                        final_tag, new_pending = detect_best_tag_with_fallback(
                            user_text, clean_text or "...", self.session.pending_action_tag
                        )
                        self.session.pending_action_tag = new_pending
                        # Summary turn: the full summary card is already on screen, so Riya's spoken short version of it
                        # is neither shown again nor saved twice in the transcript
                        summary_card = getattr(self.session, "pending_summary_card", "") or ""
                        self.session.pending_summary_card = ""
                        shown_text = "" if summary_card else (clean_text or "...")

                        await self.send_json({
                            "type": "bot_spoken_text",
                            "text": shown_text or "...",
                            "tag": final_tag,
                            "turnId": self.session.current_voice_turn_id
                        })
                        
                        if user_text and user_text != "Hello":
                            self.session.add_transcript_turn("user", user_text)
                        if summary_card:
                            self.session.add_transcript_turn("model", summary_card)
                        elif clean_text and clean_text != "...":
                            self.session.add_transcript_turn("model", clean_text)
                        log_live_voice_conversation(user_text, summary_card or clean_text or "...", dict(self.session.booking_slots))
                        await self.send_json({
                            "type": "reply_complete",
                            "userText": user_text,
                            "botText": shown_text,
                            "tag": final_tag,
                            "totalChunks": self.session.chunk_index,
                            "slots": dict(self.session.booking_slots),
                            "userName": self.session.user_name,
                            "userConcern": self.session.user_concern,
                            "userCity": self.session.booking_slots.get("city"),
                            "userDoctor": self.session.booking_slots.get("doctor_name"),
                            "userPhone": self.session.booking_slots.get("phone")
                        })
                        
                        # Background Bot STT transcription only if we did not get native transcription and have audio
                        if not self.session.full_bot_reply and len(current_assistant_audio) > 0:
                            asyncio.create_task(self.transcribe_bot_audio(current_assistant_audio))
                            
                    else:
                        await self.send_json({"type": "idle"})
                    
                    # ⚡ RESET FOR NEXT VOICE TURN (Distinct chat bubble & clear transcription accumulator) ⚡
                    self.session.chunk_index = 0
                    self.session.display_str = ""
                    self.session.full_bot_reply = ""
                    self.session.current_user_transcription = ""
                    self.session.latest_typed_user_text = ""
                    self.session.current_voice_turn_id += 1
                    self.session.reset_activity_timer()
                    self.session.latest_client_history = []
                    self.session.clear_voice_intercept_flags()
                    await self.sync_slots_to_gemini()
                    if correction_note and not is_correction_reply:
                        await self.request_spoken_correction(correction_note)
        except Exception as e:
            import traceback
            print(f"[ERROR] Error parsing Gemini WS frame: {e}", flush=True)
            traceback.print_exc()

    async def stream_gemini_chat_reply(self, user_text, history, system_prompt):
        try:
            api_key = os.getenv("GEMINI_API_KEY_NEW") or os.getenv("GEMINI_API_KEY")
            contents = sanitize_gemini_history(history)
            safe_text = user_text or ""
            
            if contents and contents[-1]["role"] == "user":
                if safe_text:
                    contents[-1]["parts"][0]["text"] += " \n " + safe_text
            else:
                if safe_text:
                    contents.append({"role": "user", "parts": [{"text": safe_text}]})
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TEXT_MODEL}:streamGenerateContent?alt=sse&key={api_key}"
            payload = {
                "systemInstruction": {"parts": [{"text": system_prompt}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.2}
            }
            
            display_str = ""
            best_tag = detect_best_tag(user_text, "")
            
            max_retries = 3
            success = False
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    display_str = "" # Reset on retry
                    async with httpx.AsyncClient() as client:
                        async with client.stream("POST", url, json=payload, timeout=30.0) as response:
                            if response.status_code != 200:
                                raise Exception(f"Gemini REST failure: {response.status_code}")
                                
                            async for line in response.aiter_lines():
                                line = line.strip()
                                if not line.startswith("data: "):
                                    continue
                                payload_data = line[6:]
                                if not payload_data:
                                    continue
                                
                                try:
                                    json_data = json.loads(payload_data)
                                    parts = json_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                                    for part in parts:
                                        delta = part.get("text", "")
                                        if delta and not part.get("thought"):
                                            display_str += delta
                                            await self.send_json({
                                                "type": "bot_text_chunk",
                                                "text": delta,
                                                "tag": best_tag
                                            })
                                except Exception:
                                    pass
                    success = True
                    break
                except Exception as e:
                    last_error = e
                    if "50" in str(e) or "429" in str(e): # Handle 5xx and 429
                        print(f"[WARNING] Gemini API error: {e}. Retrying {attempt+1}/{max_retries}...")
                        await asyncio.sleep(2 * (attempt + 1))
                    else:
                        raise e
            
            if not success:
                if last_error is not None:
                    raise last_error
                raise RuntimeError("Gemini REST request failed after maximum retries")
            
            final_text = clean_assistant_text(display_str.strip() or "Okay.")
            final_tag, new_pending = detect_best_tag_with_fallback(
                user_text, final_text, self.session.pending_action_tag
            )
            self.session.pending_action_tag = new_pending
            
            await self.send_json({
                "type": "bot_spoken_text",
                "text": final_text,
                "tag": final_tag
            })
                    
            await self.send_json({
                "type": "reply_complete",
                "userText": user_text or "Text Input",
                "botText": final_text,
                "tag": final_tag,
                "totalChunks": 0
            })
            self.session.reset_activity_timer()
        except Exception as e:
            print(f"[ERROR] Chat mode text generation error: {e}")
            fallback_text = "I'm sorry, I am having trouble processing that right now. Please try asking again."
            await self.send_json({
                "type": "bot_spoken_text",
                "text": fallback_text
            })
            await self.send_json({
                "type": "reply_complete",
                "userText": user_text or "Text Input",
                "botText": fallback_text,
                "tag": final_tag if 'final_tag' in locals() else None,
                "totalChunks": 0
            })
            self.session.reset_activity_timer()

    async def transcribe_interrupted_bot_text(self, audio_bytes, turn_id):
        try:
            lang = self.session.current_language or 'en-IN'
            bot_text = await transcribe_voice_data(audio_bytes, 24000, language_code=lang)
            if bot_text:
                clean_text = clean_assistant_text(bot_text).strip()
                if clean_text:
                    if not clean_text.endswith("..."):
                        clean_text += " ..."
                    best_tag = detect_best_tag(self.session.latest_typed_user_text, clean_text)
                    await self.send_json({
                        "type": "bot_spoken_text",
                        "text": clean_text,
                        "tag": best_tag,
                        "turnId": turn_id
                    })
        except Exception as e:
            print(f"Error transcribing interrupted bot text: {e}")
