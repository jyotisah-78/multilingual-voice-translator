"""
gui.py
------
The Tkinter front-end. Responsible ONLY for layout and wiring user actions
to background threads - all the actual speech/translation/TTS work lives in
speech_recognition_module.py, translator.py and text_to_speech.py so this
file stays easy to read.

Threading model
----------------
Every operation that can block (microphone listening, network calls) runs
in a background `threading.Thread`. Background threads never touch Tkinter
widgets directly - instead they put small dict "messages" onto a
`queue.Queue`, and the GUI thread drains that queue every 100 ms via
`root.after(...)`. This keeps the window responsive and avoids the
Tk "not thread-safe" pitfalls.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import speech_recognition_module as stt
import translator as mt
import text_to_speech as tts
from utils import LANGUAGE_NAMES, LANGUAGES, TranslationHistory, get_logger

logger = get_logger()


class VoiceTranslatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI-Based Real-Time Multilingual Voice Translator")
        self.root.geometry("900x680")
        self.root.minsize(820, 620)

        self.event_queue = queue.Queue()
        self.history = TranslationHistory()

        self.is_listening = False          # continuous-listen loop flag
        self.busy = False                  # true while any background op runs
        self.last_audio_path = None        # for "Replay" button
        self.auto_speak = tk.BooleanVar(value=True)

        self._build_widgets()
        self._poll_queue()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = ttk.Frame(self.root, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(
            header, text="AI-Based Real-Time Multilingual Voice Translator",
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left")

        # ---- Language selection row -----------------------------------
        lang_frame = ttk.Frame(self.root, padding=(16, 4))
        lang_frame.pack(fill="x")

        ttk.Label(lang_frame, text="Source Language:").grid(row=0, column=0, sticky="w")
        self.source_lang = tk.StringVar(value="English")
        ttk.Combobox(
            lang_frame, textvariable=self.source_lang, values=LANGUAGE_NAMES,
            state="readonly", width=16,
        ).grid(row=0, column=1, padx=(6, 24))

        ttk.Button(lang_frame, text="\u21c4 Swap", command=self._swap_languages, width=8).grid(
            row=0, column=2, padx=(0, 24)
        )

        ttk.Label(lang_frame, text="Target Language:").grid(row=0, column=3, sticky="w")
        self.target_lang = tk.StringVar(value="Hindi")
        ttk.Combobox(
            lang_frame, textvariable=self.target_lang, values=LANGUAGE_NAMES,
            state="readonly", width=16,
        ).grid(row=0, column=4, padx=(6, 0))

        # ---- Control buttons row ---------------------------------------
        btn_frame = ttk.Frame(self.root, padding=(16, 8))
        btn_frame.pack(fill="x")

        self.start_btn = ttk.Button(btn_frame, text="\u25cf Start Listening", command=self.start_listening)
        self.start_btn.pack(side="left", padx=(0, 8))

        self.stop_btn = ttk.Button(btn_frame, text="\u25a0 Stop Listening", command=self.stop_listening, state="disabled")
        self.stop_btn.pack(side="left", padx=(0, 8))

        self.translate_btn = ttk.Button(btn_frame, text="Translate", command=self.manual_translate)
        self.translate_btn.pack(side="left", padx=(0, 8))

        self.speak_btn = ttk.Button(btn_frame, text="\U0001f50a Speak Translation", command=self.speak_translation)
        self.speak_btn.pack(side="left", padx=(0, 8))

        self.replay_btn = ttk.Button(btn_frame, text="\u21bb Replay", command=self.replay_translation)
        self.replay_btn.pack(side="left", padx=(0, 8))

        ttk.Checkbutton(btn_frame, text="Auto-speak", variable=self.auto_speak).pack(side="left", padx=(8, 0))

        # ---- Recognized text panel --------------------------------------
        rec_frame = ttk.LabelFrame(self.root, text="Recognized Speech / Text", padding=8)
        rec_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.recognized_text = tk.Text(rec_frame, height=6, wrap="word", font=("Segoe UI", 11))
        self.recognized_text.pack(fill="both", expand=True)
        self.recognized_text.bind("<KeyRelease>", lambda e: self._update_counts())
        self.recognized_text.bind("<Command-Return>", lambda e: (self.manual_translate(), "break")[1])
        self.recognized_text.bind("<Control-Return>", lambda e: (self.manual_translate(), "break")[1])

        self.recognized_count_lbl = ttk.Label(rec_frame, text="0 words / 0 characters")
        self.recognized_count_lbl.pack(anchor="e", pady=(2, 0))

        # ---- Translated text panel ---------------------------------------
        trans_frame = ttk.LabelFrame(self.root, text="Translated Text", padding=8)
        trans_frame.pack(fill="both", expand=True, padx=16, pady=(4, 4))
        self.translated_text = tk.Text(trans_frame, height=6, wrap="word", font=("Segoe UI", 11))
        self.translated_text.pack(fill="both", expand=True)

        self.translated_count_lbl = ttk.Label(trans_frame, text="0 words / 0 characters")
        self.translated_count_lbl.pack(anchor="e", pady=(2, 0))

        # ---- Secondary action buttons -------------------------------------
        action_frame = ttk.Frame(self.root, padding=(16, 4))
        action_frame.pack(fill="x")
        ttk.Button(action_frame, text="Copy Translation", command=self.copy_translation).pack(side="left", padx=(0, 8))
        ttk.Button(action_frame, text="Save Translation", command=self.save_translation).pack(side="left", padx=(0, 8))
        ttk.Button(action_frame, text="View History", command=self.view_history).pack(side="left", padx=(0, 8))
        ttk.Button(action_frame, text="Clear / Reset", command=self.clear_all).pack(side="left", padx=(0, 8))

        # ---- Status bar + progress + latency ------------------------------
        status_frame = ttk.Frame(self.root, padding=(16, 6))
        status_frame.pack(fill="x", side="bottom")

        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=140)
        self.progress.pack(side="right")

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(status_frame, textvariable=self.status_var, font=("Segoe UI", 10, "italic")).pack(side="left")

        self.latency_var = tk.StringVar(value="")
        ttk.Label(status_frame, textvariable=self.latency_var, font=("Segoe UI", 9)).pack(side="left", padx=(20, 0))

    # ------------------------------------------------------------------
    # Small helpers
    # ------------------------------------------------------------------
    def _lang_codes(self):
        src = LANGUAGES[self.source_lang.get()]
        tgt = LANGUAGES[self.target_lang.get()]
        return src, tgt

    def _swap_languages(self):
        s, t = self.source_lang.get(), self.target_lang.get()
        self.source_lang.set(t)
        self.target_lang.set(s)

    def _update_counts(self):
        rec = self.recognized_text.get("1.0", "end").strip()
        trans = self.translated_text.get("1.0", "end").strip()
        self.recognized_count_lbl.config(
            text=f"{len(rec.split()) if rec else 0} words / {len(rec)} characters"
        )
        self.translated_count_lbl.config(
            text=f"{len(trans.split()) if trans else 0} words / {len(trans)} characters"
        )

    def _set_busy(self, busy, status=None):
        self.busy = busy
        if status:
            self.status_var.set(status)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _post(self, **kwargs):
        """Thread-safe: push an update from a worker thread to the GUI queue."""
        self.event_queue.put(kwargs)

    # ------------------------------------------------------------------
    # Start / Stop continuous listening
    # ------------------------------------------------------------------
    def start_listening(self):
        if self.is_listening:
            return
        self.is_listening = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.status_var.set("Listening... Speak into your microphone.")
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop_listening(self):
        self.is_listening = False
        self.stop_btn.config(state="disabled")
        self.start_btn.config(state="normal")
        self.status_var.set("Stopped listening.")

    def _listen_loop(self):
        src, tgt = self._lang_codes()
        first_phrase = True
        while self.is_listening:
            self._post(status=f"Listening ({self.source_lang.get()})... Speak now", busy=True)
            text, error, rec_time = stt.recognize_speech(src["sr"], timeout=6, phrase_time_limit=15)

            if not self.is_listening:
                break  # user pressed Stop while we were listening

            if error:
                # If it was just silence/timeout, continue listening smoothly
                if "No speech detected" in error:
                    self._post(status="Listening... (Speak anytime)", busy=True, latency=f"recognition={rec_time}s")
                else:
                    self._post(status=error, busy=False, latency=f"recognition={rec_time}s")
                continue  # keep listening for the next phrase

            # Immediately display the recognized speech in real time
            self._post(
                recognized=text,
                append=(not first_phrase),
                status=f"Recognized! Translating to {self.target_lang.get()}...",
                busy=True
            )
            translated, t_error, t_time = mt.translate_text(text, src["translate"], tgt["translate"])

            if t_error:
                self._post(status=t_error, busy=False,
                           latency=f"recognition={rec_time}s translation={t_time}s")
                continue

            tts_time = 0.0
            if self.auto_speak.get():
                self._post(status="Speaking translation...", busy=True)
                _, s_error, tts_time = tts.speak_text(translated, tgt["tts"])
                if s_error:
                    self._post(status=s_error, busy=False)

            self._post(
                translated=translated,
                append=(not first_phrase),
                status="Listening... Speak next phrase (or click Stop)" if self.is_listening else "Ready.",
                busy=self.is_listening,
                latency=(
                    f"recognition={rec_time}s  translation={t_time}s  "
                    f"tts={tts_time}s  total={round(rec_time + t_time + tts_time, 3)}s"
                ),
                history=(self.source_lang.get(), self.target_lang.get(), text, translated,
                         rec_time, t_time, tts_time),
            )
            first_phrase = False

        self._post(status="Stopped.", busy=False)

    # ------------------------------------------------------------------
    # Manual actions
    # ------------------------------------------------------------------
    def manual_translate(self):
        if self.busy:
            return
        text = self.recognized_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to translate", "Type or recognize some text first.")
            return
        src, tgt = self._lang_codes()
        self._set_busy(True, "Translating...")
        threading.Thread(target=self._manual_translate_worker, args=(text, src, tgt), daemon=True).start()

    def _manual_translate_worker(self, text, src, tgt):
        translated, error, t_time = mt.translate_text(text, src["translate"], tgt["translate"])
        if error:
            self._post(status=error, busy=False)
            return
        self._post(
            translated=translated, status="Ready.", busy=False,
            latency=f"translation={t_time}s",
            history=(self.source_lang.get(), self.target_lang.get(), text, translated, 0.0, t_time, 0.0),
        )

    def speak_translation(self):
        text = self.translated_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to speak", "There is no translated text yet.")
            return
        tgt = LANGUAGES[self.target_lang.get()]
        self._set_busy(True, "Speaking...")
        threading.Thread(target=self._speak_worker, args=(text, tgt["tts"]), daemon=True).start()

    def _speak_worker(self, text, lang_code):
        path, error, elapsed = tts.speak_text(text, lang_code, keep_file=True)
        if error:
            self._post(status=error, busy=False)
            return
        if self.last_audio_path:
            tts.cleanup_audio_file(self.last_audio_path)
        self.last_audio_path = path
        self._post(status="Ready.", busy=False, latency=f"tts={elapsed}s")

    def replay_translation(self):
        if not self.last_audio_path:
            messagebox.showinfo("Nothing to replay", "Speak a translation first.")
            return
        self._set_busy(True, "Replaying...")
        threading.Thread(target=self._replay_worker, daemon=True).start()

    def _replay_worker(self):
        error = tts.replay_audio(self.last_audio_path)
        self._post(status=error or "Ready.", busy=False)

    # ------------------------------------------------------------------
    # Utility actions
    # ------------------------------------------------------------------
    def copy_translation(self):
        text = self.translated_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to copy", "There is no translated text yet.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Translation copied to clipboard.")

    def save_translation(self):
        text = self.translated_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo("Nothing to save", "There is no translated text yet.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text file", "*.txt")],
            initialfile="translation.txt",
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self.status_var.set(f"Saved to {path}")

    def view_history(self):
        win = tk.Toplevel(self.root)
        win.title("Translation History")
        win.geometry("560x420")
        text_widget = tk.Text(win, wrap="word", font=("Segoe UI", 10))
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert("1.0", self.history.as_text())
        text_widget.config(state="disabled")

        btn_row = ttk.Frame(win, padding=8)
        btn_row.pack(fill="x")
        ttk.Button(
            btn_row, text="Export History to File",
            command=lambda: self._export_history(),
        ).pack(side="left")

    def _export_history(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text file", "*.txt")],
            initialfile="translation_history.txt",
        )
        if path:
            self.history.save_to_file(path)
            self.status_var.set(f"History exported to {path}")

    def clear_all(self):
        self.recognized_text.delete("1.0", "end")
        self.translated_text.delete("1.0", "end")
        self._update_counts()
        self.status_var.set("Cleared.")
        self.latency_var.set("")

    # ------------------------------------------------------------------
    # Queue polling - the ONLY place worker-thread results touch widgets
    # ------------------------------------------------------------------
    def _poll_queue(self):
        try:
            while True:
                msg = self.event_queue.get_nowait()

                if "busy" in msg:
                    self._set_busy(msg["busy"], msg.get("status"))
                elif "status" in msg:
                    self.status_var.set(msg["status"])

                if "recognized" in msg:
                    if msg.get("append"):
                        current = self.recognized_text.get("1.0", "end-1c").strip()
                        new_content = f"{current}\n{msg['recognized']}" if current else msg["recognized"]
                        self.recognized_text.delete("1.0", "end")
                        self.recognized_text.insert("1.0", new_content)
                    else:
                        self.recognized_text.delete("1.0", "end")
                        self.recognized_text.insert("1.0", msg["recognized"])
                    self.recognized_text.see("end")

                if "translated" in msg:
                    if msg.get("append"):
                        current = self.translated_text.get("1.0", "end-1c").strip()
                        new_content = f"{current}\n{msg['translated']}" if current else msg["translated"]
                        self.translated_text.delete("1.0", "end")
                        self.translated_text.insert("1.0", new_content)
                    else:
                        self.translated_text.delete("1.0", "end")
                        self.translated_text.insert("1.0", msg["translated"])
                    self.translated_text.see("end")

                if "latency" in msg:
                    self.latency_var.set(msg["latency"])

                if "history" in msg:
                    self.history.add(*msg["history"])

                self._update_counts()

        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)

    def on_close(self):
        self.is_listening = False
        if self.last_audio_path:
            tts.cleanup_audio_file(self.last_audio_path)
        self.root.destroy()
