import sys
import os
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

filepath = r"d:\media\voice_agent\ai\conversation_manager.py"
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update name regex to support aur/or/hamara/and
old_name_prefix = r"(?:maru|maro|maaru|mari|mera|meri|apna|majhe|amar)\s+(?:naam|nam|name|naav|nav|नाव|નામ|नाम)"
new_name_prefix = r"(?:maru|maro|maaru|mari|mera|meri|apna|majhe|amar|aur|or|hamara|and)\s+(?:naam|nam|name|naav|nav|नाव|નામ|नाम)"
if old_name_prefix in content:
    content = content.replace(old_name_prefix, new_name_prefix)
    print("✓ Updated name regex prefix.")

# 2. Update suffix stripping in name extraction
old_strip1 = r"\s+(?:chhe|che|hai|hain|hoon|hu|is|am|are|hूँ|છે|છુ|છીએ|હું|હે|તો|પણ|and|yes|no|है|हूँ|हैं|हो|था|थी|थे|હતો|હતી|હતા)\b.*$"
new_strip1 = r"\s+(?:chhe|che|hai|hain|hoon|hu|is|am|are|se|te|thi|hूँ|છે|છુ|છીએ|હું|હે|તો|પણ|સે|તે|થી|and|yes|no|है|हूँ|हैं|हो|था|थी|थे|હતો|હતી|હતા)\b.*$"
if old_strip1 in content:
    content = content.replace(old_strip1, new_strip1)

old_strip2 = r"\s+(?:છે|છુ|છીએ|હું|હે|તો|પણ|है|हूँ|हैं|हो|था|थी|थे|હતો|હતી|હતા).*$"
new_strip2 = r"\s+(?:છે|છુ|છીએ|હું|હે|તો|પણ|સે|તે|થી|है|हूँ|हैं|हो|था|थी|थे|હતો|હતી|હતા).*$"
if old_strip2 in content:
    content = content.replace(old_strip2, new_strip2)
print("✓ Updated suffix stripping in name extraction.")

# 3. Add decline, agreement, and profession detection to update_session_memory
target_user_text = "        if user_text:\n            text = user_text.strip()"
new_user_text_handling = """        if user_text:
            text = user_text.strip()
            
            # Detect user declining consultation / not wanting to book right now
            if any(w in text.lower() for w in [
                "ના ના", "નથી કરવું", "નથી કરાવી", "પહેલા સમજાવો", "પહેલા જણાવો", "પહેલા મને", "નથી જોતી",
                "नहीं", "ना ना", "अभी नहीं", "पहले समझाओ", "पहले बताओ", "सवाल है", "नहीं चाहिए", "नहीं करानी",
                "not now", "no need", "don't want", "dont want", "explain first", "tell me first"
            ]):
                self.session.consultation_declined = True

            # Detect user explicitly agreeing or asking to book consultation
            if any(w in text.lower() for w in [
                "બુક કરો", "બુક કરી દો", "બુક કરી દ્યો", "અપોઇન્ટમેન્ટ બુક", "અપૉઇન્ટમેન્ટ બુક",
                "बुक करो", "बुक कर दो", "बुक कर दीजिए", "अपॉइंटमेंट बुक", "बुक करा",
                "book appointment", "book my appointment", "help me book", "yes book", "ha book", "haan book"
            ]):
                self.session.consultation_agreed = True
                self.session.consultation_declined = False

            # Detect profession inquiry answers
            prof_map = {
                "doctor": "Doctor", "dr": "Doctor", "physician": "Doctor", "surgeon": "Doctor", "ડેન્ટિસ્ટ": "Dentist", "dentist": "Dentist",
                "teacher": "Teacher", "professor": "Teacher", "શિક્ષક": "Teacher", "शिक्षक": "Teacher",
                "engineer": "Engineer", "developer": "Engineer", "coder": "Engineer", "એન્જિનિયર": "Engineer", "इंजीनियर": "Engineer",
                "lawyer": "Lawyer", "advocate": "Lawyer", "વકીલ": "Lawyer", "वकील": "Lawyer",
                "chartered accountant": "CA", "ca": "CA", "સીએ": "CA",
                "businessman": "Businessman", "business": "Businessman", "વેપારી": "Businessman", "व्यापारी": "Businessman",
                "student": "Student", "વિદ્યાર્થી": "Student", "छात्र": "Student",
                "architect": "Architect", "આર્કિટેક્ટ": "Architect",
                "sales": "Sales Professional", "marketing": "Marketing Professional"
            }
            tl_words = re.findall(r'[A-Za-z\\u0A80-\\u0AFF\\u0900-\\u097F]+', text.lower())
            for w in tl_words:
                if w in prof_map:
                    self.session.user_profession = prof_map[w]
                    break"""

if target_user_text in content:
    content = content.replace(target_user_text, new_user_text_handling, 1)
    print("✓ Added decline, agreement, and profession detection to update_session_memory.")

# 4. Insert _build_next_step_instruction helper method
build_method_code = '''    def _build_next_step_instruction(self, user_text, history, user_lang, display_name, fn, ln, cn, ct, dr, ph, pending_doc):
        """Constructs the exact, step-by-step instruction for Riya, enforcing consultation permission gates,
        proactive profession inquiry, diverse zero-pressure follow-ups, and sequential slot progression."""
        slots = self.session.booking_slots
        if slots.get("is_submitted"):
            return (
                f"🚨 MANDATORY POST-SUBMISSION PERMANENT LOCK (CRITICAL OVERRIDE):\\n"
                f"The consultation appointment for {self.session.user_name or fn or 'the patient'} (Phone: {ph}, City: {ct}, Doctor: {dr}, Concern: {cn}) has ALREADY BEEN SUCCESSFULLY SUBMITTED to our clinic team!\\n"
                f"RULES:\\n"
                f"1. NEVER ask 'Shall I book your appointment?', 'Shall I submit your appointment?', 'Should I book your consultation?', 'તમારી અપૉઇન્ટમેન્ટ બુક કરી નાખું?', 'आपकी अपॉइंटमेंट बुक कर दूं?' or offer booking again.\\n"
                f"2. UNLESS the user explicitly requests: 'I want to change my appointment', 'modify details', or 'book another appointment', you must NEVER prompt for booking or confirmation.\\n"
                f"3. For all other questions (veneers, costs, procedure, warranty, clinic timings, friendly conversation, sports/movies off-topic), answer warmly, helpfully, and authoritatively without mentioning booking an appointment."
            )
        elif not fn and not self.session.user_name:
            return "STEP 1 (NAME): Ask for the patient's full name in their language: 'Let's start with your beautiful name, what is your name?'"
        elif not cn and not self.session.user_concern:
            return (
                f"STEP 2 (DENTAL CONCERN): The patient's name is '{display_name}'. "
                f"Warmly acknowledge their name and ask what dental concern, pain, or smile improvement they would like to discuss: "
                f"'બહુ સરસ, {display_name}! તમને તમારા દાંત કે સ્માઇલ વિશે કઈ સમસ્યા છે?'"
            )
        elif not getattr(self.session, 'consultation_agreed', False) and not ct:
            offer_count = getattr(self.session, 'consultation_offer_count', 0)
            declined = getattr(self.session, 'consultation_declined', False)
            if offer_count < 1 and not declined:
                self.session.consultation_offer_count = offer_count + 1
                return (
                    f"STEP 2.5 (CONCERN ACKNOWLEDGEMENT & CONSULTATION OFFER - MANDATORY PERMISSION GATE):\\n"
                    f"The patient '{display_name}' revealed their dental concern: '{cn}'.\\n"
                    f"Empathetically acknowledge their specific concern in {user_lang}, and ask if they would like you to help book a consultation appointment with our USD Certified Smile Designer to resolve it!\\n"
                    f"🚨 CRITICAL MANDATORY GATE: DO NOT start booking, DO NOT ask for City, and DO NOT ask for Doctor yet in this turn until the patient explicitly says YES or agrees!\\n"
                    f"• Gujarati: 'હું સમજી શકું છું કે તમને {cn}ની સમસ્યા છે, {display_name}. શું હું આના ઉકેલ માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું?'\\n"
                    f"• Hindi: 'मैं समझ सकती हूँ कि आपको {cn} की समस्या आ रही है, {display_name}। क्या मैं इसके समाधान के लिए हमारे USD सर्टिफाइड स्माइल डिज़ाइनर के साथ अपॉइंटमेंट बुक करने में आपकी मदद કરूँ?'\\n"
                    f"• English: 'I understand you are experiencing {cn}, {display_name}. Would you like me to help book a consultation appointment with our USD Certified Smile Designer for this?'"
                )
            else:
                # Patient has questions or declined booking -> PURE CONVERSATIONAL AI SMILE CONSULTANT!
                if not getattr(self.session, 'asked_profession', False) and not getattr(self.session, 'user_profession', None):
                    self.session.asked_profession = True
                    return (
                        f"CONVERSATIONAL AI SMILE CONSULTANT (PROACTIVE PROFESSION INQUIRY - ZERO BOOKING PRESSURE):\\n"
                        f"The patient '{display_name}' is exploring their teeth/concern ({cn}) and has not agreed to booking yet.\\n"
                        f"🚨 ABSOLUTE MANDATE: DO NOT ask to book an appointment! DO NOT ask 'Shall I book your appointment?' or 'Would you like to know our philosophy?'. DO NOT ask for City or Doctor!\\n"
                        f"1. Answer the patient's immediate question directly, warmly, and concisely in 1-2 short sentences in {user_lang}.\\n"
                        f"2. Then PROACTIVELY ask what they do for work in {user_lang}:\\n"
                        f"   • Gujarati: 'તેમ છતાં, {display_name}, જો હું પૂછી શકું, તમે શું કામ કરો છો?'\\n"
                        f"   • Hindi: 'वैसे, {display_name}, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं?'\\n"
                        f"   • English: 'By the way, {display_name}, if I may ask, what do you do for work?'\\n"
                        f"3. STOP speaking immediately after asking."
                    )
                else:
                    return (
                        f"CONVERSATIONAL AI SMILE CONSULTANT (VARIED EXPLORATORY DIALOGUE - ZERO BOOKING PRESSURE):\\n"
                        f"The patient '{display_name}' has questions about their teeth/smile ({cn}) or treatment.\\n"
                        f"🚨 ABSOLUTE MANDATE: DO NOT ask to book an appointment! DO NOT say 'Shall I book your appointment?' or 'Would you like to know our philosophy?'. DO NOT ask for City or Doctor!\\n"
                        f"1. Answer their question directly and concisely in 1-2 sentences in {user_lang}.\\n"
                        f"2. Use a natural varied follow-up, or stop speaking:\\n"
                        f"   - Ask their preferred smile brightness/shade: 'Do you prefer a natural tooth shade or bright white?'\\n"
                        f"   - Ask how they feel in photos: 'When you see photos of your smile, what would you most like to enhance?'\\n"
                        f"   - Mention website features: 'You can also preview your smile using our Ultimate Smile AI simulator on this page, or explore before-and-after cases in our Gallery!'\\n"
                        f"3. WAIT for the patient to explicitly say they want to book an appointment before asking for City!"
                    )
        elif not ct:
            return (
                f"STEP 3 (CITY): The patient '{display_name}' wants to book an appointment for '{cn}'.\\n"
                f"Ask which city they are located in so we can find our closest USD Certified Smile Designer: "
                f"'તમે કયા શહેરમાં રહો છો, તે જણાવશો જેથી હું તમારી અપોઇન્ટમેન્ટ બુક કરી શકું?'"
            )
        elif not dr:
            if pending_doc:
                return f"STEP 4 (DOCTOR CONFIRMATION): The user mentioned doctor candidate {pending_doc}. Confirm the doctor in {user_lang}: 'Are you talking about {pending_doc} in {ct}?'"
            else:
                return f"STEP 4 (DOCTOR SELECTION): For {cn or 'your dental consultation'} in {ct}, ask the patient which USD Certified Smile Designer they want to consult with in {ct} (NEVER auto-assign a doctor!)."
        elif not ph:
            return f"STEP 5 (MOBILE NUMBER): Doctor {dr} in {ct} is selected. Ask for their 10-digit mobile phone number in {user_lang}: 'Could you please provide your 10-digit mobile phone number?' (NEVER guess phone number!)."
        else:
            return get_review_summary_prompt(user_lang, display_name, ph, ct, cn, dr)

'''

target_stream_chat = "    async def stream_chat_text_response(self, user_text, history, system_prompt):"
if "_build_next_step_instruction" not in content:
    assert target_stream_chat in content, "target_stream_chat not found in content!"
    content = content.replace(target_stream_chat, build_method_code + target_stream_chat, 1)
    print("✓ Added _build_next_step_instruction method before stream_chat_text_response.")

# 5. Use _build_next_step_instruction in stream_chat_text_response
old_instruction_block = """        if slots.get("is_submitted"):
            next_step_instruction = (
                f"🚨 MANDATORY POST-SUBMISSION PERMANENT LOCK (CRITICAL OVERRIDE):\\n"
                f"The consultation appointment for {self.session.user_name or fn or 'the patient'} (Phone: {ph}, City: {ct}, Doctor: {dr}, Concern: {cn}) has ALREADY BEEN SUCCESSFULLY SUBMITTED to our clinic team!\\n"
                f"RULES:\\n"
                f"1. NEVER ask 'Shall I book your appointment?', 'Shall I submit your appointment?', 'Should I book your consultation?', 'તમારી અપૉઇન્ટમેન્ટ બુક કરી નાખું?', 'आपकी अपॉइंटमेंट बुक कर दूं?' or offer booking again.\\n"
                f"2. UNLESS the user explicitly requests: 'I want to change my appointment', 'modify details', or 'book another appointment', you must NEVER prompt for booking or confirmation.\\n"
                f"3. For all other questions (veneers, costs, procedure, warranty, clinic timings, friendly conversation, sports/movies off-topic), answer warmly, helpfully, and authoritatively without mentioning booking an appointment."
            )
        elif not fn and not self.session.user_name:
            next_step_instruction = "STEP 1 (NAME): Ask for the patient's full name in their language: 'Let's start with your beautiful name, what is your name?'"
        elif not ct:
            display_name = f"{fn} {ln}".strip() if (ln and ln != "-" and ln.lower() != fn.lower()) else (self.session.user_name or fn or "Patient")
            next_step_instruction = (
                f"STEP 2 (CITY): The patient's name is '{display_name}'. "
                f"Greet {display_name} (if the user asks about their name or says they already gave it, warmly confirm: 'Yes, my apologies! Your name is {display_name}.') "
                f"and ask for their city in {user_lang}: 'Which city are you located in so I can check for our closest USD Certified Smile Designer?'"
            )
        elif not cn:
            next_step_instruction = f"STEP 3 (CONCERN): Patient is located in {ct}. Ask for their dental concern in {user_lang}: 'What dental concern or smile improvement would you like to discuss in {ct}?'"
        elif not dr:
            if pending_doc:
                next_step_instruction = f"STEP 4 (DOCTOR CONFIRMATION): The user mentioned doctor candidate {pending_doc}. Confirm the doctor in {user_lang}: 'Are you talking about {pending_doc} in {ct}?'"
            else:
                next_step_instruction = f"STEP 4 (DOCTOR SELECTION): For {cn or 'your dental consultation'} in {ct}, ask the patient which USD Certified Smile Designer they want to consult with in {ct} (NEVER auto-assign a doctor!)."
        elif not ph:
            next_step_instruction = f"STEP 5 (MOBILE NUMBER): Doctor {dr} in {ct} is selected. Ask for their 10-digit mobile phone number in {user_lang}: 'Could you please provide your 10-digit mobile phone number?' (NEVER guess phone number!)."
        else:
            display_name = f"{fn} {ln}".strip() if (ln and ln != "-" and ln.lower() != fn.lower()) else (self.session.user_name or fn or "Patient")
            next_step_instruction = get_review_summary_prompt(user_lang, display_name, ph, ct, cn, dr)"""

new_instruction_block = """        display_name = f"{fn} {ln}".strip() if (ln and ln != "-" and ln.lower() != fn.lower()) else (self.session.user_name or fn or "Patient")
        next_step_instruction = self._build_next_step_instruction(
            user_text, history, user_lang, display_name, fn, ln, cn, ct, dr, ph, pending_doc
        )"""

if old_instruction_block in content:
    content = content.replace(old_instruction_block, new_instruction_block, 1)
    print("✓ Replaced instruction block in stream_chat_text_response with helper method call.")

# 6. Guard against premature review summary / false submission in stream_chat_text_response
target_sync_block = """        # ⚡ CRITICAL: Extract and synchronize slots directly from Riya's review/confirmation message ⚡
        summary_slots = extract_slots_from_review_summary(clean_text or full_text)"""

new_sync_block = """        # ⚡ Guard against premature review summaries with missing fields ⚡
        if is_submit_review_summary(clean_text or full_text):
            temp_sum = extract_slots_from_review_summary(clean_text or full_text)
            has_fn = bool(temp_sum.get("first_name") or self.session.booking_slots.get("first_name") or self.session.user_name)
            has_ct = bool(temp_sum.get("city") or self.session.booking_slots.get("city"))
            has_dr = bool(temp_sum.get("doctor_name") or self.session.booking_slots.get("doctor_name"))
            has_ph = bool(temp_sum.get("phone") or self.session.booking_slots.get("phone"))
            has_cn = bool(temp_sum.get("message") or self.session.booking_slots.get("message") or self.session.user_concern)
            if not (has_fn and has_ct and has_dr and has_ph and has_cn):
                # Missing essential slot: Reject premature review summary and ask for missing field!
                print(f"[WARN] Premature review summary intercepted! Missing slots: fn={has_fn}, ct={has_ct}, dr={has_dr}, ph={has_ph}, cn={has_cn}")
                cur_ct = self.session.booking_slots.get("city") or temp_sum.get("city")
                cur_dr = self.session.booking_slots.get("doctor_name") or temp_sum.get("doctor_name")
                cur_ph = self.session.booking_slots.get("phone") or temp_sum.get("phone")
                disp_n = self.session.user_name or self.session.booking_slots.get("first_name") or "અમિતભાઈ"
                if not cur_ct:
                    clean_text = f"{disp_n}, તમે કયા શહેરમાં રહો છો તે જણાવશો જેથી હું અમારા સૌથી નજીકના USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર વિશે જણાવી શકું?" if "gu" in user_lang else f"{disp_n}, आप किस शहर में हैं ताकि मैं आपके सबसे नज़दीकी USD सर्टिफाइड स्माइल डिज़ाइनर का पता बता सकूँ?"
                elif not cur_dr:
                    clean_text = f"તમે {cur_ct}માં કયા USD સર્ટિફાઇડ ડૉક્ટર સાથે કન્સલ્ટ કરવા માંગો છો? તમે અમારા Find Dentist પેજ પર પણ જોઈ શકો છો." if "gu" in user_lang else f"कृपया {cur_ct} में हमारे USD सर्टिफाइड डॉक्टर का चयन करें या Find Dentist पेज पर देखें।"
                elif not cur_ph:
                    clean_text = f"ચોક્કસ! તમારો 10 અંકનો મોબાઇલ નંબર જણાવશો?" if "gu" in user_lang else f"कृपया अपना 10 अंकों का मोबाइल नंबर बता दीजिए?"
                full_text = clean_text

        # ⚡ CRITICAL: Extract and synchronize slots directly from Riya's review/confirmation message ⚡
        summary_slots = extract_slots_from_review_summary(clean_text or full_text) if is_submit_review_summary(clean_text or full_text) else {}"""

if target_sync_block in content:
    content = content.replace(target_sync_block, new_sync_block, 1)
    print("✓ Added guard against premature review summaries in stream_chat_text_response.")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("✓ conversation_manager.py successfully updated!")
