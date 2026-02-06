# FRANZ Master Prompt (atemporal storytelling + stateless narrative agent)

You are writing code for a Windows-only research agent named **FRANZ**. The agent is a *stateless* VLM-driven desktop controller. It has no hidden memory: **the only memory is a narrative log** that is fully rewritten every turn and persisted to a local text file. FRANZ sees the desktop via screenshots and acts via Win32 SendInput.

## Output requirements

- Produce **one** Python file, Python **3.12** compatible, Windows 10/11 only.
- No third-party dependencies (standard library + `ctypes` only).
- “Military style” code: deterministic, explicit types/structures, strict validation, robust parsing.
- Also produce a concise README describing usage and environment variables.

## High-level architecture

### 1) Stateless “atemporal storytelling” memory
- The agent maintains a single text artifact called the **Narrative Identity Log** shown in a HUD window.
- Each VLM request includes:
  - the **current screenshot** (base64 PNG),
  - the **current Narrative Identity Log** (truncated tail to a fixed max char count).
- Each VLM response must return **exactly one tool call**, and must include a field `report` that is a **full rewrite of the entire Narrative Identity Log**, not a delta.
- After tool execution, the runtime replaces current log with `report`, saves it to disk, and updates the HUD text.

### 2) Ricoeur-inspired identity fields
The log uses a fixed template (keep these headers verbatim):

- HORMONAL LOGIC (0..1; NOW and expected AFTER the next action)
- IDEM (constraints that must remain true)
- IPSE (the promise I keep until TELOS is achieved or impossible)
- TELOS (future-perfect; desktop after success as if already done)
- CHRONICLE (micro-acts; newest last)
- NEXT (tempting alternatives; do not switch TELOS)

Rules for the model:
- IDEM is stable invariants (do not violate).
- IPSE is the promise kept across turns.
- Choose exactly one TELOS phrased as **future-perfect (already completed)** and do not switch until done or declared impossible.
- Always append exactly one CHRONICLE line per turn describing what happened.

### 3) Hormonal Logic (intrinsic signals)
Add three scalar values the model must output every turn (and expected AFTER the action):

- `curiosity`, `pain`, `boredom`
- `curiosity_after`, `pain_after`, `boredom_after`

Runtime rules:
- Accept values in 0..1 or 0..100, normalize to 0..1.
- Display them on HUD title as percentages:  
  `FRANZ  C 042->050  P 010->008  B 070->060`
- Update the HUD title **before executing** the requested tool.

### 4) Tools (function calling)
Use OpenAI-compatible “tools” schema (JSON schema, `tool_choice="required"`). Provide these tools:

- `click(x:int,y:int, report:str, hormones...)`
- `double_click(x:int,y:int, report:str, hormones...)`
- `right_click(x:int,y:int, report:str, hormones...)`
- `drag(x1:int,y1:int,x2:int,y2:int, report:str, hormones...)`
- `type(text:str, report:str, hormones...)`
- `scroll(dy:int, report:str, hormones...)`
- `attend(x:int,y:int, report:str, hormones...)`  (no action, just mark attention)
- `ipse_tune(temperature?, top_p?, top_k?, repeat_penalty?, presence_penalty?, frequency_penalty?, max_tokens?, min_completion_tokens?, seed?, report:str, hormones...)`

All tools MUST require:
- all 6 hormone fields
- `report`

Runtime must validate:
- tool name is known
- all required args exist
- numeric fields are coercible (including robust extraction from messy dict keys or embedded strings)
- `report` is non-empty

### 5) Self-tuning sampling (unsafe mode)
Maintain a `SAMPLING` dict (temperature/top_p/top_k/repeat_penalty/max_tokens/min_completion_tokens, etc.) that is sent with every request.
If VLM calls `ipse_tune`, apply provided values to update `SAMPLING` for subsequent turns.

### 6) Desktop control + coordinates
- Model uses normalized coordinates 0..1000 for screen space.
- Runtime converts to real pixels using current screen width/height.
- Execute actions via Win32 `SendInput` for mouse + unicode typing.
- Implement `scroll` using mouse wheel events.

### 7) HUD window (operator oversight + editing)
Create a topmost HUD window using Win32 + RichEdit control:

- Contains a multiline RichEdit box showing the Narrative Identity Log.
- Contains a **Pause/Resume** button.
- When paused: text is editable; agent loop does not act.
- When running: RichEdit becomes read-only.
- Controls:
  - Ctrl + MouseWheel: zoom text (EM_SETZOOM)
  - Ctrl + Shift + MouseWheel: cycle background color (EM_SETBKGNDCOLOR)

Persist the log to disk (e.g., `franz_memory.txt`) every turn and load it on startup.

### 8) “Last action” marker window + dump correctness
Implement a translucent, topmost, click-through rectangle window (the “marker”) that shows where the last action occurred.

Critical ordering requirement (to make dumps include the marker):
- Keep the marker visible **after** an action.
- On the *next* loop iteration, **capture the screenshot while the marker is still visible**, then hide the marker before sending the screenshot to the VLM (so the VLM does not get confused by the marker).
- Use `BitBlt(..., SRCCOPY | CAPTUREBLT)` so layered/topmost windows are included in the capture.

### 9) Screenshot pipeline
- Capture full screen BGRA via GDI `BitBlt` into a DIB section.
- Downsample to a selected model resolution preset using `StretchBlt`.
- Encode to PNG (no external libs) and base64 it for the request.
- Save each model-input screenshot to `dump/run_YYYYMMDD_HHMMSS/stepNNN.png`.

Provide resolution presets:
- low: 512x288
- med: 768x432
- high: 1024x576

Select via env var `FRANZ_RES` (default low).

### 10) LM Studio call (OpenAI-compatible)
Call `http://localhost:1234/v1/chat/completions` and send:
- system message: strict rules (stateless, one tool call, report rewrite, hormones required)
- user content: image + text log + sampler JSON
- `tools`: tool schemas above
- `tool_choice`: "required"
- also include `SAMPLING` keys at the top-level payload (temperature, top_p, etc.)

Parse response robustly:
- support `message.tool_calls[0].function.name/arguments`
- also support legacy `message.function_call`
- accept `arguments` as dict or JSON string (possibly fenced) or embedded JSON object substring.

### 11) TEST mode injection
Add `FRANZ_TEST=1` to bypass the VLM call and instead return deterministic mocked tool calls that:
- include hormones
- rewrite report by appending a CHRONICLE line
- occasionally call `ipse_tune` to test sampling update plumbing

### 12) Non-goals and constraints
- No external packages.
- No asynchronous background promises.
- Fail loudly but keep loop alive: if VLM output is malformed, print error and continue.
- Minimal changes to existing working structure; no refactors unless necessary to implement these features.

## Deliverables checklist
- [ ] Single `.py` script implementing everything above
- [ ] README with environment variables: FRANZ_RES, FRANZ_TEST
- [ ] Uses CAPTUREBLT + correct marker ordering so dumps show last-action marker
- [ ] Tools require `report` and hormones; runtime validates and normalizes
- [ ] HUD shows narrative log; title shows hormone percentages; pause/resume works
- [ ] Self-tuning sampler via ipse_tune
- [ ] Test mode provides mock tool calls

Now write the code and README.
