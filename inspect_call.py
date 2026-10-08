import sqlite3, os, json
from pathlib import Path

db_path = Path(os.environ['LOCALAPPDATA']) / 'FluxDemo' / 'flux.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

call = conn.execute("SELECT * FROM agent_calls WHERE call_id='call_dabc73f45029'").fetchone()
if call:
    print('Call status:', call['status'])
    print('Call err:', call['error_message'])
    print('Call prompt_hash:', call['prompt_hash'])

res = conn.execute("SELECT * FROM budget_reservations WHERE call_id='call_dabc73f45029'").fetchone()
if res:
    print('Reservation status:', res['status'])
    print('Reserved amount:', res['reserved_amount_usd'])

# Also let's check subtasks for that run
subtasks = conn.execute("SELECT * FROM subtasks WHERE run_id='run_d01a439e54fc'").fetchall()
for s in subtasks:
    print(f"Subtask {s['subtask_id']} ({s['assigned_agent']}): status={s['status']}")
    if s['assigned_agent'] == 'opus':
        print(f"  Opus output length: {len(s['output'] or '')}")
        with open('opus_subtask_output.txt', 'w', encoding='utf-8') as f:
            f.write(s['output'] or '')
