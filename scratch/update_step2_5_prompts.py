# 1. conversation.md
conv_path = r"d:\media\voice_agent\prompts\conversation.md"
with open(conv_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

s_idx = None
e_idx = None
for i, line in enumerate(lines):
    if "Step 2.5. MANDATORY CONSULTATION PERMISSION GATE" in line:
        s_idx = i
    if s_idx is not None and "Step 3. City Confirmation" in line:
        e_idx = i
        break

if s_idx is not None and e_idx is not None:
    new_block = [
        "       Step 2.5. MANDATORY CONSULTATION PERMISSION GATE & PROFESSION INQUIRY (CRITICAL BEFORE STARTING BOOKING):\n",
        "              • When the patient shares their dental concern or smile goal (e.g. \"मुझे स्माइल डिजाइन करवानी है\", \"दांत में गैप है\", \"yellow teeth\"):\n",
        "                - DO NOT jump straight to asking City or Doctor!\n",
        "                - Empathetically acknowledge their concern/vision in their language, ask for their profession (if not already asked), AND ask if they would like help booking a consultation:\n",
        "                  - Hindi: \"मैं समझ सकती हूँ कि आपको [समस्या/स्माइલ ડિઝાઇન] की समस्या आ रही है, [Name]। वैसे, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं? क्या मैं इसके समाधान के लिए हमारे USD सर्टिफाइड स्माइल डिज़ाइनर के साथ आपकी कन्सल्टेशन अपॉइंटमेंट बुक करने में मदद करूँ?\"\n",
        "                  - Gujarati: \"હું સમજી શકું છું કે તમને [સમસ્યા/સ્માઇલ ડિઝાઇન]ની સમસ્યા છે, [Name]. તેમ છતાં, જો હું પૂછી શકું, તમે શું કામ કરો છો? શું હું આના માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું?\"\n",
        "                  - English: \"I understand you are experiencing [concern/smile design], [Name]. By the way, may I ask what you do for work? Would you like me to help book a consultation appointment with our USD Certified Smile Designer for this?\"\n",
        "                - 🚨 ABSOLUTE MANDATORY RULE: YOU MUST WAIT FOR THE PATIENT TO SAY YES / AGREE (\"Yes\" / \"Sure\" / \"Haan\" / \"Ha\" / \"Chokkas\" / \"Please do\" / \"करा दो\")!\n",
        "                  • IF USER SAYS YES / AGREES: Proceed directly to Step 3 (City)!\n",
        "                  • IF USER SAYS NO OR ASKS A QUESTION (e.g., \"how much does it cost?\", \"what are veneers?\"): DO NOT ask for City, Doctor, or Phone! Answer their questions helpfully as an expert AI Smile Consultant and converse naturally.\n"
    ]
    lines[s_idx:e_idx] = new_block
    with open(conv_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Updated Step 2.5 in conversation.md successfully!")

# 2. prompt_builder.py
pb_path = r"d:\media\voice_agent\ai\prompt_builder.py"
with open(pb_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

s_idx = None
e_idx = None
for i, line in enumerate(lines):
    if "Step 2.5. MANDATORY CONSULTATION PERMISSION GATE" in line:
        s_idx = i
    if s_idx is not None and "Step 3. City Confirmation" in line:
        e_idx = i
        break

if s_idx is not None and e_idx is not None:
    new_block = [
        "        Step 2.5. MANDATORY CONSULTATION PERMISSION GATE & PROFESSION INQUIRY (CRITICAL BEFORE STARTING BOOKING):\n",
        "                 • When the patient shares their dental concern or smile goal (e.g. \"मुझे स्माइल डिजाइन करवानी है\", \"दांतों में गैप है\", \"yellow teeth\"):\n",
        "                   - DO NOT jump straight to asking City or Phone!\n",
        "                   - Empathetically acknowledge their specific concern in their language, ask for their profession (if not already asked), AND ask if they would like help booking a consultation:\n",
        "                     - English: \"I understand you are experiencing [symptom/concern], [Name]. By the way, may I ask what you do for work? Would you like me to help book a consultation appointment with our USD Certified Smile Designer for this?\"\n",
        "                     - Gujarati: \"હું સમજી શકું છું કે તમને [symptom/સમસ્યા] છે, [Name]. તેમ છતાં, જો હું પૂછી શકું, તમે શું કામ કરો છો? શું હું આના ઉકેલ માટે અમારા USD સર્ટિફાઇડ સ્માઇલ ડિઝાઇનર સાથે કન્સલ્ટેશન અપૉઇન્ટમેન્ટ બુક કરવામાં મદદ કરું?\"\n",
        "                     - Hindi: \"मैं समझ सकती हूँ कि आपको [symptom/समस्या] आ रही है, [Name]। वैसे, अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं? क्या मैं इसके समाधान के लिए हमारे USD सर्टिफाइड स्माइल डिज़ाइनर के साथ अपॉइंटमेंट बुक करने में आपकी मदद करूँ?\"\n",
        "                   - 🚨 ABSOLUTE MANDATORY RULE: YOU MUST WAIT FOR THE PATIENT TO SAY YES / AGREE!\n",
        "                     DO NOT ask for City or Phone unless and until the patient explicitly agrees (\"Yes\" / \"Sure\" / \"Haan\" / \"Ha\" / \"Chokkas\" / \"Please do\" / \"करा दो\")!\n",
        "                     Once user agrees or if user initiated booking, NEVER RE-ASK THIS QUESTION!\n"
    ]
    lines[s_idx:e_idx] = new_block
    with open(pb_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("Updated Step 2.5 in prompt_builder.py successfully!")
