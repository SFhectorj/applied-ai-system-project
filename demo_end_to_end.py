"""End-to-end run of PawPal+ with the AI Care Advisor. Run: python demo_end_to_end.py

For each input, every stage is printed:
  1 INPUT -> 2 RETRIEVE (RAG) -> 3 GENERATE+VALIDATE -> 4 SELF-CHECK -> 5 OWNER APPROVES -> 6 DAILY PLAN
Then a RAG ablation shows that retrieval, not chance, drives the output.
Offline generator, so it needs no API key and is deterministic.
"""

from advisor import CareAdvisor, build_query
from pawpal_system import Owner, Pet, Scheduler, Task


def run_case(n, title, owner, advisor):
    print(f"\n{'=' * 78}\nEND-TO-END CASE {n}: {title}\n{'=' * 78}")
    print("[1 INPUT]")
    for p in owner.pets:
        print(f"  pet={p.name} ({p.species}, age {p.age}) needs={p.special_needs!r} "
              f"existing={[t.title for t in p.tasks]}")
    print(f"  owner has {owner.available_minutes} min today")

    print("[2 RETRIEVE] knowledge-base passages ranked for each pet (species/age filtered)")
    for p in owner.pets:
        hits = advisor.kb.retrieve(build_query(p), p.species, p.age, k=3)
        print(f"  {p.name}: query={build_query(p)!r}")
        for passage, score in hits:
            print(f"    {score:.2f}  [{passage.id}] {passage.title}")

    report = advisor.advise(owner)
    print(f"[3 GENERATE + VALIDATE] mode={report.mode}, {len(report.suggestions)} suggestions kept")
    for s in report.suggestions:
        print(f"  {s.pet_name}: {s.title} ({s.duration_minutes} min, {s.priority}) "
              f"conf={s.confidence:.2f} cites [{s.source_id}]")
        print(f"      why: {s.rationale}")

    print("[4 SELF-CHECK] simulated against the real Scheduler")
    for s in report.suggestions:
        print(f"  {s.title}: {'fits today' if s.fits else 'DOES NOT FIT'}"
              + "".join(f" | {note}" for note in s.notes))
    for w in report.warnings:
        print(f"  WARNING: {w}")

    approved = [s for s in report.suggestions if s.fits]
    print(f"[5 OWNER APPROVES] (simulated click on Add) {len(approved)} of "
          f"{len(report.suggestions)} added as tasks")
    pets = {p.name: p for p in owner.pets}
    for s in approved:
        task_id = max((t.id for t in owner.get_all_tasks()), default=0) + 1
        pets[s.pet_name].add_task(s.to_task(task_id))

    print("[6 DAILY PLAN] produced by the original PawPal+ Scheduler")
    sched = Scheduler(owner)
    plan = sched.generate_plan()
    names = {t.id: p.name for p in owner.pets for t in p.tasks}
    for t in sched.sort_by_time(plan.scheduled_tasks):
        print(f"  [x] {t.preferred_time or '--:--'}  {names[t.id]:<4} {t.title:<36} {t.duration_minutes:>3} min  [{t.priority}]")
    for t in plan.skipped_tasks:
        print(f"  [ ] skipped {names[t.id]}: {t.title} - {plan.explanations[t.id]}")
    print(f"  total {plan.get_total_minutes()} of {owner.available_minutes} min")


def main():
    adv = CareAdvisor(use_llm=False)

    o = Owner("Demo", 90)
    o.add_pet(Pet("Tom", "cat", 4, "diabetes"))
    run_case(1, "diabetic cat, relaxed day", o, adv)

    o = Owner("Demo", 60)
    rex = Pet("Rex", "dog", 10, "arthritis")
    rex.add_task(Task(1, "Morning walk", "exercise", 20, "high", "08:00"))
    o.add_pet(rex)
    run_case(2, "senior arthritic dog who already has a walk", o, adv)

    o = Owner("Demo", 20)
    o.add_pet(Pet("Bun", "other", 2))
    o.add_pet(Pet("Mia", "cat", 3, "no known allergies"))
    run_case(3, "two pets, only 20 minutes, negated condition", o, adv)

    print(f"\n{'=' * 78}\nRAG ABLATION: same cat (age 4), only the special-needs text changes\n{'=' * 78}")
    for needs in ["", "diabetes", "anxiety"]:
        o = Owner("Demo", 120)
        o.add_pet(Pet("Cat", "cat", 4, needs))
        r = adv.advise(o)
        print(f"  needs={needs!r:<11} -> " + ", ".join(
            f"{s.title} [{s.priority}]" for s in r.suggestions if s.source_id.startswith("med-")
        ) + ("" if any(s.source_id.startswith("med-") for s in r.suggestions) else "(no medical/special-needs task)"))


if __name__ == "__main__":
    main()
