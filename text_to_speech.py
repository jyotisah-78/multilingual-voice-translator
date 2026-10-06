"""
text_to_speech.py
------------------
Converts translated text into speech using gTTS
and plays the generated MP3 using macOS built-in `afplay`.

No pygame required.
"""

import os
import subprocess
import tempfile
import time

from gtts import gTTS
from gtts.tts import gTTSError

from utils import Stopwatch, get_logger

logger = get_logger()


def speak_text(text, lang_code, keep_file=False):
    """
    Convert translated text to speech and play it.

    Returns:
        (audio_path_or_None, error, elapsed_seconds)
    """

    watch = Stopwatch().start()

    if not text or not text.strip():
        return (
            None,
            "Nothing to speak: translated text is empty.",
            watch.elapsed(),
        )

    tmp_path = None

    try:
        # Create temporary MP3 file
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".mp3",
            prefix="voice_translator_"
        )
        os.close(tmp_fd)

        # Generate speech
        tts = gTTS(
            text=text,
            lang=lang_code
        )

        tts.save(tmp_path)

        # Play using macOS built-in audio player
        _play_audio_file(tmp_path)

        if keep_file:
            return tmp_path, None, watch.elapsed()

        return None, None, watch.elapsed()

    except gTTSError as exc:
        logger.error("gTTS error: %s", exc)

        return (
            None,
            "Could not generate speech audio. "
            "Check your internet connection.",
            watch.elapsed(),
        )

    except Exception as exc:
        logger.error("Text-to-speech error: %s", exc)

        return (
            None,
            f"Unexpected error during text-to-speech: {exc}",
            watch.elapsed(),
        )

    finally:
        if tmp_path and not keep_file:
            _safe_delete(tmp_path)


def replay_audio(path):
    """
    Replay previously generated audio.
    """

    if not path or not os.path.exists(path):
        return "No previous translation audio is available to replay."

    try:
        _play_audio_file(path)
        return None

    except Exception as exc:
        logger.error("Replay error: %s", exc)
        return f"Could not replay audio: {exc}"


def cleanup_audio_file(path):
    """
    Delete a previously kept audio file.
    """

    if path:
        _safe_delete(path)


def _play_audio_file(path):
    """
    Play MP3 using macOS built-in afplay.
    """

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Audio file not found: {path}"
        )

    result = subprocess.run(
        ["afplay", path],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Audio playback failed: {result.stderr.strip()}"
        )


def _safe_delete(path):
    """
    Safely delete temporary audio file.
    """

    try:
        if path and os.path.exists(path):
            os.remove(path)

    except OSError as exc:
        logger.warning(
            "Could not delete temp audio file %s: %s",
            path,
            exc
        )