import sys
import os
import re

sys.stdout.reconfigure(encoding='utf-8')

def test_pattern():
    p = 'aur naam Amit bhai se'
    pattern = r"(?:my name is|my full name is|myself|call me|i am|i'm|this is|મારું નામ|મારુ નામ|મારો નામ|મારી નામ|(?:maru|maro|maaru|mari|mera|meri|apna|majhe|amar|aur|or|hamara|and)\s+(?:naam|nam|name|naav|nav|नाव|નામ|नाम)|maru naam|maro naam|maru nam|maro nam|नाम|मेरा नाम|mera naam|mera nam|नाव|माझे नाव|majhe nav|নাম|আমার নাম|amar naam|பெயர்|என் பெயர்|en peyar|పేరు|నా పేరు|naa peru|ಹೆસರು|ನನ್ನ ಹೆಸರು|nanna hesaru|പേര്|എന്റെ പേര്|ente peru|ਨਾਮ|ਮੇਰਾ ਨਾਮ|mera naa|ਨਾਮ|ਮੋરા ਨਾਮ|mora nama)\s*[:：\-]?\s*([A-Za-z\u0A80-\u0AFF\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F\u0C80-\u0CFF\u0D00-\u0D7F\u0A00-\u0A7F\u0B00-\u0B7F\s]{2,60})"
    m = re.search(pattern, p, re.I)
    assert m, "Pattern did not match!"
    print("Matched group 1:", m.group(1))

    cand_full = m.group(1).strip()
    cand_full = re.split(r"[\-\–\—\n,|!?।.;:\(\)\[\]]", cand_full)[0].strip()
    cand_full = re.sub(r"\s+(?:chhe|che|hai|hain|hoon|hu|is|am|are|se|te|thi|hूँ|છે|છુ|છીએ|હું|હે|તો|પણ|સે|તે|થી|and|yes|no|है|हूँ|हैं|हो|था|थी|थे|હતો|હતી|હતા)\b.*$", "", cand_full, flags=re.I).strip()
    parts = cand_full.split()
    stop_verbs = ["se", "to", "bhi", "hai", "hain", "hoon", "hu", "chhe", "che", "is", "am", "are", "છે", "છુ", "છીએ", "હું", "હે", "તો", "પણ", "है", "हूँ", "हैं", "हो", "था", "थी", "थे", "સે", "તે"]
    parts = [p_w for p_w in parts if p_w.lower() not in stop_verbs]
    raw_fn = parts[0].strip()
    raw_ln = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    print(f"Result: fn='{raw_fn}', ln='{raw_ln}'")

if __name__ == "__main__":
    test_pattern()
