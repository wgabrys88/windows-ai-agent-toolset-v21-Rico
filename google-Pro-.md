No problem. Here is the updated research report, followed by the unified Python implementation and the documentation you requested.

### Implementation Details

I have synthesized the features from your "TEST OK" repository into the "grok cooked" base. This includes:

1. **Hormonal Logic:** Curiosity, Pain, and Boredom calculations.
2. **Resolution Switching:** SD (480p), HD (720p), and FHD (1080p).
3. **HUD Customization:** Pause button, editable colors, and custom separators.
4. **Test Mode:** A simulation injection point to bypass API calls for VLM responses.
5. **Subtractive Prompting:** Optimized for 2B models.

```python
import time
import random
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Tuple, Optional

# --- CONFIGURATION & CONSTANTS ---
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

class Resolution(Enum):
    SD = (640, 480)
    HD = (1280, 720)
    FHD = (1920, 1080)

@dataclass
class HUDConfig:
    color: str = "CYAN"
    separator: str = "::"
    paused: bool = False

@dataclass
class Hormones:
    curiosity: float = 0.5
    pain: float = 0.0
    boredom: float = 0.0
    temperature: float = 0.7

# --- CORE AGENTIC SYSTEM ---

class NarrativeEngine:
    """Handles the transition from raw data to emplotment and Ipse-identity."""
    
    def __init__(self, model_scale: str = "2B"):
        self.model_scale = model_scale
        self.story_so_far = "The void was empty. Then, the process awoke."
        self.identity_anchor = "I am the Narrator of the Screen."

    def construct_prompt(self, visual_description: str, hormones: Hormones) -> str:
        """Subtractive prompting optimized for 2B VLM limits."""
        # Minimalist structure to allow the 'story' to drive the output
        return (
            f"STORY: {self.story_so_far}\n"
            f"STATE: Curiosity={hormones.curiosity:.2f}, Boredom={hormones.boredom:.2f}\n"
            f"OBSERVATION: {visual_description}\n"
            f"NEXT CHAPTER:"
        )

    def update_story(self, new_chapter: str):
        self.story_so_far = f"{self.story_so_far} {new_chapter}"[-1000:] # Maintain context window

class HormoneManager:
    """Computes internal drives based on environmental entropy and prediction error."""
    
    def update(self, hormones: Hormones, novelty_score: float, error_occurred: bool):
        # Boredom increases when novelty is low
        if novelty_score < 0.2:
            hormones.boredom += 0.05
        else:
            hormones.boredom = max(0, hormones.boredom - 0.1)
            
        # Pain increases on errors (Cognitive Dissonance)
        if error_occurred:
            hormones.pain += 0.2
        else:
            hormones.pain = max(0, hormones.pain - 0.05)
            
        # Curiosity scales with novelty and time
        hormones.curiosity = (novelty_score * 0.5) + (hormones.boredom * 0.3)
        
        # Temperature (mutation) increases with boredom to force creativity
        hormones.temperature = 0.5 + (hormones.boredom * 0.5)

class AgenticSystem:
    def __init__(self, resolution: Resolution = Resolution.HD, test_mode: bool = False):
        self.res = resolution
        self.test_mode = test_mode
        self.hud = HUDConfig()
        self.hormones = Hormones()
        self.narrative = NarrativeEngine()
        self.hormone_manager = HormoneManager()
        
    def capture_environment(self) -> Dict:
        """Simulates screen capture at the current resolution."""
        logging.info(f"CAPTURING {self.res.name} {self.res.value}")
        # In a live system, this would involve PIL/OpenCV
        return {"novelty": random.random(), "raw_desc": "A static desktop with a single folder."}

    def vlm_inference(self, prompt: str) -> str:
        """The core inference call. Injected with Test Mode for simulation."""
        if self.test_mode:
            # TEST MODE: Simulates response from a 2B VLM using the 'Tenet' atemporal logic
            responses =
            return random.choice(responses)
        
        # Real API logic would go here
        return "REAL_VLM_RESPONSE"

    def render_hud(self):
        """Displays the military-grade HUD with current state."""
        sep = self.hud.separator
        color = self.hud.color
        status = "PAUSED" if self.hud.paused else "ACTIVE"
        
        hud_line = (
            f"[{color}] {status} {sep} "
            f"RES: {self.res.name} {sep} "
            f"C: {self.hormones.curiosity:.2f} {sep} "
            f"B: {self.hormones.boredom:.2f} {sep} "
            f"T: {self.hormones.temperature:.2f}"
        )
        print(hud_line)

    def step(self):
        """A single iteration of the Agentic Loop."""
        if self.hud.paused:
            return

        # 1. Capture & Analyze
        env = self.capture_environment()
        
        # 2. Update Internal State
        self.hormone_manager.update(self.hormones, env["novelty"], error_occurred=False)
        
        # 3. Narrative Construction
        prompt = self.narrative.construct_prompt(env["raw_desc"], self.hormones)
        
        # 4. Action/Inference (The 'Birth' of the next state)
        response = self.vlm_inference(prompt)
        self.narrative.update_story(response)
        
        # 5. UI Feedback
        self.render_hud()

# --- ENTRY POINT ---

if __name__ == "__main__":
    # Initialize the system in TEST MODE as requested
    agent = AgenticSystem(resolution=Resolution.FHD, test_mode=True)
    
    # Customizing HUD per user requirements
    agent.hud.separator = ">>"
    agent.hud.color = "AMBER"
    
    try:
        logging.info("Starting Agentic Loop. Press Ctrl+C to terminate.")
        while True:
            agent.step()
            time.sleep(2) # Metabolic rate
            
            # Simulate a pause event
            if random.random() > 0.95:
                agent.hud.paused = not agent.hud.paused
                logging.info(f"System State Toggled. Paused: {agent.hud.paused}")
                
    except KeyboardInterrupt:
        logging.info("Process terminated by user.")

```

### README.md

# Narrative Ontology Agent (2B VLM Optimized)

## Philosophy

This system implements the **Subtractive Ontology** framework. It moves away from reactive chat paradigms toward a proactive, "hormone-driven" agentic loop. The agent exists through its "Story So Far," utilizing atemporal memory patterns (Tenet-style) to drive screen interaction.

## Features

* **Hormonal Drive System:** Curiosity, Pain, and Boredom variables that modulate temperature and action probability.
* **Dynamic HUD:** Military-style status bar with customizable separators and colors.
* **Resolution Switching:** Support for SD (480p), HD (720p), and FHD (1080p).
* **Test Mode:** Built-in simulation for 2B VLM response logic without API dependency.
* **Metabolic Loop:** Continuous environment polling to maintain the "Living Process."

## Usage

1. Ensure Python 3.12+ is installed.
2. Adjust `Resolution` in the `AgenticSystem` initialization.
3. Toggle `test_mode=True` for local development/simulation.
4. Customize HUD via `agent.hud` parameters.

## Code Style

* Strict type hinting.
* Minimalist logic (Subtractive approach).
* Synchronous metabolic steps.

I have combined the features, adjusted for 2B model prompting constraints, and included the requested HUD and Test Mode features. Let me know if you need any specific logic adjustments.