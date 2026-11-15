# Portfolio artifact: PawPal+ AI Care Advisor

**Code:** https://github.com/SFhectorj/applied-ai-system-project

**What it is:** A pet-care scheduler extended with a retrieval-augmented AI advisor that finds the care a pet is missing, validates it against the owner's real schedule, and requires owner approval before anything is added. 63 unit tests, a 10-scenario eval, confidence scoring, logging, and a model card.

## Reflection: what this project says about me as an AI engineer

This project shows that I treat the model as one component in a system I'm responsible for, not as the system. The most useful work wasn't the Claude call; it was grounding every suggestion in retrieved sources, enforcing limits in code rather than in the prompt, putting a human approval step before any action, and building an eval that could tell me I was wrong. It did: a rabbit got no advice, and a casual "no known allergies" produced a medication task, and both came from testing my own work adversarially instead of trusting the happy path. I also try to be straight about what I haven't proven. The knowledge base is unreviewed by a vet, the confidence score isn't calibrated, and the live-model eval hasn't run yet, and I wrote all of that into the model card. I used Claude Code heavily to build this, and I see my job in that loop as setting requirements, reviewing what comes back, and probing for the failures the tests don't cover. That mix of building quickly with AI while staying skeptical about reliability and safety is the kind of engineer I want to be.
