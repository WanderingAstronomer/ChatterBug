"""Storage helpers for ChatterBug.

Provides atomic `append_transcript(text, meta, base_dir=None)` which appends a
<t> entry into `transcripts.xml` under `~/.chatterbug` by default.
"""
from pathlib import Path
import os
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional


def _ensure_base(base_dir: Path) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def append_transcript(text: str, meta: dict, base_dir: Optional[Path] = None) -> Path:
    if base_dir is None:
        base_dir = Path.home() / ".chatterbug"
    base_dir = _ensure_base(Path(base_dir))
    target = base_dir / "transcripts.xml"

    if target.exists():
        tree = ET.parse(target)
        root = tree.getroot()
    else:
        root = ET.Element("transcripts")

    attrs = {
        "at": datetime.utcnow().isoformat() + "Z",
        "engine": str(meta.get("engine", "")),
        "model": str(meta.get("model", "")),
        "lang": str(meta.get("lang", "en")),
        "dur_s": str(meta.get("dur_s", "")),
    }
    t = ET.SubElement(root, "t", attrib=attrs)
    t.text = text

    fd, tmp_path = tempfile.mkstemp(dir=str(base_dir))
    os.close(fd)
    tmp = Path(tmp_path)
    ET.ElementTree(root).write(tmp, encoding="utf-8", xml_declaration=True)
    os.replace(str(tmp), str(target))
    return target
