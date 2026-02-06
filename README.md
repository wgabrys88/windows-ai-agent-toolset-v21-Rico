# FRANZ — Stateless Narrative Agent (Idem / Ipse)

FRANZ is a Windows desktop mouse+keyboard agent driven by a *stateless* VLM (Qwen3‑VL‑2B‑Instruct in LM Studio).  
The VLM never receives hidden state: every turn it receives only:
1) the downsampled screenshot, and  
2) the current contents of the cyan HUD window (the *entire* memory).

In response, the VLM must choose a tool call and provide a `report` string that **rewrites the full HUD log**.

## Ricoeurian framing: IDEM / IPSE → task persistence

This variant structures the HUD “memory” as a narrative-identity log:

- **IDEM** = sameness / constraints that must remain true (what you keep stable).
- **IPSE** = selfhood / promise you keep through change (what you commit to).
- **TELOS** = the *future-perfect* “as-if already completed” description of the desktop state after success.
- **CHRONICLE** = micro-acts, newest last.

The goal is to prevent task-hopping: once TELOS is chosen and written, IPSE binds the agent to pursue it until completed or declared impossible, while other tempting tasks can be recorded as `NEXT` without switching.

## Tools (OpenAI-compatible function calling)

Spatial / interaction tools:

- `click(x,y,report)`
- `double_click(x,y,report)`
- `right_click(x,y,report)`
- `drag(x1,y1,x2,y2,report)`
- `type(text,report)`
- `scroll(dy,report)`
- `attend(x,y,report)` — shows the red “attention” box without acting (a narrative gesture; useful while waiting).

Self-modification tool:

- `ipse_tune(..., report)` — updates sampling parameters used in subsequent `/v1/chat/completions` calls.
  Supported keys: `temperature`, `top_p`, `top_k`, `repeat_penalty`, `presence_penalty`, `frequency_penalty`,
  `max_tokens`, `min_completion_tokens`, `seed`.

  **Unsafe mode:** values are applied as provided (after numeric coercion). If your backend rejects a value, the request can fail.

### The `report` contract

Every tool call must include `report` which **fully rewrites** the entire HUD log in the fixed template:

- IDEM
- IPSE
- TELOS
- CHRONICLE

This is the only memory FRANZ has.

## Red box appears in dumps (screen capture behavior)

Two fixes ensure the red “attention” box can appear inside `dump/run_*/stepNNN.png` screenshots:

- The previous cycle’s red box is hidden **after** the next screenshot is captured (workflow order).
- Screen capture uses `SRCCOPY | CAPTUREBLT`, allowing layered windows (HUD + red box) to be included.

## Running

1. Start LM Studio with the model loaded and OpenAI-compatible server enabled (default `http://localhost:1234`).
2. Run:

   ```bash
   python main.py
   ```

3. Use the HUD: write any initial context / “opening scene” into the log, then press **RESUME**.

## Files

- `main.py` — agent loop, HUD overlay, red attention box, tool execution, VLM call + function parsing.
- `dump/run_*/stepNNN.png` — per-step screenshots used for debugging.