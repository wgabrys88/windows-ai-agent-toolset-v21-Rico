# FRANZ (grok base + TEST-OK features)

This is a merge of `grok-cooked-today.py` (base) plus missing agent features from `main_basic-refactoring-TEST-OK.py`:

- Stateless narrative memory sent as text context (the HUD log) on every request.
- Tool schema requires `report` (full rewrite of the narrative log every turn).
- `ipse_tune` tool allows the model to change sampling parameters at runtime (unsafe mode).
- Pause/Resume button in HUD. HUD is editable only when paused.
- HUD background color cycling and a visible separator line in the story.
- CAPTUREBLT capture so layered/topmost windows (HUD and red box) can appear in dumps.
- TEST mode (mock VLM responses injected where the real VLM call happens).
- Three resolution presets with environment-variable switching.

## Run

```powershell
python franz_grok_merged.py
```

A `dump/run_YYYYMMDD_HHMMSS/` folder is created with `stepNNN.png` screenshots.

The narrative is persisted to `franz_memory.txt`.

## Controls

- Click RESUME to start the loop. Click PAUSE to stop acting and edit the story.
- Ctrl + MouseWheel: zoom HUD text.
- Ctrl + Shift + MouseWheel: cycle HUD background color.

## Resolution presets

Set `FRANZ_RES`:

- low: 512x288 (default)
- med: 768x432
- high: 1024x576

Example:

```powershell
setx FRANZ_RES high
```

## Test mode

Set `FRANZ_TEST=1` to bypass LM Studio and use an internal mock model that returns tool calls and rewrites the story.

```powershell
setx FRANZ_TEST 1
python franz_grok_merged.py
```

## LM Studio API

This uses OpenAI-compatible `/v1/chat/completions` with tools.
