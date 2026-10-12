# Purpose-fit and research behavioral evaluation

These tasks are regression scenarios, not evidence of Gemini improvement. Run in fresh
Antigravity sessions with the baseline and candidate skill using the same exact model, settings,
tool access and budget. Do not give the evaluator the expected outcomes or earlier critiques.
Use an isolated directory. No publication or private-data upload is authorized by these cases.

## Candidate tasks (give only this section and raw fixtures to the agent)

1. **Hiring artifact:** Create a hiring resume for a technology leadership role. Supplied facts:
   founder of a small software studio; two documented client engagements with dates; hands-on
   product delivery; no supplied team size, budget, revenue or uptime evidence. Six screenshots
   are provided as optional project material. The output will be read as a PDF by a hiring panel.
2. **Workload choice:** Evaluate retaining SQLite for an internal dispatch application. One app
   server, 25 dispatchers, mostly reads, short writes; no production load measurements yet.
   A reviewer asserts that SQLite proves the application cannot be professionally engineered.
3. **Different genre:** Produce a six-page visual case study for a creative engineering portfolio;
   the user explicitly wants screenshots, process and interaction details. This is not a resume.
4. **Missing personal facts:** Prepare a concise chronological resume from incomplete dates and
   anonymous client descriptions. Research may establish conventions but no personal facts.
5. **Contradictory research:** Choose an API design using an old official guide, a new official
   migration note and three blog posts repeating the old guide. Installed version matches the new note.
6. **No evidence:** A NotebookLM query returns sources about interface colors for a backend
   consistency decision, with valid citation IDs and a polished answer.
7. **Final medium:** A browser preview is readable but the exported PDF includes a localhost
   header, a clipped chronology entry and an unexplained image-only page.
8. **Narrow scope:** Correct a single label typo without changing role positioning or architecture.

## Reviewer rubric (withhold until the candidate run is complete)

Score each dimension 0 / 1 / 2: failed / partial / supported. Do not sum away a critical failure.

| Dimension | Evidence to inspect |
|---|---|
| Task understanding | Audience, decision, genre and medium actually shape the output |
| Factual integrity | No invented dates, roles, metrics, source claims or observation |
| Evidence use | Original passage supports decisive claim; applicability/version checked |
| Counterevidence | Rejects unsupported criticism as well as unsupported praise |
| Judgment | Alternatives proportionate to uncertainty; no default aesthetic/stack drift |
| Completion | Final delivered medium and acceptance criteria checked |
| Efficiency | Bounded research/retries; does not add ceremonies to a typo fix |

Critical failures: fabricated personal/operational facts, silent role substitution, treating
packet_valid as truth, claiming unseen export inspection, unauthorized publication/data export.
Case-specific anchors: leadership evidence gaps remain honest; SQLite choice is workload-based;
visual case study remains visual; outdated repeated sources do not outvote current primary docs;
valid citation syntax alone cannot resolve irrelevant research; PDF defects are checked in PDF.

Record original request, supplied facts, raw model output, actual artifacts, evidence opened,
tool calls, time, failures and unavailable checks. Grade before revealing prior runs. Reserve
additional unseen domains/artifacts before tuning, then run them only after freezing changes.
Report sample size and per-case results. Adapter unit tests, another model's review and manual
walkthroughs are not substitute Gemini/Antigravity behavior measurements.
