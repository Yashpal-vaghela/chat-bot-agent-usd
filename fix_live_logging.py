path = r'd:\media\voice_agent\ai\conversation_manager.py'
with open(path, 'r', encoding='utf-8') as f:
    code = f.read()

log_helper = '''def log_live_conversation(mode, user_text, bot_text, slots):
    import sys
    fn = slots.get('first_name') or '-'
    ln = slots.get('last_name') or '-'
    name_str = f"{fn} {ln}".strip() if ln != '-' else fn
    city_str = slots.get('city') or '-'
    doc_str = slots.get('doctor_name') or '-'
    msg_str = slots.get('message') or '-'
    phone_str = slots.get('phone') or '-'
    sub_str = "YES (Submitted to CRM)" if slots.get('is_submitted') else "No"

    sep = "=" * 70
    log_msg = (
        f"\\n{sep}\\n"
        f"⚡ [{mode.upper()}]\\n"
        f"👤 USER : {user_text}\\n"
        f"🤖 RIYA : {bot_text}\\n"
        f"📋 SLOTS: Name: {name_str} | City: {city_str} | Doctor: {doc_str} | Concern: {msg_str} | Phone: {phone_str} | Submitted: {sub_str}\\n"
        f"{sep}\\n"
    )
    print(log_msg, flush=True)
'''

if 'def log_live_conversation' not in code:
    code = log_helper + "\n" + code

# Call in stream_chat_text_response on reply_complete
old_chat_reply = '''        await self.send_json({
            "type": "reply_complete",
            "userText": user_text,
            "botText": clean_text or full_text,
            "tag": final_tag,
            "totalChunks": 1,
            "slots": dict(self.session.booking_slots),
            "userName": self.session.user_name,
            "userConcern": self.session.user_concern,
            "userCity": self.session.booking_slots.get("city"),
            "userDoctor": self.session.booking_slots.get("doctor_name"),
            "userPhone": self.session.booking_slots.get("phone")
        })'''

new_chat_reply = '''        log_live_conversation("Chat Mode", user_text, clean_text or full_text, dict(self.session.booking_slots))
        await self.send_json({
            "type": "reply_complete",
            "userText": user_text,
            "botText": clean_text or full_text,
            "tag": final_tag,
            "totalChunks": 1,
            "slots": dict(self.session.booking_slots),
            "userName": self.session.user_name,
            "userConcern": self.session.user_concern,
            "userCity": self.session.booking_slots.get("city"),
            "userDoctor": self.session.booking_slots.get("doctor_name"),
            "userPhone": self.session.booking_slots.get("phone")
        })'''

code = code.replace(old_chat_reply, new_chat_reply)

with open(path, 'w', encoding='utf-8') as f:
    f.write(code)

print("Updated conversation_manager.py with log_live_conversation!")
