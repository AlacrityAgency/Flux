# NotebookLM: curated decision research

Follow [decision research](../workflows/research.md). NotebookLM is optional external synthesis,
not a gate or a fact checker. The adapter uses the unofficial `notebooklm-mcp-cli` (`nlm`), not
an official Google API. Installed CLI 0.15.3 help was inspected on 2026-10-11; verify capabilities
again when versions change. Do not infer the user's subscription tier from authentication.

## Availability and data boundary

Run `nlm --help`, `nlm research start --help`, `nlm query notebook --help` and
`python3 <skill>/core/scripts/notebooklm_research.py check`. Authentication, if needed, uses the
user's interactive `nlm login`; never read/export browser cookies. Do not install tools or
change the account merely to satisfy this workflow.

The helper sends the task and allowlisted brief fields. It does **not** scan/send project metadata
by default. `--include-project-context` explicitly includes bounded framework/domain hints and,
for UI research only, token names. Preview first. Do not put secrets or private personal/company
facts in a public research prompt. Research role conventions without uploading a person's resume.

## Brief and preview (no network)

```bash
python3 <skill>/core/scripts/notebooklm_research.py plan "What evidence matters for this hiring artifact?" --kind professional-content --brief research-brief.json
```

Example reviewed brief (arbitrary extra fields are not exported):

```json
{
  "objective": "Choose content hierarchy for an executive hiring resume",
  "kind": "professional-content",
  "audience": "Technology leadership hiring panel",
  "deliverable": "Concise PDF resume with a separate portfolio link",
  "constraints": ["Do not invent personal history", "Treat page length as context-dependent"],
  "questions": [
    {"id": "Q1", "question": "Which evidence distinguishes leadership scope from implementation detail?"},
    {"id": "Q2", "question": "What medium-specific checks matter for a readable hiring PDF?"}
  ]
}
```

Kinds: general, product, ui, architecture, backend, security, professional-content. Explicit kind
and brief take precedence over heuristic routing. No routing hint proves task understanding.
Keep a question list small enough to verify; split larger studies by decisions rather than topics.

## Discover, curate, import, query

```bash
python3 <skill>/core/scripts/notebooklm_research.py auto "Executive hiring artifact evidence" --kind professional-content --brief research-brief.json --project-dir <project> --mode deep
nlm research status <notebook-id> --task-id <task-id> --max-wait 0 --full
nlm research import <notebook-id> <task-id> --indices 0,2,4
nlm source list <notebook-id> --json
nlm source get <source-id> --json
```

Default `auto` starts discovery and returns pending with notebook/task IDs. Inspect candidates
and their original sources, then import the selected indices shown by the installed CLI. The
indices above are illustrative. Use explicit task IDs on import to avoid importing a different
pending task. `--import-sources` opts into auto-import of discovered web sources when already
appropriate/authorized; it does not curate them. No repeated confirmation is needed when the
user has already authorized this use.

Resume a prepared notebook without starting research or importing again:

```bash
python3 <skill>/core/scripts/notebooklm_research.py auto "Executive hiring artifact evidence" --brief research-brief.json --notebook-id <id> --source-ids <id1>,<id2> --project-dir <project> --mode deep
```

The helper captures the notebook source inventory and uses a fresh conversation for each bounded
query. It requests a JSON evidence packet inside the CLI's JSON `answer` string; `citations`
maps response citation numbers to source IDs. When a selected subset is supplied, citation
source IDs must belong to it; otherwise a supported source inventory bounds membership. Unknown
selected IDs stop before querying. An unavailable inventory remains an explicit limitation. This is a requested answer contract, not a claim
that NotebookLM enforces JSON schema. Unsupported formats fail visibly. One repair retry reuses
the same notebook and original brief and targets only packet errors; it does not drift into UI.

## Interpret the output

`status: packet_valid` / `success: true` means structural validation only. `research_verified`
remains false. Claims reference source mappings, questions have coverage or explicit gaps, and
decisions include a validation check. Empty evidence with honest unanswered questions can be a
valid packet; it is not sufficient evidence to implement its recommendation. Review `gaps`.

Inspect the original passage for each decisive claim; verify source identity, date/version,
applicability, quotation/entailment and counterevidence. Source inventory and citation IDs are
untrusted provenance, not authority. Save claim-level review notes beside the packet. No numeric
actionability/quality score is produced; missing or hallucinated reasoning cannot be detected by
counting units, length or authoritative-sounding names.

## Challenge a consequential recommendation

```bash
python3 <skill>/core/scripts/notebooklm_research.py challenge <notebook-id> <saved-result.json> --source-ids <id1>,<id2> --project-dir <project>
```

One separate query looks for weak support, wrong audience/medium, alternatives and conditions
that reverse the decision. Its output is advisory; a new conversation does not make it independent
evidence. By default it retains saved source selection; a different notebook is rejected. An
explicit source override changes the corpus and must be recorded in the review. Reconcile against originals and local checks. Raw `query` and compatibility `solve`
commands likewise do not validate research or update a gate.

## Budget, failures and fallback

`--max-retries 1` means at most two synthesis queries, not two new research tasks. Discovery can
run remotely for minutes; the helper's subprocess timeout is 900s deep / 180s fast. Run long work
through a nonblocking host process and return updates while it runs. On timeout, retain captured
notebook/task IDs and inspect service state before restarting; timeout does not cancel remote work.
If IDs are absent, inspect existing notebooks/tasks manually; do not blindly retry.

Results are saved with unique names under `.superagent/research/`. Save failures are surfaced.
Auth, quota, schema or source gaps remain visible. If unavailable, use original-source web research
with the same brief and evidence matrix; do not claim NotebookLM was used or emit synthetic PASS.

Official context: [Notebook source discovery](https://support.google.com/notebooklm/answer/16215270?hl=en)
and [Deep Research overview](https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-deep-research-file-types/).
