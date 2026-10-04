"""
3D avatar -- a rigged GLB/VRM character rendered with three.js inside QtWebEngine.

    WebAvatar   inherits HoloAvatar, so the mouth is driven by the very same tuned
                lip-sync model as the hologram and the photo avatar (viseme
                schedule -> jaw, lip spread, blink, lids, gaze, head sway). It
                paints nothing itself; it just produces a small "pose" dict.
    StageView   the QWebEngineView that shows assets/avatar3d/viewer.html. It
                takes that pose ~30x a second and reports what it found in the
                model (blendshape style, blink support...).
    AssetServer a tiny read-only HTTP server bound to 127.0.0.1 that serves
                assets/avatar3d/ to the stage (ES modules and .wasm decoders can
                not be loaded from file:// reliably). Loopback only -- it is not
                reachable from the network.

The heavy imports are optional: without PyQt6-WebEngine, WEB_OK is False and the
app simply keeps using the photo / hologram avatar.

NOTE: QtWebEngine must be imported *before* the QApplication is created, so this
module is imported by ui.py at start-up.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QTimer, QUrl, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from core.avatar import HoloAvatar

# ── QtWebEngine bootstrap ────────────────────────────────────────────────────
_SOFTWARE_FLAGS = ["--disable-gpu-compositing", "--use-gl=angle", "--use-angle=swiftshader",
                   "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def _prepare_env() -> None:
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").split()
    if os.environ.get("MARK_WEBGL_SOFTWARE") == "1":            # no usable GPU / VM / remote desktop
        flags += _SOFTWARE_FLAGS
    if hasattr(os, "geteuid") and os.geteuid() == 0:            # Chromium refuses to sandbox as root
        flags.append("--no-sandbox")
    seen, out = set(), []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    if out:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(out)


WEB_OK = False
WEB_ERR = ""
QWebEngineView = object            # placeholders so the module always imports
QWebEnginePage = object
try:
    _prepare_env()
    if QCoreApplication.instance() is None:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    from PyQt6.QtWebEngineWidgets import QWebEngineView            # noqa: F811
    from PyQt6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings  # noqa: F811
    WEB_OK = True
except Exception as _e:            # pragma: no cover -- optional dependency
    WEB_ERR = str(_e)

WEB_INSTALL_HINT = "3D avatars need PyQt6-WebEngine:  pip install \"PyQt6-WebEngine>=6.6,<7\""


# ── paths ────────────────────────────────────────────────────────────────────
def asset_dir() -> Path:
    base = (Path(sys.executable).parent if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent.parent)
    return base / "assets" / "avatar3d"


def glb_path() -> Path:
    return asset_dir() / "avatar.glb"


def frame_path() -> Path:
    return asset_dir() / "avatar3d.json"


def stage_available() -> bool:
    """True when a custom 3D avatar can be shown: WebEngine present and a GLB installed."""
    return WEB_OK and glb_path().is_file() and (asset_dir() / "viewer.html").is_file()


def stage_ready() -> bool:
    """True when the 3D stage can run at all -- WebEngine present. A GLB is not required:
    without one the stage shows a built-in male/female character (see core/web_avatar.py loadProcedural)."""
    return WEB_OK and (asset_dir() / "viewer.html").is_file()


_VIEW_MODES = ("auto", "full", "bust", "head")


def load_frame() -> dict:
    try:
        d = json.loads(frame_path().read_text(encoding="utf-8"))
    except Exception:
        d = {}
    mode = d.get("mode", "auto")
    return {"zoom": float(d.get("zoom", 1.0)), "offsetY": float(d.get("offsetY", 0.0)),
            "mode": mode if mode in _VIEW_MODES else "auto"}


def save_frame(d: dict) -> None:
    """Merge zoom / offsetY / mode into the saved framing (missing keys keep their value)."""
    cur = load_frame()
    for k in ("zoom", "offsetY", "mode"):
        if k in d:
            cur[k] = d[k]
    try:
        frame_path().write_text(json.dumps(cur), encoding="utf-8")
    except Exception:
        pass


# ── loopback asset server ────────────────────────────────────────────────────
class _Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".js": "text/javascript", ".mjs": "text/javascript", ".wasm": "application/wasm",
                      ".glb": "model/gltf-binary", ".json": "application/json"}

    def log_message(self, *a, **k):            # silence the console
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):                          # no dot-files, no directory listings
        if any(seg.startswith(".") for seg in self.path.split("?")[0].split("/")):
            self.send_error(404)
            return
        super().do_GET()

    def list_directory(self, path):
        self.send_error(404)
        return None


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class AssetServer:
    _inst: "AssetServer | None" = None

    @classmethod
    def instance(cls) -> "AssetServer":
        if cls._inst is None:
            cls._inst = AssetServer()
        return cls._inst

    def __init__(self) -> None:
        handler = functools.partial(_Handler, directory=str(asset_dir()))
        self._srv = _Server(("127.0.0.1", 0), handler)        # loopback only
        self.port = self._srv.server_address[1]
        threading.Thread(target=self._srv.serve_forever, daemon=True, name="avatar3d-assets").start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}"


# ── the web stage widget ─────────────────────────────────────────────────────
class _Page(QWebEnginePage):
    message = pyqtSignal(str, dict)

    def javaScriptConsoleMessage(self, level, msg, line, source):     # noqa: N802
        if isinstance(msg, str) and msg.startswith("@@"):
            tag, _, payload = msg[2:].partition(" ")
            try:
                data = json.loads(payload) if payload else {}
            except Exception:
                data = {}
            self.message.emit(tag, data if isinstance(data, dict) else {})


class StageView(QWebEngineView):
    ready = pyqtSignal(dict)
    loaded = pyqtSignal(dict)
    failed = pyqtSignal(str)
    frame_changed = pyqtSignal(dict)

    _LOAD_TIMEOUT_MS = 40000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = _Page(self)
        self.setPage(self._page)
        self._page.setBackgroundColor(QColor("#070a0f"))
        self._page.message.connect(self._on_message)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        s = self.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.ShowScrollBars, False)
        s.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        self._ready = False
        self._done = False
        self._last_push = 0.0
        self._insets = (0, 0, 0, 0)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_timeout)

    # -- lifecycle -----------------------------------------------------------
    def start(self, low_quality: bool = False, gender: str | None = None, name: str = "") -> None:
        """gender ('male' | 'female') selects the built-in character and is used only when no
        custom GLB is installed; a custom GLB always takes precedence."""
        from urllib.parse import quote
        srv = AssetServer.instance()
        q = f"t={int(time.time())}"
        if glb_path().is_file():
            q += "&avatar=/avatar.glb"
        elif gender in ("male", "female"):
            q += f"&gender={gender}"
        if name:
            q += f"&name={quote(name)}"
        if low_quality or os.environ.get("MARK_WEBGL_SOFTWARE") == "1":
            q += "&quality=low"
        self.setUrl(QUrl(f"{srv.base}/viewer.html?{q}"))
        self._timer.start(self._LOAD_TIMEOUT_MS)

    def _on_timeout(self) -> None:
        if not self._done:
            self._done = True
            self.failed.emit("the 3D stage did not finish loading (WebGL may be unavailable)")

    def _fail(self, msg: str) -> None:
        if not self._done:
            self._done = True
            self._timer.stop()
            self.failed.emit(msg)

    def _on_message(self, tag: str, data: dict) -> None:
        if tag == "ready":
            self._ready = True
            self.set_insets(*self._insets)
            self.ready.emit(data)
        elif tag == "loaded":
            # Always emit -- not just on the very first load -- so a later gender switch
            # (set_gender -> loadProcedural) or a fresh loadAvatar() also notifies the host.
            if not self._done:
                self._done = True
                self._timer.stop()
            self.loaded.emit(data)
        elif tag in ("error", "fatal"):
            self._fail(str(data.get("msg", tag)))
        elif tag == "frame":
            self.frame_changed.emit(data)

    def shutdown(self) -> None:
        """Destroy the view (and its page) immediately -- call before the QApplication goes away."""
        self._timer.stop()
        self._ready = False
        self.hide()
        try:
            from PyQt6 import sip
            sip.delete(self)
        except Exception:
            self.deleteLater()

    # -- commands ------------------------------------------------------------
    def _js(self, code: str) -> None:
        if self._ready:
            self._page.runJavaScript(code)

    def set_frame(self, zoom: float, offset_y: float, mode: str | None = None) -> None:
        m = f",mode:'{mode}'" if mode in _VIEW_MODES else ""
        self._js(f"stage.setFrame({{zoom:{float(zoom):.4f},offsetY:{float(offset_y):.4f}{m}}})")

    def set_insets(self, top: int, bottom: int, left: int = 0, right: int = 0) -> None:
        """Tell the stage how much of the window is covered by floating panels (top/bottom/
        left/right) so the character is framed in the free band between them."""
        self._insets = (int(top), int(bottom), int(left), int(right))
        self._js(f"stage.setInsets({{top:{int(top)},bottom:{int(bottom)},left:{int(left)},right:{int(right)}}})")

    def set_gender(self, gender: str) -> None:
        """Switch the built-in character's gender live (no effect if a custom GLB is loaded)."""
        if gender in ("male", "female"):
            self._js(f"stage.loadProcedural('{gender}')")

    def set_theme(self, accent: str | None = None, bg0: str | None = None, bg1: str | None = None) -> None:
        d = {k: v for k, v in (("accent", accent), ("bg0", bg0), ("bg1", bg1)) if v}
        self._js(f"stage.setTheme({json.dumps(d)})")

    def demo(self, on: bool) -> None:
        self._js(f"stage.demo({'true' if on else 'false'})")

    def push_pose(self, pose: dict) -> None:
        """Called every animation tick; throttled to ~30 Hz."""
        if not self._ready:
            return
        now = time.monotonic()
        if now - self._last_push < 0.030:
            return
        self._last_push = now
        payload = json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in pose.items()},
                             separators=(",", ":"))
        self._page.runJavaScript(f"window.stage&&stage.setPose({payload})")


# ── the avatar object the HUD drives ─────────────────────────────────────────
def _clamp(v: float, a: float, b: float) -> float:
    return a if v < a else b if v > b else v


class WebAvatar(HoloAvatar):
    """Runs the shared lip-sync model and exposes the result as `pose` for the 3D stage."""

    IS_3D = True

    def __init__(self) -> None:
        super().__init__()
        self.SPAN = 2.3
        self.pose: dict = {}
        self._muted = False

    def step(self, dt, amp, speaking=False, muted=False, state="", **kw):
        self._muted = bool(muted)
        super().step(dt, amp, speaking=speaking, muted=muted, state=state, **kw)
        blink = _clamp(float(self._blink), 0.0, 1.0)
        blink = blink * blink * (3.0 - 2.0 * blink)
        lids = _clamp(float(self._lids), 0.0, 1.0)
        gx, gy = (float(self._gaze[0]), float(self._gaze[1])) if self._gaze else (0.0, 0.0)
        self.pose = {
            "o": 0.0 if self._muted else _clamp(float(self._mouth), 0.0, 1.0),
            "w": _clamp(float(self._wide), -1.0, 1.0),
            "c": max(blink, 1.0 - lids),
            "br": _clamp(float(self._brow), -0.4, 1.0),
            "gx": _clamp(gx, -1.0, 1.0),
            "gy": _clamp(gy, -1.0, 1.0),
            "yaw": float(self._yaw),
            "pitch": -float(self._pitch),          # holo: + = up ; three.js head bone: + = nod down
            "roll": 0.0,
            "lv": 0.0 if self._muted else _clamp(float(self._glow), 0.0, 1.0),
            "mu": self._muted,
        }

    def paint(self, *args, **kwargs) -> None:      # the web stage draws the character
        return
