# 🐾 PawPal+ with an AI Care Advisor

A pet-care planner that builds a daily schedule across multiple pets **and** uses retrieval-augmented AI to tell owners what care each pet is actually missing.

## Original project: PawPal+ (Modules 1-3)

This project extends **PawPal+**, the pet-care scheduler I built in Modules 1-3. PawPal+ let a busy owner track care tasks (walks, feeding, meds, grooming) for several pets, then generated a priority-based daily plan that fit the owner's available minutes and explained why each task was scheduled or skipped. Its logic layer (`Owner`, `Pet`, `Task`, `Scheduler`, `DailyPlan`) also handled sorting, filtering, recurring tasks and conflict warnings, all behind a Streamlit UI and covered by 44 tests. Full documentation of that original system is kept in [`docs/scheduler_details.md`](docs/scheduler_details.md).

## Summary: what this adds and why it matters

The original app scheduled whatever tasks the owner remembered to enter. It could not notice that a diabetic cat has no insulin task, or that a 10-year-old arthritic dog needs joint care. The **AI Care Advisor** closes that gap:

1. It **retrieves** care guidance matching each pet's species, age and special needs.
2. It **generates** task suggestions grounded in that guidance (with Claude, or an offline fallback).
3. It **validates** and **self-checks** them against the owner's real schedule and time budget.
4. The owner **approves** each suggestion before it becomes a task.

Retrieval isn't decoration: different pets retrieve different passages and get different tasks, priorities and rationales. The advisor never adds anything on its own, and it keeps working with no API key or when the model fails.

## Architecture overview

Source: [`diagrams/system.mmd`](diagrams/system.mmd) (Mermaid).

```
pet profile -> Retriever -> Generator (Claude | offline) -> Guardrails -> Self-check -> Suggestions -> Human approves -> Scheduler -> Daily plan
                  ^                                                                        |
            knowledge base                                          pytest + eval_advisor.py + pawpal.log watch every stage
```

| Component | File | Role |
|-----------|------|------|
| Retriever | `rag.py` | Loads `knowledge/pet_care.json` (16 passages), filters by species and age, ranks with TF-IDF cosine similarity. |
| Generator | `advisor.py` | Claude returns JSON suggestions that must cite a retrieved passage; an offline generator builds them from the same passages when there is no key or the call fails. |
| Guardrails | `advisor.py: validate()` | Rejects suggestions that cite unretrieved sources, have invalid values, or duplicate existing tasks. |
| Self-check (agentic step) | `advisor.py: _check()` | Simulates the plan on a copy of the owner's data, clears preferred times that clash, flags suggestions that won't fit. |
| Scheduling engine | `pawpal_system.py` | The original PawPal+ logic. Approved suggestions become ordinary `Task`s here. |
| UI | `app.py` | Streamlit app with the "AI Care Advisor" section and an **Add** button per suggestion (the human checkpoint). |
| Testing | `tests/`, `eval_advisor.py` | 55 unit tests plus a scenario eval that measures retrieval correctness and consistency. |
| Logging | `logging_setup.py` | `pawpal.log` records retrieval scores, LLM request ids and token counts, and rejected suggestions. |

## Setup instructions

Requires Python 3.10+.

```bash
git clone <this repo> && cd applied-ai-system-final
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Optional: use Claude for generation. Without it the advisor runs in offline mode.
export ANTHROPIC_API_KEY=your-key
# Optional: choose a different model (default claude-opus-5-5)
export PAWPAL_MODEL=claude-sonnet-5-5

streamlit run app.py               # web UI
python main.py                     # terminal demo of the original scheduler
python -m pytest                   # unit tests
python eval_advisor.py             # reliability eval (add --llm to test Claude, needs a key)
```

To try the advisor in the UI: add a pet (put a condition such as `arthritis` or `diabetes` in *Special needs*), then click **Get care suggestions** and **Add** the ones you want.

## Sample interactions

The first three are real output from the **offline** generator (reproducible with no key: `CareAdvisor(use_llm=False).advise(owner)`). With a key set, Claude writes the titles and rationales but is held to the same retrieved passages and the same validation.

**1. Special needs change the advice.** Input: Tom, cat, age 4, special needs `diabetes`; owner has 120 min.

```
Tom: Give insulin with meal   10 min  HIGH  daily 07:00  fits today   [source: med-diabetes]
   Tom's special needs (diabetes) match: Diabetes and insulin.
Tom: Feed cat and refresh water  5 min HIGH  daily       fits today   [source: cat-feeding]
   note: 07:00 clashed with another task; time cleared
Tom: Interactive play session 15 min MEDIUM daily 19:00  fits today   [source: cat-play]
Tom: Brush cat                 5 min  LOW   weekly       fits today   [source: cat-grooming]
```

The same cat without the `diabetes` note gets no insulin task. The self-check moved the feeding time off 07:00 because the insulin task already holds that slot.

**2. Age and existing tasks are respected.** Input: Rex, dog, age 10, special needs `arthritis`, already has "Morning walk" (08:00).

```
Rex: Give joint supplement  5 min HIGH  daily          fits today   [source: med-arthritis]
   note: 08:00 clashed with another task; time cleared
Rex: Feed breakfast        10 min HIGH  daily 07:00    fits today   [source: dog-feeding]
Rex: Brush coat            10 min LOW   weekly         fits today   [source: dog-grooming]
```

No second walk was suggested because the dog already has one, and no puppy or cat guidance was retrieved.

**3. The self-check warns when the day is too full.** Input: owner has only 15 minutes; Bun (rabbit, `other`, age 2) and Mia (cat, age 3).

```
WARNING: High-priority 'Spot-clean habitat and refresh water' for Bun won't fit today;
         consider increasing available minutes.
Bun: Spot-clean habitat and refresh water  10 min HIGH    won't fit today
Mia: Feed cat and refresh water             5 min HIGH    fits today
Mia: Scoop litter box                       5 min HIGH    fits today
Mia: Interactive play session              15 min MEDIUM  won't fit today
...
```

**4. Failure handling.** If the model call errors, refuses, or returns invalid JSON, the advisor logs the problem, shows "AI model unavailable for Mia; used built-in guidance", and returns offline suggestions instead of crashing (covered by `test_llm_failure_falls_back_to_offline` and `test_garbage_llm_output_falls_back`).

## Design decisions and trade-offs

- **Retrieval before generation, and a citation requirement.** The model may only use passages the retriever returned, and every suggestion must name one. This reduces invented advice and makes each suggestion traceable. The cost is that the advisor is only as good as the knowledge base.
- **TF-IDF instead of embeddings.** Sixteen short passages don't justify a vector database or a second API. TF-IDF is dependency-free, deterministic and easy to test. The trade-off is lexical matching: "limping" will not match "arthritis" unless the passage lists both. I mitigated this with keyword lists and by filtering on structured fields (species, age) first.
- **Offline mode is a first-class path.** The app, tests and eval all run with no API key, so anyone can reproduce results. The trade-off is two generators to keep consistent, which the eval checks.
- **Human approval for every change.** Suggestions are never added automatically. A pet-care tool that silently edits medication schedules would be a bad trade for a little convenience.
- **Validation in code, not in the prompt.** I treat model output as untrusted input. A prompt can ask for valid JSON; only code can guarantee it.
- **Self-check reuses the real scheduler.** Rather than asking the model whether a suggestion fits, `_check()` runs `Scheduler.generate_plan()` on a copy of the data. That is cheaper and exact. The trade-off is that it only fixes same-start-time clashes (the scheduler's existing limitation).
- **Kept the original engine untouched.** The advisor sits beside `pawpal_system.py` and produces ordinary `Task`s, so all 44 original tests still pass unchanged.

## Testing summary

| Layer | What it covers | Result |
|-------|----------------|--------|
| `tests/test_pawpal.py` (44) | Original scheduler: sorting, recurrence, conflicts, planning, validation | All pass |
| `tests/test_advisor.py` (11) | Species/age filtering, special needs driving retrieval, no duplicate tasks, guardrail rejections, JSON parsing, a fake LLM (valid, hallucinated and failing output), time-clash repair, overflow flagging | All pass |
| `eval_advisor.py` | 6 pet scenarios: right passages cited, wrong species/age excluded, special-needs tasks high priority, repeated runs consistent | 6/6 offline |

**What worked.** Injecting a fake LLM made the model path testable without network calls, and the citation check reliably catches hallucinated sources. Filtering by species and age before ranking kept results clean.

**What didn't, at first.** The eval's first run failed for pet species `other`: the query contained the word "other", which matched nothing in the knowledge base, so a rabbit got no advice at all. I fixed it by expanding that species into habitat-related words in the query (`SPECIES_HINTS`) and added a regression test.

**Not yet verified.** I have not run `eval_advisor.py --llm` against the live API, so Claude's consistency and quality are untested; the offline numbers above do not speak to them. The knowledge base is small and was not veterinarian-reviewed, so the advisor should be read as a reminder tool, not medical advice.

**What I learned.** An eval is worth building early: it found a real bug that unit tests with hand-picked inputs had missed. Testing the guardrails matters more than testing the model, because the guardrails are what you control.

## Reflection

This project changed how I think about "adding AI" to an application. The model was the smallest part. Most of the work was deciding what it is allowed to see (retrieval), what it is allowed to say (citations and validation), what happens when it fails (fallback), and who has the last word (the owner). I also saw how much a deterministic baseline helps: the offline generator gave me something to test against, a safe fallback, and a way to tell whether the model was adding value or just noise. Next steps would be a larger, expert-reviewed knowledge base, embedding-based retrieval, overlap-aware conflict detection, and running the `--llm` eval regularly to track model quality.

A fuller account of how I worked with AI on this project, what I accepted and rejected, and the system's limitations is in `model_card.md`.

## Project layout

```
app.py                 Streamlit UI (scheduler + AI Care Advisor)
advisor.py             Retrieval-augmented generation, guardrails, self-check
rag.py                 Knowledge-base loader and TF-IDF retriever
knowledge/pet_care.json  Care guidance passages
pawpal_system.py       Original PawPal+ scheduling engine
main.py                Terminal demo of the scheduler
eval_advisor.py        Scenario-based reliability eval
logging_setup.py       Logging configuration
tests/                 pytest suites (scheduler + advisor)
diagrams/              system.mmd (this system), uml.mmd (original classes)
docs/                  Original PawPal+ documentation
```
