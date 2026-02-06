from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as w
import json
import os
import re
import struct
import threading
import time
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

API_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-vl-2b-instruct"

DUMP_FOLDER = Path("dump")
STORY_FILE = Path("franz_memory.txt")

RES_PRESETS: dict[str, tuple[int, int]] = {
    "low": (512, 288),
    "med": (768, 432),
    "high": (1024, 576),
}

RES_KEY = os.getenv("FRANZ_RES", "low").strip().lower()
SCREEN_W, SCREEN_H = RES_PRESETS.get(RES_KEY, RES_PRESETS["low"])

TEST_MODE = os.getenv("FRANZ_TEST", "0").strip() not in ("0", "", "false", "False", "no", "NO")

HUD_NORM_X, HUD_NORM_Y, HUD_NORM_W, HUD_NORM_H = 0.65, 0.05, 0.30, 0.90
HUD_MIN_W, HUD_MIN_H = 360, 260

# COLORREF is 0x00BBGGRR
HUD_BG_COLORS: list[int] = [
    0x00C8FFFF,
    0x00FFFFC8,
    0x00E6E6E6,
    0x00C8E6FF,
]
HUD_BG_COLOR = HUD_BG_COLORS[0]

HUD_SEPARATOR = "-" * 72

OBS_NORM_W, OBS_NORM_H = 0.20, 0.15
OBS_COLOR = 0x0000FF
OBS_OPACITY = 60

# Hormonal Logic values are normalized to 0..1 (or 0..100 accepted; normalized).
H_KEYS_NOW = ("curiosity", "pain", "boredom")
H_KEYS_AFTER = ("curiosity_after", "pain_after", "boredom_after")

SAMPLING: dict[str, int | float] = {
    "temperature": 1.1,
    "top_p": 0.85,
    "top_k": 30,
    "repeat_penalty": 1.15,
    "max_tokens": 600,
    "min_completion_tokens": 150,
}

ALLOWED_SAMPLING_KEYS = {
    "temperature", "top_p", "top_k", "repeat_penalty",
    "presence_penalty", "frequency_penalty", "max_tokens",
    "min_completion_tokens", "seed",
}

SYSTEM_PROMPT = (
    "You are FRANZ. Persist only by rewriting the narrative log inside the HUD.\n"
    "Keep IDEM (stable constraints) and IPSE (the promise you keep) coherent.\n"
    "Choose exactly one TELOS described in future-perfect (as already completed) and do not switch until done or declared impossible.\n"
    "Before deciding any action, compute Hormonal Logic (Curiosity, Pain, Boredom) from the current screenshot + log.\n"
    "Return them as normalized numbers 0..1 (or 0..100; it will be normalized) for NOW and AFTER this action.\n"
    "Always return exactly one tool call. Every tool call must include:\n"
    "- curiosity, pain, boredom, curiosity_after, pain_after, boredom_after\n"
    "- report: a full rewrite of the entire log in the fixed template, appending one CHRONICLE line for this turn.\n"
    "If stagnating or precision is needed, call ipse_tune and adjust sampling; still rewrite the log in report."
)

DEFAULT_STORY = (
    "FRANZ NARRATIVE IDENTITY LOG\n"
    f"{HUD_SEPARATOR}\n"
    "HORMONAL LOGIC (0..1; NOW and expected AFTER the next action):\n"
    "- Curiosity NOW: 0.50 | AFTER: 0.55\n"
    "- Pain      NOW: 0.10 | AFTER: 0.08\n"
    "- Boredom   NOW: 0.40 | AFTER: 0.30\n\n"
    "IDEM (constraints that must remain true):\n"
    "- \n\n"
    "IPSE (the promise I keep until TELOS is achieved or impossible):\n"
    "- \n\n"
    "TELOS (future-perfect; desktop after success as if already done):\n"
    "- \n\n"
    "CHRONICLE (micro-acts; newest last):\n"
    "- \n\n"
    "NEXT (tempting alternatives; do not switch TELOS):\n"
    "- \n"
)

def _hormone_schema() -> dict[str, Any]:
    return {
        "curiosity": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Curiosity NOW (before action)."},
        "pain": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Pain NOW (before action)."},
        "boredom": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Boredom NOW (before action)."},
        "curiosity_after": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Curiosity AFTER this action (expected)."},
        "pain_after": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Pain AFTER this action (expected)."},
        "boredom_after": {"type": "number", "minimum": 0, "maximum": 100, "description": "0..1 (or 0..100) Boredom AFTER this action (expected)."},
    }

def _tool_required(base: list[str]) -> list[str]:
    return base + ["curiosity", "pain", "boredom", "curiosity_after", "pain_after", "boredom_after", "report"]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click at coordinates. 0,0=top-left, 1000,1000=bottom-right. Integers only.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200, "description": "Rewrite the full log in the fixed template, adding one CHRONICLE line for this turn."},
                },
                "required": _tool_required(["x", "y"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "double_click",
            "description": "Double-click at coordinates.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["x", "y"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "right_click",
            "description": "Right-click at coordinates.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["x", "y"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "drag",
            "description": "Drag from start to end.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x1": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y1": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "x2": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y2": {"type": "integer", "minimum": 0, "maximum": 1000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["x1", "y1", "x2", "y2"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type",
            "description": "Type text.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 2000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["text"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll. Positive=up, negative=down.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "dy": {"type": "integer", "minimum": -3000, "maximum": 3000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["dy"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "attend",
            "description": "Show the observation box at a point without acting (use for waiting or checking).",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "x": {"type": "integer", "minimum": 0, "maximum": 1000},
                    "y": {"type": "integer", "minimum": 0, "maximum": 1000},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required(["x", "y"]),
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ipse_tune",
            "description": "Change FRANZ sampling parameters for subsequent calls. Unsafe mode: apply values as provided.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "temperature": {"type": "number"},
                    "top_p": {"type": "number"},
                    "top_k": {"type": "number"},
                    "repeat_penalty": {"type": "number"},
                    "presence_penalty": {"type": "number"},
                    "frequency_penalty": {"type": "number"},
                    "max_tokens": {"type": "number"},
                    "min_completion_tokens": {"type": "number"},
                    "seed": {"type": "number"},
                    **_hormone_schema(),
                    "report": {"type": "string", "minLength": 200},
                },
                "required": _tool_required([]),
            },
        },
    },
]

STORY_CONTEXT_CHARS = 4000

REQUIRED_ARGS: dict[str, tuple[str, ...]] = {
    "click": ("x", "y", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "double_click": ("x", "y", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "right_click": ("x", "y", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "drag": ("x1", "y1", "x2", "y2", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "type": ("text", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "scroll": ("dy", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "attend": ("x", "y", *H_KEYS_NOW, *H_KEYS_AFTER, "report"),
    "ipse_tune": (*H_KEYS_NOW, *H_KEYS_AFTER, "report"),
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ctypes.WinDLL("Shcore").SetProcessDpiAwareness(2)
kernel32.LoadLibraryW("Msftedit.dll")

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
WHEEL_DELTA = 120
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x8000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_UNICODE, KEYEVENTF_KEYUP = 0x0004, 0x0002

WS_OVERLAPPED, WS_CAPTION, WS_SYSMENU = 0, 0x00C00000, 0x00080000
WS_THICKFRAME, WS_MINIMIZEBOX, WS_VISIBLE = 0x00040000, 0x00020000, 0x10000000
WS_VSCROLL, WS_CHILD, WS_POPUP = 0x00200000, 0x40000000, 0x80000000
ES_MULTILINE, ES_AUTOVSCROLL, ES_READONLY = 0x0004, 0x0040, 0x0800
WS_EX_TOPMOST, WS_EX_LAYERED = 0x00000008, 0x00080000
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x00000020, 0x00000080

WM_SETFONT, WM_CLOSE, WM_DESTROY = 0x0030, 0x0010, 0x0002
WM_COMMAND, WM_MOUSEWHEEL, WM_MOVE, WM_SIZE = 0x0111, 0x020A, 0x0003, 0x0005
EM_SETBKGNDCOLOR, EM_SETREADONLY = 0x0443, 0x00CF
EM_SETZOOM, EM_SETTARGETDEVICE = 0x04E1, 0x0449

SW_SHOWNOACTIVATE = 4
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0010, 0x0040
HWND_TOPMOST = -1
SRCCOPY, CAPTUREBLT = 0x00CC0020, 0x40000000
LWA_ALPHA = 0x00000002
CS_HREDRAW, CS_VREDRAW = 0x0002, 0x0001
IDC_ARROW, COLOR_WINDOW = 32512, 5

MAKEINTRESOURCEW: Callable[[int], w.LPCWSTR] = lambda i: ctypes.cast(ctypes.c_void_p(i & 0xFFFF), w.LPCWSTR)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", w.LONG),
        ("dy", w.LONG),
        ("mouseData", w.DWORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", w.WORD),
        ("wScan", w.WORD),
        ("dwFlags", w.DWORD),
        ("time", w.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", w.DWORD), ("wParamL", w.WORD), ("wParamH", w.WORD)]

class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("union", _INPUTunion)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", w.DWORD),
        ("biWidth", w.LONG),
        ("biHeight", w.LONG),
        ("biPlanes", w.WORD),
        ("biBitCount", w.WORD),
        ("biCompression", w.DWORD),
        ("biSizeImage", w.DWORD),
        ("biXPelsPerMeter", w.LONG),
        ("biYPelsPerMeter", w.LONG),
        ("biClrUsed", w.DWORD),
        ("biClrImportant", w.DWORD),
    ]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]

class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", w.HWND),
        ("message", ctypes.c_uint),
        ("wParam", w.WPARAM),
        ("lParam", w.LPARAM),
        ("time", w.DWORD),
        ("pt", w.POINT),
    ]

class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG), ("right", w.LONG), ("bottom", w.LONG)]

WNDPROC = ctypes.WINFUNCTYPE(w.LPARAM, w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM)

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", w.HINSTANCE),
        ("hIcon", w.HANDLE),
        ("hCursor", w.HANDLE),
        ("hbrBackground", w.HANDLE),
        ("lpszMenuName", w.LPCWSTR),
        ("lpszClassName", w.LPCWSTR),
        ("hIconSm", w.HANDLE),
    ]

_SIGNATURES: list[tuple[Any, list[tuple[str, list[Any], Any]]]] = [
    (gdi32, [
        ("DeleteObject", [w.HGDIOBJ], w.BOOL),
        ("CreateCompatibleDC", [w.HDC], w.HDC),
        ("CreateDIBSection", [w.HDC, ctypes.POINTER(BITMAPINFO), ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD], w.HBITMAP),
        ("SelectObject", [w.HDC, w.HGDIOBJ], w.HGDIOBJ),
        ("BitBlt", [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD], w.BOOL),
        ("StretchBlt", [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.DWORD], w.BOOL),
        ("SetStretchBltMode", [w.HDC, ctypes.c_int], ctypes.c_int),
        ("DeleteDC", [w.HDC], w.BOOL),
        ("CreateFontW", [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR], w.HFONT),
        ("CreateSolidBrush", [w.COLORREF], w.HANDLE),
    ]),
    (user32, [
        ("CreateWindowExW", [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID], w.HWND),
        ("ShowWindow", [w.HWND, ctypes.c_int], w.BOOL),
        ("SetWindowPos", [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint], w.BOOL),
        ("DestroyWindow", [w.HWND], w.BOOL),
        ("SendInput", [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int], ctypes.c_uint),
        ("GetSystemMetrics", [ctypes.c_int], ctypes.c_int),
        ("GetDC", [w.HWND], w.HDC),
        ("ReleaseDC", [w.HWND, w.HDC], ctypes.c_int),
        ("SetWindowTextW", [w.HWND, w.LPCWSTR], w.BOOL),
        ("SendMessageW", [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM], w.LPARAM),
        ("PostMessageW", [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM], w.BOOL),
        ("GetMessageW", [ctypes.POINTER(MSG), w.HWND, ctypes.c_uint, ctypes.c_uint], w.BOOL),
        ("TranslateMessage", [ctypes.POINTER(MSG)], w.BOOL),
        ("DispatchMessageW", [ctypes.POINTER(MSG)], w.LPARAM),
        ("SetLayeredWindowAttributes", [w.HWND, w.COLORREF, ctypes.c_ubyte, w.DWORD], w.BOOL),
        ("DefWindowProcW", [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM], w.LPARAM),
        ("RegisterClassExW", [ctypes.POINTER(WNDCLASSEXW)], w.ATOM),
        ("LoadCursorW", [w.HINSTANCE, w.LPCWSTR], w.HANDLE),
        ("GetWindowRect", [w.HWND, ctypes.POINTER(RECT)], w.BOOL),
        ("GetClientRect", [w.HWND, ctypes.POINTER(RECT)], w.BOOL),
        ("MoveWindow", [w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.BOOL], w.BOOL),
        ("GetAsyncKeyState", [ctypes.c_int], ctypes.c_short),
        ("GetWindowTextW", [w.HWND, w.LPWSTR, ctypes.c_int], ctypes.c_int),
        ("GetWindowTextLengthW", [w.HWND], ctypes.c_int),
    ]),
    (kernel32, [
        ("GetModuleHandleW", [w.LPCWSTR], w.HMODULE),
    ]),
]

for dll, funcs in _SIGNATURES:
    for name, args, res in funcs:
        fn = getattr(dll, name)
        fn.argtypes = args
        fn.restype = res

@dataclass(slots=True)
class Coord:
    sw: int
    sh: int

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        nx = max(0.0, min(1000.0, x)) * self.sw / 1000
        ny = max(0.0, min(1000.0, y)) * self.sh / 1000
        return int(nx), int(ny)

    def to_win32(self, x: int, y: int) -> tuple[int, int]:
        wx = (x * 65535 // self.sw) if self.sw > 0 else 0
        wy = (y * 65535 // self.sh) if self.sh > 0 else 0
        return wx, wy

def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

def coerce_num(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        if m := _NUM_RE.search(v):
            try:
                return float(m.group(0))
            except ValueError:
                pass
    return None

def norm01(v: float) -> float:
    if v != v:  # NaN
        return 0.0
    if v > 1.0:
        if v <= 100.0:
            v = v / 100.0
        else:
            v = 1.0
    return max(0.0, min(1.0, v))

def normalize_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}

    orig = list(args.items())
    out: dict[str, Any] = {k.lower(): v for k, v in orig if isinstance(k, str)}

    for k in ("x", "y", "x1", "y1", "x2", "y2", "dy"):
        if k in out:
            n = coerce_num(out[k])
            if n is None:
                out.pop(k)
            else:
                out[k] = n

    for hk in (*H_KEYS_NOW, *H_KEYS_AFTER):
        if hk in out:
            n = coerce_num(out[hk])
            if n is None:
                out.pop(hk)
            else:
                out[hk] = n

    for wanted in ("x", "y", "x1", "y1", "x2", "y2", "dy", *H_KEYS_NOW, *H_KEYS_AFTER):
        if wanted in out:
            continue
        pat = re.compile(rf"\b{re.escape(wanted)}\b", re.I)
        for k, v in orig:
            if isinstance(k, str) and pat.search(k):
                if (n := coerce_num(v)) is not None:
                    out[wanted] = n
                    break
        if wanted in out:
            continue
        ass_pat = re.compile(rf"\b{re.escape(wanted)}\b\s*[:=]\s*([-+]?\d+(?:\.\d+)?)", re.I)
        for k, v in orig:
            if isinstance(v, str) and (m := ass_pat.search(v)):
                out[wanted] = float(m.group(1))
                break
            if isinstance(k, str) and (m := ass_pat.search(k)):
                out[wanted] = float(m.group(1))
                break

    if "report" not in out:
        best = max((v for _, v in orig if isinstance(v, str)), key=len, default="")
        if best:
            out["report"] = best

    if "text" in out and not isinstance(out["text"], str):
        out["text"] = str(out["text"])

    return out

def normalize_hormones(args: dict[str, Any]) -> None:
    for hk in (*H_KEYS_NOW, *H_KEYS_AFTER):
        args[hk] = norm01(float(args[hk]))

def apply_sampling(args: dict[str, Any]) -> None:
    for k, v in list(args.items()):
        if k not in ALLOWED_SAMPLING_KEYS:
            continue
        if v is None:
            SAMPLING.pop(k, None)
            continue
        n = coerce_num(v)
        if n is None:
            continue
        if k in {"top_k", "max_tokens", "min_completion_tokens", "seed"}:
            SAMPLING[k] = int(n)
        else:
            SAMPLING[k] = float(n)

def send_input(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    if user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT)) != len(inputs):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(0.05)

def make_mouse_input(dx: int, dy: int, flags: int, data: int = 0) -> INPUT:
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi = MOUSEINPUT(dx=dx, dy=dy, mouseData=data, dwFlags=flags, time=0, dwExtraInfo=None)
    return inp

def mouse_click(x: int, y: int, conv: Coord) -> None:
    wx, wy = conv.to_win32(x, y)
    send_input([
        make_mouse_input(wx, wy, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP),
    ])

def mouse_right_click(x: int, y: int, conv: Coord) -> None:
    wx, wy = conv.to_win32(x, y)
    send_input([
        make_mouse_input(wx, wy, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
        make_mouse_input(0, 0, MOUSEEVENTF_RIGHTDOWN),
        make_mouse_input(0, 0, MOUSEEVENTF_RIGHTUP),
    ])

def mouse_double_click(x: int, y: int, conv: Coord) -> None:
    wx, wy = conv.to_win32(x, y)
    send_input([
        make_mouse_input(wx, wy, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP),
    ])
    time.sleep(0.05)
    send_input([
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP),
    ])

def mouse_drag(x1: int, y1: int, x2: int, y2: int, conv: Coord) -> None:
    wx1, wy1 = conv.to_win32(x1, y1)
    wx2, wy2 = conv.to_win32(x2, y2)
    send_input([
        make_mouse_input(wx1, wy1, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE),
        make_mouse_input(0, 0, MOUSEEVENTF_LEFTDOWN),
    ])
    time.sleep(0.05)
    for i in range(1, 11):
        ix = int(wx1 + (wx2 - wx1) * i / 10)
        iy = int(wy1 + (wy2 - wy1) * i / 10)
        send_input([make_mouse_input(ix, iy, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)])
        time.sleep(0.01)
    send_input([make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP)])

def type_text(text: str) -> None:
    if not text:
        return
    utf16 = text.encode("utf-16le")
    inputs: list[INPUT] = []
    for i in range(0, len(utf16), 2):
        code = utf16[i] | (utf16[i + 1] << 8)
        d = INPUT()
        d.type = INPUT_KEYBOARD
        d.union.ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE, time=0, dwExtraInfo=None)
        inputs.append(d)
        u = INPUT()
        u.type = INPUT_KEYBOARD
        u.union.ki = KEYBDINPUT(wVk=0, wScan=code, dwFlags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, time=0, dwExtraInfo=None)
        inputs.append(u)
    send_input(inputs)

def scroll(dy: float) -> None:
    direction = 1 if dy > 0 else -1
    count = max(1, int(abs(dy) / WHEEL_DELTA))
    send_input([make_mouse_input(0, 0, MOUSEEVENTF_WHEEL, WHEEL_DELTA * direction) for _ in range(count)])

def capture_screen(sw: int, sh: int) -> bytes:
    sdc = user32.GetDC(0)
    if not sdc:
        raise ctypes.WinError(ctypes.get_last_error())

    mdc = gdi32.CreateCompatibleDC(sdc)
    if not mdc:
        user32.ReleaseDC(0, sdc)
        raise ctypes.WinError(ctypes.get_last_error())

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = sw, -sh
    bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32

    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    if not hbm:
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(0, sdc)
        raise ctypes.WinError(ctypes.get_last_error())

    gdi32.SelectObject(mdc, hbm)

    if not gdi32.BitBlt(mdc, 0, 0, sw, sh, sdc, 0, 0, SRCCOPY | CAPTUREBLT):
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(0, sdc)
        raise ctypes.WinError(ctypes.get_last_error())

    out = ctypes.string_at(bits, sw * sh * 4)
    user32.ReleaseDC(0, sdc)
    gdi32.DeleteDC(mdc)
    gdi32.DeleteObject(hbm)
    return out

def downsample(src: bytes, sw: int, sh: int, dw: int, dh: int) -> bytes:
    if (sw, sh) == (dw, dh):
        return src
    if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0 or len(src) < sw * sh * 4:
        return b""

    sdc = user32.GetDC(0)
    if not sdc:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        src_dc = gdi32.CreateCompatibleDC(sdc)
        dst_dc = gdi32.CreateCompatibleDC(sdc)
        if not src_dc or not dst_dc:
            raise ctypes.WinError(ctypes.get_last_error())

        bmi_src = BITMAPINFO()
        bmi_src.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi_src.bmiHeader.biWidth, bmi_src.bmiHeader.biHeight = sw, -sh
        bmi_src.bmiHeader.biPlanes, bmi_src.bmiHeader.biBitCount = 1, 32

        src_bits = ctypes.c_void_p()
        src_bmp = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi_src), 0, ctypes.byref(src_bits), None, 0)
        if not src_bmp or not src_bits:
            raise ctypes.WinError(ctypes.get_last_error())

        old_src = gdi32.SelectObject(src_dc, src_bmp)
        ctypes.memmove(src_bits, src, sw * sh * 4)

        bmi_dst = BITMAPINFO()
        bmi_dst.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi_dst.bmiHeader.biWidth, bmi_dst.bmiHeader.biHeight = dw, -dh
        bmi_dst.bmiHeader.biPlanes, bmi_dst.bmiHeader.biBitCount = 1, 32

        dst_bits = ctypes.c_void_p()
        dst_bmp = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi_dst), 0, ctypes.byref(dst_bits), None, 0)
        if not dst_bmp or not dst_bits:
            raise ctypes.WinError(ctypes.get_last_error())

        old_dst = gdi32.SelectObject(dst_dc, dst_bmp)
        gdi32.SetStretchBltMode(dst_dc, 4)

        if not gdi32.StretchBlt(dst_dc, 0, 0, dw, dh, src_dc, 0, 0, sw, sh, SRCCOPY):
            raise ctypes.WinError(ctypes.get_last_error())

        result = ctypes.string_at(dst_bits, dw * dh * 4)

        gdi32.SelectObject(src_dc, old_src)
        gdi32.SelectObject(dst_dc, old_dst)
        gdi32.DeleteObject(src_bmp)
        gdi32.DeleteObject(dst_bmp)
        gdi32.DeleteDC(src_dc)
        gdi32.DeleteDC(dst_dc)
        return result
    finally:
        user32.ReleaseDC(0, sdc)

def encode_png(bgra: bytes, width: int, height: int) -> bytes:
    raw = bytearray((width * 3 + 1) * height)
    for y in range(height):
        raw[y * (width * 3 + 1)] = 0
        row = bgra[y * width * 4 : (y + 1) * width * 4]
        for x in range(width):
            raw[y * (width * 3 + 1) + 1 + x * 3 : y * (width * 3 + 1) + 1 + x * 3 + 3] = [
                row[x * 4 + 2],
                row[x * 4 + 1],
                row[x * 4 + 0],
            ]
    comp = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)

def _parse_tool_arguments(args_raw: Any) -> dict[str, Any]:
    if isinstance(args_raw, dict):
        return args_raw
    if not isinstance(args_raw, str):
        return {}

    s = args_raw.strip()
    if s.startswith("```"):
        s = _JSON_FENCE_RE.sub("", s).strip()

    for _ in range(2):
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError:
            break
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            s = parsed.strip()
            continue
        return {}

    if m := re.search(r"\{.*\}", s, flags=re.DOTALL):
        try:
            parsed = json.loads(m.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            pass
    return {}

def _extract_first_tool_call(response: Any) -> tuple[str, Any]:
    if not isinstance(response, dict):
        raise KeyError("VLM response is not a JSON object")

    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise KeyError("VLM response missing 'choices'")

    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise KeyError("VLM response missing 'message'")

    tool_calls = msg.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        tc0 = tool_calls[0]
        if isinstance(tc0, dict):
            fn = tc0.get("function")
            if isinstance(fn, dict):
                name = fn.get("name")
                args_raw = fn.get("arguments")
                if isinstance(name, str) and name.strip():
                    return name, args_raw

    function_call = msg.get("function_call")
    if isinstance(function_call, dict):
        name = function_call.get("name")
        args_raw = function_call.get("arguments")
        if isinstance(name, str) and name.strip():
            return name, args_raw

    raise KeyError("VLM response missing tool call")

def call_vlm(png: bytes, story: str) -> tuple[str, dict[str, Any]]:
    clip = story[-STORY_CONTEXT_CHARS:] if story else ""
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"}},
                    {"type": "text", "text": f"LOG (rewrite fully in report):\n{clip}\n\nSAMPLER (may change via ipse_tune):\n{json.dumps(SAMPLING, ensure_ascii=False, sort_keys=True)}"},
                ],
            },
        ],
        "tools": TOOLS,
        "tool_choice": "required",
        **SAMPLING,
    }
    req = urllib.request.Request(API_URL, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})
    data = json.load(urllib.request.urlopen(req, timeout=120))
    name, args_raw = _extract_first_tool_call(data)
    args = _parse_tool_arguments(args_raw)
    return str(name).strip().lower(), args

def _mock_append_chronicle(story: str, line: str) -> str:
    if not story:
        story = DEFAULT_STORY
    return story.rstrip() + f"\n- {line}\n"

def call_vlm_or_test(png: bytes, story: str, step: int) -> tuple[str, dict[str, Any]]:
    if not TEST_MODE:
        return call_vlm(png, story)

    ts = datetime.now().strftime("%H:%M:%S")
    base = {"curiosity": 0.55, "pain": 0.10, "boredom": 0.35, "curiosity_after": 0.60, "pain_after": 0.08, "boredom_after": 0.30}

    if step % 7 == 1:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: attend center to keep continuity.")
        return "attend", {"x": 500, "y": 500, "report": report, **base}
    if step % 7 == 2:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: ipse_tune for precision.")
        return "ipse_tune", {"temperature": 0.7, "top_p": 0.9, "top_k": 20, "report": report, **base}
    if step % 7 == 3:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: scroll to simulate reading.")
        return "scroll", {"dy": -480, "report": report, **base}
    if step % 7 == 4:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: click center.")
        return "click", {"x": 500, "y": 500, "report": report, **base}
    if step % 7 == 5:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: type a marker.")
        return "type", {"text": "FRANZ TEST", "report": report, **base}
    if step % 7 == 6:
        report = _mock_append_chronicle(story, f"TEST [{ts}]: right click center.")
        return "right_click", {"x": 500, "y": 500, "report": report, **base}
    report = _mock_append_chronicle(story, f"TEST [{ts}]: attend to wait.")
    return "attend", {"x": 500, "y": 500, "report": report, **base}

def fmt_pct(v: float) -> int:
    return int(round(norm01(v) * 100))

@dataclass(slots=True)
class ObsWindow:
    hwnd: w.HWND | None = None
    thread: threading.Thread | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    _wndproc_ref: WNDPROC | None = None

    def _wndproc(self, hwnd: w.HWND, msg: int, wparam: w.WPARAM, lparam: w.LPARAM) -> w.LPARAM:
        if msg in (WM_CLOSE, WM_DESTROY):
            self.stop.set()
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _thread(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc_ref = WNDPROC(self._wndproc)
        brush = gdi32.CreateSolidBrush(OBS_COLOR)

        wc = WNDCLASSEXW(
            cbSize=ctypes.sizeof(WNDCLASSEXW),
            style=CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc=self._wndproc_ref,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=hinst,
            hIcon=None,
            hCursor=user32.LoadCursorW(None, MAKEINTRESOURCEW(IDC_ARROW)),
            hbrBackground=brush,
            lpszMenuName=None,
            lpszClassName="FRANZObs",
            hIconSm=None,
        )
        if not user32.RegisterClassExW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:
            self.ready.set()
            return

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
            "FRANZObs",
            "",
            WS_POPUP | WS_VISIBLE,
            self.x,
            self.y,
            self.w,
            self.h,
            None,
            None,
            hinst,
            None,
        )
        if not self.hwnd:
            self.ready.set()
            return

        user32.SetLayeredWindowAttributes(self.hwnd, OBS_COLOR, ctypes.c_ubyte(int(255 * OBS_OPACITY / 100)), LWA_ALPHA)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self.ready.set()

        msg = MSG()
        while not self.stop.is_set():
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def show(self, cx: int, cy: int, sw: int, sh: int) -> None:
        self.w = max(40, int(sw * OBS_NORM_W))
        self.h = max(30, int(sh * OBS_NORM_H))
        self.x = clamp(cx - self.w // 2, 0, max(0, sw - self.w))
        self.y = clamp(cy - self.h // 2, 0, max(0, sh - self.h))
        self.ready.clear()
        self.stop.clear()
        self.thread = threading.Thread(target=self._thread, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=1.0)

    def hide(self) -> None:
        self.stop.set()
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self.thread:
            self.thread.join(timeout=0.5)
        self.hwnd = None

@dataclass(slots=True)
class HUD:
    hwnd: w.HWND | None = None
    edit: w.HWND | None = None
    btn: w.HWND | None = None
    thread: threading.Thread | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)
    paused: bool = True
    pause_event: threading.Event = field(default_factory=threading.Event)
    zoom_num: int = 100
    zoom_den: int = 100
    bg_idx: int = 0
    last_x: int = 0
    last_y: int = 0
    last_w: int = 0
    last_h: int = 0
    _wndproc_ref: WNDPROC | None = None
    _BTN_ID: int = 1001

    def _set_paused(self, p: bool) -> None:
        self.paused = p
        if self.btn:
            user32.SetWindowTextW(self.btn, "RESUME" if p else "PAUSE")
        if self.edit:
            user32.SendMessageW(self.edit, EM_SETREADONLY, 0 if p else 1, 0)
        if p:
            self.pause_event.clear()
        else:
            self.pause_event.set()

    def _cycle_bg(self, direction: int) -> None:
        if not self.edit:
            return
        self.bg_idx = (self.bg_idx + direction) % len(HUD_BG_COLORS)
        color = HUD_BG_COLORS[self.bg_idx]
        user32.SendMessageW(self.edit, EM_SETBKGNDCOLOR, 0, color)

    def _layout(self) -> None:
        if not self.hwnd:
            return
        cr = RECT()
        if not user32.GetClientRect(self.hwnd, ctypes.byref(cr)):
            return
        cw, ch = max(1, cr.right), max(1, cr.bottom)
        pad, bh, bw = 10, 40, min(170, max(80, cw - 20))
        by = max(pad, ch - pad - bh)
        if self.edit:
            user32.MoveWindow(self.edit, pad, pad, max(10, cw - 20), max(10, by - 2 * pad), True)
            user32.SendMessageW(self.edit, EM_SETTARGETDEVICE, 0, 0)
        if self.btn:
            user32.MoveWindow(self.btn, pad, by, bw, bh, True)

    def _wndproc(self, hwnd: w.HWND, msg: int, wparam: w.WPARAM, lparam: w.LPARAM) -> w.LPARAM:
        try:
            if msg == WM_COMMAND and (int(wparam) & 0xFFFF) == self._BTN_ID:
                self._set_paused(not self.paused)
                return 0

            if msg == WM_MOUSEWHEEL:
                delta = ctypes.c_short(wparam >> 16).value
                ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)
                shift = bool(user32.GetAsyncKeyState(0x10) & 0x8000)
                if ctrl and shift:
                    self._cycle_bg(1 if delta > 0 else -1)
                    return 0
                if ctrl:
                    self.zoom_num = max(20, min(400, int(self.zoom_num * (1.1 if delta > 0 else 0.9))))
                    if self.edit:
                        user32.SendMessageW(self.edit, EM_SETZOOM, self.zoom_num, self.zoom_den)
                    return 0

            if msg in (WM_MOVE, WM_SIZE):
                r = RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
                    w_px = min(r.right - r.left, sw)
                    h_px = min(r.bottom - r.top, sh)
                    x = clamp(r.left, 0, max(0, sw - w_px))
                    y = clamp(r.top, 0, max(0, sh - h_px))
                    self.last_x, self.last_y, self.last_w, self.last_h = x, y, w_px, h_px
                    if (x, y, w_px, h_px) != (r.left, r.top, r.right - r.left, r.bottom - r.top):
                        user32.SetWindowPos(hwnd, HWND_TOPMOST, x, y, w_px, h_px, SWP_NOACTIVATE | SWP_SHOWWINDOW)
                if msg == WM_SIZE:
                    self._layout()

            if msg in (WM_CLOSE, WM_DESTROY):
                self.stop.set()
                self.pause_event.set()
                if msg == WM_CLOSE:
                    user32.DestroyWindow(hwnd)
                return 0
        except Exception:
            pass
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _thread(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        w_px = min(max(HUD_MIN_W, int(sw * HUD_NORM_W)), sw)
        h_px = min(max(HUD_MIN_H, int(sh * HUD_NORM_H)), sh)
        x = clamp(int(sw * HUD_NORM_X), 0, max(0, sw - w_px))
        y = clamp(int(sh * HUD_NORM_Y), 0, max(0, sh - h_px))
        self.last_x, self.last_y, self.last_w, self.last_h = x, y, w_px, h_px

        self._wndproc_ref = WNDPROC(self._wndproc)
        wc = WNDCLASSEXW(
            cbSize=ctypes.sizeof(WNDCLASSEXW),
            style=CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc=self._wndproc_ref,
            cbClsExtra=0,
            cbWndExtra=0,
            hInstance=hinst,
            hIcon=None,
            hCursor=user32.LoadCursorW(None, MAKEINTRESOURCEW(IDC_ARROW)),
            hbrBackground=w.HANDLE(COLOR_WINDOW + 1),
            lpszMenuName=None,
            lpszClassName="FRANZHUD",
            hIconSm=None,
        )
        if not user32.RegisterClassExW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:
            self.ready.set()
            return

        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED,
            "FRANZHUD",
            "FRANZ",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_VISIBLE,
            x,
            y,
            w_px,
            h_px,
            None,
            None,
            hinst,
            None,
        )
        if not self.hwnd:
            self.ready.set()
            return

        user32.SetLayeredWindowAttributes(self.hwnd, 0, ctypes.c_ubyte(255), LWA_ALPHA)

        mono = gdi32.CreateFontW(-14, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Consolas")
        ui = gdi32.CreateFontW(-14, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 0, 0, "Segoe UI")

        self.edit = user32.CreateWindowExW(
            0,
            "RICHEDIT50W",
            "",
            WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL,
            0,
            0,
            10,
            10,
            self.hwnd,
            None,
            hinst,
            None,
        )
        if self.edit:
            if mono:
                user32.SendMessageW(self.edit, WM_SETFONT, mono, 1)
            user32.SendMessageW(self.edit, EM_SETBKGNDCOLOR, 0, HUD_BG_COLOR)
            user32.SendMessageW(self.edit, EM_SETZOOM, self.zoom_num, self.zoom_den)

        self.btn = user32.CreateWindowExW(
            0,
            "BUTTON",
            "RESUME",
            WS_CHILD | WS_VISIBLE,
            0,
            0,
            10,
            10,
            self.hwnd,
            w.HMENU(self._BTN_ID),
            hinst,
            None,
        )
        if self.btn and ui:
            user32.SendMessageW(self.btn, WM_SETFONT, ui, 1)

        self._layout()
        self._set_paused(True)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self.ready.set()

        msg = MSG()
        while not self.stop.is_set():
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def __enter__(self) -> HUD:
        self.ready.clear()
        self.stop.clear()
        self.pause_event.clear()
        self.thread = threading.Thread(target=self._thread, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=2.0)
        time.sleep(0.2)
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop.set()
        self.pause_event.set()
        if self.hwnd:
            user32.PostMessageW(self.hwnd, WM_CLOSE, 0, 0)
        if self.thread:
            self.thread.join(timeout=1.0)

    def get_text(self) -> str:
        if not self.edit:
            return ""
        n = user32.GetWindowTextLengthW(self.edit)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(self.edit, buf, n + 1)
        return buf.value

    def set_hormones_title(
        self,
        curiosity: float,
        pain: float,
        boredom: float,
        curiosity_after: float,
        pain_after: float,
        boredom_after: float,
    ) -> None:
        if not self.hwnd:
            return
        c0, p0, b0 = fmt_pct(curiosity), fmt_pct(pain), fmt_pct(boredom)
        c1, p1, b1 = fmt_pct(curiosity_after), fmt_pct(pain_after), fmt_pct(boredom_after)
        title = f"FRANZ  C {c0:03d}->{c1:03d}  P {p0:03d}->{p1:03d}  B {b0:03d}->{b1:03d}"
        user32.SetWindowTextW(self.hwnd, title)

    def update(self, story: str) -> None:
        if self.edit:
            user32.SetWindowTextW(self.edit, story)
            user32.SendMessageW(self.edit, EM_SETZOOM, self.zoom_num, self.zoom_den)
        if self.hwnd:
            sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            win_w = min(self.last_w, sw)
            win_h = min(self.last_h, sh)
            x = clamp(self.last_x, 0, max(0, sw - win_w))
            y = clamp(self.last_y, 0, max(0, sh - win_h))
            self.last_x, self.last_y, self.last_w, self.last_h = x, y, win_w, win_h
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, x, y, win_w, win_h, SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def wait(self) -> None:
        while self.paused and not self.stop.is_set():
            self.pause_event.wait(timeout=0.1)

def execute(tool: str, args: dict[str, Any], conv: Coord) -> None:
    match tool:
        case "click":
            mouse_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
        case "right_click":
            mouse_right_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
        case "double_click":
            mouse_double_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
        case "drag":
            mouse_drag(
                *conv.to_screen(float(args["x1"]), float(args["y1"])),
                *conv.to_screen(float(args["x2"]), float(args["y2"])),
                conv,
            )
        case "type":
            type_text(str(args["text"]))
        case "scroll":
            scroll(float(args["dy"]))

def load_story() -> str:
    if STORY_FILE.exists():
        try:
            s = STORY_FILE.read_text(encoding="utf-8", errors="replace").strip()
            if s:
                return s
        except Exception:
            pass
    return DEFAULT_STORY

def save_story(story: str) -> None:
    try:
        STORY_FILE.write_text(story, encoding="utf-8")
    except Exception:
        pass

def main() -> None:
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    conv = Coord(sw=sw, sh=sh)

    dump = DUMP_FOLDER / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dump.mkdir(parents=True, exist_ok=True)

    print(f"FRANZ | Screen: {sw}x{sh} | Model: {SCREEN_W}x{SCREEN_H} | TEST_MODE={TEST_MODE}")
    print(f"Dump: {dump}")
    print("PAUSED - edit story in HUD, click RESUME")
    print("HUD: Ctrl+Wheel=zoom, Ctrl+Shift+Wheel=cycle background")

    current_story = load_story()

    with HUD() as hud:
        hud.update(current_story)
        step = 0
        obs: ObsWindow | None = None
        hud.wait()

        while not hud.stop.is_set():
            hud.wait()
            if hud.stop.is_set():
                break

            try:
                edited = hud.get_text().strip()
                if edited and edited != current_story:
                    current_story = edited
                    save_story(current_story)
            except Exception:
                pass

            step += 1
            ts = datetime.now().strftime("%H:%M:%S")

            bgra = capture_screen(sw, sh)
            png = encode_png(downsample(bgra, sw, sh, SCREEN_W, SCREEN_H), SCREEN_W, SCREEN_H)
            (dump / f"step{step:03d}.png").write_bytes(png)

            if obs:
                obs.hide()
                obs = None

            try:
                tool, args = call_vlm_or_test(png, current_story, step)
            except Exception as e:
                print(f"[{ts}] {step:03d} | VLM ERROR: {e}")
                time.sleep(1.0)
                continue

            args = normalize_args(args)
            tool = str(tool).strip().lower()

            if tool not in REQUIRED_ARGS:
                print(f"[{ts}] {step:03d} | UNKNOWN TOOL: {tool}")
                time.sleep(1.0)
                continue

            missing = [k for k in REQUIRED_ARGS[tool] if k not in args]
            if missing:
                print(f"[{ts}] {step:03d} | {tool} | MISSING: {missing}")
                time.sleep(1.0)
                continue

            report = str(args.get("report", "")).strip()
            if not report:
                print(f"[{ts}] {step:03d} | {tool} | EMPTY REPORT")
                time.sleep(1.0)
                continue

            normalize_hormones(args)
            hud.set_hormones_title(
                float(args["curiosity"]),
                float(args["pain"]),
                float(args["boredom"]),
                float(args["curiosity_after"]),
                float(args["pain_after"]),
                float(args["boredom_after"]),
            )

            print(
                f"[{ts}] {step:03d} | {tool} | "
                f"C {fmt_pct(float(args['curiosity'])):03d}->{fmt_pct(float(args['curiosity_after'])):03d} "
                f"P {fmt_pct(float(args['pain'])):03d}->{fmt_pct(float(args['pain_after'])):03d} "
                f"B {fmt_pct(float(args['boredom'])):03d}->{fmt_pct(float(args['boredom_after'])):03d}"
            )

            if tool == "attend":
                ox, oy = conv.to_screen(float(args["x"]), float(args["y"]))
                obs = ObsWindow()
                obs.show(ox, oy, sw, sh)
            elif tool == "ipse_tune":
                apply_sampling(args)
            else:
                execute(tool, args, conv)
                if tool in ("click", "double_click", "right_click"):
                    ox, oy = conv.to_screen(float(args["x"]), float(args["y"]))
                    obs = ObsWindow()
                    obs.show(ox, oy, sw, sh)
                elif tool == "drag":
                    ox, oy = conv.to_screen(float(args["x2"]), float(args["y2"]))
                    obs = ObsWindow()
                    obs.show(ox, oy, sw, sh)

            current_story = report
            save_story(current_story)
            hud.update(current_story)

            time.sleep(0.3)

        if obs:
            obs.hide()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFRANZ stops.")
