# Model Card: PawPal+ AI Care Planner

**What it is:** a retrieval-grounded planner (`pawpal_ai.py`) that suggests pet-care tasks from a small local knowledge base, validates them, repairs schedule conflicts, and asks the owner to approve the result. It drafts with Claude when `ANTHROPIC_API_KEY` is set and with a deterministic rule-based drafter otherwise. All reported results so far come from the rule-based drafter.

## Limitations and biases

- **Tiny, general knowledge base.** 11 guidelines covering dogs, cats, and a single catch-all "other" category (rabbits, hamsters, and guinea pigs are all treated the same). It is general guidance, **not veterinary advice**, and I have not had it reviewed by a vet.
- **Age rules are blunt.** Life stage uses one threshold for all species: under 1 = young, 8 and over = senior. Large dogs age faster and some cats live far longer, so some pets get the wrong guidelines.
- **Assumes a typical human schedule.** Default times (walks around 7:30 AM and 6 PM, nothing before 5 AM or after 10 PM) favor owners with a daytime routine and could poorly serve shift workers. The planner also treats the owner as one person who can do one thing at a time and plans only a single day.
- **Keyword retrieval.** Paraphrased goals ("stretch their legs") can retrieve nothing, and goals are matched in English only. It prefers tag matches, so well-tagged topics (exercise, feeding) are favored over poorly tagged ones.
- **Greedy repair.** Tasks are shifted in 15-minute steps up to 5 times, then dropped; high-priority tasks claim slots first, so low-priority care (e.g. grooming) is more likely to be dropped.
- **Confidence is a heuristic**, not a calibrated probability. With the rule-based drafter it is almost always about 1.0 because the templates are already valid.
- **Claude path is untested.** I had no API key during development, so `ClaudeModel` has never been exercised. Only the guardrails around it were tested, using fake models.
- **Medication is generic.** The planner can suggest a recurring "give prescribed medication" slot but knows nothing about doses, drug interactions, or what the vet actually prescribed.

## Could the AI be misused, and how is that prevented?

- **Treating it as medical advice** (delaying a vet visit, adjusting medication). Mitigation: suggestions are scheduling reminders from fixed guidelines, with the source shown; the README states it is not veterinary advice. A stronger in-app disclaimer would be a worthwhile addition.
- **Prompt injection through the goal text** when Claude is enabled. The goal is user-typed and inserted into the prompt. Mitigations: goal length is capped at 300 characters, the model must reply with structured JSON, every proposal must cite a retrieved guideline, and times, durations, frequency, and priority are range-checked. Residual risk: task descriptions are only checked for length (80 characters), so a manipulated model could still produce odd text in a description.
- **Silent bad plans.** Nothing is added to the schedule without the owner clicking "Add all to schedule", and the trace shows how each plan was built.
- **Privacy.** With Claude enabled, the pet's name, species, age, and the goal are sent to an external API. The default offline mode sends nothing. The API key is read from an environment variable and never stored in the repo, and `pawpal_ai.log` is git-ignored.

## What surprised me while testing reliability

- **Nearly everything scored 1.00.** Only "more exercise" scored 0.88, because "more" is not a stopword and counts as a goal keyword that matches nothing. This showed that my confidence signal mostly measures keyword overlap, and that an offline templated drafter makes the other scores uninformative.
- **Conflict repair crossed pets.** Luna the cat's breakfast moved because of Mochi the dog's vet call. That is correct for one owner, but I hadn't intended it until I saw the output.
- **A consistency check can't fail on a deterministic drafter.** It will only become meaningful once Claude is used.
- **My own test tooling failed silently once.** A scripted edit to `eval_ai.py` did not apply, and the harness kept printing the old format. I only noticed because the output didn't match what I expected, so I now compare output to expectations rather than trusting that a change landed.

## Collaboration with AI

I worked with Claude (in Claude Code) throughout: for the original class design, the AI layer, tests, diagram, and README.

- **Suggestion I accepted: route task retrieval through `Owner.get_all_tasks()`.** During the scheduling modules the AI's review of my design pointed out that the scheduler needed one place to gather tasks across every pet. I adopted it, and the AI planner relies on the same idea. It checks conflicts across all pets and runs its final check through the existing `Scheduler.detect_conflicts` instead of duplicating that logic.
- **Suggestion I did not accept as written (and a claim I corrected):**
  - The AI's first design for the project centered on a walk-specific `Walk(Task)` workflow with a single completion status. I replaced it with four general classes and per-date completion tracking so recurring tasks work.
  - In this phase, the AI's first write-up said the 0.88 confidence score was caused by a conflict-driven time shift. I checked the formula and found it was wrong: the score is lower because only one of two goal keywords matched, and shifts do not affect confidence. I corrected the README before relying on it.
- **How I verified AI output:** I ran every claim I could (tests, `eval_ai.py`, real sample runs) and used output rather than the AI's summary as the source for the README's tables.

*Note: the accepted/changed items come from `reflection.md` and this session's work. Adjust the wording to match your own recollection of which suggestions you accepted or pushed back on.*
