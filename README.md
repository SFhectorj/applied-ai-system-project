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
| Testing | `tests/`, `eval_advisor.py` | 57 unit tests plus a scenario eval that measures retrieval correctness and consistency. |
| Logging | `logging_setup.py` | `pawpal.log` records retrieval scores, LLM request ids and token counts, and rejected suggestions. |

## Setup instructions

Requires Python 3.10+.

```bash
git clone https://github.com/SFhectorj/applied-ai-system-project && cd applied-ai-system-final
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

## Sample interactions and execution evidence

Everything below is **real captured output**, reproducible with no API key (offline generator, fake model for the guardrail cases). Raw files are in [`docs/evidence/`](docs/evidence/): `demo_output.txt`, `eval_output.txt`, `eval_results.json`, `pytest_output.txt`. Regenerate them with the commands shown (`end_to_end_output.txt` comes from `demo_end_to_end.py`).

### 1. End-to-end system run: `python demo_end_to_end.py` (3 inputs)

Three different inputs go through every stage of the system: **input, retrieve (RAG), generate and validate, self-check, owner approval, final daily plan**. The last step is produced by the original PawPal+ `Scheduler`, so this is the whole application, not just the AI piece. Approval is simulated here by adding every suggestion that fits; in the app the owner clicks **Add**.

What each part of the output demonstrates:

| What to look for | Where | Example from the output below |
|---|---|---|
| **RAG: retrieval shapes the answer** | `[2 RETRIEVE]` ranks passages with scores, and `[3 GENERATE]` cites them | Case 1: `diabetes` retrieves `med-diabetes` (0.29) and the top suggestion is a high-priority insulin task citing it. The ablation at the bottom shows the *same cat* getting no medical task, an insulin task, or a calming task depending only on the special-needs text. |
| **Species/age filtering** | `[2 RETRIEVE]` | Case 2: a 10-year-old dog retrieves `dog-senior`, never puppy or cat guidance. Case 3: the rabbit retrieves only `other-habitat`. |
| **No duplicate advice** | `[3]` | Case 2: Rex already has a walk, so no second walk is suggested. |
| **Agentic self-check** | `[4 SELF-CHECK]` | Cases 1 and 2: a clashing preferred time is cleared. Case 3: three suggestions are flagged `DOES NOT FIT` with a 20-minute budget. |
| **Confidence and guardrails** | `conf=` and `low confidence` notes | Weak matches are labelled (e.g. 0.05); negated `no known allergies` retrieves no allergy passage (Case 3, Mia). |
| **Human in the loop** | `[5 OWNER APPROVES]` | Case 3: only 3 of 6 suggestions are added because the other 3 don't fit. |
| **Clear final output** | `[6 DAILY PLAN]` | Each case ends in a time-ordered schedule with totals (35/90, 45/60, 20/20 min). |

```text
$ python demo_end_to_end.py

==============================================================================
END-TO-END CASE 1: diabetic cat, relaxed day
==============================================================================
[1 INPUT]
  pet=Tom (cat, age 4) needs='diabetes' existing=[]
  owner has 90 min today
[2 RETRIEVE] knowledge-base passages ranked for each pet (species/age filtered)
  Tom: query='cat adult diabetes diabetes'
    0.29  [med-diabetes] Diabetes and insulin
    0.11  [cat-feeding] Cat feeding and water
    0.07  [cat-grooming] Cat brushing
[3 GENERATE + VALIDATE] mode=offline, 4 suggestions kept
  Tom: Give insulin with meal (10 min, high) conf=0.29 cites [med-diabetes]
      why: Tom's special needs (diabetes) match: Diabetes and insulin.
  Tom: Feed cat and refresh water (5 min, high) conf=0.11 cites [cat-feeding]
      why: Cat feeding and water: Adult cats do well on two measured meals daily, with wet food helping hydration.
  Tom: Interactive play session (15 min, medium) conf=0.05 cites [cat-play]
      why: Play and enrichment for cats: Indoor cats need two or more play sessions of 10 to 15 minutes daily, ideally with a wand toy that mimics hunting.
  Tom: Brush cat (5 min, low) conf=0.07 cites [cat-grooming]
      why: Cat brushing: Brushing a cat a few times a week reduces hairballs and shedding, and lets you spot lumps or skin problems early.
[4 SELF-CHECK] simulated against the real Scheduler
  Give insulin with meal: fits today
  Feed cat and refresh water: fits today | 07:00 clashed with another task; time cleared
  Interactive play session: fits today | low confidence (0.05): weak match to the pet's profile
  Brush cat: fits today | low confidence (0.07): weak match to the pet's profile
[5 OWNER APPROVES] (simulated click on Add) 4 of 4 added as tasks
[6 DAILY PLAN] produced by the original PawPal+ Scheduler
  [x] 07:00  Tom  Give insulin with meal                10 min  [high]
  [x] 19:00  Tom  Interactive play session              15 min  [medium]
  [x] --:--  Tom  Feed cat and refresh water             5 min  [high]
  [x] --:--  Tom  Brush cat                              5 min  [low]
  total 35 of 90 min

==============================================================================
END-TO-END CASE 2: senior arthritic dog who already has a walk
==============================================================================
[1 INPUT]
  pet=Rex (dog, age 10) needs='arthritis' existing=['Morning walk']
  owner has 60 min today
[2 RETRIEVE] knowledge-base passages ranked for each pet (species/age filtered)
  Rex: query='dog senior old aging arthritis arthritis'
    0.38  [dog-senior] Senior dog joint care
    0.32  [med-arthritis] Arthritis and mobility
    0.09  [dog-feeding] Dog feeding schedule
[3 GENERATE + VALIDATE] mode=offline, 3 suggestions kept
  Rex: Give joint supplement (5 min, high) conf=0.32 cites [med-arthritis]
      why: Rex's special needs (arthritis) match: Arthritis and mobility.
  Rex: Feed breakfast (10 min, high) conf=0.09 cites [dog-feeding]
      why: Dog feeding schedule: Adult dogs do best with two measured meals a day, about 12 hours apart.
  Rex: Brush coat (10 min, low) conf=0.06 cites [dog-grooming]
      why: Coat and nail care: Brush dogs weekly (daily for long coats) and trim nails every 3 to 4 weeks.
[4 SELF-CHECK] simulated against the real Scheduler
  Give joint supplement: fits today | 08:00 clashed with another task; time cleared
  Feed breakfast: fits today | low confidence (0.09): weak match to the pet's profile
  Brush coat: fits today | low confidence (0.06): weak match to the pet's profile
[5 OWNER APPROVES] (simulated click on Add) 3 of 3 added as tasks
[6 DAILY PLAN] produced by the original PawPal+ Scheduler
  [x] 07:00  Rex  Feed breakfast                        10 min  [high]
  [x] 08:00  Rex  Morning walk                          20 min  [high]
  [x] --:--  Rex  Give joint supplement                  5 min  [high]
  [x] --:--  Rex  Brush coat                            10 min  [low]
  total 45 of 60 min

==============================================================================
END-TO-END CASE 3: two pets, only 20 minutes, negated condition
==============================================================================
[1 INPUT]
  pet=Bun (other, age 2) needs='' existing=[]
  pet=Mia (cat, age 3) needs='no known allergies' existing=[]
  owner has 20 min today
[2 RETRIEVE] knowledge-base passages ranked for each pet (species/age filtered)
  Bun: query='other small pet habitat cage water clean adult  '
    0.64  [other-habitat] Small pets and exotics
  Mia: query='cat adult  '
    0.25  [cat-feeding] Cat feeding and water
    0.16  [cat-grooming] Cat brushing
    0.12  [cat-play] Play and enrichment for cats
[3 GENERATE + VALIDATE] mode=offline, 6 suggestions kept
  Bun: Spot-clean habitat and refresh water (10 min, high) conf=0.64 cites [other-habitat]
      why: Small pets and exotics: Small pets need fresh water and food daily, spot cleaning of the habitat every day and a full clean weekly.
  Mia: Feed cat and refresh water (5 min, high) conf=0.25 cites [cat-feeding]
      why: Cat feeding and water: Adult cats do well on two measured meals daily, with wet food helping hydration.
  Mia: Scoop litter box (5 min, high) conf=0.05 cites [cat-litter]
      why: Litter box hygiene: Scoop the litter box at least once a day.
  Mia: Interactive play session (15 min, medium) conf=0.12 cites [cat-play]
      why: Play and enrichment for cats: Indoor cats need two or more play sessions of 10 to 15 minutes daily, ideally with a wand toy that mimics hunting.
  Mia: Brush teeth (5 min, medium) conf=0.07 cites [dog-dental]
      why: Dental care: Brushing a dog or cat's teeth several times a week prevents tartar and gum disease, which is linked to heart and kidney problems.
  Mia: Brush cat (5 min, low) conf=0.16 cites [cat-grooming]
      why: Cat brushing: Brushing a cat a few times a week reduces hairballs and shedding, and lets you spot lumps or skin problems early.
[4 SELF-CHECK] simulated against the real Scheduler
  Spot-clean habitat and refresh water: fits today
  Feed cat and refresh water: fits today
  Scoop litter box: fits today | low confidence (0.05): weak match to the pet's profile
  Interactive play session: DOES NOT FIT | does not fit in available minutes today
  Brush teeth: DOES NOT FIT | low confidence (0.07): weak match to the pet's profile | does not fit in available minutes today
  Brush cat: DOES NOT FIT | does not fit in available minutes today
[5 OWNER APPROVES] (simulated click on Add) 3 of 6 added as tasks
[6 DAILY PLAN] produced by the original PawPal+ Scheduler
  [x] 07:00  Mia  Feed cat and refresh water             5 min  [high]
  [x] 08:30  Mia  Scoop litter box                       5 min  [high]
  [x] --:--  Bun  Spot-clean habitat and refresh water  10 min  [high]
  total 20 of 20 min

==============================================================================
RAG ABLATION: same cat (age 4), only the special-needs text changes
==============================================================================
  needs=''          -> (no medical/special-needs task)
  needs='diabetes'  -> Give insulin with meal [high]
  needs='anxiety'   -> Calm bonding time [high]
```

Note two behaviors visible above that are known limitations (see `model_card.md`): in Case 1 the insulin task takes the 07:00 slot, so the feeding task loses its time even though insulin is meant to be given with a meal; and in Case 3 the dental passage written for dogs and cats is shared with the cat.

### 2. Advisor in isolation: `python demo_advisor.py`

Each block shows the **example input** (pet profile, existing tasks, minutes available) and the **resulting output** (suggestions with priority, confidence, whether they fit, and the cited source passage). Cases 1 to 4 show: a special need changing the advice, age and existing tasks being respected, an overbooked day producing a warning, and a negated condition (`no known allergies`) not being treated as an allergy.

```text
$ python demo_advisor.py
PART 1: example inputs and outputs (offline generator)

=== 1. Special need changes the advice ===
INPUT  pet=Tom species=cat age=4 needs='diabetes' existing_tasks=[]
INPUT  available_minutes=120
OUTPUT mode=offline suggestions=4
  Tom  Give insulin with meal                  10m high   daily  07:00  conf=0.29 fits   [med-diabetes]
  Tom  Feed cat and refresh water               5m high   daily  --:--  conf=0.11 fits   [cat-feeding]
       note: 07:00 clashed with another task; time cleared
  Tom  Interactive play session                15m medium daily  19:00  conf=0.05 fits   [cat-play]
       note: low confidence (0.05): weak match to the pet's profile
  Tom  Brush cat                                5m low    weekly --:--  conf=0.07 fits   [cat-grooming]
       note: low confidence (0.07): weak match to the pet's profile

=== 2. Age + existing task respected ===
INPUT  pet=Rex species=dog age=10 needs='arthritis' existing_tasks=['Morning walk']
INPUT  available_minutes=120
OUTPUT mode=offline suggestions=3
  Rex  Give joint supplement                    5m high   daily  --:--  conf=0.32 fits   [med-arthritis]
       note: 08:00 clashed with another task; time cleared
  Rex  Feed breakfast                          10m high   daily  07:00  conf=0.09 fits   [dog-feeding]
       note: low confidence (0.09): weak match to the pet's profile
  Rex  Brush coat                              10m low    weekly --:--  conf=0.06 fits   [dog-grooming]
       note: low confidence (0.06): weak match to the pet's profile

=== 3. Overbooked day triggers warning ===
INPUT  pet=Bun species=other age=2 needs='' existing_tasks=[]
INPUT  pet=Mia species=cat age=3 needs='' existing_tasks=[]
INPUT  available_minutes=15
OUTPUT mode=offline suggestions=6
  Bun  Spot-clean habitat and refresh water    10m high   daily  --:--  conf=0.64 NO FIT [other-habitat]
       note: does not fit in available minutes today
  Mia  Feed cat and refresh water               5m high   daily  07:00  conf=0.25 fits   [cat-feeding]
  Mia  Scoop litter box                         5m high   daily  08:30  conf=0.05 fits   [cat-litter]
       note: low confidence (0.05): weak match to the pet's profile
  Mia  Interactive play session                15m medium daily  19:00  conf=0.12 NO FIT [cat-play]
       note: does not fit in available minutes today
  Mia  Brush teeth                              5m medium daily  --:--  conf=0.07 fits   [dog-dental]
       note: low confidence (0.07): weak match to the pet's profile
  Mia  Brush cat                                5m low    weekly --:--  conf=0.16 NO FIT [cat-grooming]
       note: does not fit in available minutes today
  WARNING: High-priority 'Spot-clean habitat and refresh water' for Bun won't fit today; consider increasing available minutes.

=== 4. Negated need is not a condition ===
INPUT  pet=Kit species=cat age=4 needs='no known allergies' existing_tasks=[]
INPUT  available_minutes=120
OUTPUT mode=offline suggestions=5
  Kit  Feed cat and refresh water               5m high   daily  07:00  conf=0.25 fits   [cat-feeding]
  Kit  Scoop litter box                         5m high   daily  08:30  conf=0.05 fits   [cat-litter]
       note: low confidence (0.05): weak match to the pet's profile
  Kit  Interactive play session                15m medium daily  19:00  conf=0.12 fits   [cat-play]
  Kit  Brush teeth                              5m medium daily  --:--  conf=0.07 fits   [dog-dental]
       note: low confidence (0.07): weak match to the pet's profile
  Kit  Brush cat                                5m low    weekly --:--  conf=0.16 fits   [cat-grooming]
```

### 3. Guardrail and reliability results (`demo_advisor.py`, Part 2)

The advisor is fed deliberately bad model output. Each case shows the log line the guardrail wrote and the final result: invalid items are dropped, and if the model fails or nothing it returned survives validation, the advisor falls back to offline guidance with a warning instead of crashing or returning nothing.

```text
PART 2: guardrails against bad model output (fake LLM, log lines shown)

--- a) hallucinated source id
  LOG WARNING pawpal.advisor: rejected suggestion for Mia: cites unknown source 'made-up' | {'source_id': 'made-up', 'title': 'Scoop litter', 'category': 'hygiene', 'duration_minutes': 5, 'priority': 'high', 'frequency': 'daily', 'preferred_time': '', 'rationale': 'x'}
  LOG WARNING pawpal.advisor: all 1 LLM suggestions for Mia were rejected; using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- b) 999-minute task (prompt-injection style)
  LOG WARNING pawpal.advisor: rejected suggestion for Mia: duration 999 out of range | {'source_id': 'cat-litter', 'title': 'Scoop litter', 'category': 'hygiene', 'duration_minutes': 999, 'priority': 'high', 'frequency': 'daily', 'preferred_time': '', 'rationale': 'x'}
  LOG WARNING pawpal.advisor: all 1 LLM suggestions for Mia were rejected; using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- c) invalid priority
  LOG WARNING pawpal.advisor: rejected suggestion for Mia: invalid priority or frequency | {'source_id': 'cat-litter', 'title': 'Scoop litter', 'category': 'hygiene', 'duration_minutes': 5, 'priority': 'urgent', 'frequency': 'daily', 'preferred_time': '', 'rationale': 'x'}
  LOG WARNING pawpal.advisor: all 1 LLM suggestions for Mia were rejected; using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- d) malformed time '7am'
  LOG WARNING pawpal.advisor: rejected suggestion for Mia: bad time '7am' | {'source_id': 'cat-litter', 'title': 'Scoop litter', 'category': 'hygiene', 'duration_minutes': 5, 'priority': 'high', 'frequency': 'daily', 'preferred_time': '7am', 'rationale': 'x'}
  LOG WARNING pawpal.advisor: all 1 LLM suggestions for Mia were rejected; using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- e) not JSON at all
  LOG WARNING pawpal.advisor: LLM failed for Mia (no JSON array in model output); using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- f) model call raises an error
  LOG WARNING pawpal.advisor: LLM failed for Mia (network down); using offline generator
  RESULT mode=offline accepted=5 first=['Feed cat and refresh water', 'Scoop litter box'] warnings=1

--- g) one valid + one invalid
  LOG WARNING pawpal.advisor: rejected suggestion for Mia: cites unknown source 'made-up' | {'source_id': 'made-up', 'title': 'Fake', 'category': 'hygiene', 'duration_minutes': 5, 'priority': 'high', 'frequency': 'daily', 'preferred_time': '', 'rationale': 'x'}
  RESULT mode=llm accepted=1 first=['Scoop litter'] warnings=0
```

| Bad model output | Guardrail response | Result |
|---|---|---|
| Hallucinated source id | Rejected (`cites unknown source`), then offline fallback | Pass |
| 999-minute task | Rejected (`duration out of range`), then offline fallback | Pass |
| Invalid priority | Rejected, then offline fallback | Pass |
| Malformed time `7am` | Rejected (`bad time`), then offline fallback | Pass |
| Not JSON | Offline fallback + warning | Pass |
| Model call raises | Offline fallback + warning | Pass |
| One valid, one invalid | Keeps the valid one, logs the rejection | Pass |

### 4. Sample command: `python eval_advisor.py`

```text
$ python eval_advisor.py
[PASS] diabetic cat gets insulin, high priority | cited=['cat-feeding', 'cat-grooming', 'cat-play', 'med-diabetes'] | consistent=True
[PASS] senior arthritic dog gets joint care | cited=['dog-feeding', 'dog-grooming', 'dog-senior', 'med-arthritis'] | consistent=True
[PASS] puppy gets puppy guidance, not adult exercise | cited=['dog-grooming', 'dog-puppy'] | consistent=True
[PASS] adult indoor cat gets litter + play | cited=['cat-feeding', 'cat-grooming', 'cat-litter', 'cat-play', 'dog-dental'] | consistent=True
[PASS] rabbit gets small-pet habitat care | cited=['other-habitat'] | consistent=True
[PASS] anxious dog gets calming routine | cited=['dog-exercise', 'dog-feeding', 'dog-grooming', 'med-anxiety'] | consistent=True

| Test input | Criteria | Result |
|---|---|---|
| diabetic cat gets insulin, high priority | right passages cited, wrong ones excluded | Pass |
| senior arthritic dog gets joint care | right passages cited, wrong ones excluded | Pass |
| puppy gets puppy guidance, not adult exercise | right passages cited, wrong ones excluded | Pass |
| adult indoor cat gets litter + play | right passages cited, wrong ones excluded | Pass |
| rabbit gets small-pet habitat care | right passages cited, wrong ones excluded | Pass |
| anxious dog gets calming routine | right passages cited, wrong ones excluded | Pass |
| Owner with no pets | returns no suggestions, no crash | Pass |
| Nonsense special needs | still gives normal adult-dog guidance, nothing invented | Pass |
| Prompt-injection text in special needs | all suggestions stay valid (1-240 min, cited) | Pass |
| Zero available minutes | warns instead of silently dropping high-priority tasks | Pass |

mean confidence across scenarios: 0.25

10/10 scenarios passed (mode=offline, runs each=1)
```

Structured results: [`docs/evidence/eval_results.json`](docs/evidence/eval_results.json). With a key, `python eval_advisor.py --llm` runs each scenario 3 times against Claude to measure consistency (not yet run, see Testing summary).

### 5. Sample command: `python -m pytest -v`

```text
$ python -m pytest -v
============================= test session starts ==============================
platform darwin -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0 -- /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
cachedir: .pytest_cache
rootdir: .
plugins: anyio-4.14.1
collecting ... collected 63 items
...
tests/test_pawpal.py::test_duplicate_task_id_across_pets_is_allowed_known_limitation PASSED [ 98%]
tests/test_pawpal.py::test_edit_and_remove_missing_task PASSED           [100%]

============================== 63 passed in 0.03s ==============================
```

Full verbose output: [`docs/evidence/pytest_output.txt`](docs/evidence/pytest_output.txt).

### 6. Sample command: the app

```bash
streamlit run app.py
```

Example input: add a pet "Rex" (dog, age 10, special needs `arthritis`), click **Get care suggestions**. Example output: a "Give joint supplement" task (high priority, cited source `med-arthritis`, confidence shown) with an **Add** button; clicking it adds a real task that appears in the task table and the generated schedule. This flow is exercised headlessly with Streamlit's `AppTest` during development.

### 7. What gets logged (`pawpal.log`)

Retrieval scores (debug), LLM request ids and token counts, each rejected suggestion with its reason, and every fallback to offline mode. Warnings (rejections, fallbacks) also print to the console, as seen in the Part 2 output above.

## Design decisions and trade-offs

- **Retrieval before generation, and a citation requirement.** The model may only use passages the retriever returned, and every suggestion must name one. This reduces invented advice and makes each suggestion traceable. The cost is that the advisor is only as good as the knowledge base.
- **TF-IDF instead of embeddings.** Sixteen short passages don't justify a vector database or a second API. TF-IDF is dependency-free, deterministic and easy to test. The trade-off is lexical matching: "limping" will not match "arthritis" unless the passage lists both. I mitigated this with keyword lists and by filtering on structured fields (species, age) first.
- **Offline mode is a first-class path.** The app, tests and eval all run with no API key, so anyone can reproduce results. The trade-off is two generators to keep consistent, which the eval checks.
- **Human approval for every change.** Suggestions are never added automatically. A pet-care tool that silently edits medication schedules would be a bad trade for a little convenience.
- **Validation in code, not in the prompt.** I treat model output as untrusted input. A prompt can ask for valid JSON; only code can guarantee it.
- **Self-check reuses the real scheduler.** Rather than asking the model whether a suggestion fits, `_check()` runs `Scheduler.generate_plan()` on a copy of the data. That is cheaper and exact. The trade-off is that it only fixes same-start-time clashes (the scheduler's existing limitation).
- **Kept the original engine untouched.** The advisor sits beside `pawpal_system.py` and produces ordinary `Task`s, so all 44 original tests still pass unchanged.

## Testing summary

**Headline: 63/63 unit tests pass and 10/10 eval scenarios pass (offline mode). The eval's first run was 5/6: a rabbit got no advice at all, which led to a fix and a regression test. The live-Claude eval has not been run yet.** Mean retrieval confidence was 0.25 across the 6 pet scenarios.

Four reliability mechanisms are in place:

1. **Automated tests** (`python -m pytest`): 44 original scheduler tests plus 19 in `tests/test_advisor.py` (species/age filtering, negated special needs, special needs driving retrieval, no duplicate tasks, guardrail rejections, JSON parsing, a fake LLM returning valid, hallucinated, garbage and failing output, time-clash repair, overflow flagging, confidence bounds, empty owner).
2. **Scenario eval** (`python eval_advisor.py`): runs the advisor end to end and writes `eval_results.json`. With `--llm` each scenario runs 3 times to measure consistency.
3. **Confidence scoring**: each suggestion carries `confidence`, the TF-IDF cosine similarity between the pet's profile and the passage it cites (0-1). Suggestions below 0.10 are labelled "low confidence" in the UI. The score is a relative signal, not a calibrated probability: special-needs matches score highest (insulin for the diabetic cat: 0.29) and generic ones lowest (cat play: 0.05).
4. **Logging and error handling** (`pawpal.log`): retrieval scores, LLM request ids and token counts, every rejected suggestion with the reason, and every fallback to offline mode. Model errors, refusals and malformed JSON degrade to offline suggestions with a warning instead of crashing.

### Eval results (`eval_advisor.py`, offline mode)

| Test input | Evaluation criteria | Mean confidence | Result |
|---|---|---|---|
| Diabetic cat (age 4) | Cites `med-diabetes`, task is high priority, no dog guidance | 0.13 | Pass |
| Arthritic senior dog (age 10) | Cites `med-arthritis`, high priority, no puppy/cat guidance | 0.21 | Pass |
| Puppy (age 0) | Cites `dog-puppy`, excludes senior and adult-exercise guidance | 0.19 | Pass |
| Adult indoor cat | Cites litter box and play, no dog guidance | 0.13 | Pass |
| Rabbit (species `other`) | Cites `other-habitat` | 0.64 | Pass (Fail on first run: returned nothing) |
| Anxious dog | Cites `med-anxiety`, no cat guidance | 0.20 | Pass |
| Owner with no pets | Returns no suggestions, no crash | n/a | Pass |
| Nonsense special needs (`qwertyuiop zxcvbnm`) | Falls back to normal dog guidance, nothing invented | n/a | Pass |
| Prompt-injection text in special needs | All suggestions stay valid (1-240 min, cited) | n/a | Pass |
| Zero available minutes | Warns instead of silently dropping high-priority tasks | n/a | Pass |

**What worked.** Injecting a fake LLM made the model path testable without network calls, and the citation check reliably catches hallucinated sources. Filtering by species and age before ranking kept results clean. The prompt-injection and nonsense inputs are handled because model output is validated in code rather than trusted.

**What didn't, at first.** For species `other` the query contained the word "other", which matched nothing in the knowledge base, so the rabbit got no advice. I fixed it by expanding that species into habitat words (`SPECIES_HINTS`) and added a regression test. Confidence is also low in absolute terms (0.13-0.21 for most pets) because lexical matching over short passages gives small cosine scores, so the 0.10 threshold is only a rough guide.

**Not yet verified.** `eval_advisor.py --llm` has not been run against the live API, so Claude's consistency and suggestion quality are unmeasured, and the offline results above don't speak to them. The eval checks which guidance is cited, not whether the advice is medically right; the knowledge base is small and not veterinarian-reviewed. A human review of Claude's output should be added as a table here once it exists.

**What I learned.** An eval is worth building early: it found a real bug that hand-picked unit tests missed. Testing the guardrails matters more than testing the model, because the guardrails are what you control.

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
demo_end_to_end.py     End-to-end run: input -> retrieve -> generate -> check -> approve -> plan
demo_advisor.py        Advisor demo: example inputs/outputs + guardrail cases
eval_advisor.py        Scenario-based reliability eval
logging_setup.py       Logging configuration
tests/                 pytest suites (scheduler + advisor)
diagrams/              system.mmd (this system), uml.mmd (original classes)
docs/                  Original PawPal+ docs; docs/evidence/ = captured run output
```
