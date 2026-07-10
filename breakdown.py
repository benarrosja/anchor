# handles Gemini JSON integation and prompting for task micro-step breakdown.
# No flask dependency - independenly testable with pytest
# called by app.py /task/<id>/breakdown route

import json
import os
import re
from google import genai

# ========Gemini client ====
_client = None  # lazy singleton.Avoids re-initialising on every call 

def _get_client():
    """Returns a shared Gemini client, initialised once per process"""
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError("GEMINI_API_KEY is not set in environment.")
        _client = genai.Client(api_key=api_key)
    return _client


#=========== prompting=======

def _building_prompt(title: str, deadline: str, priority: int, estimate_mins: int, energy_level: int) -> str:
    """
    Constructs an ADHD-Aware prompt that instructs Gemini to return a strict JSON array of micro-steps - no prose, no markdown.

    Energy level shapes step size:
    1-2 (low) -> 3 tiniy steps, each < 5 min
    3 (okay) -> 4 steps, each <10
    4-5 (high) -> 5 steps, each < 15 min
    """
    energy_labels = {1: "exhauted", 2: "low", 3: "okay", 4: "good", 5: "enegised"}
    energy_word = energy_labels.get(energy_level, "okay")

    if energy_level <=2:
        step_count =3
        max_mins = 5
    elif energy_level ==3:
        step_count = 4
        max_mins = 10
    else:
        step_count = 5
        max_mins = 15
    deadline_str = f"due {deadline}" if deadline else " no deadline set"
    priority_str = {1: "low", 2: "medium", 3: "high"}.get(priority, "medium")

    prompt = f"""
You are an ADHD productivity coach. A user is stuck on a task and needs it broken into concrete, specific micro-steps they can start RIGHT NOW.
Task details:
- Title: "{title}"
- Deadline: {deadline_str}
- Priority: {priority_str}
- Estimated total time: {estimate_mins} minutes
-User's current energy: {energy_word} (level {energy_level}/5)

Rules:
1. Return ONLY a valid JSON array. No markdown, no explanation, no prose.
2. Exactly {step_count} steps. Each step must take < {max_mins} minutes.
3. Every step must be a single, specific physical action ( not "think about X").
4. Steps must be ordered - completing step 1 makes step 2 easier.
5. Because the user has ADHD, avoid vague advice like " just start" or "focus".
6. Adapt difficulty to energy level "{energy_word}": {"simpler, shorter steps" if energy_level <=2 else "normal steps"}.

Return format (strictly):
[
    {{"step": 1, "action": "...", "duration_mins": ...}},
    {{"step": 2, "action": "...", "duration_mins": ...}}
]
""".strip()

    return prompt
# ==========JSON validation and Parsing ===========================

def _parse_steps(raw_text: str) -> list[dict]:
    """
    Extracts and validates the JSON array from Gemini's response.
    Gemini sometimes wraps JSON in markdown fences — this strips them.
    Raises ValueError if the structure is invalid.
    """
    # Strip markdown fences if present: ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip()

    # Find the first [ ... ] block in case there's extra text
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in Gemini response.")

    steps = json.loads(match.group())

    if not isinstance(steps, list) or len(steps) == 0:
        raise ValueError("Parsed result is not a non-empty list.")

    # Validate each step has the required keys
    for s in steps:
        if not isinstance(s, dict):
            raise ValueError(f"Step is not a dict: {s}")
        if "action" not in s:
            raise ValueError(f"Step missing 'action' key: {s}")
        # Ensure step and duration_mins exist with safe defaults
        s.setdefault("step", steps.index(s) + 1)
        s.setdefault("duration_mins", 5)

    return steps

# Fallback steps - when hemini fail or reutnes invalid JSON

def _fallback_steps(title: str, energy_level: int) -> list[dict]:
    """
    Returns generic but honest micro-steps when Gemini is unavailable.
    Energy-aware: low energy → fewer, smaller steps.
    """
    if energy_level <= 2:
        return [
            {"step": 1, "action": f"Open the file or app related to '{title}'.", "duration_mins": 2},
            {"step": 2, "action": "Write one sentence about what this task requires.", "duration_mins": 3},
            {"step": 3, "action": "Set a 5-minute timer and do just the first thing you wrote.", "duration_mins": 5},
        ]
    else:
        return [
            {"step": 1, "action": f"Re-read the task title '{title}' and write what 'done' looks like.", "duration_mins": 2},
            {"step": 2, "action":"Identify the single blocking question or resource you need.", "duration_mins": 3},
            {"step": 3, "action": "Do the smallest possible physical action (open a doc, write a heading, send one message).", "duration_mins": 5},
            {"step": 4, "action":"Set a 10-minute timer and work only on step 3's output.", "duration_mins": 10},
        ]

# ======== Public API - the only function app.py should import

def get_task_breakdown(title: str,
                       deadline: str | None,
                       priority: int,
                       estimate_mins: int,
                       energy_level: int = 3) -> dict:
    """
    Main entry point called by the Flask route.

    Returns a dict:
    {
        "steps": [ {"step": 1, "action": "...", "duration_mins": 5}, ... ],
        "source": "gemini" | "fallback",
        "error": None | "short error description"
    }

    Never raises — always returns a usable response.
    """
    prompt = _building_prompt(title, deadline, priority, estimate_mins, energy_level)

    try:
        client = _get_client()
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        raw_text = response.text.strip()
        steps = _parse_steps(raw_text)

        return {"steps": steps, "source": "gemini", "error": None}

    except Exception as e:
        # Log the real error server-side, return safe fallback to user
        print(f"[breakdown.py] Gemini error: {e}")
        fallback = _fallback_steps(title, energy_level)
        return {"steps": fallback, "source": "fallback", "error": str(e)}