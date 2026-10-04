"""
Local wake-word detection for Roohvi.

Design goals:
  • ZERO cost when the feature is off — openwakeword is imported ONLY inside
    start()/install helpers, never at module load. If the user never enables
    wake word, none of this touches the app.
  • ZERO latency on the audio path — the microphone callback only ever does a
    cheap, non-blocking queue push (feed()); the actual model inference runs in
    this module's own background thread, so the real-time audio thread and the
    Gemini stream are never slowed.
  • Fully local & offline — audio fed here never leaves the machine; there is no
    network call except the one-time model download the user triggers from the UI.

openwakeword ships small ONNX models (a few MB each) and runs comfortably on a
CPU.

WHICH PHRASE?  openWakeWord ships only a handful of stock phrases (alexa, hey_mycroft,
hey_jarvis, hey_marvin, timer, weather). A phrase of your own, such as "Hey Roohvi",
needs a model trained for it (see docs/WAKE_WORD.md, about an hour on a free Colab).
Resolution order:
  1. config "wake_model_path"           -> that .onnx/.tflite file
  2. models/wake/*.onnx|*.tflite        -> a file with 'roohvi' in its name first
  3. config "wake_model"                -> a stock model name (default FALLBACK_MODEL)
The phrase shown to the user comes from config "wake_phrase", else from the model.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

# Stock model used until a custom Roohvi model is dropped in (see above).
FALLBACK_MODEL = "hey_mycroft"
_PRETTY = {"hey_mycroft": "Hey Mycroft", "hey_jarvis": "Hey Jarvis", "hey_marvin": "Hey Marvin",
           "alexa": "Alexa", "timer": "Timer", "weather": "Weather"}


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


CUSTOM_DIR = _base_dir() / "models" / "wake"


def _cfg(key: str) -> str:
    try:
        from memory.config_manager import load_api_keys
        return str(load_api_keys().get(key) or "").strip()
    except Exception:
        return ""


def custom_model_path() -> Path | None:
    """A user-trained wake model on disk, or None."""
    p = _cfg("wake_model_path")
    if p and Path(p).is_file():
        return Path(p)
    if CUSTOM_DIR.is_dir():
        files = sorted(list(CUSTOM_DIR.glob("*.onnx")) + list(CUSTOM_DIR.glob("*.tflite")))
        for f in files:
            if "roohvi" in f.stem.lower():
                return f
        if files:
            return files[0]
    return None


def wake_model() -> str:
    """What to hand to openWakeWord: a file path (custom) or a stock model name."""
    c = custom_model_path()
    return str(c) if c else (_cfg("wake_model") or FALLBACK_MODEL)


def phrase() -> str:
    """The words the user should say, for every message and label in the app."""
    p = _cfg("wake_phrase")
    if p:
        return p
    c = custom_model_path()
    if c:
        return c.stem.replace("_", " ").replace("-", " ").title()
    name = wake_model()
    return _PRETTY.get(name, name.replace("_", " ").title())


# kept for older imports
WAKE_MODEL = FALLBACK_MODEL
# Score in [0,1]; above this counts as a detection. Tunable per environment.
DEFAULT_THRESHOLD = 0.5
# Mic frames arrive at 16 kHz int16; this is just the detector's input rate.
SAMPLE_RATE = 16000


def is_installed() -> bool:
    """True if the openwakeword package is importable (no model check)."""
    try:
        import importlib.util
        return importlib.util.find_spec("openwakeword") is not None
    except Exception:
        return False


def is_ready() -> bool:
    """True if openwakeword is installed AND its model files are present on disk.

    This is a cheap, DETERMINISTIC file-existence check. It deliberately does NOT
    construct a Model to probe readiness — doing that is slow and, worse, can clash
    with the detector's own Model when it's already running, which intermittently
    returned False and made the UI flicker to 'not downloaded'. Never raises.
    """
    if not is_installed():
        return False
    try:
        import openwakeword
        models_dir = Path(openwakeword.__file__).resolve().parent / "resources" / "models"
        if not models_dir.is_dir():
            return False
        if custom_model_path():
            has_wake = True            # the user's own file; only the feature models are needed
        else:
            name = wake_model()
            has_wake = (any(models_dir.glob(f"{name}*.onnx"))
                        or any(models_dir.glob(f"{name}*.tflite")))
        has_mel = (any(models_dir.glob("melspectrogram*.onnx"))
                   or any(models_dir.glob("melspectrogram*.tflite")))
        has_emb = (any(models_dir.glob("embedding_model*.onnx"))
                   or any(models_dir.glob("embedding_model*.tflite")))
        return bool(has_wake and has_mel and has_emb)
    except Exception:
        return False


def install_and_download(logger: Callable[[str], None] = print,
                         notify: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """
    One-click setup for the UI button: pip-install openwakeword if missing, then
    download the wake model. Returns (ok, message). Never raises — every failure
    is reported through the returned message and the logger.
    """
    _tell = notify or (lambda _msg: None)
    try:
        if not is_installed():
            logger("Wake word: installing openwakeword (one-time)…")
            _tell("Wake word: installing openwakeword (one-time)…")
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "openwakeword"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]
                return False, f"pip install failed: {tail[0][:160]}"
        # Download the pretrained melspectrogram/embedding + wake models.
        logger("Wake word: downloading models…")
        _tell("Wake word: downloading models…")
        try:
            import openwakeword.utils as _u
            try:
                # a custom model still needs the shared feature models, which come with any stock download
                _u.download_models([FALLBACK_MODEL if custom_model_path() else wake_model()])
            except TypeError:
                _u.download_models()   # older signature downloads the default set
        except Exception as e:
            return False, f"model download failed: {e}"

        if not is_ready():
            return False, "installed, but the wake model could not be loaded."
        logger("Wake word: ready.")
        return True, "Wake word installed and ready."
    except Exception as e:
        return False, f"setup error: {e}"


class WakeWordDetector:
    """
    Runs the wake model in a dedicated thread. The mic thread calls feed() with
    raw int16 frames; detections invoke on_detect() (called from this thread —
    the callback must marshal to whatever loop/UI it needs).
    """

    def __init__(self, on_detect: Callable[[], None],
                 threshold: float = DEFAULT_THRESHOLD,
                 logger: Callable[[str], None] = print,
                 notify: Callable[[str], None] | None = None):
        self._on_detect = on_detect
        self._threshold = threshold
        self._logger    = logger
        # See PluginRegistry: `logger` is the console and gets everything,
        # `notify` is the activity log and gets only what the user must act on.
        self._notify    = notify or (lambda _msg: None)
        self._queue: queue.Queue = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._running = False
        self._model = None
        self._ready = False

    def start(self) -> bool:
        """Load the model and spawn the inference thread. Returns True on success.
        Safe to call again — a no-op if already running. Never raises."""
        if self._running:
            return True
        try:
            from openwakeword.model import Model
            spec = wake_model()
            fw = "tflite" if spec.lower().endswith(".tflite") else "onnx"
            self._model = Model(wakeword_models=[spec], inference_framework=fw)
        except Exception as e:
            self._logger(f"Wake word: could not load model — {e}")
            self._notify("Wake word unavailable — use the WAKE NOW button.")
            self._model = None
            return False
        self._running = True
        self._ready = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="WakeWordThread")
        self._thread.start()
        self._logger(f"Wake word: listening for '{phrase()}'" + ("" if custom_model_path() else " (stock phrase)") + ".")
        return True

    def stop(self) -> None:
        self._running = False
        # unblock the thread if it's waiting on the queue
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        self._model = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def feed(self, frame_int16) -> None:
        """Called from the mic callback (real-time thread). Must stay cheap and
        never block — the frame is copied and dropped if the queue is backed up."""
        if not self._running:
            return
        try:
            # frame_int16 is a numpy int16 array (possibly 2-D mono) — flatten to 1-D
            data = frame_int16[:, 0].copy() if getattr(frame_int16, "ndim", 1) > 1 else frame_int16.copy()
            self._queue.put_nowait(data)
        except queue.Full:
            pass
        except Exception:
            pass

    def _loop(self) -> None:
        import numpy as np
        while self._running:
            try:
                frame = self._queue.get()
                if frame is None or not self._running:
                    break
                scores = self._model.predict(np.asarray(frame, dtype=np.int16))
                score = 0.0
                if isinstance(scores, dict):
                    # exactly one model is loaded, so its score is the max of the dict
                    if scores:
                        score = max(float(v) for v in scores.values())
                if score >= self._threshold:
                    # drain any backlog so we don't double-fire on the same utterance
                    self._drain()
                    try:
                        self._on_detect()
                    except Exception as e:
                        self._logger(f"Wake word: on_detect error — {e}")
            except Exception as e:
                self._logger(f"Wake word: inference error — {e}")

    def _drain(self) -> None:
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass
