import sys
sys.path.insert(0, 'src')
import asyncio, json, os
from pathlib import Path
from flux.settings import get_settings
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace
from flux.api.app import inspect_folder
from flux.providers.gapgpt import GapGPTAdapter
from flux.engine.orchestrator import FluxEngine

settings = get_settings()

db_path = Path(os.environ['LOCALAPPDATA']) / 'FluxDemo' / 'flux.db'
conn = init_db(db_path)
repo = Repository(conn)
workspace = Workspace(repo)
provider = GapGPTAdapter(api_key=settings.gapgpt_api_key)
engine = FluxEngine(repo, provider)

proj = workspace.get_project('proj_acd3bf5499f5')
if not proj:
    proj = workspace.create_project('Ageis', r'D:\project\Ageis-2-main', 'پروژه تست')

folder_info = inspect_folder(proj['path'])
files = [e['name'] for e in folder_info.get('entries', [])] if folder_info.get('exists') else []
print(f"Project: {proj['name']}, Path: {proj['path']}, Files found: {len(files)}")

context = []
if files:
    context.append({
        'ref': f"folder:{proj['path']}",
        'title': f"پوشهٔ کاری {proj['name']}",
        'content': f"Project: {proj['name']}\nFolder: {proj['path']}\nFiles ({len(files)}): {', '.join(files[:50])}"
    })

task_payload = {
    'task_id': 'run_ageis_live_' + os.urandom(4).hex(),
    'root_id': 'root_ageis_live',
    'project_id': proj['id'],
    'human_owner': 'Me',
    'objective': 'بررسی کن این پروژه رو و مشکلاتش رو بگو',
    'scope': ['بررسی ساختار، معماری و اعلام اشکالات پروژه Ageis'],
    'out_of_scope': ['تغییرات خارج از محدودهٔ تعریف‌شده'],
    'acceptance_criteria': ['تحلیل ساختاری و فنی پروژه و ارائهٔ گزارش جامع اشکالات'],
    'dependencies': [],
    'allowed_tools': [],
    'allowed_paths': [proj['path']],
    'artifact_refs': [],
    'budget_cap_usd': 0.5,
    'context': context,
    'workflow': 'team',
    'priority': 'P2',
    'data_class': 'internal'
}

run_id, _ = engine.submit_run(task_payload)
print('Submitted Ageis test run:', run_id)

async def main():
    print('Executing run across 5 agents...')
    result = await engine.execute_run(run_id)
    with open('ageis_test_result.txt', 'w', encoding='utf-8') as out:
        out.write(f"STATUS: {result.status}\n")
        out.write(f"SUMMARY: {result.summary}\n")
        out.write(f"BUDGET REMAINING: {result.budget_remaining_usd}\n\n")
        
        events = repo.get_events(run_id)
        out.write("EVENTS:\n")
        for ev in events:
            out.write(f"  {ev['sequence']}: {ev['from_state']} -> {ev['to_state']} | {ev['reason']}\n")
            
        subtasks = repo.get_subtasks(run_id)
        out.write("\nSUBTASKS:\n")
        for st in subtasks:
            out.write(f"  [{st['assigned_agent']}] {st['subtask_id']}: status={st['status']}\n")
            out.write(f"  Summary: {st['summary']}\n")
            if st.get('output'):
                out.write(f"  Output length: {len(str(st['output']))}\n")

    print('Execution complete! STATUS:', result.status)
    print('Wrote ageis_test_result.txt')

asyncio.run(main())
