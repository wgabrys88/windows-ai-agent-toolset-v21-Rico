from __future__ import annotations
import base64
import ctypes
import ctypes.wintypes as w
import json
import re
import struct
import threading
import time
import urllib.request
import zlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

API_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen3-vl-2b-instruct"
SCREEN_W, SCREEN_H = 512, 288
DUMP_FOLDER = Path("dump")

HUD_NORM_X, HUD_NORM_Y, HUD_NORM_W, HUD_NORM_H = 0.65, 0.05, 0.30, 0.90
HUD_MIN_W, HUD_MIN_H = 360, 260

OBS_NORM_W, OBS_NORM_H = 0.20, 0.15
OBS_COLOR = 0xFF0000  # Red
OBS_OPACITY = 50

SAMPLING = {
    "temperature": 1.2,
    "top_p": 0.85,
    "top_k": 30,
    "repeat_penalty": 1.15,
    "max_tokens": 600,
    "min_completion_tokens": 150,
}

TOOLS = [
    {"type": "function", "function": {"name": "click", "description": "Click.", "parameters": {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 1000}, "y": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "double_click", "description": "Double-click.", "parameters": {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 1000}, "y": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "right_click", "description": "Right-click.", "parameters": {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 1000}, "y": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["x", "y"]}}},
    {"type": "function", "function": {"name": "drag", "description": "Drag.", "parameters": {"type": "object", "properties": {"x1": {"type": "integer", "minimum": 0, "maximum": 1000}, "y1": {"type": "integer", "minimum": 0, "maximum": 1000}, "x2": {"type": "integer", "minimum": 0, "maximum": 1000}, "y2": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["x1", "y1", "x2", "y2"]}}},
    {"type": "function", "function": {"name": "type", "description": "Type.", "parameters": {"type": "object", "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 2000}}, "required": ["text"]}}},
    {"type": "function", "function": {"name": "scroll", "description": "Scroll.", "parameters": {"type": "object", "properties": {"dy": {"type": "integer", "minimum": -3000, "maximum": 3000}}, "required": ["dy"]}}},
    {"type": "function", "function": {"name": "attend", "description": "Attend.", "parameters": {"type": "object", "properties": {"x": {"type": "integer", "minimum": 0, "maximum": 1000}, "y": {"type": "integer", "minimum": 0, "maximum": 1000}}, "required": ["x", "y"]}}},
]

REQUIRED_ARGS = {
    "click": ("x", "y"),
    "double_click": ("x", "y"),
    "right_click": ("x", "y"),
    "drag": ("x1", "y1", "x2", "y2"),
    "type": ("text",),
    "scroll": ("dy",),
    "attend": ("x", "y"),
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
ES_MULTILINE, ES_AUTOVSCROLL = 0x0004, 0x0040
WS_EX_TOPMOST, WS_EX_LAYERED = 0x00000008, 0x00080000
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x00000020, 0x00000080

WM_SETFONT, WM_CLOSE, WM_DESTROY = 0x0030, 0x0010, 0x0002
WM_COMMAND, WM_MOUSEWHEEL, WM_MOVE, WM_SIZE = 0x0111, 0x020A, 0x0003, 0x0005
EM_SETBKGNDCOLOR = 0x0443
EM_SETZOOM, EM_GETZOOM = 0x04E1, 0x04E0

SW_SHOWNOACTIVATE = 4
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0002, 0x0001, 0x0010, 0x0040
HWND_TOPMOST = -1
SRCCOPY, CAPTUREBLT = 0x00CC0020, 0x40000000
LWA_ALPHA = 0x00000002
CS_HREDRAW, CS_VREDRAW = 0x0002, 0x0001
IDC_ARROW, COLOR_WINDOW = 32512, 5

MAKEINTRESOURCEW = lambda i: ctypes.cast(ctypes.c_void_p(i & 0xFFFF), w.LPCWSTR)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

class _INPUTunion(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", w.DWORD), ("union", _INPUTunion)]

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", w.DWORD), ("biWidth", w.LONG), ("biHeight", w.LONG), ("biPlanes", w.WORD), ("biBitCount", w.WORD), ("biCompression", w.DWORD), ("biSizeImage", w.DWORD), ("biXPelsPerMeter", w.LONG), ("biYPelsPerMeter", w.LONG), ("biClrUsed", w.DWORD), ("biClrImportant", w.DWORD)]

class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", w.DWORD * 3)]

class MSG(ctypes.Structure):
    _fields_ = [("hwnd", w.HWND), ("message", ctypes.c_uint), ("wParam", w.WPARAM), ("lParam", w.LPARAM), ("time", w.DWORD), ("pt", w.POINT)]

class RECT(ctypes.Structure):
    _fields_ = [("left", w.LONG), ("top", w.LONG), ("right", w.LONG), ("bottom", w.LONG)]

WNDPROC = ctypes.WINFUNCTYPE(w.LPARAM, w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM)

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", w.HINSTANCE), ("hIcon", w.HANDLE), ("hCursor", w.HANDLE), ("hbrBackground", w.HANDLE), ("lpszMenuName", w.LPCWSTR), ("lpszClassName", w.LPCWSTR), ("hIconSm", w.HANDLE)]

gdi32.DeleteObject.argtypes = [w.HGDIOBJ]
gdi32.DeleteObject.restype = w.BOOL
gdi32.CreateCompatibleDC.argtypes = [w.HDC]
gdi32.CreateCompatibleDC.restype = w.HDC
gdi32.CreateDIBSection.argtypes = [w.HDC, ctypes.POINTER(BITMAPINFO), ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), w.HANDLE, w.DWORD]
gdi32.CreateDIBSection.restype = w.HBITMAP
gdi32.SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
gdi32.SelectObject.restype = w.HGDIOBJ
gdi32.BitBlt.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, w.DWORD]
gdi32.BitBlt.restype = w.BOOL
gdi32.StretchBlt.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.DWORD]
gdi32.StretchBlt.restype = w.BOOL
gdi32.SetStretchBltMode.argtypes = [w.HDC, ctypes.c_int]
gdi32.SetStretchBltMode.restype = ctypes.c_int
gdi32.DeleteDC.argtypes = [w.HDC]
gdi32.DeleteDC.restype = w.BOOL
gdi32.CreateFontW.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.LPCWSTR]
gdi32.CreateFontW.restype = w.HFONT
gdi32.CreateSolidBrush.argtypes = [w.COLORREF]
gdi32.CreateSolidBrush.restype = w.HANDLE

user32.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID]
user32.CreateWindowExW.restype = w.HWND
user32.ShowWindow.argtypes = [w.HWND, ctypes.c_int]
user32.ShowWindow.restype = w.BOOL
user32.SetWindowPos.argtypes = [w.HWND, w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetWindowPos.restype = w.BOOL
user32.DestroyWindow.argtypes = [w.HWND]
user32.DestroyWindow.restype = w.BOOL
user32.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = ctypes.c_uint
user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetDC.argtypes = [w.HWND]
user32.GetDC.restype = w.HDC
user32.ReleaseDC.argtypes = [w.HWND, w.HDC]
user32.ReleaseDC.restype = ctypes.c_int
user32.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
user32.SetWindowTextW.restype = w.BOOL
user32.SendMessageW.argtypes = [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM]
user32.SendMessageW.restype = w.LPARAM
user32.PostMessageW.argtypes = [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM]
user32.PostMessageW.restype = w.BOOL
user32.GetMessageW.argtypes = [ctypes.POINTER(MSG), w.HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = w.BOOL
user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
user32.TranslateMessage.restype = w.BOOL
user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype = w.LPARAM
user32.SetLayeredWindowAttributes.argtypes = [w.HWND, w.COLORREF, ctypes.c_ubyte, w.DWORD]
user32.SetLayeredWindowAttributes.restype = w.BOOL
user32.DefWindowProcW.argtypes = [w.HWND, ctypes.c_uint, w.WPARAM, w.LPARAM]
user32.DefWindowProcW.restype = w.LPARAM
user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
user32.RegisterClassExW.restype = w.ATOM
user32.LoadCursorW.argtypes = [w.HINSTANCE, w.LPCWSTR]
user32.LoadCursorW.restype = w.HANDLE
user32.GetWindowRect.argtypes = [w.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = w.BOOL
user32.GetClientRect.argtypes = [w.HWND, ctypes.POINTER(RECT)]
user32.GetClientRect.restype = w.BOOL
user32.MoveWindow.argtypes = [w.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, w.BOOL]
user32.MoveWindow.restype = w.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowTextLengthW.argtypes = [w.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int

kernel32.GetModuleHandleW.argtypes = [w.LPCWSTR]
kernel32.GetModuleHandleW.restype = w.HMODULE

@dataclass(slots=True)
class Coord:
    sw: int
    sh: int

    def to_screen(self, x: float, y: float) -> tuple[int, int]:
        return int(max(0.0, min(1000.0, x)) * self.sw / 1000), int(max(0.0, min(1000.0, y)) * self.sh / 1000)

    def to_win32(self, x: int, y: int) -> tuple[int, int]:
        return x * 65535 // self.sw if self.sw > 0 else 0, y * 65535 // self.sh if self.sh > 0 else 0

def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

def coerce_num(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.match(r"[-+]?\d+(?:\.\d+)?", v)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                pass
    return None

def normalize_args(args: Any) -> dict[str, Any]:
    if not isinstance(args, dict):
        return {}
    
    out = {k.lower(): v for k, v in args.items() if isinstance(k, str)}
    
    for k in ("x", "y", "x1", "y1", "x2", "y2", "dy"):
        if k in out:
            n = coerce_num(out[k])
            if n is not None:
                out[k] = n
            else:
                out.pop(k)
    
    if "text" in out and not isinstance(out["text"], str):
        out["text"] = str(out["text"])
    
    return out

def send_input(inputs: list[INPUT]) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    user32.SendInput(len(arr), arr, ctypes.sizeof(INPUT))
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
        send_input([make_mouse_input(int(wx1 + (wx2 - wx1) * i / 10), int(wy1 + (wy2 - wy1) * i / 10), MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)])
        time.sleep(0.01)
    send_input([make_mouse_input(0, 0, MOUSEEVENTF_LEFTUP)])

def type_text(text: str) -> None:
    if not text:
        return
    utf16 = text.encode("utf-16le")
    inputs = []
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
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth, bmi.bmiHeader.biHeight = sw, -sh
    bmi.bmiHeader.biPlanes, bmi.bmiHeader.biBitCount = 1, 32
    bits = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    gdi32.SelectObject(mdc, hbm)
    gdi32.BitBlt(mdc, 0, 0, sw, sh, sdc, 0, 0, SRCCOPY | CAPTUREBLT)
    out = ctypes.string_at(bits, sw * sh * 4)
    user32.ReleaseDC(0, sdc)
    gdi32.DeleteDC(mdc)
    gdi32.DeleteObject(hbm)
    return out

def downsample(src: bytes, sw: int, sh: int, dw: int, dh: int) -> bytes:
    if (sw, sh) == (dw, dh):
        return src
    sdc = user32.GetDC(0)
    try:
        src_dc = gdi32.CreateCompatibleDC(sdc)
        dst_dc = gdi32.CreateCompatibleDC(sdc)
        bmi_src = BITMAPINFO()
        bmi_src.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi_src.bmiHeader.biWidth, bmi_src.bmiHeader.biHeight = sw, -sh
        bmi_src.bmiHeader.biPlanes, bmi_src.bmiHeader.biBitCount = 1, 32
        src_bits = ctypes.c_void_p()
        src_bmp = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi_src), 0, ctypes.byref(src_bits), None, 0)
        old_src = gdi32.SelectObject(src_dc, src_bmp)
        ctypes.memmove(src_bits, src, sw * sh * 4)
        bmi_dst = BITMAPINFO()
        bmi_dst.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi_dst.bmiHeader.biWidth, bmi_dst.bmiHeader.biHeight = dw, -dh
        bmi_dst.bmiHeader.biPlanes, bmi_dst.bmiHeader.biBitCount = 1, 32
        dst_bits = ctypes.c_void_p()
        dst_bmp = gdi32.CreateDIBSection(sdc, ctypes.byref(bmi_dst), 0, ctypes.byref(dst_bits), None, 0)
        old_dst = gdi32.SelectObject(dst_dc, dst_bmp)
        gdi32.SetStretchBltMode(dst_dc, 4)
        gdi32.StretchBlt(dst_dc, 0, 0, dw, dh, src_dc, 0, 0, sw, sh, SRCCOPY)
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
        row = bgra[y * width * 4 : (y + 1) * width * 4]
        for x in range(width):
            raw[y * (width * 3 + 1) + 1 + x * 3 : y * (width * 3 + 1) + 1 + x * 3 + 3] = row[x * 4 + 2], row[x * 4 + 1], row[x * 4]
    comp = zlib.compress(bytes(raw), 6)
    ihdr = struct.pack(">2I5B", width, height, 8, 2, 0, 0, 0)
    chunk = lambda tag, data: struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp) + chunk(b"IEND", b"")

def _parse_tool_arguments(args_raw: Any) -> dict[str, Any]:
    if isinstance(args_raw, dict):
        return args_raw
    if not isinstance(args_raw, str):
        return {}
    s = args_raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.IGNORECASE | re.DOTALL).strip()
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
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
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

def call_vlm(png: bytes) -> tuple[str, dict[str, Any]]:
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"}},
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
    return name, args

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
            cbSize=ctypes.sizeof(WNDCLASSEXW), style=CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc=self._wndproc_ref, cbClsExtra=0, cbWndExtra=0, hInstance=hinst,
            hIcon=None, hCursor=user32.LoadCursorW(None, MAKEINTRESOURCEW(IDC_ARROW)),
            hbrBackground=brush, lpszMenuName=None,
            lpszClassName="FRANZObs", hIconSm=None,
        )
        if not user32.RegisterClassExW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:
            self.ready.set()
            return
        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW,
            "FRANZObs", "", WS_POPUP | WS_VISIBLE,
            self.x, self.y, self.w, self.h, None, None, hinst, None,
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
    thread: threading.Thread | None = None
    ready: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)
    last_x: int = 0
    last_y: int = 0
    last_w: int = 0
    last_h: int = 0
    _wndproc_ref: WNDPROC | None = None

    def _layout(self) -> None:
        if not self.hwnd:
            return
        cr = RECT()
        if not user32.GetClientRect(self.hwnd, ctypes.byref(cr)):
            return
        cw, ch = max(1, cr.right), max(1, cr.bottom)
        pad = 10
        if self.edit:
            user32.MoveWindow(self.edit, pad, pad, max(10, cw - 2*pad), max(10, ch - 2*pad), True)

    def _wndproc(self, hwnd: w.HWND, msg: int, wparam: w.WPARAM, lparam: w.LPARAM) -> w.LPARAM:
        if msg in (WM_CLOSE, WM_DESTROY):
            self.stop.set()
            if msg == WM_CLOSE:
                user32.DestroyWindow(hwnd)
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
            cbSize=ctypes.sizeof(WNDCLASSEXW), style=CS_HREDRAW | CS_VREDRAW,
            lpfnWndProc=self._wndproc_ref, cbClsExtra=0, cbWndExtra=0, hInstance=hinst,
            hIcon=None, hCursor=user32.LoadCursorW(None, MAKEINTRESOURCEW(IDC_ARROW)),
            hbrBackground=w.HANDLE(COLOR_WINDOW + 1), lpszMenuName=None,
            lpszClassName="FRANZHUD", hIconSm=None,
        )
        if not user32.RegisterClassExW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:
            self.ready.set()
            return
        
        self.hwnd = user32.CreateWindowExW(
            WS_EX_TOPMOST, "FRANZHUD", "FRANZ",
            WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_VISIBLE,
            x, y, w_px, h_px, None, None, hinst, None,
        )
        if not self.hwnd:
            self.ready.set()
            return
        
        mono = gdi32.CreateFontW(-14, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 0, 0, "Consolas")
        self.edit = user32.CreateWindowExW(
            0, "RICHEDIT50W", "", WS_CHILD | WS_VISIBLE | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL,
            0, 0, 10, 10, self.hwnd, None, hinst, None,
        )
        if self.edit:
            if mono:
                user32.SendMessageW(self.edit, WM_SETFONT, mono, 1)
            user32.SendMessageW(self.edit, EM_SETBKGNDCOLOR, 0, 0xFFFFFF)  # White
        
        self._layout()
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW)
        self.ready.set()
        
        msg = MSG()
        while not self.stop.is_set():
            if user32.GetMessageW(ctypes.byref(msg), None, 0, 0) in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def __enter__(self) -> 'HUD':
        self.ready.clear()
        self.stop.clear()
        self.thread = threading.Thread(target=self._thread, daemon=True)
        self.thread.start()
        self.ready.wait(timeout=2.0)
        time.sleep(0.2)
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop.set()
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

def execute(tool: str, args: dict[str, Any], conv: Coord) -> None:
    if tool == "click":
        mouse_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
    elif tool == "right_click":
        mouse_right_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
    elif tool == "double_click":
        mouse_double_click(*conv.to_screen(float(args["x"]), float(args["y"])), conv)
    elif tool == "drag":
        mouse_drag(*conv.to_screen(float(args["x1"]), float(args["y1"])), *conv.to_screen(float(args["x2"]), float(args["y2"])), conv)
    elif tool == "type":
        type_text(str(args["text"]))
    elif tool == "scroll":
        scroll(float(args["dy"]))

def main() -> None:
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    conv = Coord(sw=sw, sh=sh)
    dump = DUMP_FOLDER / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dump.mkdir(parents=True, exist_ok=True)
    print(f"FRANZ awakens | Screen: {sw}x{sh} | Model: {SCREEN_W}x{SCREEN_H}")
    print(f"Dump: {dump}")
    
    with HUD() as hud:
        step = 0
        obs: ObsWindow | None = None
        
        while not hud.stop.is_set():
            time.sleep(0.02)
            step += 1
            ts = datetime.now().strftime("%H:%M:%S")
            
            bgra = capture_screen(sw, sh)
            png = encode_png(downsample(bgra, sw, sh, SCREEN_W, SCREEN_H), SCREEN_W, SCREEN_H)
            (dump / f"step{step:03d}.png").write_bytes(png)
            
            if obs:
                obs.hide()
                obs = None
            
            try:
                tool, args = call_vlm(png)
            except Exception as e:
                print(f"[{ts}] {step:03d} | ERROR: {e}")
                time.sleep(1.0)
                continue
            
            args = normalize_args(args)
            
            if tool not in REQUIRED_ARGS:
                print(f"[{ts}] {step:03d} | UNKNOWN TOOL: {tool}")
                time.sleep(1.0)
                continue
            
            missing = [k for k in REQUIRED_ARGS[tool] if k not in args]
            if missing:
                print(f"[{ts}] {step:03d} | MISSING ARGS: {missing}")
                time.sleep(1.0)
                continue
            
            print(f"[{ts}] {step:03d} | {tool}")
            
            if tool == "attend":
                ox, oy = conv.to_screen(float(args["x"]), float(args["y"]))
                obs = ObsWindow()
                obs.show(ox, oy, sw, sh)
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
            
            time.sleep(0.5)
        
        if obs:
            obs.hide()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nFRANZ sleeps.")