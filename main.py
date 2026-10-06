"""
main.py
-------
Entry point for the AI-Based Real-Time Multilingual Voice Translator.

Run with:  python main.py
"""

import tkinter as tk

from gui import VoiceTranslatorApp
from utils import get_logger

logger = get_logger()


def main():
    root = tk.Tk()
    app = VoiceTranslatorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    logger.info("Application started.")
    root.mainloop()
    logger.info("Application closed.")


if __name__ == "__main__":
    main()
