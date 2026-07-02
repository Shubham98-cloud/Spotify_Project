import re
import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

# Regular expressions for PII scrubbing
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
IP_REGEX = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
MENTION_REGEX = re.compile(r"@\w+")

def scrub_pii(text: str) -> str:
    """
    Scrubs personally identifiable information (PII) like emails, phone numbers,
    IP addresses, and social media handles from text.
    """
    if not text:
        return ""
    
    text = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
    text = PHONE_REGEX.sub("[REDACTED_PHONE]", text)
    text = IP_REGEX.sub("[REDACTED_IP]", text)
    text = MENTION_REGEX.sub("[REDACTED_HANDLE]", text)
    return text

def is_likely_english(text: str) -> bool:
    """
    Fast heuristic to detect if text is already English (or Latin-script).
    Checks the ratio of standard ASCII characters (32-127).
    English text is almost entirely ASCII, so a ratio > 0.88 means skip translation.
    This avoids making an HTTP call to Google Translate for every English review.
    """
    if not text:
        return True
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return (ascii_chars / len(text)) > 0.88


def translate_to_english(text: str) -> str:
    """
    Translates text to English if it's in another language.
    Uses deep-translator with Google Translate backend.
    Skips the API call entirely if text is already detected as English/ASCII.
    """
    if not text:
        return ""
    
    # Check if text is long enough to translate
    if len(text.strip()) < 3:
        return text

    # Fast path: skip API call if text is already English (ASCII-dominant)
    if is_likely_english(text):
        return text

    try:
        # GoogleTranslator auto-detects source language
        translator = GoogleTranslator(source='auto', target='en')
        translated_text = translator.translate(text)
        return translated_text
    except Exception as e:
        logger.warning(f"Translation failed for text: '{text[:30]}...'. Error: {e}")
        return text
def infer_user_segments(text: str) -> list:
    """
    Infers user segments and problem domains based on keywords present in the text.
    """
    segments = []
    text_lower = text.lower()

    # Premium vs Free User segments
    if any(kw in text_lower for kw in ["premium", "subscription", "pay", "paid", "cost", "price", "billing", "subscribe"]):
        segments.append("Premium User")
    if any(kw in text_lower for kw in ["free user", "free tier", "ads", "advertisement", "commercials", "sponsor"]):
        segments.append("Free User")

    # Discovery vs UI vs Performance problem areas
    if any(kw in text_lower for kw in ["recommend", "suggest", "discover", "loop", "same song", "playlist", "shuffle", "repeat", "boring", "fatigue", "echo chamber"]):
        segments.append("Discovery Issue")
    if any(kw in text_lower for kw in ["ui", "ux", "button", "interface", "layout", "design", "navigation"]):
        segments.append("UI/UX Issue")
    if any(kw in text_lower for kw in ["crash", "freeze", "slow", "bug", "broken", "lag", "stop", "offline"]):
        segments.append("Performance/Stability Issue")

    # Default segment if none match
    if not segments:
        segments.append("General Feedback")

    return segments

ALLOWED_CHAR_PATTERN = re.compile(r"^[a-zA-Z0-9\s.,!?'\"()\-]*$")

def clean_and_enrich_review(review: dict) -> dict:
    """
    Cleans review text (PII scrubbing + English translation) and enriches it
    with inferred user segment tags.
    Returns None if the review does not satisfy the length or special character constraints.
    """
    raw_content = review.get("content", "") or ""
    
    # 1. Filter: length must be up to 50 characters
    if not (0 < len(raw_content.strip()) <= 50):
        return None
        
    # 2. Filter: must not contain any emoji or special characters
    if not ALLOWED_CHAR_PATTERN.match(raw_content):
        return None

    cleaned_review = review.copy()
    raw_title = review.get("title", "") or ""
    
    # 1. Scrub PII from title and content
    scrubbed_title = scrub_pii(raw_title)
    scrubbed_content = scrub_pii(raw_content)
    
    # 2. Translate to English
    translated_title = translate_to_english(scrubbed_title)
    translated_content = translate_to_english(scrubbed_content)
    
    # 3. Infer segments based on the cleaned English text
    combined_text = f"{translated_title} {translated_content}"
    inferred_tags = infer_user_segments(combined_text)
    
    # Update dictionary
    cleaned_review["title"] = translated_title
    cleaned_review["content"] = translated_content
    cleaned_review["inferred_segments"] = inferred_tags
    cleaned_review["is_translated"] = (translated_content != scrubbed_content)
    
    return cleaned_review

if __name__ == "__main__":
    # Test cases
    test_text = "Hi, my email is test@domain.com and phone is +1-555-019-9922. Contact me at @tester."
    print("Scrubbed:", scrub_pii(test_text))
    
    test_foreign = "Me encanta esta aplicación, pero siempre me recomienda las mismas canciones."
    translated = translate_to_english(test_foreign)
    print("Translated:", translated)
    print("Segments:", infer_user_segments(translated))
