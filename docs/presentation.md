# PawPal+ AI Care Advisor: 6-minute presentation

Target length: ~6 min (about 700 spoken words plus a 2 min live demo). Rehearse once with a timer.

## Before you present (2 min of prep)
- Terminal in the project folder with the venv active; font size large.
- `python demo_end_to_end.py` run once so you know it works (no API key needed).
- `streamlit run app.py` already open in a browser tab, one pet pre-added: Tom, cat, age 4, special needs `diabetes`.
- Have the README architecture table and `docs/evidence/` ready as backup if the demo fails.

---

## Slide 1 (0:00-0:30): The problem
**Title:** PawPal+ planned the tasks you remembered. It couldn't tell you what you forgot.

Say: "My Module 1-3 project, PawPal+, builds a daily schedule across several pets. But it only schedules what the owner types in. It would never notice a diabetic cat with no insulin task, or an arthritic senior dog with no joint care. For this project I added an AI Care Advisor that closes that gap."

## Slide 2 (0:30-1:45): How it works
**Show:** `diagrams/system.mmd` rendered, or this line:

`pet profile -> Retriever -> Generator -> Guardrails -> Self-check -> Owner approves -> Scheduler -> Daily plan`

Say, one stage at a time:
1. **Retrieve (RAG).** 16 care passages, filtered by species and age, ranked with TF-IDF similarity.
2. **Generate.** Claude (or an offline fallback with no key) turns the retrieved passages into task suggestions. Each suggestion must cite a passage.
3. **Guardrails in code, not prompts.** Anything citing an unretrieved source, with invalid values, or duplicating an existing task is rejected.
4. **Self-check (the agentic step).** The system simulates the plan on a copy of the owner's data, clears time clashes, and flags what won't fit the time budget.
5. **Human approves.** Nothing becomes a task until the owner clicks Add.

Key line: "The model proposes, the code verifies, the human decides."

## Slide 3 (1:45-3:45): Live demo
**Demo A (60 s), terminal:** `python demo_end_to_end.py`, scroll to Case 1 then the ablation at the bottom.
- Point at `[2 RETRIEVE]`: `diabetes` pulls `med-diabetes` (0.29).
- Point at the ablation: same cat, three different special-needs texts, three different tasks (none / insulin / calming). That shows retrieval changes the output.
- Point at Case 3: 20-minute budget, 3 of 6 suggestions flagged `DOES NOT FIT`.

**Demo B (60 s), Streamlit UI:** click **Get care suggestions** for Tom, show the confidence labels and rationale, click **Add** on insulin, show it land in the daily plan.

If the demo breaks: show `docs/evidence/end_to_end_output.txt`, which is real captured output.

## Slide 4 (3:45-5:15): Reliability and what I learned
**Numbers:** 63/63 unit tests, 10/10 eval scenarios (offline), per-suggestion confidence score, `pawpal.log` for every retrieval and rejection.

Four lessons (pick the best three if short on time):
1. **My first eval run was 5/6.** A rabbit got no advice because the species word `other` matched nothing. Hand-picked unit tests never hit it; a scenario eval found it in seconds.
2. **Hand probing beat my tests.** Typing "no known allergies" produced a high-priority allergy medication task. My tests had no negation cases. I fixed it, but only partly (see the model card).
3. **The self-check was correct and still wrong.** It resolved a time clash by moving feeding off the insulin slot, but insulin is meant to be given with food. The rule worked; it just didn't understand the pet.
4. **Guardrails mattered more than prompt wording.** Prompt-injection text passed harmlessly because the model's output is validated in code.

## Slide 5 (5:15-6:00): Honest limits and wrap-up
- Knowledge base is 16 passages I wrote, not vet-reviewed. Matching is lexical, so "limping" misses arthritis. Confidence is a ranking signal, not a probability.
- The live-Claude path is tested only with a fake model; `eval_advisor.py --llm` has not been run yet. This is the first thing I'd do next.
- Not veterinary advice, and the model card says so.

Close: "The part I'm proudest of isn't the AI call. It's the scaffolding around it: grounding, validation, a human checkpoint, and an eval that told me when I was wrong."

---

## Likely Q&A
- **Why TF-IDF, not embeddings?** Small corpus, zero dependencies, deterministic and easy to debug. Embeddings would fix the "limping" miss and are the next upgrade.
- **Why an offline mode?** Demo works without a key, tests are deterministic, and it's the fallback when the API fails.
- **How do you know the advice is right?** I don't, medically. The eval checks grounding and retrieval, not correctness. A vet review is the missing step.
- **Where did AI help in building it?** Claude Code wrote most of the code from my requirements; I reviewed, ran, and probed it. See `model_card.md` section 4.
