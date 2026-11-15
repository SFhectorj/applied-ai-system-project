"""Reproducible demo of the Care Advisor (no API key needed). Run: python demo_advisor.py

Part 1 shows example inputs and outputs. Part 2 feeds the advisor deliberately bad
"model" output to show the guardrails and fallback working, printing the log lines.
"""

import json
import logging
import sys

from advisor import CareAdvisor
from pawpal_system import Owner, Pet, Task


def show(title, owner, advisor):
    print(f"\n=== {title} ===")
    for p in owner.pets:
        print(f"INPUT  pet={p.name} species={p.species} age={p.age} needs={p.special_needs!r} "
              f"existing_tasks={[t.title for t in p.tasks]}")
    print(f"INPUT  available_minutes={owner.available_minutes}")
    r = advisor.advise(owner)
    print(f"OUTPUT mode={r.mode} suggestions={len(r.suggestions)}")
    for s in r.suggestions:
        fit = "fits" if s.fits else "NO FIT"
        print(f"  {s.pet_name:<4} {s.title:<38} {s.duration_minutes:>3}m {s.priority:<6} "
              f"{s.frequency:<6} {s.preferred_time or '--:--'}  conf={s.confidence:.2f} {fit:<6} [{s.source_id}]")
        for n in s.notes:
            print(f"       note: {n}")
    for w in r.warnings:
        print(f"  WARNING: {w}")


def owner_of(minutes, *pets):
    o = Owner("Demo", minutes)
    for p in pets:
        o.add_pet(p)
    return o


def main():
    adv = CareAdvisor(use_llm=False)
    print("PART 1: example inputs and outputs (offline generator)")
    show("1. Special need changes the advice", owner_of(120, Pet("Tom", "cat", 4, "diabetes")), adv)
    rex = Pet("Rex", "dog", 10, "arthritis")
    rex.add_task(Task(1, "Morning walk", "exercise", 20, "high", "08:00"))
    show("2. Age + existing task respected", owner_of(120, rex), adv)
    show("3. Overbooked day triggers warning", owner_of(15, Pet("Bun", "other", 2), Pet("Mia", "cat", 3)), adv)
    show("4. Negated need is not a condition", owner_of(120, Pet("Kit", "cat", 4, "no known allergies")), adv)

    print("\n\nPART 2: guardrails against bad model output (fake LLM, log lines shown)")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("  LOG %(levelname)s %(name)s: %(message)s"))
    logging.getLogger("pawpal").addHandler(handler)
    logging.getLogger("pawpal").setLevel(logging.WARNING)

    def item(**kw):
        base = {"source_id": "cat-litter", "title": "Scoop litter", "category": "hygiene",
                "duration_minutes": 5, "priority": "high", "frequency": "daily",
                "preferred_time": "", "rationale": "x"}
        return {**base, **kw}

    cases = {
        "a) hallucinated source id": [item(source_id="made-up")],
        "b) 999-minute task (prompt-injection style)": [item(duration_minutes=999)],
        "c) invalid priority": [item(priority="urgent")],
        "d) malformed time '7am'": [item(preferred_time="7am")],
        "e) not JSON at all": "I'm sorry, I can't help with that.",
        "f) model call raises an error": RuntimeError("network down"),
        "g) one valid + one invalid": [item(), item(source_id="made-up", title="Fake")],
    }
    for name, payload in cases.items():
        def llm(system, prompt, payload=payload):
            if isinstance(payload, Exception):
                raise payload
            return payload if isinstance(payload, str) else json.dumps(payload)
        print(f"\n--- {name}")
        r = CareAdvisor(llm=llm).advise(owner_of(120, Pet("Mia", "cat", 3)))
        titles = [s.title for s in r.suggestions]
        print(f"  RESULT mode={r.mode} accepted={len(titles)} first={titles[:2]} warnings={len(r.warnings)}")


if __name__ == "__main__":
    main()
