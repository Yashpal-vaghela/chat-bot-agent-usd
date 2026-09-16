import re

cm_path = r"d:\media\voice_agent\ai\conversation_manager.py"
with open(cm_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update top imports
old_top_import = 'from voice_agent.utils.helpers import clean_assistant_text, clean_hallucinations, extract_slots_from_review_summary, is_submit_review_summary, transliterate_to_english, strip_diacritics, ALL_CERTIFIED_DOCTORS_LIST, is_cancel_submit, is_explicit_submit_command, is_affirmative_submit, is_cancel_response_text, is_submit_response_text'
new_top_import = 'from voice_agent.utils.helpers import clean_assistant_text, clean_hallucinations, extract_slots_from_review_summary, is_submit_review_summary, transliterate_to_english, strip_diacritics, ALL_CERTIFIED_DOCTORS_LIST, DOCTOR_HOME_CITIES, MULTILINGUAL_CITY_MAP, is_cancel_submit, is_explicit_submit_command, is_affirmative_submit, is_cancel_response_text, is_submit_response_text'

if old_top_import in content:
    content = content.replace(old_top_import, new_top_import, 1)
    print("Updated top import!")
else:
    print("Warning: old_top_import not found directly")

# 2. Remove line 128 import
content = re.sub(r'from voice_agent\.utils\.helpers import MULTILINGUAL_CITY_MAP[^\n]*\n', '', content)

# 3. Remove local def is_affirmative_submit in update_session_memory
local_def_pattern = r'        def is_affirmative_submit\(text\):[\s\S]*?            return False\n\n'
if re.search(local_def_pattern, content):
    content = re.sub(local_def_pattern, '', content, count=1)
    print("Removed local def is_affirmative_submit!")
else:
    print("Warning: local def is_affirmative_submit not found")

# 4. Remove local import at line 1583
content = content.replace('                from voice_agent.gemini.client import is_affirmative_submit\n', '')

# 5. Remove local import at line 1843
content = re.sub(r'            from voice_agent\.utils\.helpers import DOCTOR_HOME_CITIES[^\n]*\n', '', content)

with open(cm_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Saved updated conversation_manager.py successfully!")
