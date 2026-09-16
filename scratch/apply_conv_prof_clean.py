path = r"d:\media\voice_agent\prompts\conversation.md"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines_block = [
    "     - 🚨 MANDATORY RULE — PROFESSION INQUIRY TIMING & AT LEAST ONCE IN CONVERSATION:\n",
    "       • 🚨 TIMING IN MESSAGES 1 & 2:\n",
    "         Do NOT ask \"What is your profession?\" or \"What do you do for work?\" in messages 1 and 2 (which focus strictly on greeting, name confirmation, and initial concern).\n",
    "       • MANDATORY AT LEAST ONCE IN WHOLE CONVERSATION (STARTING MESSAGE 3 / CONCERN STEP):\n",
    "         Riya MUST ask about the patient's work or profession at least once in the conversation (ideally in message 3 when acknowledging their dental concern or during smile exploration) in the user's active language:\n"
]

# Find index of line starting with "     - 🚨 ABSOLUTE MANDATORY RULE — PROFESSION INQUIRY TIMING"
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "PROFESSION INQUIRY TIMING" in line:
        start_idx = i
    if start_idx is not None and "English: \"By the way" in line:
        end_idx = i
        break

if start_idx is not None and end_idx is not None:
    lines[start_idx:end_idx] = new_lines_block
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Replaced lines in conversation.md successfully!")
else:
    print(f"Could not find markers: start={start_idx}, end={end_idx}")
