#!/usr/bin/env python3
"""
Personen-Erkennung fuer SpyPoint-Fotos (Diebstahlschutz)
========================================================

Prueft Fotos mit einem kleinen, lokal laufenden KI-Modell (YOLO11n als ONNX,
~10 MB, keine Cloud) darauf, ob ein Mensch zu sehen ist. Wird von
spypoint_download.py fuer jedes neu heruntergeladene Foto aufgerufen.

Fotos mit Person werden zusaetzlich nach spypoint-photos/personen/ kopiert;
nur dieser Ordner loest in Home Assistant eine Push-Warnung aus.

Modellpfad: Standard ~/spypoint-models/yolo11n.onnx, abweichend per
Umgebungsvariable SPYPOINT_MODEL. Wie das Modell erzeugt wird, steht im README.

Manuell testen:
    ~/spypoint-env/bin/python ~/spypoint_personen.py FOTO.jpg [FOTO2.jpg ...]
"""

import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MODEL_PATH = Path(os.environ.get("SPYPOINT_MODEL", Path.home() / "spypoint-models" / "yolo11n.onnx"))
INPUT_SIZE = 640
PERSON_CLASS = 0          # COCO-Klasse 0 = person
MIN_CONFIDENCE = 0.30     # ab dieser Sicherheit gilt es als Person (getestet an 83 Fotos: Menschen >= 0.32, leer <= 0.11)

_session = None


def _get_session():
    global _session
    if _session is None:
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 2   # Pi nicht ausbremsen
        _session = ort.InferenceSession(str(MODEL_PATH), opts, providers=["CPUExecutionProvider"])
    return _session


def _letterbox(img: Image.Image) -> np.ndarray:
    """Seitenverhaeltnis erhaltend auf 640x640 skalieren, Rand grau auffuellen."""
    img = img.convert("RGB")
    scale = INPUT_SIZE / max(img.size)
    new_size = (round(img.width * scale), round(img.height * scale))
    canvas = Image.new("RGB", (INPUT_SIZE, INPUT_SIZE), (114, 114, 114))
    canvas.paste(img.resize(new_size, Image.BILINEAR),
                 ((INPUT_SIZE - new_size[0]) // 2, (INPUT_SIZE - new_size[1]) // 2))
    arr = np.asarray(canvas, dtype=np.float32) / 255.0
    return arr.transpose(2, 0, 1)[np.newaxis]   # 1x3x640x640


def person_confidence(path) -> float:
    """Hoechste Sicherheit (0..1), mit der auf dem Foto ein Mensch erkannt wurde."""
    session = _get_session()
    with Image.open(path) as img:
        tensor = _letterbox(img)
    output = session.run(None, {session.get_inputs()[0].name: tensor})[0]  # 1x84x8400
    person_scores = output[0, 4 + PERSON_CLASS, :]
    return float(person_scores.max())


def has_person(path) -> bool:
    return person_confidence(path) >= MIN_CONFIDENCE


if __name__ == "__main__":
    for p in sys.argv[1:]:
        conf = person_confidence(p)
        print(f"{'PERSON' if conf >= MIN_CONFIDENCE else '------'}  {conf:5.2f}  {Path(p).name}")
