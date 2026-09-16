import re

def is_affirmative_submit(text):
    tl = text.lower().strip()
    tl = re.sub(r'[\s.,!?\\/]+$', '', tl)
    short_affirms = [
        "submit", "yes", "yea", "yep", "yeah", "ok", "okay", "sure", "done", "please do", "confirm", "proceed",
        "haan", "ha", "haa", "ha ji", "haan ji", "kar do", "kardo", "kari do", "kari dyo", "kar dyo", "haa kari dyo",
        "yes submit", "chalega", "thik chhe", "theek hai", "bhaley", "chokkas", "zarur", "zaroor", "submit karo", "submit kar do", "submit kari dyo"
    ]
    if tl in short_affirms:
        return f"EXACT MATCH: '{tl}'"
    edit_words = ["change", "update", "edit", "instead", "no my", "no, my", "spelling", "mistake"]
    if any(ew in tl for ew in edit_words):
        return False
    for phrase in [
        "submit", "confirm", "book", "kari dyo", "kari do", "kar do", "kardo", "submitt",
        "mari booking", "મારી બુકિંગ", "મારી અપૉઇન્ટમેન્ટ", "मेरी बुकिंग"
    ]:
        if phrase in tl:
            return f"SUBSTRING MATCH: '{phrase}'"
    return False

def is_cancel_submit(text):
    tl = text.lower().strip()
    tl = re.sub(r'[\s.,!?\\/]+$', '', tl)
    cancel_keywords = [
        "cancel", "abort", "stop booking", "stop appointment",
        "cancel karvi", "cancel karvu", "cancel karo", "cancel kar do", "cancel kardo", "cancel karna"
    ]
    for kw in cancel_keywords:
        if kw in tl:
            return f"CANCEL MATCH: '{kw}'"
    return False

texts = [
    "oh nice its that much fast ?",
    "okay thanks can you explain me how your dentist is speccial ?",
    "i want to know and i m talking to you in english btw i want to know how your smile desaigner is speccial thenmy smile dentist",
    "english"
]

for t in texts:
    print(f"Text: '{t}'")
    print("  is_affirmative:", is_affirmative_submit(t))
    print("  is_cancel:", is_cancel_submit(t))
