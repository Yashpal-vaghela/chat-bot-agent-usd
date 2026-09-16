import re

# 1. Update conversation.md
conv_path = r"d:\media\voice_agent\prompts\conversation.md"
with open(conv_path, "r", encoding="utf-8") as f:
    conv_content = f.read()

old_prof_sec_1 = """     - 🚨 ABSOLUTE MANDATORY RULE — PROFESSION INQUIRY TIMING & RESTRICTION:
       • 🚨 STRICT BAN IN FIRST 3 MESSAGES:
         You are STRICTLY FORBIDDEN from asking "What is your profession?" or "What do you do for work?" in turns 1, 2, or 3!
         The first 3 messages MUST focus entirely on understanding their smile goals, educating on USD philosophy, and answering their dental questions.
       • Timing: ONLY during open exploration starting at turn 4 or 5 (and strictly ONCE in the entire conversation), Riya may gently ask about their work or profession in the user's active language:"""

new_prof_sec_1 = """     - 🚨 MANDATORY RULE — PROFESSION INQUIRY TIMING & AT LEAST ONCE IN CONVERSATION:
       • 🚨 TIMING IN MESSAGES 1 & 2:
         Do NOT ask "What is your profession?" or "What do you do for work?" in messages 1 and 2 (which focus strictly on greeting, name confirmation, and initial concern).
       • MANDATORY AT LEAST ONCE IN WHOLE CONVERSATION (STARTING MESSAGE 3 / CONCERN STEP):
         Riya MUST ask about the patient's work or profession at least once in the conversation (ideally in message 3 when acknowledging their dental concern or during smile exploration) in the user's active language:"""

if old_prof_sec_1 in conv_content:
    conv_content = conv_content.replace(old_prof_sec_1, new_prof_sec_1, 1)
    print("Updated conversation.md section 1!")
else:
    print("Warning: old_prof_sec_1 not found in conversation.md")

old_prof_sec_2 = """1. NATURAL CONVERSATIONAL OPPORTUNITY & STRICT ONE-TIME EXPLORATORY TIMING:
   - 🚨 STRICT BAN IN FIRST 3 MESSAGES:
     NEVER ask about profession in the first 3 turns/messages of the conversation. The first 3 messages are dedicated to listening, consulting, educating, and answering the patient's questions.
   - When a user is exploring general smile goals, aesthetic aspirations, or discussing their personality/confidence (without an acute dental emergency or pain):
     After 4 to 5 exploratory turns, Riya may gently and naturally ask about their work/profession (EXACTLY ONCE IN THE WHOLE CONVERSATION):"""

new_prof_sec_2 = """1. NATURAL CONVERSATIONAL OPPORTUNITY & MANDATORY INQUIRY (AT LEAST ONCE IN CONVERSATION):
   - 🚨 TIMING IN MESSAGES 1 & 2:
     Do NOT ask about profession in messages 1 and 2 (focus strictly on greeting, name confirmation, and initial concern).
   - MANDATORY AT LEAST ONCE IN WHOLE CONVERSATION (STARTING MESSAGE 3 / CONCERN STEP):
     Riya MUST ask about the patient's work/profession at least once in the conversation (ideally in message 3 when acknowledging their dental concern or during smile exploration) (EXACTLY ONCE IN THE WHOLE CONVERSATION):"""

if old_prof_sec_2 in conv_content:
    conv_content = conv_content.replace(old_prof_sec_2, new_prof_sec_2, 1)
    print("Updated conversation.md section 2!")
else:
    print("Warning: old_prof_sec_2 not found in conversation.md")

with open(conv_path, "w", encoding="utf-8") as f:
    f.write(conv_content)


# 2. Update prompt_builder.py
pb_path = r"d:\media\voice_agent\ai\prompt_builder.py"
with open(pb_path, "r", encoding="utf-8") as f:
    pb_content = f.read()

old_pb_prof = """- 🚨 STRICT MANDATE — PROFESSION INQUIRY TIMING & RESTRICTION:
  • 🚨 STRICT BAN IN FIRST 3 MESSAGES:
    You are STRICTLY FORBIDDEN from asking "What is your profession?" or "What do you do for work?" in turns 1, 2, or 3!
    The first 3 messages MUST focus entirely on understanding their smile goals, educating on USD philosophy, and answering their questions.
  • In Riya's conversational flow during open exploration (ONLY starting at turn 4 or 5), Riya may gently ask what the user's profession or work is in the user's language:"""

new_pb_prof = """- 🚨 MANDATE — PROFESSION INQUIRY TIMING & AT LEAST ONCE IN CONVERSATION:
  • 🚨 TIMING IN MESSAGES 1 & 2:
    Do NOT ask "What is your profession?" or "What do you do for work?" in messages 1 and 2 (which focus strictly on greeting, name confirmation, and initial concern).
  • MANDATORY AT LEAST ONCE IN WHOLE CONVERSATION (STARTING MESSAGE 3 / CONCERN STEP):
    Riya MUST ask about the patient's work or profession at least once in the conversation (ideally in message 3 when acknowledging their dental concern or during smile exploration) in the user's active language:"""

if old_pb_prof in pb_content:
    pb_content = pb_content.replace(old_pb_prof, new_pb_prof, 1)
    print("Updated prompt_builder.py!")
else:
    print("Warning: old_pb_prof not found in prompt_builder.py")

with open(pb_path, "w", encoding="utf-8") as f:
    f.write(pb_content)


# 3. Update conversation_manager.py
cm_path = r"d:\media\voice_agent\ai\conversation_manager.py"
with open(cm_path, "r", encoding="utf-8") as f:
    cm_content = f.read()

# Step 2.5 instruction update
old_step_2_5 = """        elif not getattr(self.session, 'consultation_agreed', False) and not ct:
            next_step_instruction = (
                f"STEP 2.5 (CONCERN ACKNOWLEDGEMENT & CONSULTATION OFFER - MANDATORY PERMISSION GATE):\\n"
                f"The patient '{display_name}' revealed their dental concern: '{cn}'.\\n"
                f"Empathetically acknowledge their specific concern in {user_lang}, and ask if they would like you to help book a consultation appointment with our USD Certified Smile Designer to resolve it!\\n"
                f"🚨 CRITICAL MANDATORY GATE: DO NOT start booking, DO NOT ask for City, and DO NOT ask for Doctor yet in this turn until the patient explicitly says YES or agrees!\\n"
                f"• Gujarati: 'હું સમજી શકું છું કે તમને {cn}ની સમસ્યા છે, {display_name}. શું હું આના ઉકેલ માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું?'\\n"
                f"• Hindi: 'मैं समझ सकती हूँ कि आपको {cn} की समस्या आ रही है, {display_name}। क्या मैं इसके समाधान के लिए हमारे USD सर्टिफाइड स्माइल डिज़ाइनर के साथ अपॉइंटमेंट बुक करने में आपकी मदद करूँ?'\\n"
                f"• English: 'I understand you are experiencing {cn}, {display_name}. Would you like me to help book a consultation appointment with our USD Certified Smile Designer for this?'"
            )"""

new_step_2_5 = """        elif not getattr(self.session, 'consultation_agreed', False) and not ct:
            prof_prompt = ""
            if not getattr(self.session, "profession_asked", False):
                prof_prompt = (
                    f" Also warmly ask for their profession at this moment: "
                    f"(Gujarati: 'તેમ છતાં, {display_name}, જો હું પૂછી શકું, તમે શું કામ કરો છો?', "
                    f"Hindi: 'वैसे, {display_name}, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं?', "
                    f"English: 'By the way, {display_name}, may I ask what you do for work?')."
                )
            next_step_instruction = (
                f"STEP 2.5 (CONCERN ACKNOWLEDGEMENT, PROFESSION INQUIRY & CONSULTATION OFFER - MANDATORY PERMISSION GATE):\\n"
                f"The patient '{display_name}' revealed their dental concern: '{cn}'.\\n"
                f"Empathetically acknowledge their specific concern in {user_lang}, ask for their profession (if not already asked), and ask if they would like you to help book a consultation appointment with our USD Certified Smile Designer to resolve it!{prof_prompt}\\n"
                f"🚨 CRITICAL MANDATORY GATE: DO NOT start booking, DO NOT ask for City, and DO NOT ask for Doctor yet in this turn until the patient explicitly says YES or agrees!\\n"
                f"• Gujarati: 'હું સમજી શકું છું કે તમને {cn}ની સમસ્યા છે, {display_name}. તેમ છતાં, જો હું પૂછી શકું, તમે શું કામ કરો છો? શું હું આના ઉકેલ માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું?'\\n"
                f"• Hindi: 'मैं समझ सकती हूँ कि आपको {cn} की समस्या आ रही है, {display_name}। वैसे, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं? क्या मैं इसके समाधान के लिए हमारे USD सर्टिफाइड स्माइल डिज़ाइनर के साथ अपॉइंटमेंट बुक करने में आपकी मदद करूँ?'\\n"
                f"• English: 'I understand you are experiencing {cn}, {display_name}. By the way, may I ask what you do for work? Would you like me to help book a consultation appointment with our USD Certified Smile Designer for this?'"
            )"""

if old_step_2_5 in cm_content:
    cm_content = cm_content.replace(old_step_2_5, new_step_2_5, 1)
    print("Updated step 2.5 in conversation_manager.py!")
else:
    print("Warning: old_step_2_5 not found in conversation_manager.py")

# Active memory profession rule
old_cm_mem = """        user_turn_count = len([h for h in (history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
        if getattr(self.session, "profession_asked", False):
            active_memory += (
                "\\n- 🚨 CRITICAL ONE-TIME PROFESSION RULE: The user's profession has ALREADY been asked or discussed! "
                "You are STRICTLY FORBIDDEN from asking 'what is your profession?' or 'what do you do for work?' again! "
                "Never ask about their profession again in this conversation."
            )
        elif user_turn_count < 3:
            active_memory += (
                "\\n- 🚨 STRICT BAN IN FIRST 3 MESSAGES: Do NOT ask about profession in the first 3 turns! "
                "The first 3 messages must focus purely on understanding their smile vision and answering their questions."
            )"""

new_cm_mem = """        user_turn_count = len([h for h in (history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
        if getattr(self.session, "profession_asked", False):
            active_memory += (
                "\\n- 🚨 CRITICAL ONE-TIME PROFESSION RULE: The user's profession has ALREADY been asked or discussed! "
                "You are STRICTLY FORBIDDEN from asking 'what is your profession?' or 'what do you do for work?' again! "
                "Never ask about their profession again in this conversation."
            )
        elif user_turn_count < 2:
            active_memory += (
                "\\n- 🚨 TIMING RULE FOR MESSAGES 1 & 2: Do NOT ask about profession in messages 1 and 2 (focus strictly on greeting, name confirmation, and initial concern). "
                "Starting from message 3, ask for their profession at least once in the conversation."
            )
        else:
            active_memory += (
                "\\n- 🌟 PROFESSION INQUIRY (MANDATORY AT LEAST ONCE IN CONVERSATION): "
                "If not asked yet, warmly ask the patient about their work/profession in this turn: "
                "('By the way, [Name], what do you do for work?' / 'તેમ છતાં, [Name], તમે શું કામ કરો છો?' / 'वैसे, [Name], आप क्या काम करते हैं?'). "
                "Remember: Once asked or provided, never repeat this question in future turns."
            )"""

if old_cm_mem in cm_content:
    cm_content = cm_content.replace(old_cm_mem, new_cm_mem, 1)
    print("Updated active memory profession rule in conversation_manager.py!")
else:
    print("Warning: old_cm_mem not found in conversation_manager.py")

# Regex profession guard in stream_chat_text_response
old_cm_guard = """        # 🚨 PROFESSION GUARD: Strip if already asked OR if within first 3 messages
        user_turn_count = len([h for h in (history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
        was_profession_already_asked = getattr(self.session, "profession_asked", False)
        prof_re_patterns = [
            r"(?:by the way,?\s+)?(?:what is your profession|what do you do for work|may i ask what profession you are in)\??",
            r"(?:તેમ છતાં,?\s*(?:જો હું પૂછી શકું,?\s*)?)?(?:તમે શું કામ કરો છો|તમારો વ્યવસાય શું છે|તમારો વ્યવસાય \(પ્રોફેશન\) શું છે)\??",
            r"(?:वैसे,?\s*(?:अगर मैं पूछ सकती हूँ,?\s*)?)?(?:आप क्या काम करते हैं|आपका पेशा या प्रोफेशन क्या है|आप किस प्रोफेशन में हैं)\??"
        ]
        if was_profession_already_asked or user_turn_count < 3:
            for pat in prof_re_patterns:
                clean_text = re.sub(pat, "", clean_text, flags=re.IGNORECASE).strip()
                full_text = re.sub(pat, "", full_text, flags=re.IGNORECASE).strip()
        else:
            for pat in prof_re_patterns:
                if re.search(pat, clean_text, flags=re.IGNORECASE):
                    self.session.profession_asked = True
                    break"""

new_cm_guard = """        # 🚨 PROFESSION GUARD: Strip if already asked OR if within first 2 messages (turns 1 & 2)
        user_turn_count = len([h for h in (history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
        was_profession_already_asked = getattr(self.session, "profession_asked", False)
        prof_re_patterns = [
            r"(?:by the way,?\s+)?(?:what is your profession|what do you do for work|may i ask what profession you are in|may i ask what you do for work)\??",
            r"(?:તેમ છતાં,?\s*(?:જો હું પૂછી શકું,?\s*)?)?(?:તમે શું કામ કરો છો|તમારો વ્યવસાય શું છે|તમારો વ્યવસાય \(પ્રોફેશન\) શું છે)\??",
            r"(?:वैसे,?\s*(?:अगर मैं पूछ सकती हूँ,?\s*)?)?(?:आप क्या काम करते हैं|आपका पेशा या प्रोफेशन क्या है|आप किस प्रोफेशन में हैं)\??"
        ]
        if was_profession_already_asked or user_turn_count < 2:
            for pat in prof_re_patterns:
                clean_text = re.sub(pat, "", clean_text, flags=re.IGNORECASE).strip()
                full_text = re.sub(pat, "", full_text, flags=re.IGNORECASE).strip()
        else:
            for pat in prof_re_patterns:
                if re.search(pat, clean_text, flags=re.IGNORECASE):
                    self.session.profession_asked = True
                    break"""

if old_cm_guard in cm_content:
    cm_content = cm_content.replace(old_cm_guard, new_cm_guard, 1)
    print("Updated profession guard in conversation_manager.py!")
else:
    print("Warning: old_cm_guard not found in conversation_manager.py")

with open(cm_path, "w", encoding="utf-8") as f:
    f.write(cm_content)


# 4. Update gemini/client.py
client_path = r"d:\media\voice_agent\gemini\client.py"
with open(client_path, "r", encoding="utf-8") as f:
    client_content = f.read()

old_client_guard = """                    # 🚨 PROFESSION GUARD: Strip if already asked OR if within first 3 messages
                    user_turn_count = len([h for h in (self.session.latest_client_history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
                    was_prof_already_asked = getattr(self.session, "profession_asked", False)
                    prof_re_patterns = [
                        r"(?:by the way,?\s+)?(?:what is your profession|what do you do for work|may i ask what profession you are in)\??",
                        r"(?:તેમ છતાં,?\s*(?:જો હું પૂછી શકું,?\s*)?)?(?:તમે શું કામ કરો છો|તમારો વ્યવસાય શું છે|તમારો વ્યવસાય \(પ્રોફેશન\) શું છે)\??",
                        r"(?:वैसे,?\s*(?:अगर मैं पूछ सकती हूँ,?\s*)?)?(?:आप क्या काम करते हैं|आपका पेशा या प्रोफेशन क्या है|आप किस प्रोफेशन में हैं)\??"
                    ]
                    if (was_prof_already_asked or user_turn_count < 3) and clean_text:
                        for pat in prof_re_patterns:
                            clean_text = re.sub(pat, "", clean_text, flags=re.IGNORECASE).strip()
                    elif clean_text:
                        for pat in prof_re_patterns:
                            if re.search(pat, clean_text, flags=re.IGNORECASE):
                                self.session.profession_asked = True
                                break"""

new_client_guard = """                    # 🚨 PROFESSION GUARD: Strip if already asked OR if within first 2 messages (turns 1 & 2)
                    user_turn_count = len([h for h in (self.session.latest_client_history or []) if isinstance(h, dict) and h.get("role") in ["user", "model", "assistant"]]) // 2
                    was_prof_already_asked = getattr(self.session, "profession_asked", False)
                    prof_re_patterns = [
                        r"(?:by the way,?\s+)?(?:what is your profession|what do you do for work|may i ask what profession you are in|may i ask what you do for work)\??",
                        r"(?:તેમ છતાં,?\s*(?:જો હું પૂછી શકું,?\s*)?)?(?:તમે શું કામ કરો છો|તમારો વ્યવસાય શું છે|તમારો વ્યવસાય \(પ્રોફેશન\) શું છે)\??",
                        r"(?:वैसे,?\s*(?:अगर मैं पूछ सकती हूँ,?\s*)?)?(?:आप क्या काम करते हैं|आपका पेशा या प्रोफेशन क्या है|आप किस प्रोफेशन में हैं)\??"
                    ]
                    if (was_prof_already_asked or user_turn_count < 2) and clean_text:
                        for pat in prof_re_patterns:
                            clean_text = re.sub(pat, "", clean_text, flags=re.IGNORECASE).strip()
                    elif clean_text:
                        for pat in prof_re_patterns:
                            if re.search(pat, clean_text, flags=re.IGNORECASE):
                                self.session.profession_asked = True
                                break"""

if old_client_guard in client_content:
    client_content = client_content.replace(old_client_guard, new_client_guard, 1)
    print("Updated profession guard in client.py!")
else:
    print("Warning: old_client_guard not found in client.py")

with open(client_path, "w", encoding="utf-8") as f:
    f.write(client_content)

print("All updates applied successfully!")
