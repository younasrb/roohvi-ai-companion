"""
Build the talking-photo avatar assets from any portrait.

    python tools/make_avatar.py path/to/photo.jpg

Writes assets/avatar/photo.jpg  (4:5 head-and-shoulders crop)
       assets/avatar/face.json  (mouth / jaw / eye landmarks in crop pixels)

Run this in a throw-away virtual environment -- it needs OpenCV *contrib*
(for the facial-landmark module), which must not be installed next to the
regular opencv-python that MARK LIV itself uses:

    python -m venv .avatar-venv
    .avatar-venv/bin/pip install opencv-contrib-python numpy      # Windows: .avatar-venv\\Scripts\\pip
    .avatar-venv/bin/python tools/make_avatar.py my_photo.jpg

The two detector models (~57 MB) are downloaded once to tools/.models/.
Use a sharp, front-facing photo with a neutral, closed mouth and eyes open.
The photo never leaves your machine.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
MODELS = HERE / ".models"

LBF_URL = "https://raw.githubusercontent.com/kurnianggoro/GSOC2017/master/data/lbfmodel.yaml"
HAAR_URL = ("https://raw.githubusercontent.com/opencv/opencv/4.x/data/"
            "haarcascades/haarcascade_frontalface_default.xml")


def _fetch(url: str, dest: Path) -> Path:
    if dest.is_file() and dest.stat().st_size > 10_000:
        return dest
    MODELS.mkdir(parents=True, exist_ok=True)
    print(f"downloading {dest.name} ...")
    urllib.request.urlretrieve(url, dest)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("photo", help="portrait image (jpg/png)")
    ap.add_argument("--out", default=str(ROOT / "assets" / "avatar"), help="output folder")
    args = ap.parse_args()

    try:
        import cv2
        import numpy as np
        if not hasattr(cv2, "face"):
            raise ImportError("cv2.face missing")
    except ImportError:
        print("This tool needs opencv-contrib-python and numpy (see the header of this file).")
        return 2

    img = cv2.imread(args.photo, cv2.IMREAD_COLOR)
    if img is None:
        print("could not read", args.photo)
        return 1
    H, W = img.shape[:2]

    casc = cv2.CascadeClassifier(str(_fetch(HAAR_URL, MODELS / "haar_face.xml")))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = casc.detectMultiScale(gray, 1.1, 5, minSize=(max(60, W // 8),) * 2)
    if len(faces) == 0:
        print("no face found -- use a clear, front-facing portrait")
        return 1
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])

    fm = cv2.face.createFacemarkLBF()
    fm.loadModel(str(_fetch(LBF_URL, MODELS / "lbfmodel.yaml")))
    ok, lms = fm.fit(img, np.array([[fx, fy, fw, fh]], dtype=np.int32))
    if not ok:
        print("landmark fit failed")
        return 1
    pts = np.array(lms[0], dtype=np.float32).reshape(-1, 2)          # 68 x 2

    # ── 4:5 head-and-shoulders crop, centred on the face ────────────────────
    crop_h = min(float(H), fh * 3.0)
    crop_w = crop_h * 0.8
    if crop_w > W:
        crop_w, crop_h = float(W), W / 0.8
    cxf = float(pts[0:17, 0].mean())
    x0 = int(round(min(max(0.0, cxf - crop_w / 2), W - crop_w)))
    y0 = int(round(min(max(0.0, fy - 0.345 * fh), H - crop_h)))
    cw, ch = int(round(crop_w)), int(round(crop_h))
    crop = img[y0:y0 + ch, x0:x0 + cw]
    pts = pts - np.array([x0, y0], dtype=np.float32)

    # ── landmarks the animator needs ────────────────────────────────────────
    inner = pts[60:68]
    mouth_y = float(inner[:, 1].mean())
    corner_l, corner_r = pts[48], pts[54]
    half_w = float(abs(corner_r[0] - corner_l[0]) / 2)
    mouth_cx = float((corner_l[0] + corner_r[0]) / 2)
    chin_lm = float(pts[8, 1])
    chin_y = chin_lm + 0.20 * (chin_lm - mouth_y)          # beard/chin bottom sits below the landmark
    jaw_half = float(abs(pts[13, 0] - pts[3, 0]) / 2)

    def eye(idx):
        e = pts[idx]
        return {"x0": round(float(e[:, 0].min()), 1), "y0": round(float(e[:, 1].min()), 1),
                "x1": round(float(e[:, 0].max()), 1), "y1": round(float(e[:, 1].max()), 1)}

    meta = {
        "version": 1,
        "size": [cw, ch],
        "mouth": {
            "cx": round(mouth_cx, 1), "y": round(mouth_y, 1), "half_width": round(half_w, 1),
            "chin_y": round(chin_y, 1), "jaw_half_width": round(jaw_half, 1),
        },
        "eyes": [eye(slice(36, 42)), eye(slice(42, 48))],
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / "photo.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    (out / "face.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"crop {cw}x{ch} -> {out}")
    print(json.dumps(meta["mouth"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
