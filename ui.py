"""Minimal Tkinter UI for ChatterBug (stub implementation).

Start/Stop UI that runs recording and ASR in background threads and updates UI
via `root.after()`.
"""
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

import audio
import asr
import storage


def _worker(root, text_widget, status_var, stop_event):
    status_var.set("Recording...")
    wav_bytes, dur = audio.record(stop_event=stop_event)
    status_var.set("Transcribing...")
    txt, meta = asr.transcribe_wav(wav_bytes, lang="en")
    storage.append_transcript(txt, {**meta, "dur_s": dur})

    def ui_update():
        text_widget.delete("1.0", tk.END)
        text_widget.insert(tk.END, txt)
        root.clipboard_clear()
        root.clipboard_append(txt)
        status_var.set("Idle")

    root.after(0, ui_update)


def run_ui():
    root = tk.Tk()
    root.title("ChatterBug (MVP stub)")
    status_var = tk.StringVar(value="Idle")
    text_widget = ScrolledText(root, height=10, width=60)
    text_widget.pack(padx=8, pady=8)

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=4)
    start_btn = tk.Button(btn_frame, text="Start")
    stop_btn = tk.Button(btn_frame, text="Stop")
    start_btn.pack(side="left", padx=4)
    stop_btn.pack(side="left", padx=4)

    status_label = tk.Label(root, textvariable=status_var)
    status_label.pack(pady=4)

    stop_event = None
    worker_thread = None

    def on_start():
        nonlocal stop_event, worker_thread
        if worker_thread and worker_thread.is_alive():
            return
        stop_event = threading.Event()
        worker_thread = threading.Thread(target=_worker, args=(root, text_widget, status_var, stop_event), daemon=True)
        worker_thread.start()

    def on_stop():
        nonlocal stop_event
        if stop_event:
            stop_event.set()

    start_btn.config(command=on_start)
    stop_btn.config(command=on_stop)

    root.mainloop()
