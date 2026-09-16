path = r'd:\media\voice_agent\ai\conversation_manager.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if '# If doctor is confirmed but city is missing, infer city from doctor' in line:
        new_lines.append('        # Check and enforce Doctor-City consistency\n')
        new_lines.append('        h_doc = self.session.booking_slots.get("doctor_name")\n')
        new_lines.append('        h_city = self.session.booking_slots.get("city")\n')
        new_lines.append('        if h_doc:\n')
        new_lines.append('            doc_h_city = get_city_for_doctor(h_doc)\n')
        new_lines.append('            if doc_h_city:\n')
        new_lines.append('                if not h_city:\n')
        new_lines.append('                    self.session.booking_slots["city"] = doc_h_city\n')
        new_lines.append('                elif h_city.lower() != doc_h_city.lower():\n')
        new_lines.append('                    self.session.city_doctor_mismatch = {\n')
        new_lines.append('                        "doctor": h_doc,\n')
        new_lines.append('                        "doctor_city": doc_h_city,\n')
        new_lines.append('                        "user_city": h_city\n')
        new_lines.append('                    }\n')
        new_lines.append('                    self.session.booking_slots["doctor_name"] = ""\n')
        # Skip the next 4 lines of original
        continue
    elif 'if self.session.booking_slots.get("doctor_name") and not self.session.booking_slots.get("city"):' in line:
        continue
    elif 'doc_city = get_city_for_doctor(self.session.booking_slots["doctor_name"])' in line and 'if doc_city:' in lines[i+1]:
        continue
    elif 'if doc_city:' in line and 'self.session.booking_slots["city"] = doc_city' in lines[i+1]:
        continue
    elif 'self.session.booking_slots["city"] = doc_city' in line and i > 670 and i < 685:
        continue

    # Update doctor matching in user_text
    elif 'doc_exact = find_doctor_in_text(text, self.session.booking_slots.get("city"))' in line:
        new_lines.append('                doc_exact = find_doctor_in_text(text, self.session.booking_slots.get("city"))\n')
        new_lines.append('                if doc_exact:\n')
        new_lines.append('                    doc_home_city = get_city_for_doctor(doc_exact)\n')
        new_lines.append('                    cur_city = self.session.booking_slots.get("city")\n')
        new_lines.append('                    if cur_city and doc_home_city and cur_city.lower() != doc_home_city.lower():\n')
        new_lines.append('                        self.session.city_doctor_mismatch = {\n')
        new_lines.append('                            "doctor": doc_exact,\n')
        new_lines.append('                            "doctor_city": doc_home_city,\n')
        new_lines.append('                            "user_city": cur_city\n')
        new_lines.append('                        }\n')
        new_lines.append('                        self.session.booking_slots["doctor_name"] = ""\n')
        new_lines.append('                        self.session.pending_doctor_candidate = None\n')
        new_lines.append('                        self.session.last_uncertified_doctor = None\n')
        new_lines.append('                    else:\n')
        new_lines.append('                        self.session.booking_slots["doctor_name"] = doc_exact\n')
        new_lines.append('                        self.session.city_doctor_mismatch = None\n')
        new_lines.append('                        self.session.pending_doctor_candidate = None\n')
        new_lines.append('                        self.session.last_uncertified_doctor = None\n')
        new_lines.append('                        if doc_home_city and not cur_city:\n')
        new_lines.append('                            self.session.booking_slots["city"] = doc_home_city\n')
        continue
    elif 'if doc_exact:' in line and 'self.session.booking_slots["doctor_name"] = doc_exact' in lines[i+1]:
        continue
    elif 'self.session.booking_slots["doctor_name"] = doc_exact' in line and i > 720 and i < 740:
        continue
    elif 'self.session.pending_doctor_candidate = None' in line and i > 720 and i < 740:
        continue
    elif 'self.session.last_uncertified_doctor = None' in line and i > 720 and i < 740:
        continue
    elif 'doc_city = get_city_for_doctor(doc_exact)' in line and i > 720 and i < 740:
        continue
    elif 'if doc_city and not self.session.booking_slots.get("city"):' in line and i > 720 and i < 740:
        continue
    elif 'self.session.booking_slots["city"] = doc_city' in line and i > 720 and i < 740:
        continue
        
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Doctor-City consistency successfully applied!")
