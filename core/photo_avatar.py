"""
Photo avatar -- a real portrait that talks.

Drop-in alternative to HoloAvatar. It *inherits* HoloAvatar, so the mouth is
driven by exactly the same tuned model (viseme schedule -> jaw, lip spread,
blink, lids, idle sway) and can never drift out of sync with the audio; only
the rendering is different:

  * jaw      the lower face is warped downward (a per-column, monotone vertical
             remap with a tight ramp at the lip line and a gentle one at the
             cheeks, so the mouth parts without smearing the beard);
  * mouth    a soft dark cavity with upper teeth and a hint of tongue is
             composited into the gap and follows the lip-spread value;
  * eyes     eyelid skin is stretched over the eye for blinks, and partly for
             "thinking" / "sleeping" lids;
  * life     tiny head sway / breathing, and a status-coloured frame that glows
             with the voice.

All the heavy lifting is precomputed at load (remap tables for 17 jaw and 9 lid
levels); per frame it is one cv2.remap over a ~350x220 px patch, cached by
quantised pose, so it costs well under a millisecond on the UI thread.

Assets live in assets/avatar/ (photo.jpg + face.json) and are produced from any
portrait by tools/make_avatar.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter, QPainterPath, QPen, QPixmap

try:
    import cv2
except Exception:               # pragma: no cover -- optional at import time
    cv2 = None

from core.avatar import HoloAvatar

_JAW_LEVELS = 17
_EYE_LEVELS = 9
_JAW_QUANT = 48                 # distinct jaw poses that get rendered
_WIDE_QUANT = 6


def asset_dir() -> Path:
    base = (Path(sys.executable).parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent.parent)
    return base / "assets" / "avatar"


def is_available() -> bool:
    d = asset_dir()
    return cv2 is not None and (d / "photo.jpg").is_file() and (d / "face.json").is_file()


def _qimage(bgr: np.ndarray) -> QImage:
    # 4 bytes per pixel keeps every scanline 32-bit aligned, which Qt requires
    # (a 3-byte format corrupts patches whose width is not a multiple of 4).
    bgra = np.ascontiguousarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA))
    h, w = bgra.shape[:2]
    return QImage(bgra.data, w, h, w * 4, QImage.Format.Format_RGB32).copy()


def _smooth(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


class PhotoAvatar(HoloAvatar):
    """A portrait with a moving jaw, mouth interior, blinking eyes and life."""

    def __init__(self, folder: str | Path | None = None) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV is required for the photo avatar")
        super().__init__()
        d = Path(folder) if folder else asset_dir()
        meta = json.loads((d / "face.json").read_text(encoding="utf-8"))
        bgr = cv2.imread(str(d / "photo.jpg"), cv2.IMREAD_COLOR)
        if bgr is None:
            raise RuntimeError("photo.jpg could not be read")

        self._bgr = bgr
        self._ph, self._pw = bgr.shape[:2]
        self._aspect = self._pw / float(self._ph)
        self._base = QPixmap.fromImage(_qimage(bgr))
        self.SPAN = 2.3                       # height of the frame, in units of r
        self._muted = False
        self._speaking = False

        self._build_jaw(meta["mouth"])
        self._build_eyes(meta["eyes"])
        self._jaw_key = None
        self._jaw_img: QImage | None = None
        self._eye_key = None
        self._eye_imgs: list = []

    # ── precomputation ──────────────────────────────────────────────────────
    def _build_jaw(self, m: dict) -> None:
        cx, ym, hw = float(m["cx"]), float(m["y"]), float(m["half_width"])
        chin, jhw = float(m["chin_y"]), float(m["jaw_half_width"])
        neck = 2.4 * hw                                   # how far below the chin the pull fades out

        x0 = max(0, int(cx - 2.0 * jhw))
        x1 = min(self._pw, int(cx + 2.0 * jhw))
        y0 = max(0, int(ym - 0.6 * hw))
        y1 = min(self._ph, int(chin + neck + 8))
        self._mcx, self._mym, self._hw = cx, ym, hw
        self._jx0, self._jy0 = x0, y0
        self._jroi = np.ascontiguousarray(self._bgr[y0:y1, x0:x1])

        xs = np.arange(x0, x1, dtype=np.float32)
        ys = np.arange(y0, y1, dtype=np.float32)
        dx = xs - cx
        gj = np.exp(-(np.abs(dx) / (0.85 * jhw)) ** 3)              # jaw pull, wide and flat
        gc = np.exp(-(dx / (0.75 * hw)) ** 2)                       # 1 at the mouth, 0 at the cheeks
        ramp = 0.26 * hw + (1.05 * hw - 0.26 * hw) * (1.0 - gc)     # tight at lips, gentle at cheeks
        w_up = _smooth((ys[:, None] - ym) / ramp[None, :])
        w_dn = 1.0 - _smooth((ys[:, None] - chin) / neck)
        w = (w_up * w_dn).astype(np.float32)

        self._jaw_max = 0.42 * hw                                   # px of jaw drop at full open
        maps = []
        for k in range(_JAW_LEVELS):
            drop = self._jaw_max * k / (_JAW_LEVELS - 1)
            fwd = ys[:, None] + drop * gj[None, :] * w              # where each source row lands
            inv = np.empty_like(fwd)
            for c in range(fwd.shape[1]):                           # monotone -> exact inverse
                inv[:, c] = np.interp(ys, fwd[:, c], ys)
            maps.append((inv - y0).astype(np.float32))
        self._jmaps = maps
        self._jmap_x = np.tile((xs - x0).astype(np.float32), (len(ys), 1))
        self._jxs = (xs - x0).astype(np.float32)
        self._jys = (ys - y0).astype(np.float32)

    def _build_eyes(self, eyes: list) -> None:
        self._eyes = []
        for e in eyes:
            x0, y0, x1, y1 = float(e["x0"]), float(e["y0"]), float(e["x1"]), float(e["y1"])
            ew = max(10.0, x1 - x0)
            sk = max(4.0, 0.20 * ew)                                # skin band above the eye
            u, low = y0 - 0.5, y1 + 0.5                             # open-eye top / bottom edge
            rx0, rx1 = max(0, int(x0 - 0.18 * ew)), min(self._pw, int(x1 + 0.18 * ew) + 1)
            ry0, ry1 = max(0, int(u - sk - 5)), min(self._ph, int(low + 7))
            roi = np.ascontiguousarray(self._bgr[ry0:ry1, rx0:rx1])
            ys = np.arange(ry0, ry1, dtype=np.float32)
            xs = np.arange(rx0, rx1, dtype=np.float32)
            top = u - sk
            edge = _smooth(np.minimum(xs - rx0, rx1 - 1 - xs) / (0.24 * (rx1 - rx0))).astype(np.float32)
            maps, lashes = [], []
            for k in range(_EYE_LEVELS):
                c = k / (_EYE_LEVELS - 1)
                yd = u + c * (low - u)                              # where the lid edge ends up
                src = np.where(ys < top, ys,
                               np.where(ys < yd, top + (ys - top) * sk / max(yd - top, 1e-3), ys))
                # fade the warp to nothing at the patch's left/right edges so it
                # joins the untouched photo without a visible seam
                ident = (ys - ry0).astype(np.float32)[:, None]
                shift = ((src - ry0).astype(np.float32)[:, None] - ident)
                maps.append((ident + shift * edge[None, :]).astype(np.float32))
                # a soft lash line along the closed lid
                xp = np.clip((xs - x0) / ew, 0.0, 1.0)
                prof = np.clip(np.sin(np.pi * xp), 0.0, 1.0) ** 0.6   # sin(pi) can dip below 0 in float32
                yy = ys[:, None] - (yd + 0.2)
                lash = (np.exp(-(yy / 1.0) ** 2) * prof[None, :] * min(1.0, c * 1.6) * 0.6)
                lashes.append(lash.astype(np.float32))
            self._eyes.append({
                "x0": rx0, "y0": ry0, "roi": roi, "maps": maps, "lash": lashes,
                "mapx": np.tile((xs - rx0).astype(np.float32), (len(ys), 1)),
            })

    # ── per-frame animation state ───────────────────────────────────────────
    def step(self, dt, amp, speaking=False, muted=False, state="", **kw):
        self._muted = bool(muted)
        self._speaking = bool(speaking) and not self._muted
        super().step(dt, amp, speaking=speaking, muted=muted, state=state, **kw)

    def _closure(self) -> float:
        """0 = eyes open, 1 = shut. Blink plus the sleepy/thinking lid level."""
        blink = float(_smooth(np.float32(self._blink)))
        return max(blink, 1.0 - max(0.0, min(1.0, float(self._lids))))

    # ── rendering of the moving parts ───────────────────────────────────────
    def _jaw_image(self, open_: float, wide: float):
        q = int(round(max(0.0, min(1.0, open_)) * _JAW_QUANT))
        if q <= 0:
            return None
        wq = int(round(max(-1.0, min(1.0, wide)) * _WIDE_QUANT))
        key = (q, wq)
        if key == self._jaw_key:
            return self._jaw_img
        o = q / float(_JAW_QUANT)
        kf = o * (_JAW_LEVELS - 1)
        k0 = int(kf)
        k1 = min(k0 + 1, _JAW_LEVELS - 1)
        a = kf - k0
        my = self._jmaps[k0] if a < 1e-3 else self._jmaps[k0] * (1.0 - a) + self._jmaps[k1] * a
        img = cv2.remap(self._jroi, self._jmap_x, my, cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE)
        drop = self._jaw_max * o
        if drop >= 1.6:
            img = self._cavity(img, drop, wq / float(_WIDE_QUANT))
        self._jaw_key, self._jaw_img = key, _qimage(img)
        return self._jaw_img

    def _cavity(self, img: np.ndarray, drop: float, wide: float) -> np.ndarray:
        """Composite the inside of the mouth into the gap the jaw drop opened."""
        H, W = img.shape[:2]
        cxr = self._mcx - self._jx0
        cyr = self._mym - self._jy0
        h = 0.92 * drop * (1.0 - 0.12 * wide)
        ax = 0.64 * self._hw * (1.0 + 0.32 * wide)
        ay = 0.5 * h + 0.5
        cy = cyr + 0.5 * h - 0.3

        mask = np.zeros((H, W), np.uint8)
        S = 4
        cv2.ellipse(mask, (int(round(cxr * (1 << S))), int(round(cy * (1 << S)))),
                    (int(round(ax * (1 << S))), int(round(ay * (1 << S)))),
                    0, 0, 360, 255, -1, cv2.LINE_AA, S)
        alpha = cv2.GaussianBlur(mask, (0, 0), 0.9).astype(np.float32) / 255.0

        rows = np.arange(H, dtype=np.float32)
        t = np.clip((rows - (cy - ay)) / max(h, 1.0), 0.0, 1.0)         # 0 top of gap .. 1 bottom
        dark = np.array([30, 22, 46], np.float32)                       # BGR maroon-black
        teeth = np.array([214, 222, 232], np.float32)
        tongue = np.array([84, 72, 156], np.float32)
        ta = np.clip((drop - 3.0) / 5.0, 0.0, 1.0) * (1.0 - _smooth((t - 0.22) / 0.16))
        ga = np.clip((drop - 6.0) / 8.0, 0.0, 1.0) * _smooth((t - 0.55) / 0.35) * 0.55
        col = (dark[None, :] * (1.0 - ta - ga)[:, None]
               + teeth[None, :] * ta[:, None] + tongue[None, :] * ga[:, None])
        # the corners of the mouth sit in shadow
        xs = np.arange(W, dtype=np.float32)
        shade = 0.62 + 0.38 * np.clip(1.0 - ((xs - cxr) / max(ax, 1.0)) ** 2, 0.0, 1.0)
        cav = col[:, None, :] * shade[None, :, None]
        out = img.astype(np.float32) * (1.0 - alpha[..., None]) + cav * alpha[..., None]
        return np.clip(out, 0, 255).astype(np.uint8)

    def _eye_images(self, closure: float):
        k = int(round(max(0.0, min(1.0, closure)) * (_EYE_LEVELS - 1)))
        if k <= 0:
            return []
        if k == self._eye_key:
            return self._eye_imgs
        out = []
        for e in self._eyes:
            img = cv2.remap(e["roi"], e["mapx"], e["maps"][k], cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REPLICATE)
            lash = e["lash"][k][..., None]
            img = (img.astype(np.float32) * (1.0 - lash)
                   + np.array([22, 18, 18], np.float32) * lash)
            out.append((e["x0"], e["y0"], _qimage(np.clip(img, 0, 255).astype(np.uint8))))
        self._eye_key, self._eye_imgs = k, out
        return out

    # ── paint ───────────────────────────────────────────────────────────────
    def paint(self, p: QPainter, cx: float, cy: float, r: float,
              main: QColor, acc: QColor, bg: QColor) -> None:
        H = self.SPAN * r
        W = H * self._aspect
        rect = QRectF(cx - W / 2.0, cy - r, W, H)
        rad = min(W, H) * 0.055
        glow = 0.0 if self._muted else max(0.0, min(1.0, float(self._glow)))

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        # Status-coloured halo that breathes with the voice. While speaking it
        # takes the accent colour (matching the status pill); otherwise the
        # state colour (green listening, violet thinking...).
        ring = QColor(main if self._speaking else acc)
        n, step = 16, 1.5 + 1.6 * glow
        base = 0.020 + 0.055 * glow
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(n, 0, -1):
            spread = i * step
            c = QColor(ring)
            c.setAlpha(int(255 * base * (1.0 - (i - 1) / float(n)) ** 1.4))
            p.setBrush(QBrush(c))
            p.drawRoundedRect(rect.adjusted(-spread, -spread, spread, spread),
                              rad + spread, rad + spread)

        clip = QPainterPath()
        clip.addRoundedRect(rect, rad, rad)
        p.setClipPath(clip)
        p.fillRect(rect, bg)

        # idle life: a whisper of sway, breathing and where the eyes wander to
        zoom = 1.05 + 0.012 * glow
        k = (H / float(self._ph)) * zoom
        sx = float(self._yaw) * 9.0 + float(self._gaze[0]) * 2.2
        sy = float(self._pitch) * 30.0 + float(self._gaze[1]) * 1.6
        p.translate(rect.center().x(), rect.center().y())
        p.rotate(float(self._yaw) * 1.5)
        p.scale(k, k)
        p.translate(-self._pw / 2.0 + sx, -self._ph / 2.0 + sy)

        p.drawPixmap(0, 0, self._base)
        live_open = 0.0 if self._muted else float(self._mouth)
        jaw = self._jaw_image(live_open, float(self._wide))
        if jaw is not None:
            p.drawImage(self._jx0, self._jy0, jaw)
        for ex, ey, im in self._eye_images(self._closure()):
            p.drawImage(ex, ey, im)
        p.resetTransform()

        if self._muted:
            p.fillPath(clip, QColor(0, 0, 0, 96))
        p.setClipping(False)
        edge = QColor(ring)
        edge.setAlpha(150 if glow < 0.05 else 200)
        p.setPen(QPen(edge, 1.6))
        p.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        p.drawRoundedRect(rect, rad, rad)
        p.restore()
