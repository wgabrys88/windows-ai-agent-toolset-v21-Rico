Memory is currently disabled; if you want these specs to persist across separate chats, enable it in **Settings > Personalization > Memory**.

Here is the “master prompt” spec that captures what we built (atemporal storytelling + stateless narrative agent), plus a downloadable version you can hand to any AI and it should be able to reproduce the same architecture and code quality.

* [Download FRANZ_MASTER_PROMPT.md](sandbox:/mnt/data/FRANZ_MASTER_PROMPT.md)

## What we achieved (feature set relevant to atemporal / stateless narrative)

**Core idea: stateless narrative memory**

* The agent has no hidden memory. The *only* memory is a single **Narrative Identity Log** shown in a HUD and saved to a file.
* Every VLM call receives **(a)** current screenshot and **(b)** the current log text (tail-truncated).
* Every VLM output must be **exactly one tool call** and must include `report` = **full rewrite** of the entire log (not a delta).
* Runtime replaces the log with `report` after each step and updates HUD + disk.

**Ricoeur-inspired identity structure**

* The log template encodes:

  * **IDEM** = invariants/constraints (sameness). ([SHS Cairn.info][1])
  * **IPSE** = promise/commitment (selfhood). ([SHS Cairn.info][1])
  * **TELOS** = written in **future-perfect** (“as if already done”), anchoring the agent in outcome-imagery.
  * **CHRONICLE** = micro-acts appended each turn.

**Hormonal Logic (intrinsic signals)**

* Added 3 scalars, NOW and expected AFTER: **Curiosity / Pain / Boredom**.
* They are **required fields** in every tool call; values normalized to **0..1** (also accepts 0..100).
* Displayed in the HUD title as percentages, updated **before any action**.
* Curiosity/boredom are aligned with intrinsic motivation framing (compression progress / curiosity reward). ([arXiv][2])

**Tool-driven desktop control (LM Studio function calling)**

* Uses LM Studio OpenAI-compatible `/v1/chat/completions` with `tools` and `tool_choice="required"`. ([LM Studio][3])
* Tools: click/double/right/drag/type/scroll/attend + **ipse_tune** (self-modifying sampling params).

**Self-tuning sampler (unsafe mode)**

* Runtime keeps a `SAMPLING` dict (temperature/top_p/top_k/repeat_penalty/max_tokens/min_completion_tokens…).
* If VLM calls `ipse_tune`, runtime applies those values for subsequent requests (agent can “self-steer” by changing entropy/precision).

**HUD operator control + editing loop**

* Always-on-top HUD with RichEdit: readable narrative, editable only when paused.
* Pause/Resume button gates action execution.
* Ctrl+Wheel zoom; Ctrl+Shift+Wheel cycles HUD background.

**Action marker + dump correctness**

* A translucent, click-through marker window shows where last action happened.
* Critical ordering: marker stays visible after action; next step captures while marker exists; then marker is hidden before sending image to VLM.
* Screen capture uses `BitBlt(..., SRCCOPY | CAPTUREBLT)` so layered windows can appear in dumps. ([cyotek.com][4])

**Robust parsing / “Pylance-like” hardening**

* Defensive extraction of tool calls from either `tool_calls` or legacy `function_call`.
* Accepts `arguments` as dict or JSON string (including fenced or embedded JSON).
* Numeric coercion for coordinates/hormones and strict “required args” validation to stop type errors and partial tool payloads.

**Test mode**

* `FRANZ_TEST=1` injects a deterministic mock VLM response stream (includes hormones + report rewrites + occasional ipse_tune) at the same point where real VLM would be called.

**Resolution presets**

* `FRANZ_RES` toggles model input size: low/med/high (512×288 / 768×432 / 1024×576).

**System specs**

* Windows 10/11 only (Win32 APIs via `ctypes`).
* Python **3.12**.
* No third-party deps.
* Designed for a small VLM (Qwen3-VL 2B) so prompts are short, rigid, schema-driven.

## The exact “prompt” to recreate FRANZ

Use the downloadable file (recommended):
[FRANZ_MASTER_PROMPT.md](sandbox:/mnt/data/FRANZ_MASTER_PROMPT.md)

It instructs another AI to generate:

* a single-file Python 3.12 Windows agent,
* the full architecture above,
* the same strict schema + narrative rewrite invariant,
* marker/dump ordering and CAPTUREBLT detail,
* hormones and sampler self-tuning,
* test mode + resolution presets,
* and the “military style” coding constraints.

[1]: https://shs.cairn.info/journal-le-philosophoire-2015-1-page-151?lang=en&utm_source=chatgpt.com "Who Am I? Ipse-identity, Idem-Identity, and Narrative Identity"
[2]: https://arxiv.org/abs/0812.4360?utm_source=chatgpt.com "Driven by Compression Progress: A Simple Principle Explains Essential Aspects of Subjective Beauty, Novelty, Surprise, Interestingness, Attention, Curiosity, Creativity, Art, Science, Music, Jokes"
[3]: https://lmstudio.ai/docs/developer/openai-compat/tools?utm_source=chatgpt.com "Tool Use | LM Studio Docs"
[4]: https://www.cyotek.com/blog/capturing-screenshots-using-csharp-and-p-invoke?utm_source=chatgpt.com "Capturing screenshots using C# and p/invoke"
