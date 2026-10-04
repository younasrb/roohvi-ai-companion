"""
Nazar — the app's camera ("nazar" = sight / gaze).

The user is in charge of it, always:
  * It is OFF every time the app starts. Only the NAZAR button in Settings turns it on.
  * Even when ON it takes ONE still photo, and only when the user asks to be looked at
    (or says yes after the assistant offers). There is no video, no background capture.
  * The exact photo that is sent is shown on screen so the user can see it.
  * Nothing is written to disk. The photo exists in memory just long enough to be sent
    to the Gemini API with the next message.
  * It switches itself off after 30 minutes, and the user can switch it off any time.
"""
from __future__ import annotations

import io
import time

_state = {"enabled": False, "since": 0.0, "last": 0.0, "count": 0}
_pending = None                      # (jpeg_bytes, mime, question, "camera")

MIN_GAP_S      = 8.0                 # at least this long between two photos
MAX_PER_ON     = 12                  # photos per time the user switches Nazar on
AUTO_OFF_S     = 30 * 60
MAX_W, MAX_H   = 640, 480            # small on purpose: less data leaves the machine
JPEG_QUALITY   = 80


# ── state (called from the UI thread and from tool threads) ─────────────────
def is_enabled() -> bool:
    if _state["enabled"] and time.monotonic() - _state["since"] > AUTO_OFF_S:
        _state["enabled"] = False
    return bool(_state["enabled"])


def set_enabled(on: bool) -> None:
    _state["enabled"] = bool(on)
    if on:
        _state.update(since=time.monotonic(), last=0.0, count=0)


def take_pending():
    """main.py collects the frame here after the tool response was sent."""
    global _pending
    p, _pending = _pending, None
    return p


# ── capture ──────────────────────────────────────────────────────────────────
def _cfg() -> dict:
    try:
        from memory.config_manager import load_api_keys
        return load_api_keys() or {}
    except Exception:
        return {}


def _capture() -> tuple[bytes, str]:
    try:
        import cv2
    except Exception:
        raise RuntimeError("Camera support is not installed (pip install opencv-python).")
    cfg = _cfg()
    os_name = str(cfg.get("os_system", "windows")).lower()
    backend = cv2.CAP_DSHOW if os_name == "windows" else cv2.CAP_AVFOUNDATION if os_name == "mac" else cv2.CAP_ANY
    first = int(cfg.get("camera_index", 0))
    frame = None
    for idx in dict.fromkeys([first, 0, 1, 2]):
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue
        for _ in range(8):                       # let auto-exposure settle
            cap.read()
        ok, f = cap.read()
        cap.release()                            # the camera is released right away
        if ok and f is not None and f.mean() > 6:
            frame = f
            break
    if frame is None:
        raise RuntimeError("No camera could be opened. It may be in use by another app, or blocked in the system privacy settings.")
    h, w = frame.shape[:2]
    scale = min(MAX_W / w, MAX_H / h, 1.0)
    if scale < 1.0:
        frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise RuntimeError("Could not encode the photo.")
    return buf.tobytes(), "image/jpeg"


# ── the tool ─────────────────────────────────────────────────────────────────
def nazar(parameters: dict, player=None) -> str:
    global _pending
    question = str((parameters or {}).get("what_to_notice", "")).strip() or \
        "Gently describe what you can see, only what is plainly visible."

    if not is_enabled():
        return ("Nazar (the camera) is OFF, so you cannot see the user. Do NOT take or imply a look. If they asked to be seen, "
                "tell them kindly that they can switch Nazar on with the NAZAR button in Settings whenever they want, "
                "and that it is entirely their choice. Do not ask again if they decline.")
    now = time.monotonic()
    if _state["count"] >= MAX_PER_ON:
        return "Nazar has reached its limit of photos for this time it was switched on. Say so kindly; the user can switch it off and on to continue."
    if now - _state["last"] < MIN_GAP_S:
        return "A photo was just taken a moment ago. Use that one, or wait a few seconds."

    try:
        jpeg, mime = _capture()
    except Exception as e:
        return f"Nazar could not take a photo: {e}. Tell the user simply and kindly, and carry on without it."

    _state["last"], _state["count"] = now, _state["count"] + 1
    _pending = (jpeg, mime, question, "camera")
    if player:
        try:
            player.show_camera_frame(jpeg)       # the user sees exactly what is being sent
            player.write_log("SYS: Nazar took ONE still photo for this moment. It is not saved.")
        except Exception:
            pass
    return ("One still photo is arriving with the next message. Look at it with care and RESPECT: describe only what is plainly "
            "visible, in a sentence or two. You may gently offer ONE observation as a QUESTION the user can correct (for example "
            "'you look a bit tired, is that right?'). Never state their feelings or health as fact, never diagnose, never comment on "
            "appearance or body, and never identify anyone. Do not say you will keep watching: it was one photo, not saved.")


TOOL = {
    "name": "nazar",
    "description": (
        "Nazar is your camera: it lets you look at the user through the webcam with ONE still photo. Call it ONLY when the user "
        "asks you to look at or see them, or says yes after you offered. Never on your own, never to monitor. It works only if the "
        "user has switched Nazar on; if it is off, the tool tells you. what_to_notice is optional: what the user asked you to look at."),
    "parameters": {"type": "OBJECT", "properties": {
        "what_to_notice": {"type": "STRING", "description": "What the user wants you to look at or comment on (optional)"}},
        "required": []},
    "handler": nazar,
}
