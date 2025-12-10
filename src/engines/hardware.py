try:
    import torch
except ImportError:  # Optional dependency; fall back to CPU if unavailable.
    torch = None

def get_optimal_device() -> str:
    if torch and torch.cuda.is_available():
        return "cuda"
    return "cpu"

def get_optimal_compute_type(device: str) -> str:
    if device == "cuda":
        return "float16"
    # For CPU, int8 is generally faster and good enough for Whisper
    return "int8"
