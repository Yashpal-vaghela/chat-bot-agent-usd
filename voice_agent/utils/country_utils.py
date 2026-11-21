"""Country, postal-code and mobile-number rules for international bookings."""
import re
import unicodedata
from functools import lru_cache
from urllib.parse import quote

import httpx
import phonenumbers
from i18naddress import get_validation_rules
from phonenumbers import PhoneMetadata, PhoneNumberType

from voice_agent.utils.country_data import ALL_COUNTRIES


# Spoken / typed names -> ISO code. Cities are included because callers often answer "Dubai" or "London".
COUNTRY_ALIASES = {
    "IN": ["india", "bharat", "hindustan", "भारत", "इंडिया", "हिंदुस्तान", "ભારત", "ઇન્ડિયા", "इंडिया", "ভারত", "இந்தியா", "భారత్", "భారతదేశం", "ಭಾರತ", "ഇന്ത്യ", "ਭਾਰਤ", "ଭାରତ"],
    "AE": ["uae", "u a e", "united arab emirates", "emirates", "dubai", "abu dhabi", "sharjah", "ajman", "दुबई", "દુબઈ", "દુબઇ", "यूएई", "અબુ ધાબી"],
    "US": ["usa", "u s a", "us", "united states", "america", "new york", "new jersey", "california", "texas", "chicago", "amerika", "अमेरिका", "અમેરિકા", "યુએસએ"],
    "GB": ["uk", "u k", "united kingdom", "england", "britain", "great britain", "london", "scotland", "wales", "leicester", "birmingham", "manchester", "लंदन", "લંડન", "इंग्लैंड", "ઇંગ્લેન્ડ"],
    "CA": ["canada", "toronto", "vancouver", "brampton", "mississauga", "montreal", "calgary", "कनाडा", "કેનેડા"],
    "AU": ["australia", "austrelia", "austrellia", "sydney", "melbourne", "brisbane", "perth", "ऑस्ट्रेलिया", "ઓસ્ટ્રેલિયા"],
    "SA": ["saudi", "saudi arabia", "ksa", "riyadh", "jeddah", "dammam", "सऊदी", "સાઉદી"],
    "OM": ["oman", "muscat", "ओमान", "ઓમાન"],
    "QA": ["qatar", "doha", "कतर", "કતાર"],
    "KW": ["kuwait", "कुवैत", "કુવૈત"],
    "BH": ["bahrain", "manama", "बहरीन", "બહેરીન"],
    "SG": ["singapore", "सिंगापुर", "સિંગાપોર"],
    "DE": ["germany", "deutschland", "berlin", "munich", "frankfurt", "जर्मनी", "જર્મની"],
    "FR": ["france", "paris", "फ्रांस", "ફ્રાન્સ"],
    "NP": ["nepal", "kathmandu", "नेपाल", "નેપાળ"],
    "BD": ["bangladesh", "dhaka", "बांग्लादेश", "বাংলাদেশ"],
    "PK": ["pakistan", "karachi", "lahore", "पाकिस्तान"],
    "LK": ["sri lanka", "srilanka", "colombo", "श्रीलंका"],
    "MY": ["malaysia", "kuala lumpur", "मलेशिया"],
    "IT": ["italy", "rome", "milan", "इटली"],
    "ES": ["spain", "madrid", "barcelona", "स्पेन"],
    "NL": ["netherlands", "holland", "amsterdam", "नीदरलैंड"],
    "JP": ["japan", "tokyo", "जापान"],
    "CN": ["china", "beijing", "shanghai", "चीन"],
    "NZ": ["new zealand", "auckland", "न्यूजीलैंड", "ન્યુઝીલેન્ડ"],
    "KE": ["kenya", "nairobi", "केन्या", "કેન્યા"],
    "ZA": ["south africa", "johannesburg", "durban", "cape town", "दक्षिण अफ्रीका"],
    "HK": ["hong kong", "hongkong"],
    "IE": ["ireland", "dublin", "आयरलैंड"],
}

# Every other country of the world: name, dial code and spoken names from the full table
for _iso, (_dial, _name, _extra) in ALL_COUNTRIES.items():
    _al = COUNTRY_ALIASES.setdefault(_iso, [])
    for _a in [_name.lower()] + [e.lower() for e in _extra]:
        if _a not in _al:
            _al.append(_a)

# NOTE: restcountries.com v1-v4 (incl. the v3.1 URL in static country_utils.js) is shut down; v5 needs an account +
# API key. The built-in table in country_data.py covers every country, so no country API is called at runtime.

# Ambiguous 2-letter aliases ("us" = the pronoun) only count when the whole answer is that word
_STRICT_ALIASES = {"us", "uk", "uae", "usa", "ksa"}


def _ascii_digits(text):
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in str(text or ""))


def resolve_country(text, fuzzy=False):
    """ISO code of the country named in `text`, or None. Longest alias wins ('south africa' over 'africa')."""
    if not text:
        return None
    iso = str(text).strip()
    if iso in ALL_COUNTRIES:
        return iso
    # Only ASCII punctuation is removed: Indic vowel signs are not \w and must stay ('ભારત', 'दुबई')
    low = " " + re.sub(r"[!-/:-@\[-`{-~।]", " ", str(text).lower()) + " "
    low = re.sub(r"\s+", " ", low)
    stripped = low.strip()
    best, best_len = None, 0
    for code, aliases in COUNTRY_ALIASES.items():
        for a in aliases:
            if a in _STRICT_ALIASES:
                hit = stripped == a or stripped in (f"in {a}", f"i am in {a}", f"i live in {a}", f"from {a}")
            elif a.isascii():
                hit = f" {a} " in low
            else:
                hit = a in low
            if hit and len(a) > best_len:
                best, best_len = code, len(a)
    if best or not fuzzy:
        return best
    # Misspelt / mis-transcribed names ('austrelia', 'austrellia', 'canda', 'singapor'). Only used when the
    # patient is answering the country question, and only for words of 5+ letters ('pain' must never become Spain).
    import difflib
    words = [w for w in stripped.split() if w.isascii() and w.isalpha()]
    cands = [w for w in words if len(w) >= 5] + [f"{a} {b}" for a, b in zip(words, words[1:])]
    lookup = {a: code for code, aliases in COUNTRY_ALIASES.items() for a in aliases if a.isascii() and len(a) >= 5}
    for c in cands:
        m = difflib.get_close_matches(c, lookup.keys(), n=1, cutoff=0.8)
        if m:
            return lookup[m[0]]
    return None


def country_name(code):
    code = (code or "IN").upper()
    return ALL_COUNTRIES.get(code, ("", code, []))[1]


def dial_code(code):
    code = (code or "IN").upper()
    calling_code = phonenumbers.country_code_for_region(code)
    return f"+{calling_code}" if calling_code else ""


@lru_cache(maxsize=None)
def _postal_rule(code):
    return get_validation_rules({"country_code": code})


def has_postal_code(code):
    return "postal_code" in _postal_rule((code or "IN").upper()).allowed_fields


def postal_hint(code, include_example=True):
    if code == "BR":
        return "8-digit CEP" if include_example else "CEP"
    rule = _postal_rule(code.upper())
    label = {"zip": "ZIP code", "eircode": "Eircode"}.get(rule.postal_code_type, "postal code")
    if code in {"GB", "AU", "NZ"}:
        label = "postcode"
    if not include_example:
        return label
    if code == "US":
        return "5-digit ZIP code"
    if rule.postal_code_matchers:
        pattern = rule.postal_code_matchers[0].pattern
        digits = re.fullmatch(r"\^\\d\{(\d+)\}\$", pattern)
        if digits:
            return f"{digits[1]}-digit {label}"
    if rule.postal_code_examples:
        return f"{label} (e.g. {rule.postal_code_examples[0]})"
    return label


def phone_digits_hint(code):
    metadata = PhoneMetadata.metadata_for_region((code or "IN").upper())
    lengths = [length for length in metadata.mobile.possible_length if length > 0] if metadata else []
    if not lengths:
        return ""
    if len(lengths) == 1:
        return str(lengths[0])
    if lengths == list(range(lengths[0], lengths[-1] + 1)):
        return f"{lengths[0]} to {lengths[-1]}"
    return ", ".join(map(str, lengths[:-1])) + f" or {lengths[-1]}"


_PHONE_INPUT = re.compile(r"(?<!\w)(?:\+\s*|\()?\d(?:[\d\s().-]*\d)?(?!\w)")


def normalize_phone(raw, code):
    """Return the national significant number if it is a mobile in the selected region."""
    code = (code or "IN").upper()
    text = _ascii_digits(raw)
    if code == "IN":
        from voice_agent.utils.helpers import normalize_mobile
        return normalize_mobile(text)

    # Accept a number in a sentence, but never splice separate numbers together.
    matches = _PHONE_INPUT.findall(text)
    if len(matches) != 1 or len(re.sub(r"\D", "", text)) != len(re.sub(r"\D", "", matches[0])):
        return None
    number = matches[0]
    if "+" in text and not number.startswith("+"):
        return None
    if number.startswith("00"):
        number = "+" + number[2:]
    try:
        parsed = phonenumbers.parse(number, code)
    except phonenumbers.NumberParseException:
        return None
    if not phonenumbers.is_valid_number_for_region(parsed, code):
        return None
    if phonenumbers.number_type(parsed) not in (PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE):
        return None
    return phonenumbers.national_significant_number(parsed)


def format_e164(national, code):
    """Format the validated national number for the CRM."""
    return f"{dial_code(code)}{national}" if national else ""


def format_phone_for_display(phone, country_code=None):
    """Separate the calling code using the number itself, including on older records."""
    value = str(phone or "").strip()
    if country_code == "IN" and re.fullmatch(r"[0-9]{10}", value):
        return f"+91 {value}"
    if not re.fullmatch(r"\+[0-9 ]+", value):
        return value
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException:
        return value
    if not phonenumbers.is_possible_number(parsed):
        return value
    return f"+{parsed.country_code} {phonenumbers.national_significant_number(parsed)}"


def validate_postal(raw, code):
    """Return the full postal code in a format accepted by the selected country's rules."""
    code = (code or "IN").upper()
    val = " ".join(_ascii_digits(raw).strip().upper().split())
    if code == "IN":
        return val if re.fullmatch(r"[1-9]\d{5}", val) else None
    rule = _postal_rule(code)
    if "postal_code" not in rule.allowed_fields or not val or not re.search(r"\d", val):
        return None
    if not rule.postal_code_matchers:
        return val if re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{1,11}", val) else None
    compact = val.replace(" ", "")
    if not re.fullmatch(r"[A-Z0-9]+", compact):
        compact = val
    options = [val, compact]
    if compact.isalnum():
        for example in rule.postal_code_examples[:1]:
            if len(re.sub(r"[^A-Z0-9]", "", example.upper())) == len(compact):
                chars = iter(compact)
                options.append("".join(next(chars) if char.isalnum() else char for char in example))
    return next((option for option in options if rule.postal_code_matchers[0].fullmatch(option)), None)


_POSTAL_LABEL = re.compile(
    r"^.*?\b(?:postal\s*code|post\s*code|pin\s*code|zip(?:\s*code)?|eircode)"
    r"\s*(?:is\b\s*)?[:=]?\s*|^.*?(?:પિનકોડ|पिन\s*कोड)\s*[:=]?\s*",
    re.IGNORECASE,
)


def extract_postal(text, code):
    """Extract a complete postal-code answer, including a spoken label or grouped digits."""
    answer = _ascii_digits(text).strip(" \t.,!?")
    if code == "BR":
        answer = re.sub(r"^(?:meu |my )?CEP\b\s*(?:(?:é|is)\s+)?[:=]?\s*", "", answer, flags=re.I)
    postal = validate_postal(answer, code)
    if postal:
        return postal
    value = _POSTAL_LABEL.sub("", answer, count=1)
    value = re.sub(r"^(?:it is|it's|that is)\s+", "", value, flags=re.IGNORECASE)
    return validate_postal(value, code)


def _postal_key(postal):
    return re.sub(r"[\s-]", "", str(postal or "")).upper()


def missing_brazil_cep(slots):
    return slots.get("country_code") == "BR" and not validate_postal(slots.get("pincode"), "BR")


def lookup_postal_places(postal, code, timeout=4.0):
    """Return distinct localities for an exact postal code within the selected country."""
    code = (code or "").upper()
    postal = validate_postal(postal, code) if code and code != "IN" else None
    if not postal:
        return ()
    key = (code, _postal_key(postal))
    if key in _POSTAL_CITY_CACHE:
        return _POSTAL_CITY_CACHE[key]

    with httpx.Client(timeout=timeout, headers={"User-Agent": "usd-booking-assistant/1.0"}) as client:
        places = ()
        if code == "BR":
            city = _viacep_city(client, key[1])
            places = (city,) if city else ()
        elif code == "MX":
            places = _sepomex_places(client, postal)
        if not places:
            places, postal_area_only = _nominatim_places(client, postal, code)
            # A postal area's center can sit in one town even when several towns use the code.
            if not places or (postal_area_only and len(places) == 1):
                places = _zippopotam_places(client, postal, code) or places
    if places:
        _POSTAL_CITY_CACHE[key] = places
    return places


def lookup_postal_city(postal, code, timeout=4.0):
    """Single-city callers can only use an unambiguous result."""
    places = lookup_postal_places(postal, code, timeout)
    return places[0] if len(places) == 1 else ""


def locality_key(name):
    folded = unicodedata.normalize("NFKD", name.casefold())
    return " ".join("".join(c for c in folded if not unicodedata.combining(c)).split())


def _distinct_places(names):
    places = {}
    for name in names:
        if isinstance(name, str) and name.strip():
            name = re.sub(r"\s+(?:governorate|metropolitan city|city council|(?:city )?municipality)$",
                          "", name.strip(), flags=re.IGNORECASE)
            places.setdefault(locality_key(name), name)
    return tuple(places.values())


def _sepomex_places(client, postal):
    # The Mexico-only catalog distinguishes colonias from their city or municipality.
    def fetch_page(page):
        response = client.get("https://sepomex.kurenn.dev/api/v1/zip_codes",
                              params={"zip_code": postal, "per_page": 200, "page": page})
        response.raise_for_status()
        return response.json()

    try:
        data = fetch_page(1)
        rows = data["zip_codes"]
        for page in range(2, data["meta"]["pagination"]["total_pages"] + 1):
            rows.extend(fetch_page(page)["zip_codes"])
        return _distinct_places(
            row.get("d_ciudad") or row.get("d_mnpio")
            for row in rows if row.get("d_codigo") == postal
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return ()


def _viacep_city(client, digits):
    try:
        response = client.get(f"https://viacep.com.br/ws/{digits}/json/")
        response.raise_for_status()
        data = response.json()
        if not data.get("erro") and _postal_key(data.get("cep")) == digits:
            return (data.get("localidade") or "").strip()
    except (httpx.HTTPError, ValueError, AttributeError):
        pass
    return ""


def _nominatim_places(client, postal, code):
    try:
        response = client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"postalcode": postal, "countrycodes": code.lower(), "format": "jsonv2",
                    "addressdetails": 1, "limit": 5, "accept-language": "en"},
        )
        response.raise_for_status()
        names = []
        postal_area_only = True
        for result in response.json():
            address = result.get("address") or {}
            if address.get("country_code", "").upper() != code:
                continue
            if _postal_key(address.get("postcode")) != _postal_key(postal):
                continue
            city = next((address[field] for field in ("city", "town", "village", "municipality", "hamlet")
                         if address.get(field)), "")
            if city or code in _CITY_STATES:
                names.append(city or country_name(code))
                if result.get("addresstype") != "postcode" and result.get("type") not in ("postcode", "postal_code"):
                    postal_area_only = False
        return _distinct_places(names), postal_area_only
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        pass
    return (), False


def _zippopotam_places(client, postal, code):
    try:
        response = client.get(f"https://api.zippopotam.us/{code.lower()}/{quote(postal, safe='')}")
        response.raise_for_status()
        data = response.json()
        if data.get("country abbreviation", "").upper() != code:
            return ()
        if _postal_key(data.get("post code")) != _postal_key(postal):
            return ()
        places = data.get("places") or []
        if code == "TH" and any(place.get("state") == "Bangkok" for place in places):
            return ("Bangkok",)
        cities = _distinct_places(re.sub(r"\s+(?:G\.P\.O\.|GPO)$", "", place["place name"])
                                  for place in places if isinstance(place.get("place name"), str))
        if len(cities) == 1:
            return cities
        if code in _CITY_STATES:
            return (country_name(code),)
        return cities
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        pass
    return ()


_CITY_STATES = {"SG", "HK", "MO", "MC", "VA", "GI"}
_POSTAL_CITY_CACHE = {}


# ---------------------------------------------------------------------------------------------------------
# Spoken / chat texts for the international steps (11 languages; English fallback)
# ---------------------------------------------------------------------------------------------------------
_TXT = {
    "choose_city": {
        "en": "Postal code {postal} covers several places, including {city}. Which city or town do you live in?",
        "hi": "पोस्टल कोड {postal} में कई जगहें आती हैं, जैसे {city}। आप किस शहर या कस्बे में रहते हैं?",
        "gu": "પોસ્ટલ કોડ {postal}માં {city} સહિત અનેક વિસ્તારો આવે છે. તમે કયા શહેર કે ગામમાં રહો છો?",
        "mr": "{postal} या पोस्टल कोडमध्ये {city} यांसह अनेक ठिकाणे येतात. तुम्ही कोणत्या शहरात किंवा गावात राहता?",
        "bn": "{postal} পোস্টাল কোডে {city} সহ বেশ কিছু জায়গা আছে। আপনি কোন শহর বা এলাকায় থাকেন?",
        "ta": "{postal} அஞ்சல் குறியீட்டில் {city} உள்ளிட்ட பல இடங்கள் உள்ளன. நீங்கள் எந்த ஊரில் வசிக்கிறீர்கள்?",
        "te": "{postal} పోస్టల్ కోడ్ పరిధిలో {city} సహా అనేక ప్రాంతాలు ఉన్నాయి. మీరు ఏ ఊరిలో ఉంటారు?",
        "kn": "{postal} ಅಂಚೆ ಕೋಡ್ ವ್ಯಾಪ್ತಿಯಲ್ಲಿ {city} ಸೇರಿದಂತೆ ಹಲವು ಊರುಗಳಿವೆ. ನೀವು ಯಾವ ಊರಿನಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ?",
        "ml": "{postal} എന്ന തപാൽ കോഡിൽ {city} ഉൾപ്പെടെ പല സ്ഥലങ്ങളുണ്ട്. നിങ്ങൾ ഏത് സ്ഥലത്താണ് താമസിക്കുന്നത്?",
        "pa": "ਪੋਸਟਲ ਕੋਡ {postal} ਵਿੱਚ {city} ਸਮੇਤ ਕਈ ਥਾਵਾਂ ਆਉਂਦੀਆਂ ਹਨ। ਤੁਸੀਂ ਕਿਸ ਸ਼ਹਿਰ ਜਾਂ ਕਸਬੇ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "{postal} ପୋଷ୍ଟାଲ୍ କୋଡ୍‌ରେ {city} ସହିତ ଅନେକ ସ୍ଥାନ ଅଛି। ଆପଣ କେଉଁ ସହର ବା ଗାଁରେ ରହୁଛନ୍ତି?",
    },
    "ask_country": {
        "en": "To guide you correctly, which country do you currently live in?",
        "hi": "आपको सही मार्गदर्शन देने के लिए, आप वर्तमान में किस देश में रहते हैं?",
        "gu": "તમને યોગ્ય માર્ગદર્શન આપવા માટે, તમે હાલમાં કયા દેશમાં રહો છો?",
        "mr": "तुम्हाला योग्य मार्गदर्शन देण्यासाठी, तुम्ही सध्या कोणत्या देशात राहता?",
        "bn": "আপনাকে সঠিকভাবে গাইড করতে, আপনি বর্তমানে কোন দেশে থাকেন?",
        "ta": "உங்களுக்கு சரியாக வழிகாட்ட, நீங்கள் தற்போது எந்த நாட்டில் வசிக்கிறீர்கள்?",
        "te": "మీకు సరిగ్గా మార్గదర్శనం చేయడానికి, మీరు ప్రస్తుతం ఏ దేశంలో నివసిస్తున్నారు?",
        "kn": "ನಿಮಗೆ ಸರಿಯಾಗಿ ಮಾರ್ಗದರ್ಶನ ನೀಡಲು, ನೀವು ಪ್ರಸ್ತುತ ಯಾವ ದೇಶದಲ್ಲಿ ವಾಸಿಸುತ್ತಿದ್ದೀರಿ?",
        "ml": "നിങ്ങളെ ശരിയായി സഹായിക്കാൻ, നിങ്ങൾ ഇപ്പോൾ ഏത് രാജ്യത്താണ് താമസിക്കുന്നത്?",
        "pa": "ਤੁਹਾਨੂੰ ਸਹੀ ਮਾਰਗਦਰਸ਼ਨ ਦੇਣ ਲਈ, ਤੁਸੀਂ ਇਸ ਸਮੇਂ ਕਿਸ ਦੇਸ਼ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "ଆପଣଙ୍କୁ ସଠିକ୍ ମାର୍ଗଦର୍ଶନ ଦେବା ପାଇଁ, ଆପଣ ବର୍ତ୍ତମାନ କେଉଁ ଦେଶରେ ରହୁଛନ୍ତି?",
    },
    "country_unclear": {
        "mr": "मला देशाचं नाव नीट ऐकू आलं नाही. तुम्ही कोणत्या देशात राहता?",
        "bn": "দেশের নামটা ঠিক শুনতে পাইনি। আপনি কোন দেশে থাকেন?",
        "ta": "நாட்டின் பெயர் சரியாகக் கேட்கவில்லை. நீங்கள் எந்த நாட்டில் வசிக்கிறீர்கள்?",
        "te": "దేశం పేరు సరిగ్గా వినిపించలేదు. మీరు ఏ దేశంలో ఉంటున్నారు?",
        "kn": "ದೇಶದ ಹೆಸರು ಸರಿಯಾಗಿ ಕೇಳಿಸಲಿಲ್ಲ. ನೀವು ಯಾವ ದೇಶದಲ್ಲಿ ವಾಸಿಸುತ್ತಿದ್ದೀರಿ?",
        "ml": "രാജ്യത്തിന്റെ പേര് വ്യക്തമായി കേട്ടില്ല. നിങ്ങൾ ഏത് രാജ്യത്താണ് താമസിക്കുന്നത്?",
        "pa": "ਮੈਨੂੰ ਦੇਸ਼ ਦਾ ਨਾਂ ਸਾਫ਼ ਸੁਣਾਈ ਨਹੀਂ ਦਿੱਤਾ। ਤੁਸੀਂ ਕਿਸ ਦੇਸ਼ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "ଦେଶର ନାମ ସ୍ପଷ୍ଟ ଶୁଣିପାରିଲି ନାହିଁ। ଆପଣ କେଉଁ ଦେଶରେ ରହୁଛନ୍ତି?",
        "en": "Sorry, I could not catch the country name. Could you please tell me which country you live in?",
        "hi": "माफ़ कीजिए, मैं देश का नाम समझ नहीं पाई। कृपया बताइए आप किस देश में रहते हैं?",
        "gu": "માફ કરશો, હું દેશનું નામ સમજી શકી નહીં. કૃપા કરીને જણાવશો તમે કયા દેશમાં રહો છો?",
    },
    "ask_postal": {
        "en": "Thank you! Since you live in {country}, could you please tell me your {hint}?",
        "hi": "धन्यवाद! आप {country} में रहते हैं, कृपया अपना {hint} बताइए?",
        "gu": "આભાર! તમે {country}માં રહો છો, કૃપા કરીને તમારો {hint} જણાવશો?",
        "mr": "धन्यवाद! तुम्ही {country} मध्ये राहता, कृपया तुमचा {hint} सांगाल का?",
        "bn": "ধন্যবাদ! আপনি {country}-এ থাকেন, দয়া করে আপনার {hint} বলবেন?",
        "ta": "நன்றி! நீங்கள் {country}-ல் வசிக்கிறீர்கள், உங்கள் {hint}-ஐ சொல்ல முடியுமா?",
        "te": "ధన్యవాదాలు! మీరు {country}లో ఉంటున్నారు, దయచేసి మీ {hint} చెప్పగలరా?",
        "kn": "ಧನ್ಯವಾದಗಳು! ನೀವು {country}ದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ, ದಯವಿಟ್ಟು ನಿಮ್ಮ {hint} ತಿಳಿಸುವಿರಾ?",
        "ml": "നന്ദി! നിങ്ങൾ {country}-ൽ താമസിക്കുന്നു, ദയവായി നിങ്ങളുടെ {hint} പറയാമോ?",
        "pa": "ਧੰਨਵਾਦ! ਤੁਸੀਂ {country} ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ, ਕਿਰਪਾ ਕਰਕੇ ਆਪਣਾ {hint} ਦੱਸੋ?",
        "or": "ଧନ୍ୟବାଦ! ଆପଣ {country}ରେ ରହନ୍ତି, ଦୟାକରି ଆପଣଙ୍କ {hint} କୁହନ୍ତୁ?",
    },
    "ask_city": {
        "en": "Thank you! Which city in {country} do you live in?",
        "hi": "धन्यवाद! आप {country} के किस शहर में रहते हैं?",
        "gu": "આભાર! તમે {country}ના કયા શહેરમાં રહો છો?",
        "mr": "धन्यवाद! तुम्ही {country} मधील कोणत्या शहरात राहता?",
        "bn": "ধন্যবাদ! আপনি {country}-এর কোন শহরে থাকেন?",
        "ta": "நன்றி! நீங்கள் {country}-ல் எந்த நகரத்தில் வசிக்கிறீர்கள்?",
        "te": "ధన్యవాదాలు! మీరు {country}లో ఏ నగరంలో ఉంటున్నారు?",
        "kn": "ಧನ್ಯವಾದಗಳು! ನೀವು {country}ದ ಯಾವ ನಗರದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ?",
        "ml": "നന്ദി! നിങ്ങൾ {country}-ലെ ഏത് നഗരത്തിലാണ് താമസിക്കുന്നത്?",
        "pa": "ਧੰਨਵਾਦ! ਤੁਸੀਂ {country} ਦੇ ਕਿਸ ਸ਼ਹਿਰ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "ଧନ୍ୟବାଦ! ଆପଣ {country}ର କେଉଁ ସହରରେ ରହନ୍ତି?",
    },
    "postal_not_found": {
        "en": "I could not find a city for the {hint} {postal} in {country}. Could you please tell me which city you live in?",
        "hi": "मुझे {country} में {hint} {postal} के लिए कोई शहर नहीं मिला। कृपया बताइए आप किस शहर में रहते हैं?",
        "gu": "મને {country}માં {hint} {postal} માટે કોઈ શહેર મળ્યું નહીં. કૃપા કરીને જણાવશો તમે કયા શહેરમાં રહો છો?",
        "mr": "मला {country} मध्ये {hint} {postal} साठी कोणतेही शहर सापडले नाही. कृपया तुम्ही कोणत्या शहरात राहता ते सांगा?",
        "bn": "{country}-এ {hint} {postal}-এর জন্য কোনো শহর পাইনি। দয়া করে বলবেন আপনি কোন শহরে থাকেন?",
        "ta": "{country}-ல் {hint} {postal}-க்கு எந்த நகரமும் கிடைக்கவில்லை. நீங்கள் எந்த நகரத்தில் வசிக்கிறீர்கள்?",
        "te": "{country}లో {hint} {postal}కి ఏ నగరం దొరకలేదు. దయచేసి మీరు ఏ నగరంలో ఉంటున్నారో చెప్పండి?",
        "kn": "{country}ದಲ್ಲಿ {hint} {postal}ಗೆ ಯಾವುದೇ ನಗರ ಸಿಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ನೀವು ಯಾವ ನಗರದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ ಎಂದು ತಿಳಿಸಿ?",
        "ml": "{country}-ൽ {hint} {postal}-ന് ഒരു നഗരവും കണ്ടെത്തിയില്ല. നിങ്ങൾ ഏത് നഗരത്തിലാണ് താമസിക്കുന്നത്?",
        "pa": "{country} ਵਿੱਚ {hint} {postal} ਲਈ ਕੋਈ ਸ਼ਹਿਰ ਨਹੀਂ ਮਿਲਿਆ। ਕਿਰਪਾ ਕਰਕੇ ਦੱਸੋ ਤੁਸੀਂ ਕਿਸ ਸ਼ਹਿਰ ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ?",
        "or": "{country}ରେ {hint} {postal} ପାଇଁ କୌଣସି ସହର ମିଳିଲା ନାହିଁ। ଦୟାକରି କୁହନ୍ତୁ ଆପଣ କେଉଁ ସହରରେ ରହନ୍ତି?",
    },
    "confirm_city": {
        "en": "Based on your {hint} {postal}, you reside in {city}, {country}, right?",
        "hi": "आपके {hint} {postal} के अनुसार, आप {city}, {country} में रहते हैं, सही ना?",
        "gu": "તમારા {hint} {postal} મુજબ, તમે {city}, {country}માં રહો છો, બરાબર ને?",
        "mr": "तुमच्या {hint} {postal} नुसार, तुम्ही {city}, {country} येथे राहता, बरोबर ना?",
        "bn": "আপনার {hint} {postal} অনুযায়ী, আপনি {city}, {country}-এ থাকেন, তাই তো?",
        "ta": "உங்கள் {hint} {postal} படி, நீங்கள் {city}, {country}-ல் வசிக்கிறீர்கள், சரிதானே?",
        "te": "మీ {hint} {postal} ప్రకారం, మీరు {city}, {country}లో ఉంటున్నారు, కదా?",
        "kn": "ನಿಮ್ಮ {hint} {postal} ಪ್ರಕಾರ, ನೀವು {city}, {country}ದಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ, ಸರಿ ತಾನೇ?",
        "ml": "നിങ്ങളുടെ {hint} {postal} പ്രകാരം, നിങ്ങൾ {city}, {country}-ൽ താമസിക്കുന്നു, ശരിയല്ലേ?",
        "pa": "ਤੁਹਾਡੇ {hint} {postal} ਅਨੁਸਾਰ, ਤੁਸੀਂ {city}, {country} ਵਿੱਚ ਰਹਿੰਦੇ ਹੋ, ਠੀਕ ਹੈ ਨਾ?",
        "or": "ଆପଣଙ୍କ {hint} {postal} ଅନୁସାରେ, ଆପଣ {city}, {country}ରେ ରହନ୍ତି, ଠିକ୍ ତ?",
    },
    "postal_invalid": {
        "mr": "हा {country} साठी वैध {hint} वाटत नाही. कृपया तुमचा {hint} पुन्हा सांगाल का?",
        "bn": "এটি {country}-এর সঠিক {hint} বলে মনে হচ্ছে না। আপনার {hint} আরেকবার বলবেন?",
        "ta": "இது {country} நாட்டுக்கான சரியான {hint} போல் தெரியவில்லை. உங்கள் {hint} மீண்டும் சொல்ல முடியுமா?",
        "te": "ఇది {country}కి సరైన {hint} అనిపించడం లేదు. మీ {hint} మళ్లీ చెబుతారా?",
        "kn": "ಇದು {country} ದೇಶದ ಮಾನ್ಯವಾದ {hint} ಎಂದು ತೋರುತ್ತಿಲ್ಲ. ನಿಮ್ಮ {hint} ಮತ್ತೊಮ್ಮೆ ಹೇಳುತ್ತೀರಾ?",
        "ml": "ഇത് {country}യിലെ ശരിയായ {hint} ആണെന്ന് തോന്നുന്നില്ല. നിങ്ങളുടെ {hint} ഒന്നുകൂടി പറയാമോ?",
        "pa": "ਇਹ {country} ਲਈ ਸਹੀ {hint} ਨਹੀਂ ਲੱਗਦਾ। ਕੀ ਤੁਸੀਂ ਆਪਣਾ {hint} ਦੁਬਾਰਾ ਦੱਸ ਸਕਦੇ ਹੋ?",
        "or": "ଏହା {country} ପାଇଁ ଏକ ବୈଧ {hint} ଭଳି ଲାଗୁନାହିଁ। ଆପଣଙ୍କ {hint} ଆଉ ଥରେ କହିବେ କି?",
        "en": "Sorry, that does not look like a valid {hint} for {country}. Could you please tell me your {hint} again?",
        "hi": "माफ़ कीजिए, यह {country} का सही {hint} नहीं लग रहा। कृपया अपना {hint} फिर से बताइए?",
        "gu": "માફ કરશો, આ {country}નો સાચો {hint} લાગતો નથી. કૃપા કરીને તમારો {hint} ફરીથી જણાવશો?",
    },
    "ask_phone": {
        "bn": "ধন্যবাদ! আপনি ভারতের বাইরে থাকেন বলে আমাদের আন্তর্জাতিক রোগী পরিষেবা দল অনলাইন পরামর্শ, ডিজিটাল স্মাইল ডিজাইনের প্রিভিউ ও ভারতে চিকিৎসার পরিকল্পনায় আপনাকে সাহায্য করবে। যোগাযোগের জন্য +{dial} বাদ দিয়ে আপনার {digits} সংখ্যার {country} মোবাইল নম্বরটি বলবেন?",
        "ta": "நன்றி! நீங்கள் இந்தியாவுக்கு வெளியே வசிப்பதால், இணையவழி ஆலோசனை, டிஜிட்டல் ஸ்மைல் டிசைன் முன்னோட்டம் மற்றும் இந்தியாவில் சிகிச்சையைத் திட்டமிட எங்கள் சர்வதேச நோயாளர் குழு உங்களுக்கு உதவும். உங்களைத் தொடர்புகொள்ள, +{dial} இல்லாமல் உங்கள் {digits} இலக்க {country} கைபேசி எண்ணைச் சொல்ல முடியுமா?",
        "te": "ధన్యవాదాలు! మీరు భారతదేశం వెలుపల ఉంటున్నారు కాబట్టి ఆన్‌లైన్ సంప్రదింపులు, డిజిటల్ స్మైల్ డిజైన్ ప్రివ్యూ, భారతదేశంలో చికిత్స ప్రణాళిక గురించి మా అంతర్జాతీయ రోగుల బృందం మీకు సహాయం చేస్తుంది. మేము మిమ్మల్ని సంప్రదించడానికి +{dial} లేకుండా మీ {digits} అంకెల {country} మొబైల్ నంబర్ చెబుతారా?",
        "kn": "ಧನ್ಯವಾದಗಳು! ನೀವು ಭಾರತದ ಹೊರಗೆ ವಾಸಿಸುತ್ತಿರುವುದರಿಂದ ಆನ್‌ಲೈನ್ ಸಮಾಲೋಚನೆ, ಡಿಜಿಟಲ್ ಸ್ಮೈಲ್ ಡಿಸೈನ್ ಮುನ್ನೋಟ ಮತ್ತು ಭಾರತದಲ್ಲಿ ಚಿಕಿತ್ಸೆಯ ಯೋಜನೆಗೆ ನಮ್ಮ ಅಂತರರಾಷ್ಟ್ರೀಯ ರೋಗಿಗಳ ಸೇವಾ ತಂಡ ನೆರವಾಗುತ್ತದೆ. ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸಲು +{dial} ಹೊರತುಪಡಿಸಿ ನಿಮ್ಮ {digits} ಅಂಕಿಯ {country} ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯನ್ನು ಹೇಳುತ್ತೀರಾ?",
        "ml": "നന്ദി! നിങ്ങൾ ഇന്ത്യയ്ക്ക് പുറത്താണ് താമസിക്കുന്നത്. ഓൺലൈൻ കൺസൾട്ടേഷൻ, ഡിജിറ്റൽ സ്‌മൈൽ ഡിസൈൻ പ്രിവ്യൂ, ഇന്ത്യയിലെ ചികിത്സ ആസൂത്രണം ചെയ്യൽ എന്നിവയിൽ ഞങ്ങളുടെ അന്താരാഷ്ട്ര രോഗി സേവനസംഘം നിങ്ങളെ സഹായിക്കും. ബന്ധപ്പെടാൻ +{dial} ഒഴിവാക്കി നിങ്ങളുടെ {digits} അക്ക {country} മൊബൈൽ നമ്പർ പറയാമോ?",
        "pa": "ਧੰਨਵਾਦ! ਤੁਸੀਂ ਭਾਰਤ ਤੋਂ ਬਾਹਰ ਰਹਿੰਦੇ ਹੋ, ਇਸ ਲਈ ਸਾਡੀ ਅੰਤਰਰਾਸ਼ਟਰੀ ਮਰੀਜ਼ ਸੇਵਾ ਟੀਮ ਆਨਲਾਈਨ ਸਲਾਹ, ਡਿਜੀਟਲ ਸਮਾਈਲ ਡਿਜ਼ਾਈਨ ਦੀ ਝਲਕ ਅਤੇ ਭਾਰਤ ਵਿੱਚ ਇਲਾਜ ਦੀ ਯੋਜਨਾ ਬਾਰੇ ਤੁਹਾਡੀ ਮਦਦ ਕਰੇਗੀ। ਸੰਪਰਕ ਲਈ +{dial} ਤੋਂ ਬਿਨਾਂ ਆਪਣਾ {digits} ਅੰਕਾਂ ਵਾਲਾ {country} ਮੋਬਾਈਲ ਨੰਬਰ ਦੱਸੋਗੇ?",
        "or": "ଧନ୍ୟବାଦ! ଆପଣ ଭାରତ ବାହାରେ ରହୁଥିବାରୁ ଅନଲାଇନ୍ ପରାମର୍ଶ, ଡିଜିଟାଲ୍ ସ୍ମାଇଲ୍ ଡିଜାଇନ୍‌ର ପୂର୍ବଦର୍ଶନ ଓ ଭାରତରେ ଚିକିତ୍ସା ଯୋଜନା ପାଇଁ ଆମର ଆନ୍ତର୍ଜାତୀୟ ରୋଗୀ ସେବା ଦଳ ଆପଣଙ୍କୁ ସାହାଯ୍ୟ କରିବ। ଯୋଗାଯୋଗ ପାଇଁ +{dial} ବାଦ ଦେଇ ଆପଣଙ୍କ {digits} ଅଙ୍କ ବିଶିଷ୍ଟ {country} ମୋବାଇଲ୍ ନମ୍ବର କହିବେ କି?",
        "en": "Thank you! Since you are located outside India, our international patient team will personally guide you about a virtual consultation, a digital smile design preview and planning your treatment in India. Could you please share your {digits}-digit {country} mobile number (without +{dial}) so our team can contact you?",
        "hi": "धन्यवाद! आप भारत के बाहर रहते हैं, इसलिए हमारी इंटरनेशनल पेशेंट टीम आपको वर्चुअल कंसल्टेशन, डिजिटल स्माइल डिज़ाइन प्रीव्यू और भारत में ट्रीटमेंट प्लान करने के बारे में खुद मार्गदर्शन देगी। कृपया अपना {digits} अंकों का {country} मोबाइल नंबर (+{dial} के बिना) बताइए ताकि हमारी टीम आपसे संपर्क कर सके?",
        "gu": "આભાર! તમે ભારતની બહાર રહો છો, તેથી અમારી ઇન્ટરનેશનલ પેશન્ટ ટીમ તમને વર્ચ્યુઅલ કન્સલ્ટેશન, ડિજિટલ સ્માઇલ ડિઝાઇન પ્રિવ્યૂ અને ભારતમાં ટ્રીટમેન્ટ પ્લાન કરવા વિશે જાતે માર્ગદર્શન આપશે. કૃપા કરીને તમારો {digits} અંકનો {country} મોબાઇલ નંબર (+{dial} વગર) જણાવશો જેથી અમારી ટીમ તમારો સંપર્ક કરી શકે?",
        "mr": "धन्यवाद! तुम्ही भारताबाहेर राहता, त्यामुळे आमची इंटरनॅशनल पेशंट टीम तुम्हाला व्हर्च्युअल कन्सल्टेशन, डिजिटल स्माइल डिझाइन प्रिव्ह्यू आणि भारतातील ट्रीटमेंट प्लॅनबद्दल स्वतः मार्गदर्शन करेल. कृपया तुमचा {digits} अंकी {country} मोबाइल नंबर (+{dial} शिवाय) सांगाल का?",
    },
    "phone_invalid": {
        "mr": "हा {country} साठी वैध मोबाइल नंबर वाटत नाही. +{dial} वगळून {digits} अंक हवेत. कृपया नंबर पुन्हा सांगाल का?",
        "bn": "এটি {country}-এর সঠিক মোবাইল নম্বর বলে মনে হচ্ছে না। +{dial} বাদ দিয়ে {digits}টি সংখ্যা থাকা দরকার। নম্বরটি আবার বলবেন?",
        "ta": "இது {country} நாட்டுக்கான சரியான கைபேசி எண் போல் தெரியவில்லை. +{dial} இல்லாமல் {digits} இலக்கங்கள் இருக்க வேண்டும். மீண்டும் சொல்ல முடியுமா?",
        "te": "ఇది {country}కి సరైన మొబైల్ నంబర్ అనిపించడం లేదు. +{dial} లేకుండా {digits} అంకెలు ఉండాలి. మళ్లీ చెబుతారా?",
        "kn": "ಇದು {country} ದೇಶದ ಮಾನ್ಯವಾದ ಮೊಬೈಲ್ ಸಂಖ್ಯೆಯಂತೆ ತೋರುತ್ತಿಲ್ಲ. +{dial} ಹೊರತುಪಡಿಸಿ {digits} ಅಂಕಿಗಳಿರಬೇಕು. ಮತ್ತೊಮ್ಮೆ ಹೇಳುತ್ತೀರಾ?",
        "ml": "ഇത് {country}യിലെ ശരിയായ മൊബൈൽ നമ്പർ ആണെന്ന് തോന്നുന്നില്ല. +{dial} ഒഴിവാക്കിയാൽ {digits} അക്കങ്ങൾ വേണം. ഒന്നുകൂടി പറയാമോ?",
        "pa": "ਇਹ {country} ਲਈ ਸਹੀ ਮੋਬਾਈਲ ਨੰਬਰ ਨਹੀਂ ਲੱਗਦਾ। +{dial} ਤੋਂ ਬਿਨਾਂ ਇਸ ਵਿੱਚ {digits} ਅੰਕ ਹੋਣੇ ਚਾਹੀਦੇ ਹਨ। ਦੁਬਾਰਾ ਦੱਸੋਗੇ?",
        "or": "ଏହା {country} ପାଇଁ ଏକ ବୈଧ ମୋବାଇଲ୍ ନମ୍ବର ଭଳି ଲାଗୁନାହିଁ। +{dial} ବାଦ ଦେଲେ {digits}ଟି ଅଙ୍କ ରହିବା ଦରକାର। ଆଉ ଥରେ କହିବେ କି?",
        "en": "Sorry, that does not look like a valid {country} mobile number. It should have {digits} digits (without +{dial}). Could you please share it again?",
        "hi": "माफ़ कीजिए, यह सही {country} मोबाइल नंबर नहीं लग रहा। इसमें {digits} अंक होने चाहिए (+{dial} के बिना)। कृपया फिर से बताइए?",
        "gu": "માફ કરશો, આ સાચો {country} મોબાઇલ નંબર લાગતો નથી. તેમાં {digits} અંક હોવા જોઈએ (+{dial} વગર). કૃપા કરીને ફરીથી જણાવશો?",
    },
}


def intl_text(key, lang, code=None, **kw):
    lang = (lang or "en")[:2].lower()
    table = _TXT[key]
    tpl = table.get(lang) or table["en"]
    if code:
        kw.setdefault("country", country_name(code))
        kw.setdefault("hint", postal_hint(code, include_example=key not in {"confirm_city", "postal_not_found"}))
        kw.setdefault("digits", phone_digits_hint(code))
        kw.setdefault("dial", re.sub(r"\D", "", dial_code(code)))
    return tpl.format(**kw)


def is_international(slots_or_code):
    code = slots_or_code.get("country_code") if isinstance(slots_or_code, dict) else slots_or_code
    return bool(code) and str(code).upper() != "IN"
