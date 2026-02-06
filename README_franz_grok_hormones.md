# FRANZ (Hormonal Logic: Curiosity, Pain, Boredom)

This build extends the working `franz_grok_merged.py` with three scalar values that the VLM must supply on every turn:

- Curiosity (NOW and expected AFTER the action)
- Pain (NOW and expected AFTER the action)
- Boredom (NOW and expected AFTER the action)

They are sent back as tool arguments and displayed in the HUD title as percentages:

`FRANZ  C 042->050  P 010->008  B 070->060`

Values are expected in 0..1. If the model returns 0..100, the runtime normalizes them.

## Why this design

Curiosity and boredom are commonly modeled as intrinsic motivation signals that modulate exploration vs exploitation, and boredom can shift behavior toward exploration when the current trajectory yields low informational gain. Pain is the simplest negative cost signal. See: Schmidhuber (intrinsic motivation/compression progress) and Oudeyer et al. (learning progress / curiosity) and recent boredom motivation work.

## What changed (minimal)

- Added hormone fields to every tool schema (required):
  - curiosity, pain, boredom, curiosity_after, pain_after, boredom_after
- Added normalization (0..1) and HUD title update before any action is executed.
- Updated TEST mode to emit hormone fields.

## Run

```powershell
python franz_grok_hormones.py
```

## Test mode

```powershell
setx FRANZ_TEST 1
python franz_grok_hormones.py
```

## Resolution presets

Set `FRANZ_RES`:

- low: 512x288 (default)
- med: 768x432
- high: 1024x576
