# Decision-oriented research

Read when an unresolved question can change product, domain, content or technical decisions.
Use [task framing](../task-framing.md) first and [NotebookLM](../integrations/notebooklm.md) for its adapter.

## 1. Build a research brief

Use the helper's `plan` command to preview a packet contract without network calls. Specify the
audience, deliverable, decision and a small set of answerable questions with stable IDs. Set the
domain explicitly for mixed projects. Do not submit personal facts as public-research questions.
List constraints, geography/jurisdiction if relevant, applicable versions, and excluded topics.
Do not let implementation details such as CSS tokens redefine the subject of the research.

Prioritize questions whose answer can reverse a decision. Choose fast for a narrow fact, deep
for a genuine comparison/synthesis, and none when existing evidence suffices. Declare a budget
in questions/queries or time; stop at adequate decision coverage, not an arbitrary source count.

## 2. Curate a corpus

Discover candidate sources, then inspect title, author/publisher, date/version, source type,
scope, applicability and original URL. Prefer primary documentation for APIs/standards, empirical
work for empirical claims, and actual target job descriptions/recipient requirements for role fit.
Competitor pages support observations about competitors; they do not prove user demand or outcomes.

Use NotebookLM discovery to find candidates, not to make all candidates authoritative. Inspect the
original before treating a decisive claim as established. Duplicate articles citing one source
are one evidence lineage, not independent corroboration. Exclude stale versions, irrelevant
regions, marketing assertions presented as facts and synthesis that cites only another synthesis.
Preserve useful disagreement rather than selecting only supportive sources.

## 3. Ask bounded questions over selected sources

Use a focused source subset for each question. Request:

- What the source states, with citation and locator, separated from inference/recommendation.
- Conditions, exceptions, date/version, and applicability to this task.
- Counterevidence and unresolved disagreement; absence of evidence is an acceptable finding.
- Alternatives, tradeoffs, and the local or recipient-facing check needed before adoption.

For multi-hop conclusions, collect evidence for every link. Ask a follow-up only for a specific
missing link or contradiction. Do not ask the same broad question repeatedly. Do not upload the
entire codebase, resume or customer dataset merely to provide context.

## 4. Convert synthesis to an evidence matrix

Maintain question -> claim -> citation/source ID -> original URL/section -> applicability ->
decision -> acceptance check. The helper validates packet structure and citation references only.
It cannot determine that a quotation is accurate, that a URL is trustworthy, or that the claim
answers the question. These checks belong to the agent reading the originals.

Keep statuses distinct:

| Status | Meaning |
|---|---|
| discovered | Candidate found; not yet reviewed/imported |
| pending | Service/import/answer not complete |
| packet_valid | Packet is parseable and references resolve within the response |
| source_verified | Agent checked the actual passage and applicability |
| locally_validated | Relevant behavior measured or requirement checked locally |
| unresolved | Missing evidence, contradiction or untested assumption |

Never promote `packet_valid` to `source_verified` automatically. Record review notes next to the
saved packet with the claim ID, original location, reviewer observation and date. For each
material claim use this compact record (not an automatic promotion of the whole packet):

```text
claim_id / question_id:
source_id + original URL + section/page:
publication/effective version + retrieved/reviewed date:
original observation (short excerpt or faithful paraphrase):
entailment: supports | contradicts | insufficient
applicability and evidence lineage:
status: source_verified | unresolved
local check: observed result and scope | not run
remaining gap / effect on decision:
```

A verified citation for one claim cannot validate uncited dependencies in a multi-hop conclusion.
Preserve the packet and original corpus selection alongside these records. User-supplied
facts may be attributed to the user; do not label them independently verified.

## 5. Adversarial synthesis and stop rule

For a consequential choice, run a separate challenge pass after inspecting primary evidence:
"Which recommendation fails for this audience, constraint, workload or version? What fact would
reverse it? Which citation fails to support its claim? What did the corpus omit?"
The helper provides `challenge` for an existing notebook and saved packet; its answer is advisory
and cannot revise a verified record automatically. A separate conversation is not an independent
model or independent evidence. Prefer deterministic checks where available.

Finish when decisive questions have applicable evidence and a validation plan, or label the
remaining decisions conditional. More source imports are justified only for a named evidence gap.
Preserve notebook/task IDs on errors; inspect existing remote work before starting a duplicate.

## Research quality checks

Check question coverage, claim-to-source entailment, source independence, recency/version,
counterevidence, uncertainty and effect on the decision. Do not score research by word count,
prestigious source names, CSS units or citation-shaped text. Good evidence may be qualitative.
Report research limitations separately from execution tests and from model benchmark results.
