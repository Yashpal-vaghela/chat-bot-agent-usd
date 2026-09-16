import re

MULTILINGUAL_CITY_MAP = {
    # Gujarat
    "અમદાવાદ": "Ahmedabad", "ahmedabad": "Ahmedabad", "amdavad": "Ahmedabad",
    "સુરત": "Surat", "surat": "Surat",
    "વડોદરા": "Vadodara", "vadodara": "Vadodara", "baroda": "Vadodara",
    "રાજકોટ": "Rajkot", "rajkot": "Rajkot",
    "જામનગર": "Jamnagar", "jamnagar": "Jamnagar",
    "ભરૂચ": "Bharuch", "bharuch": "Bharuch",
    "હળવદ": "Halvad", "halvad": "Halvad",
    "ધ્રાંગધ્રા": "Dhrangadhra", "dhrangadhra": "Dhrangadhra",
    # India Metro & Others
    "મુંબઈ": "Mumbai", "मुंबई": "Mumbai", "mumbai": "Mumbai", "bombay": "Mumbai",
    "પુણે": "Pune", "पुणे": "Pune", "pune": "Pune",
    "delhi": "New Delhi", "new delhi": "New Delhi", "gurugram": "Gurugram", "gurgaon": "Gurugram",
    "bangalore": "Bangalore", "bengaluru": "Bangalore", "hyderabad": "Hyderabad", "chennai": "Chennai",
    "madras": "Chennai", "gwalior": "Gwalior", "indore": "Indore", "sangli": "Sangli",
    "guwahati": "Guwahati", "guntur": "Guntur", "faridkot": "Faridkot",
    "sri ganganagar": "Sri Ganganagar", "ganganagar": "Sri Ganganagar", "malda": "Malda"
}

ALL_CERTIFIED_DOCTORS_LIST = [
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
    "Dr. Adil Lyngdoh", "Dr. Asmita Sodhi", "Dr. Neetu Jindal", "Dr. A K Saha"
]

def extract_slots_from_review_summary(text: str) -> dict:
    """Extracts all 5 structured appointment booking slots from a bot review summary message across all 11 languages."""
    if not text:
        return {}
    extracted = {}

    STOP_DELIM = r"(?=\s*[-•*]\s*(?:નામ|Name|नाम|नाव|নাম|பெயர்|పేరు|ಹೆಸರು|പേര്|ਨਾਮ|ਨਾਮ|ફોન|Phone|मोबाइल|Mobile|ফোন|தொலைபேசி|ఫోన్|ಫೋನ್|ਫ਼ੋਨ|ଫୋନ୍|શહેર|City|शहर|ಶহর|நகரம்|నగరం|ನಗರ|നഗരം|ਸ਼ਹਿਰ|ସହର|ડૉક્ટર|Doctor|डॉक्टर|ডাক্তার|மருத்துவர்|డాక్టర్|ವೈದ್ಯರು|ਡਾਕਟਰ|ଡାକ୍ତର|સમસ્યા|Concern|Problem|Issue|समस्या|সমস্যা|பிரச்சனை|సమస్య|ಸಮಸ್ಯೆ|ಪ್ರಶ್ನೆ|ਸਮੱਸਿਆ|ସମସ୍ୟା)|(?:\n|$)|\s*(?:કૃપા કરીને|Please|कृपया|దయచేసి|ದಯವಿಟ್ಟು|தயவுசெய்து|ದಯಮಾಡಿ|దయచేసి))"

    # 1. Name: (e.g. - નામ: Rehmat Mohan / - Name: John Doe / - ಹೆಸರು: ...)
    m_name = re.search(r"[-•*]?\s*(?:નામ|Name|नाम|नाव|নাম|பெயர்|పేరు|ಹೆಸರು|പേര്|ਨਾਮ|ਨਾਮ)\s*[:：\-]\s*(.*?)" + STOP_DELIM, text, re.IGNORECASE)
    if m_name:
        cand_name = re.sub(r"[*_`]", "", m_name.group(1)).strip()
        parts = cand_name.split()
        if parts:
            f_cand = parts[0].strip().capitalize()
            l_cand = " ".join(parts[1:]).strip().capitalize() if len(parts) > 1 else ""
            extracted["first_name"] = f_cand
            extracted["last_name"] = l_cand if l_cand else "-"
            extracted["user_name"] = f"{f_cand} {l_cand}".strip() if l_cand else f_cand
            
    # 2. Phone: (e.g. - ફોન: 1122334455)
    m_ph = re.search(r"[-•*]?\s*(?:ફોન|Phone|मोबाइल|Mobile|ফোন|தொலைபேசி|ఫోన్|ಫೋನ್|ਫ਼ੋਨ|ଫୋନ୍)\s*[:：\-]\s*(.*?)" + STOP_DELIM, text, re.IGNORECASE)
    if m_ph:
        raw_ph = re.sub(r"[*_`]", "", m_ph.group(1)).strip()
        digits = "".join(filter(str.isdigit, raw_ph))
        if len(digits) >= 10:
            extracted["phone"] = digits[-10:]
            
    # 3. City: (e.g. - શહેર: સુરત)
    m_city = re.search(r"[-•*]?\s*(?:શહેર|City|शहर|ಶহর|நகரம்|నగరం|ನಗರ|നഗരം|ਸ਼ਹਿਰ|ସହର)\s*[:：\-]\s*(.*?)" + STOP_DELIM, text, re.IGNORECASE)
    if m_city:
        raw_city = re.sub(r"[*_`]", "", m_city.group(1)).strip()
        tl = raw_city.lower()
        for k, standard_name in MULTILINGUAL_CITY_MAP.items():
            if k in raw_city or (k.isascii() and re.search(r"\b" + re.escape(k) + r"\b", tl)):
                extracted["city"] = standard_name
                break
        if not extracted.get("city") and len(raw_city) >= 3 and raw_city.lower() not in ["none", "null", "-", "--"]:
            extracted["city"] = raw_city.title()
            
    # 4. Doctor: (e.g. - ડૉક્ટર: Dr. Viren K Savani)
    m_doc = re.search(r"[-•*]?\s*(?:ડૉક્ટર|Doctor|डॉक्टर|ডাক্তার|மருத்துவர்|డాక్టర్|ವೈದ್ಯರು|ਡਾਕਟਰ|ଡାକ୍ତର)\s*[:：\-]\s*(.*?)" + STOP_DELIM, text, re.IGNORECASE)
    if m_doc:
        raw_doc = re.sub(r"[*_`]", "", m_doc.group(1)).strip()
        raw_doc_clean = re.sub(r"^dr\.?\s*", "", raw_doc, flags=re.IGNORECASE).strip().lower()
        for doc in ALL_CERTIFIED_DOCTORS_LIST:
            doc_clean = re.sub(r"^dr\.?\s*", "", doc, flags=re.IGNORECASE).strip().lower()
            if doc_clean == raw_doc_clean or doc_clean in raw_doc_clean or raw_doc_clean in doc_clean:
                extracted["doctor_name"] = doc
                break
        if not extracted.get("doctor_name") and len(raw_doc) >= 4 and raw_doc.lower() not in ["none", "null", "-", "--"]:
            extracted["doctor_name"] = raw_doc if raw_doc.lower().startswith("dr") else f"Dr. {raw_doc}"
            
    # 5. Concern / Message: (e.g. - સમસ્યા: Smile Makeover)
    m_concern = re.search(r"[-•*]?\s*(?:સમસ્યા|Concern|Problem|Issue|समस्या|সমস্যা|பிரச்சனை|సమస్య|ಸಮಸ್ಯೆ|ಪ್ರಶ್ನೆ|ਪ੍ਰੇਸ਼ਾਨੀ|ਸਮੱਸਿਆ|ସମସ୍ୟା)\s*[:：\-]\s*(.*?)" + STOP_DELIM, text, re.IGNORECASE)
    if m_concern:
        raw_concern = re.sub(r"[*_`]", "", m_concern.group(1)).strip()
        if len(raw_concern) >= 2 and raw_concern.lower() not in ["none", "null", "not provided", "-", "--"]:
            extracted["message"] = raw_concern
            extracted["user_concern"] = raw_concern
            
    return extracted

sample_gu = """આભાર! તમારી બધી વિગતો નોંધી લીધી છે: - નામ: Rehmat Mohan - ફોન: 1122334455 - શહેર: સુરત - સમસ્યા: Smile Makeover - ડૉક્ટર: Dr. Viren K Savani કૃપા કરીને આ અપૉઇન્ટમેન્ટ રિક્વેસ્ટ મોકલવા માટે 'submit' લખો અથવા કહો."""
sample_kn = """ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಎಲ್ಲಾ ವಿವರಗಳನ್ನು ದಾಖಲಿಸಲಾಗಿದೆ: - ಹೆಸರು: Praful Nil pankaj - ಫೋನ್: 1234567890 - ನಗರ: Rajkot - ಸಮಸ್ಯೆ: smile makeover and design - ವೈದ್ಯರು: Dr. Pagisha Sojitra ದಯವಿಟ್ಟು ಈ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ವಿನಂತಿಯನ್ನು ಕಳುಹಿಸಲು 'submit' ಎಂದು ಬರೆಯಿರಿ ಅಥವಾ ಹೇಳಿ."""

print("GU Result:", extract_slots_from_review_summary(sample_gu))
print("KN Result:", extract_slots_from_review_summary(sample_kn))
