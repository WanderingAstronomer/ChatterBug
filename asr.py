"""Minimal ASR stub.

`transcribe_wav(wav_bytes: bytes, lang: str='en') -> (text, meta)`
returns a placeholder transcription and a metadata dict.
"""
import time

def transcribe_wav(wav_bytes: bytes, lang: str = "en"):
    start = time.time()
    # placeholder implementation
    text = "[transcription placeholder]"
    meta = {
        "engine": "stub",
        "model": "none",
        "dur_s": 0.0,
        "load_ms": int((time.time() - start) * 1000),
        "mem_mb": 0,
        "rtf": 0.0,
        "lang": lang,
    }
    return text, meta
