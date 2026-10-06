"""DeepL API translation backend used by the GUI."""

import os
from pathlib import Path

import deepl
import requests
from dotenv import load_dotenv

from utils import Stopwatch, get_logger

logger = get_logger()
load_dotenv(Path(__file__).with_name(".env"))

MAX_CHARS = 4500


def _libretranslate_fallback(text, source_code, target_code):
    """Try one request against the configured LibreTranslate API."""
    endpoint = os.getenv(
        "LIBRETRANSLATE_URL", "http://127.0.0.1:5000/translate"
    ).strip()
    payload = {
        "q": text,
        "source": source_code.lower(),
        "target": target_code.lower(),
        "format": "text",
    }
    api_key = os.getenv("LIBRETRANSLATE_API_KEY", "").strip()
    if api_key:
        payload["api_key"] = api_key

    try:
        response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        translated = response.json().get("translatedText")
        if not translated:
            return None, "LibreTranslate returned an empty result."
        return translated, None
    except requests.RequestException as exc:
        logger.error("LibreTranslate fallback request failed: %s", exc)
        return None, f"LibreTranslate is unreachable at {endpoint}. Start the local server or check the configured URL."
    except (ValueError, TypeError, AttributeError) as exc:
        logger.error("Invalid LibreTranslate fallback response: %s", exc)
        return None, "LibreTranslate returned an invalid response."


def _fallback_error(text, source_code, target_code, primary_error):
    translated, fallback_error = _libretranslate_fallback(
        text, source_code, target_code
    )
    if translated:
        logger.warning("DeepL unavailable; LibreTranslate fallback succeeded.")
        return translated, None
    return None, f"{primary_error} {fallback_error}"


def translate_text(text, source_code, target_code):
    """
    Translate `text` from `source_code` to `target_code`.

    Returns
    -------
    (translated_text, error, elapsed_seconds)
    """
    watch = Stopwatch().start()

    if not text or not text.strip():
        return None, "Nothing to translate: input text is empty.", watch.elapsed()

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS]
        logger.info("Input text truncated to %d characters before translation.", MAX_CHARS)

    if source_code == target_code:
        # Same language selected on both sides - nothing meaningful to do.
        return text, None, watch.elapsed()

    api_key = os.getenv("TRANSLATION_API_KEY", "").strip()
    if not api_key or api_key == "PASTE_YOUR_REAL_KEY_HERE":
        translated, fallback_error = _libretranslate_fallback(
            text, source_code, target_code
        )
        if translated:
            logger.warning("DeepL API key missing; LibreTranslate fallback succeeded.")
            return translated, None, watch.elapsed()
        message = (
            "DeepL API key is missing, and the LibreTranslate fallback failed. "
            f"{fallback_error}"
        )
        logger.error(message)
        return None, message, watch.elapsed()

    try:
        client = deepl.DeepLClient(api_key)
        result = client.translate_text(
            text,
            source_lang=source_code.upper(),
            target_lang=target_code.upper(),
        )
        translated = result.text
        if not translated:
            return None, "Translation returned an empty result. Please try again.", watch.elapsed()
        return translated, None, watch.elapsed()

    except deepl.AuthorizationException as exc:
        logger.error("DeepL API key was rejected: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            "The DeepL API key was rejected. Check the key in .env.",
        )
        return translated, error, watch.elapsed()

    except deepl.QuotaExceededException as exc:
        logger.error("DeepL API quota exceeded: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            "The DeepL free translation quota has been reached.",
        )
        return translated, error, watch.elapsed()

    except deepl.TooManyRequestsException as exc:
        logger.error("DeepL API rate limit reached: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            "DeepL is temporarily rate-limiting requests.",
        )
        return translated, error, watch.elapsed()

    except deepl.DeepLException as exc:
        logger.error("DeepL translation error: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            f"DeepL could not translate this text: {exc}",
        )
        return translated, error, watch.elapsed()

    except ConnectionError as exc:
        logger.error("Connection error during DeepL translation: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            "Could not reach DeepL. Check your internet connection.",
        )
        return translated, error, watch.elapsed()

    except Exception as exc:  # pragma: no cover - safety net
        logger.error("Unexpected translation error: %s", exc)
        translated, error = _fallback_error(
            text, source_code, target_code,
            f"Unexpected DeepL translation error: {exc}",
        )
        return translated, error, watch.elapsed()
