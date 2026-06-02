
import re

# Word-level substitutions (case-sensitive regex with word boundaries where possible)
WORD_SUBSTITUTIONS = [
    (r'\bBrahmanand\b', 'ब्रह्मानंद'),
    (r'\bSatguru\b', 'सतगुरु'),
    (r'\bSantmat\b', 'संतमत'),
    (r'\bSurat Shabda\b', 'सुरत शब्द'),
    (r'\bViyanamaya Kosha\b', 'विज्ञानमय कोश'),
    (r'\bviyanamaya kosha\b', 'विज्ञानमय कोश'),
    (r'\bUpasana\b', 'उपासना'),
    (r'\bupasana\b', 'उपासना'),
    (r'\bBhakti\b', 'भक्ति'),
    (r'\bJnana\b', 'ज्ञान'),
    (r'\bjnana\b', 'ज्ञान'),
    (r'\bKarma\b', 'कर्मा'),
    (r'\bkarma\b', 'कर्मा'),
    (r'\bNarad\b', 'नारद'),
    (r'\bFatehgarh\b', 'फतेहगढ़'),
    (r'\bBabuji\b', 'बाबूजी'),
    (r'\bLalaji\b', 'लालाजी'),
    (r'\bDaaji\b', 'दाजी'),
    (r'\bLive\b', 'लाइव'),
    (r'\bjudgement\b', 'जजमेंट'),
    (r'\bJudgement\b', 'जजमेंट'),
    (r'\bjudgment\b', 'जजमेंट'),
    (r'\b1983\b', 'उन्नीस सौ तिरासी'),
    (r'दाजी', 'दाजी'), # Ensure it matches with nukta if needed, though Daaji is usually fine.
    (r'\bद\b', 'द'), # Placeholder to ensure 'द' isn't misread, but actually we want to fix 'द पावर'
    (r'\bद पावर ऑफ पैराडॉक्स\b', 'द पावर ऑफ पैराडॉक्स'), # ElevenLabs sometimes fails on single characters
    (r'\bद\b\s+', 'द '), # Force space
]

PAUSE_FIX_PATTERNS = [
    (r'\bकमलेश डी\.\s*पटेल\b', 'कमलेश डी पटेल'),
    (r'\bKamlesh D\.\s*Patel\b', 'कमलेश डी पटेल'),
    (r'\bD\.\s*Patel\b', 'डी पटेल'),
    (r'\bO\s+Henry\b', 'ओ हेनरी'),
    (r'\bRam\s+Chandra\b', 'रामचंद्र'),
    (r'Actionable\.\s*Step', 'Actionable Step'),
    (r'Actionable\s{2,}Step', 'Actionable Step'),
]


def apply_pronunciation_fixes(text: str) -> str:
    """Apply word-level substitutions for known mispronounced terms."""
    if not text:
        return text
    for pattern, replacement in WORD_SUBSTITUTIONS:
        text = re.sub(pattern, replacement, text)
    return text


def normalize_pauses(text: str) -> str:
    """Fix patterns that cause unnatural pauses in ElevenLabs eleven_v3."""
    if not text:
        return text
    for pattern, replacement in PAUSE_FIX_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def apply_all_fixes(text: str) -> str:
    """Apply nukta normalization, pronunciation fixes, and pause normalization."""
    from modules.nukta_normalizer import normalize_nukta
    text = normalize_nukta(text)
    text = apply_pronunciation_fixes(text)
    text = normalize_pauses(text)
    return text
