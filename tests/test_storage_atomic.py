import xml.etree.ElementTree as ET
from pathlib import Path

import storage


def test_append_transcript_creates_file(tmp_path):
    base = tmp_path / ".chatterbug"
    meta = {"engine": "t", "model": "m", "lang": "en", "dur_s": "1.2"}
    path = storage.append_transcript("hello world", meta, base_dir=base)
    assert path.exists()
    tree = ET.parse(path)
    root = tree.getroot()
    assert root.find("t") is not None
