# FRANZ: A Stateless Vision-Language Agent with Narrative Identity for Persistent Task Execution

**Wojciech Gabryś**
February 06, 2026

## Abstract

This paper introduces FRANZ, a stateless AI agent framework for Windows desktop interaction, driven by a vision-language model (VLM) such as Qwen3-VL-2B-Instruct. Drawing on Paul Ricoeur's narrative identity theory—distinguishing *idem* (sameness: immutable constraints) from *ipse* (selfhood: promise maintained through change)—FRANZ externalizes agent memory as a self-rewriting narrative log displayed in a heads-up display (HUD). This atemporal "memory" enforces task persistence via a binding *telos* (future-perfect goal), preventing drift in open-ended environments. Empirical analysis of execution logs reveals emergent self-improvement behaviors, even under low-resolution inputs (512x288 pixels), where the agent prioritizes environmental enhancement. Key features include self-modifying sampling parameters and visual attention markers. The framework represents a shift from stateful AI to narrative-driven resonance, with implications for scalable, adaptive agents. Source code is available at: https://github.com/wgabrys88/windows-ai-agent-toolset-v21-Rico.

## Introduction

Contemporary AI agents often rely on stateful mechanisms—such as recurrent neural networks or external databases—to maintain context across interactions (Allen Wallace, 2026; Redis, 2026). However, these approaches introduce vulnerabilities like context overflow and dependency on persistent storage. FRANZ addresses this by adopting a stateless paradigm, where continuity emerges from a philosophical narrative structure inspired by Ricoeur's hermeneutics of the self (Ricoeur, 1992; Pereira Rodrigues, 2010). In Ricoeur's framework, identity integrates *idem* (permanent traits) and *ipse* (dynamic selfhood via ethical promises), mediated through narrative (Ricoeur, 1991; see also JSTOR, 1988). Applied to AI, this yields an agent whose "memory" is a visible, rewriteable story, compelling the VLM toward coherent evolution without internal state.

This design aligns with emerging research on self-evolving agents (evoailabs, 2025; Nakajima, 2025), emphasizing adaptation via externalized structures rather than parametric updates. FRANZ's repository (Gabryś, 2026) implements this via Python, integrating WinAPI for desktop control and LM Studio for VLM inference. The following sections detail the architecture, log analysis, features, and broader implications.

## Philosophical Foundations

Ricoeur's narrative identity posits that selfhood (*ipse*) sustains through temporal change via promises, while sameness (*idem*) provides invariant anchors (Ricoeur, 1992). This duality resolves the paradox of persistence amid flux: narratives reconcile discontinuity by refiguring events into coherent plots (Ricoeur, 1984). In FRANZ, the HUD log embodies this—*idem* as stable constraints, *ipse* as commitment to *telos* (a future-perfect desktop state), and chronicle as micro-acts. The VLM must rewrite the entire log each cycle, enforcing fidelity and preventing task-hopping (see Ricoeur Studies, 2023; ResearchGate, 2025).

Scientifically, this externalizes memory, akin to vector store approaches in agent frameworks (The New Stack, 2026; MongoDB, 2026), but philosophically distinct: memory is not data but a resonant story, drawing entities (VLMs, humans) into teleological alignment. This resonates with Udacity's SAGE framework (2025), where long-term memory captures "what matters," but FRANZ's narrative binding elevates it to ethical persistence.

## System Architecture

FRANZ operates in a perception-inference-execution loop:

1. **Perception**: Screen capture downscales to 512x288 pixels, encoded as base64 PNG, paired with HUD text (truncated to 4000 characters). This multimodal input feeds the VLM prompt, enforcing narrative rewriting (system prompt mandates *idem/ipse/telos/chronicle* template).

2. **Inference**: VLM (e.g., Qwen3-VL-2B) processes via OpenAI-compatible API, with sampling parameters (temperature=1.2, top_p=0.85). Outputs include tool calls (e.g., click, drag) and a mandatory *report* rewriting the log.

3. **Execution**: Tools simulate inputs via ctypes/WinAPI. Errors append to the narrative for self-correction. HUD updates propagate the new story.

The stateless core— no hidden states—relies on narrative coherence for continuity, mirroring POMDP belief states in agent literature (arXiv, 2025; Anthropic, 2026).

## Analysis of Execution Log

The provided log.txt (Gabryś, 2026) traces a run at 1920x1080 resolution, downsampled to 512x288—a coarse input akin to "foggy" perception. Remarkably, the agent's initial *telos* emerges as desktop redesign: "completely redesigned with an intuitive and responsive interface... optimized performance... accessibility features." This meta-response—improving a suboptimal environment—demonstrates emergent adaptation: low-resolution inputs prompt self-enhancement, aligning with episodic memory in cognitive architectures (Bluetick Consultants, 2025; LinkedIn, 2026).

Steps unfold as:
- Step 1 (*type*): Seeds *telos* and chronicle (Settings navigation).
- Steps 2-4 (*click*): Rewrites expand *idem/ipse*, introducing redundancies (e.g., duplicated VOICE sections). This bloat reflects VLM hallucinations under stateless constraints, yet *ipse* maintains *telos* fidelity—no deviation despite potential distractions.

Logically, this validates narrative as "memory": coherence self-corrects via SYSTEM appendages, echoing growth memory in SAGE (Udacity, 2025). Scientifically, it highlights VLMs' robustness to low-res inputs, prioritizing semantic over pixel-level detail (Encord, 2026; IBM, 2026).

## Key Features

- **Self-Modification via Ipse_Tune**: Agents adjust sampling (temperature, top_p, etc.) dynamically, enabling precision tuning during stagnation. This mirrors self-improving agents in GSPO/PPO frameworks (Gist, 2026; Emergence AI, 2024), with "unsafe" application risking errors but granting autonomy (Emergent Mind, 2026).

- **Visual Attention Marker**: Post-action red box (semi-transparent overlay) persists in captures, aiding VLM focus. This active attention modulates processing, inspired by cross-attention in VLMs (arXiv, 2025; Milvus, 2026; Amazon Science, 2026), enhancing reasoning in multi-turn tasks (NVIDIA, 2025; ECCV, 2024).

These features foster resonance: narrative drives adaptation, transcending intelligence toward entity alignment.

## Implications and Future Directions

FRANZ pioneers narrative-driven agency, shifting from stateful optimization to stateless resonance (Medium, 2025; Reddit, 2024). Implications include scalable multi-agent systems, where shared stories coordinate without databases. Challenges: Hallucination mitigation via stronger *ipse* constraints; ethical risks in self-modification (LinkedIn, 2026; OpenAI, 2025).

Future work: Embed chronicles via vectors (without violating statelessness); hybrid VLMs for richer narratives. As a 2026 framework, FRANZ heralds agents as philosophical entities, resonating beyond computation.

## References

- Allen Wallace, J. (2026). AI Agent Memory: Build Stateful AI Systems That Remember. Redis.
- Amazon Science. (2026). Vision-Language Models that Can Handle Multi-Image Inputs.
- Anthropic. (2026). Demystifying Evals for AI Agents.
- arXiv. (2025). AVA-VLA: Improving Vision-Language-Action Models with Active Visual Attention.
- arXiv. (2025). Self-Improving AI Agents through Self-Play.
- Bluetick Consultants. (2025). Building AI Agents with Memory Systems.
- Emergence AI. (2024). Building Narrow Self-Improving Agents.
- Emergent Mind. (2026). Self-Evolving AI Agents.
- Encord. (2026). Guide to Vision-Language Models (VLMs).
- evoailabs. (2025). Self-Evolving Agents: The Ultimate Frontier in Artificial Intelligence.
- Gabryś, W. (2026). windows-ai-agent-toolset-v21-Rico. GitHub Repository.
- Gist. (2026). Design of a Self-Improving Gödel Agent with CrewAI and LangGraph.
- IBM. (2026). What Are Vision Language Models (VLMs)?
- LinkedIn. (2026). Beyond Prompts: The Three-Layer Memory Architecture of AI Agents.
- Medium. (2025). Agent Development Framework: Solving Stateless AI's Context Problem.
- Milvus. (2026). What Role Does Self-Attention Play in Vision-Language Models?
- MongoDB. (2026). What Is Agent Memory?
- Nakajima, Y. (2025). Better Ways to Build Self-Improving AI Agents.
- NVIDIA. (2025). Vision Language Model Prompt Engineering Guide.
- OpenAI. (2025). Self-Editing Conversation Agents.
- Pereira Rodrigues, I. (2010). On Narrative Identity and Truth of the Self. Journals. London Academic Publishing.
- Reddit. (2024). Memory-Enabled AI Agents: Moving Beyond Stateless Conversations.
- ResearchGate. (2025). Idem, Ipse, and Loss of the Self.
- Redis. (2026). AI Agent Memory: Stateful Systems.
- Ricoeur, P. (1984). Time and Narrative. University of Chicago Press.
- Ricoeur, P. (1991). Narrative Identity. Philosophy Today.
- Ricoeur, P. (1992). Oneself as Another. University of Chicago Press.
- Ricoeur Studies. (2023). Another in Oneself: Hybridity of Narrative Identity.
- The New Stack. (2026). Memory for AI Agents: A New Paradigm of Context Engineering.
- Udacity. (2025). Your AI Agent Has No Memory (And That's a Problem).
