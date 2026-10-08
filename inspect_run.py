import sqlite3, os, json
from pathlib import Path

db_path = Path(os.environ['LOCALAPPDATA']) / 'FluxDemo' / 'flux.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

run = conn.execute("SELECT * FROM runs WHERE run_id='run_aa796c116ca5'").fetchone()
with open('inspect_output.txt', 'w', encoding='utf-8') as out:
    if run:
        out.write(f"RUN ID: {run['run_id']} STATUS: {run['status']}\n")
        
        events = conn.execute("SELECT * FROM events WHERE run_id=? ORDER BY sequence", (run['run_id'],)).fetchall()
        out.write("\nEVENTS:\n")
        for ev in events:
            out.write(f"  Seq {ev['sequence']}: {ev['from_state']} -> {ev['to_state']} | {ev['reason']}\n")

        calls = conn.execute("SELECT * FROM agent_calls WHERE run_id=? ORDER BY created_at", (run['run_id'],)).fetchall()
        out.write("\nCALLS:\n")
        for c in calls:
            out.write(f"  Call {c['call_id']}: {c['agent_role']} ({c['model_id']}) -> {c['status']} | err: {c['error_message']}\n")

        subtasks = conn.execute("SELECT * FROM subtasks WHERE run_id=?", (run['run_id'],)).fetchall()
        out.write("\nSUBTASKS:\n")
        for s in subtasks:
            out.write(f"  Subtask {s['subtask_id']}: {s['assigned_agent']} -> status={s['status']}\n")
            out.write(f"    Summary: {s['summary']}\n")

        decision = conn.execute("SELECT * FROM decisions WHERE run_id=?", (run['run_id'],)).fetchone()
        if decision:
            out.write(f"\nDECISION: {decision['decision']} confidence={decision['confidence']}\n")
            out.write(f"  Passed criteria: {decision['passed_criteria']}\n")
            out.write(f"  Failed criteria: {decision['failed_criteria']}\n")
            out.write(f"  Blocking issues: {decision['blocking_issues']}\n")
    else:
        out.write("Run not found\n")

print("Wrote inspect_output.txt")
