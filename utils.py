"""
utils.py
--------
Shared configuration and small helper utilities used across the project:
  - LANGUAGES: master language table (speech-recognition locale code,
    translator code, text-to-speech code) for all 15 supported languages.
  - Logger setup (writes errors/events to translator.log).
  - TranslationHistory: keeps an in-memory list of past translations for
    the session, and can save them to a text file.
"""

import logging
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------
# "sr"        -> locale code used by SpeechRecognition / Google Web Speech API
# "translate" -> ISO 639-1 code used by the DeepL API
# "tts"       -> language code used by gTTS
LANGUAGES = {
    "English":   {"sr": "en-IN", "translate": "en", "tts": "en"},
    "Hindi":     {"sr": "hi-IN", "translate": "hi", "tts": "hi"},
    "Marathi":   {"sr": "mr-IN", "translate": "mr", "tts": "mr"},
    "Bengali":   {"sr": "bn-IN", "translate": "bn", "tts": "bn"},
    "Gujarati":  {"sr": "gu-IN", "translate": "gu", "tts": "gu"},
    "Tamil":     {"sr": "ta-IN", "translate": "ta", "tts": "ta"},
    "Telugu":    {"sr": "te-IN", "translate": "te", "tts": "te"},
    "Kannada":   {"sr": "kn-IN", "translate": "kn", "tts": "kn"},
    "Malayalam": {"sr": "ml-IN", "translate": "ml", "tts": "ml"},
    "Punjabi":   {"sr": "pa-IN", "translate": "pa", "tts": "pa"},
    "Urdu":      {"sr": "ur-IN", "translate": "ur", "tts": "ur"},
    "French":    {"sr": "fr-FR", "translate": "fr", "tts": "fr"},
    "German":    {"sr": "de-DE", "translate": "de", "tts": "de"},
    "Spanish":   {"sr": "es-ES", "translate": "es", "tts": "es"},
    "Japanese":  {"sr": "ja-JP", "translate": "ja", "tts": "ja"},
}

LANGUAGE_NAMES = list(LANGUAGES.keys())


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def get_logger():
    """Return a logger that writes timestamped events/errors to translator.log
    as well as the console, without adding duplicate handlers on re-import."""
    logger = logging.getLogger("voice_translator")
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler("translator.log", encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    return logger


# ---------------------------------------------------------------------------
# Simple stopwatch helper for latency measurement
# ---------------------------------------------------------------------------
class Stopwatch:
    """Small helper to measure elapsed wall-clock time for a step."""

    def __init__(self):
        self._start = None

    def start(self):
        self._start = time.perf_counter()
        return self

    def elapsed(self):
        """Return elapsed seconds since start(), rounded to 3 decimals."""
        if self._start is None:
            return 0.0
        return round(time.perf_counter() - self._start, 3)


# ---------------------------------------------------------------------------
# Translation history (for the "Translation history" enhancement)
# ---------------------------------------------------------------------------
class TranslationHistory:
    """Keeps a session-level record of translations, including the
    recognition/translation/TTS latency for each entry, so the user can
    review past translations and export them for the project report."""

    def __init__(self):
        self.records = []

    def add(self, source_lang, target_lang, source_text, translated_text,
            recognition_time, translation_time, tts_time):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_lang": source_lang,
            "target_lang": target_lang,
            "source_text": source_text,
            "translated_text": translated_text,
            "recognition_time_s": recognition_time,
            "translation_time_s": translation_time,
            "tts_time_s": tts_time,
            "total_time_s": round(
                (recognition_time or 0) + (translation_time or 0) + (tts_time or 0), 3
            ),
        }
        self.records.append(entry)
        return entry

    def clear(self):
        self.records = []

    def as_text(self):
        """Render the full history as a human-readable text block, suitable
        for saving to a .txt file or displaying in a history panel."""
        if not self.records:
            return "No translations yet."
        lines = []
        for i, r in enumerate(self.records, start=1):
            lines.append(
                f"[{i}] {r['timestamp']}\n"
                f"    {r['source_lang']} -> {r['target_lang']}\n"
                f"    Source     : {r['source_text']}\n"
                f"    Translated : {r['translated_text']}\n"
                f"    Latency (s): recognition={r['recognition_time_s']} "
                f"translation={r['translation_time_s']} "
                f"tts={r['tts_time_s']} total={r['total_time_s']}\n"
            )
        return "\n".join(lines)

    def save_to_file(self, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.as_text())
