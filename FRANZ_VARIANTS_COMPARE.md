# FRANZ Variant Inventory & Merge Notes (base: self-execution.py)

Generated: 2026-02-06 19:22:47

This document compares all attached local variants and summarizes which parts are worth merging into **self-execution.py** (the chosen base). It also cross-references older public repos to keep the iteration aligned with the long-term goal (“Memento Protocol”: stateless narrative identity + memory as text-surface).

---

## 1) High-level architecture (self-execution.py)

**Loop (intended):**
1. Capture screen → downsample → encode PNG → dump to disk.
2. Send to LM Studio **chat completions** with tool schemas.
3. Execute one tool call (mouse/keyboard/attend) + show red observation rectangle at last action point.
4. Persist the rewritten narrative to `franz_memory.txt` and mirror it into the HUD.

**Reality check (current base behavior):**
- The base hides the HUD during screenshot capture (`SW_HIDE`) and sends **image-only** to the VLM.
- Because LM Studio calls are stateless, this makes the agent effectively memoryless unless memory is also sent as text context.

So: **either keep HUD visible in the screenshot** *or* **send the story as text** in the request (recommended; keeps dumps clean and remains stateless).

---

## 2) Feature matrix (local files)

| file                              | captureblt   | robust_parse   | stateless_text_context   | ipse_tune   | hud_get_text   | story_file   | hud_hidden_during_capture   | tool_arg_story   | tool_arg_report   |
|:----------------------------------|:-------------|:---------------|:-------------------------|:------------|:---------------|:-------------|:----------------------------|:-----------------|:------------------|
| self-execution.py                 | True         | True           | False                    | False       | False          | True         | True                        | True             | False             |
| main.py                           | False        | False          | True                     | False       | True           | False        | False                       | False            | True              |
| main_basic-refactoring-TEST-OK.py | True         | True           | True                     | True        | True           | False        | False                       | False            | True              |
| main-IDEOLO.py                    | True         | True           | False                    | False       | False          | False        | False                       | True             | False             |
| main-weird-stuff.py               | True         | True           | False                    | False       | True           | False        | False                       | False            | False             |
| grok-cooked-today.py              | True         | True           | False                    | False       | True           | False        | False                       | False            | False             |
| startupmessageadded.py            | True         | True           | False                    | False       | True           | False        | False                       | False            | False             |

---

## 3) What each local variant contributed

### main.py
- + Stateless memory (sends `STORY:` text alongside image).
- − Missing CAPTUREBLT ⇒ observation overlay not present in dumps.
- − Naive tool parsing ⇒ intermittent type errors.

### main_basic-refactoring-TEST-OK.py
- + Robust tool-call parsing.
- + `ipse_tune` + `apply_sampling()` (runtime sampler changes).
- + `HUD.get_text()` (import human edits after resume).
- + Sends memory clip + sampler dict as text context.

### main-IDEOLO.py
- + Strong constitution / narrative identity template.
- − Still image-only (relies on HUD being visible in screenshot).

### main-weird-stuff.py
- Experimental HUD_TEXT overwrites; loosened tool schemas (can drop memory enforcement).

### grok-cooked-today.py / startupmessageadded.py
- Minimal HUD monitor style; mostly useful for WinAPI/tool wiring tests.

---

## 4) Merge diffs

### 4.1 Composite patch onto self-execution.py (recommended)

```diff
--- a/self-execution.py
+++ b/self-execution.py
@@ -37,6 +37,29 @@
     "max_tokens": 600,
     "min_completion_tokens": 150,
 }
+
+ALLOWED_SAMPLING_KEYS = {
+    "temperature", "top_p", "top_k", "repeat_penalty",
+    "presence_penalty", "frequency_penalty", "max_tokens",
+    "min_completion_tokens", "seed",
+}
+
+def apply_sampling(args: dict[str, Any]) -> None:
+    """Unsafe mode: apply sampler keys as provided (after numeric coercion)."""
+    for k, v in list(args.items()):
+        if k not in ALLOWED_SAMPLING_KEYS:
+            continue
+        if v is None:
+            SAMPLING.pop(k, None)
+            continue
+        n = coerce_num(v)
+        if n is None:
+            continue
+        if k in {"top_k", "max_tokens", "min_completion_tokens", "seed"}:
+            SAMPLING[k] = int(n)
+        else:
+            SAMPLING[k] = float(n)
+
 
 CONSTITUTION = """FRANZ IDENTITY PROTOCOL
 
@@ -200,6 +223,7 @@
     "type": ("text", "story"),
     "scroll": ("dy", "story"),
     "attend": ("x", "y", "story"),
+    "ipse_tune": ("story",),
 }
 
 user32 = ctypes.WinDLL("user32", use_last_error=True)
@@ -679,14 +703,17 @@
     
     raise KeyError("VLM response missing tool call")
 
-def call_vlm(png: bytes) -> tuple[str, dict[str, Any]]:
+def call_vlm(png: bytes, story: str) -> tuple[str, dict[str, Any]]:
+    clip = story[-STORY_CONTEXT_CHARS:] if story else ""
     payload = {
         "model": MODEL_NAME,
         "messages": [
+            {"role": "system", "content": CONSTITUTION},
             {
                 "role": "user",
                 "content": [
                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64.b64encode(png).decode('ascii')}"}},
+                    {"type": "text", "text": f"MEMORY (most recent; rewrite fully in tool story):\n{clip}\n\nSAMPLER (may change via ipse_tune):\n{json.dumps(SAMPLING, ensure_ascii=False, sort_keys=True)}"},
                 ],
             },
         ],
@@ -700,7 +727,7 @@
     args = _parse_tool_arguments(args_raw)
     return str(name).strip().lower(), args
 
-@dataclass(slots=True)
+
 class ObsWindow:
     hwnd: w.HWND | None = None
     thread: threading.Thread | None = None
@@ -945,6 +972,19 @@
         if self.thread:
             self.thread.join(timeout=1.0)
 
+    def get_text(self) -> str:
+        if not self.edit:
+            return ""
+        try:
+            n = user32.GetWindowTextLengthW(self.edit)
+            if n <= 0:
+                return ""
+            buf = ctypes.create_unicode_buffer(n + 1)
+            user32.GetWindowTextW(self.edit, buf, n + 1)
+            return buf.value
+        except Exception:
+            return ""
+
     def update(self, story: str) -> None:
         if self.edit:
             current_num = ctypes.c_uint()
@@ -1047,7 +1087,7 @@
             
             try:
                 try:
-                    tool, args = call_vlm(png)
+                    tool, args = call_vlm(png, current_story)
                 except Exception as e:
                     print(f"\n[{ts}] {step:03d} | VLM ERROR: {e}")
                     time.sleep(1.0)
@@ -1078,6 +1118,8 @@
                     ox, oy = conv.to_screen(float(args["x"]), float(args["y"]))
                     obs = ObsWindow()
                     obs.show(ox, oy, sw, sh)
+                elif tool == "ipse_tune":
+                    apply_sampling(args)
                 else:
                     execute(tool, args, conv)
                     
```

### 4.2 Minimal patch (fix “red box missing in dump” in main.py)

```diff
--- a/main.py
+++ b/main.py
@@ -413,7 +413,7 @@
         user32.ReleaseDC(0, sdc)
         raise ctypes.WinError(ctypes.get_last_error())
     gdi32.SelectObject(mdc, hbm)
-    if not gdi32.BitBlt(mdc, 0, 0, sw, sh, sdc, 0, 0, SRCCOPY):
+    if not gdi32.BitBlt(mdc, 0, 0, sw, sh, sdc, 0, 0, SRCCOPY | CAPTUREBLT):
         gdi32.DeleteObject(hbm)
         gdi32.DeleteDC(mdc)
         user32.ReleaseDC(0, sdc)
```

---

## 6) External repos (web) — extracted ideas to port into FRANZ

### 6.1 Your older FRANZ toolsets (wgabrys88/*)

**v20-FRANZ-2**
- Claims “stateless architecture maintained” plus “red box shown for ALL spatial actions” and “story full replacement (not append)”.
- Mentions font zoom persistence fix and variable-shadowing fix; these both map to the current WinAPI HUD implementation.

**v19.9-T200-Terminator**
- Explicitly states the key “3-input loop”: screenshot after action + story text memory + red box pointer, and recommends the story focus on progress instead of coordinates.

**v19.5-MADAFAK-JOKER**
- Calls out Observe/Execute confusion and suggests a dedicated UI control (instead of the generic pause/resume) to reduce mode drift.

**The-Memento-Protocol**
- Frames “Trust” and “Energy” as core: trust reduces verification cost; low-trust increases repeated checking / higher-fidelity capture.

Practical translation into FRANZ:
- Add a single scalar in the narrative: `TRUST ∈ [0..1]` (or `energy_budget`) that the model can adjust (via tool) to request higher-res capture / extra verification steps when needed.

### 6.2 Research/benchmark repos to align iteration & measure progress

**OS-Symphony**
- Uses an Orchestrator coordinating:
  - Reflection-Memory Agent with milestone-driven long-term memory + structured message protocol, aimed at fixing visual context loss.
  - “SeeAct” style Multimodal Searcher that generates visually aligned tutorials.

Mapping into FRANZ (single-file version):
- Add a “Milestone” line type in your story template (separate from Chronicle).
- Add a “reflection” mini-pass (tool-free) that runs every N steps: restate the current Milestone(s), check contradictions, and decide whether to self-tune sampler.

**Microsoft UFO**
- Emphasizes hybrid actions (GUI + API), speculative multi-action (reducing LLM calls), and a knowledge substrate (docs/demos/traces).
- Even if FRANZ stays GUI-only, the pattern is useful: keep a small, searchable execution-trace log separate from narrative, and let the model retrieve it.

**Agent-S**
- Shows a strong pattern: split “main model” from a dedicated grounding model for coordinates.
- For FRANZ: keep Qwen3-VL-2B for narrative + decision, but optionally add a dedicated “grounder” later if coordinate quality becomes the bottleneck.

---

## 7) Optional diffs suggested by the external repos (not implemented above)

1) **Observe/Execute button** (v19.5): rename the HUD button + semantics to reduce “mode confusion”.
2) **Milestone memory** (OS-Symphony): add a structured “Milestones” section to the story template; update it every K steps, not every step.
3) **Verification knob** (Memento Protocol): introduce a `quality`/`trust` parameter; low trust triggers higher capture resolution or extra no-op “confirm” steps.
4) **Trace substrate** (UFO): add a small append-only `trace.jsonl` separate from story, so the story can stay literary while trace stays forensic.

