"""
speech_recognition_module.py
-----------------------------
Wraps the `SpeechRecognition` library to capture microphone audio and
convert it to text using the free Google Web Speech API.

This module deliberately returns (result, error) tuples instead of raising
exceptions, so the GUI layer can show a friendly status message instead of
crashing.
"""

import os
import speech_recognition as sr
from utils import Stopwatch, get_logger

logger = get_logger()

# Ensure standard binary locations are in PATH so FLAC utility is found on macOS Apple Silicon / Intel
for _p in ["/opt/homebrew/bin", "/usr/local/bin"]:
    if _p not in os.environ.get("PATH", "").split(os.path.pathsep):
        os.environ["PATH"] = f"{_p}{os.path.pathsep}{os.environ.get('PATH', '')}"

# A single shared Recognizer keeps calibration (energy threshold) consistent
# across repeated calls in the same session.
_recognizer = sr.Recognizer()
_recognizer.dynamic_energy_threshold = True
_calibrated = False


def list_microphones():
    """Return the list of available input device names (useful for
    debugging 'wrong microphone' issues)."""
    try:
        return sr.Microphone.list_microphone_names()
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.error("Could not list microphones: %s", exc)
        return []


def recognize_speech(language_code, timeout=6, phrase_time_limit=15,
                      device_index=None):
    """
    Listen on the microphone and convert speech to text.

    Parameters
    ----------
    language_code : str
        Locale code understood by the Google Web Speech API, e.g. "en-IN".
    timeout : int
        Seconds to wait for speech to *start* before giving up.
    phrase_time_limit : int
        Maximum seconds a single phrase is allowed to run for.
    device_index : int or None
        Optional specific microphone device index.

    Returns
    -------
    (text, error, elapsed_seconds)
        `text` is the recognized string, or None if recognition failed.
        `error` is a short, user-friendly error message, or None on success.
    """
    global _calibrated
    watch = Stopwatch().start()

    try:
        with sr.Microphone(device_index=device_index) as source:
            # Adjust ambient noise once or calibrate smoothly
            if not _calibrated:
                _recognizer.adjust_for_ambient_noise(source, duration=0.5)
                _calibrated = True
            try:
                audio = _recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            except sr.WaitTimeoutError:
                return None, "No speech detected. Please try speaking again.", watch.elapsed()

    except OSError as exc:
        # Raised when no microphone is found or the OS denies access to it.
        logger.error("Microphone error: %s", exc)
        return None, (
            "Could not access the microphone. Check that it is connected "
            "and that the app has microphone permission."
        ), watch.elapsed()

    try:
        text = _recognizer.recognize_google(audio, language=language_code)
        if not text or not text.strip():
            return None, "Recognized empty speech. Please try again.", watch.elapsed()
        return text, None, watch.elapsed()

    except sr.UnknownValueError:
        return None, "Could not understand the audio. Please speak clearly and try again.", watch.elapsed()

    except sr.RequestError as exc:
        logger.error("Speech API request error: %s", exc)
        return None, (
            "Could not reach the speech recognition service. "
            "Check your internet connection."
        ), watch.elapsed()

    except Exception as exc:  # pragma: no cover - safety net
        logger.error("Unexpected recognition error: %s", exc)
        return None, f"Unexpected error during speech recognition: {exc}", watch.elapsed()
