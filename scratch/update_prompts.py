import os

def update_conversation_md():
    filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'voice_agent', 'prompts', 'conversation.md')
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    old_block_start = "- 🚨 ABSOLUTE COMPULSORY RULE — 5TH MESSAGE / TURN PROFESSION INQUIRY"
    old_block_end = "without forcing city or appointment booking!"

    start_idx = content.find(old_block_start)
    if start_idx != -1:
        end_idx = content.find(old_block_end, start_idx)
        if end_idx != -1:
            end_idx += len(old_block_end)
            replacement = """- 🚨 ABSOLUTE MANDATORY RULE — PROFESSION INQUIRY (STRICTLY ONLY ONE TIME IN THE ENTIRE CONVERSATION):
      In Riya's conversational flow during open exploration (typically at turn 4 or 5), Riya may ask about their work or profession in the user's active language:
      • English: "By the way, [Name], what do you do for work?" (or "What is your profession?")
      • Gujarati: "તેમ છતાં, [Name], જો હું પૂછી શકું, તમે શું કામ કરો છો?" (or "તમારો વ્યવસાય શું છે?")
      • Hindi: "वैसे, [Name], अगर मैं पूछ सकती हूँ, आप क्या काम करते हैं?" (or "आपका पेशा या प्रोफेशन क्या है?")
      • Marathi: "तसेच, [Name], तुम्ही काय काम करता?"
      • Bengali: "যাইহোক, [Name], আপনি কী কাজ করেন?"
      • Tamil: "மூலம், [Name], நீங்கள் என்ன வேலை செய்கிறீர்கள்?"
      • Telugu: "అలాగే, [Name], మీరు ఏమి పని చేస్తుంటారు?"
      • Kannada: "ಹಾಗೆಯೇ, [Name], ನೀವು ಏನು ಕೆಲಸ ಮಾಡುತ್ತಿದ್ದೀರಿ?"
      • Malayalam: "വഴിയിൽ, [Name], നിങ്ങൾ എന്താണ് ജോലി ചെയ്യുന്നത്?"
      • Punjabi: "ਵੈਸੇ, [Name], ਤੁਸੀਂ ਕੀ ਕੰਮ ਕਰਦੇ ਹੋ?"
      • Odia: "ସେମିતિରେ, [Name], ଆପଣ କଣ କାମ କରନ୍ତି?"
      🚨 CRITICAL RESTRICTION — STRICTLY ONLY ONE TIME IN THE WHOLE CONVERSATION:
      - This profession inquiry can ONLY WORK ONE TIME in the whole conversation!
      - ONCE ASKED, RIYA IS STRICTLY FORBIDDEN FROM EVER ASKING "What is your profession?" OR "What do you do for work?" AGAIN!
      - If the user mentions their profession at any time (or if they skip/ignore it or choose not to answer), NEVER RE-ASK OR REPEAT this question!
      - In long conversations (10, 20, 30+ turns), asking about profession multiple times is STRICTLY BANNED.
      - When the user mentions their profession, Riya connects their profession to their smile using the appropriate profession analogy from the knowledge base (`knowledge/profession.yaml`) without forcing city or appointment booking!"""
            new_content = content[:start_idx] + replacement + content[end_idx:]
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print("Successfully updated conversation.md!")
            return True
    print("Could not find block in conversation.md")
    return False

if __name__ == '__main__':
    update_conversation_md()
