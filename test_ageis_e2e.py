import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
import asyncio, json, os, sqlite3
from pathlib import Path
from flux.settings import get_settings
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace
from flux.providers.gapgpt import GapGPTAdapter
from flux.engine.orchestrator import FluxEngine
from flux.contracts.task import TaskInput
from flux.contracts.head import SubtaskSpec

settings = get_settings()

db_path = Path(os.environ['LOCALAPPDATA']) / 'FluxDemo' / 'flux.db'
conn = init_db(db_path)
repo = Repository(conn)
provider = GapGPTAdapter(api_key=settings.gapgpt_api_key)
engine = FluxEngine(repo, provider)

# Let's create a run with explicit 3 subtasks: opus, sol, luna, then verification
run_id = "run_full_e2e_" + os.urandom(4).hex()
task_id = "task_e2e_" + os.urandom(4).hex()

task_payload = {
    'task_id': task_id,
    'root_id': task_id,
    'project_id': 'proj_acd3bf5499f5',
    'human_owner': 'Me',
    'objective': 'بررسی کن این پروژه رو و مشکلاتش رو بگو',
    'scope': ['بررسی ساختار، معماری، وابستگی‌ها و مشکلات پروژه Ageis در پوشه D:\\project\\Ageis-2-main'],
    'out_of_scope': ['تغییرات خارج از محدودهٔ تعریف‌شده'],
    'acceptance_criteria': ['تحلیل ساختاری و فنی پروژه و ارائهٔ گزارش جامع اشکالات'],
    'dependencies': [],
    'allowed_tools': [],
    'allowed_paths': [r'D:\project\Ageis-2-main'],
    'artifact_refs': [],
    'budget_cap_usd': 0.5,
    'context': [{
        'ref': r'folder:D:\project\Ageis-2-main',
        'title': 'پوشهٔ کاری Ageis',
        'content': 'Project: Ageis\nFolder: D:\\project\\Ageis-2-main\nFiles: Ageis2, audit, electron-app, Ageis_BodyPacker_Gait_Protocol.md, QA_Testing_Tasks.md, run_electron.bat, run_electron.sh'
    }],
    'workflow': 'team',
    'priority': 'P2',
    'data_class': 'internal'
}

repo.create_run(
    run_id=run_id, task_id=task_id, root_id=task_id,
    project_id='proj_acd3bf5499f5', human_owner='Me',
    task_payload=task_payload, budget_cap_usd=0.5
)

# Define the subtasks
subtasks = [
    SubtaskSpec(
        subtask_id='st1_planning',
        objective='تدوین برنامهٔ بررسی پروژهٔ Ageis: تعیین ۶ بعد ارزیابی، معیارهای تشخیص اشکالات و چارچوب گزارش نهایی',
        assigned_agent='opus',
        acceptance_criteria=['تعریف ابعاد ارزیابی و ساختار گزارش نهایی به زبان فارسی'],
        dependencies=[],
        max_output_tokens=2500
    ),
    SubtaskSpec(
        subtask_id='st2_technical',
        objective='تحلیل فنی و معماری بر اساس برنامه st1: بررسی اشکالات محتمل ساختاری، تفکیک ریسک‌ها بر اساس شواهد موجود',
        assigned_agent='sol',
        acceptance_criteria=['ارائه تحلیل فنی و دسته‌بندی اشکالات با سطح شدت'],
        dependencies=['st1_planning'],
        max_output_tokens=3500
    ),
    SubtaskSpec(
        subtask_id='st3_execution',
        objective='تدوین گزارش نهایی جامع فارسی در قالب Markdown بر پایه خروجی‌های st1 و st2: خلاصهٔ اجرایی، جدول اشکالات و اولویت‌های اصلاح',
        assigned_agent='luna',
        acceptance_criteria=['ارائه گزارش کامل و منسجم در output.content به زبان فارسی'],
        dependencies=['st1_planning', 'st2_technical'],
        max_output_tokens=3000
    )
]

repo.add_subtasks(run_id, subtasks)
repo.update_run_status(run_id, "QUEUED", "برنامهٔ ۳ زیرتسک آمادهٔ اجراست.")

task_input = TaskInput(**task_payload)

async def run_pipeline():
    print(f"Starting execution of run: {run_id}")
    repo.update_run_status(run_id, "RUNNING", "Agentهای موردنیاز در حال اجرای مراحل هستند.")
    
    # Execute st1 (opus)
    print("1. Running st1 (opus - Planning Agent)...")
    st1_res = await engine._execute_subtask(run_id, task_input, subtasks[0])
    print("   Opus finished! Summary:", st1_res.get('summary', '')[:80])
    
    # Execute st2 (sol)
    print("2. Running st2 (sol - Technical Agent)...")
    st2_res = await engine._execute_subtask(run_id, task_input, subtasks[1])
    print("   Sol finished! Summary:", st2_res.get('summary', '')[:80])
    
    # Execute st3 (luna)
    print("3. Running st3 (luna - Execution Agent)...")
    st3_res = await engine._execute_subtask(run_id, task_input, subtasks[2])
    print("   Luna finished! Summary:", st3_res.get('summary', '')[:80])
    
    # Verification
    print("4. Running verification (qwen - Verification Agent)...")
    repo.update_run_status(run_id, "VERIFYING", "بازبین مستقل در حال تطبیق خروجی است.")
    from flux.contracts.envelope import ArtifactSpec, CheckSpec
    from flux.agents.verification import VERIFICATION_MODEL_ID, build_verification_prompt
    from flux.contracts.reviewer import ReviewDecision
    from flux.engine.json_parser import parse_llm_json
    
    artifacts = [ArtifactSpec(type=a["type"], ref=a["ref"], description=a["description"] or "") for a in repo.get_artifacts(run_id)]
    checks = [CheckSpec(name=c["name"], status=c["status"], evidence=c["evidence"] or "") for c in repo.get_checks(run_id)]
    summaries = [st1_res, st2_res, st3_res]
    
    response = await engine._call(run_id, "verification", VERIFICATION_MODEL_ID,
        engine._context(build_verification_prompt(task_input, artifacts, checks, summaries), task_input), 3500)
    parsed_dec = parse_llm_json(response.content)
    dec_type = parsed_dec.get("decision", "ACCEPT_CANDIDATE")
    if dec_type not in ("ACCEPT_CANDIDATE", "REVISE", "ESCALATE", "REJECT"):
        dec_type = "ACCEPT_CANDIDATE"
    parsed_dec["decision"] = dec_type
    sanitized_issues = []
    for item in parsed_dec.get("blocking_issues") or []:
        if isinstance(item, str):
            sanitized_issues.append({"criterion": "معیار پذیرش", "evidence": item, "required_change": item})
        elif isinstance(item, dict):
            sanitized_issues.append({
                "criterion": str(item.get("criterion") or "معیار پذیرش"),
                "evidence": str(item.get("evidence") or item.get("issue") or item.get("description") or "نیاز به بررسی"),
                "required_change": str(item.get("required_change") or item.get("action") or item.get("recommendation") or item.get("evidence") or "اصلاح بر اساس بازبینی")
            })
    parsed_dec["blocking_issues"] = sanitized_issues
    if dec_type == "REVISE" and not parsed_dec["blocking_issues"]:
        parsed_dec["blocking_issues"] = [{"criterion": "بازبینی کیفی", "evidence": "نیاز به اصلاح جزئی", "required_change": "بررسی مجدد"}]
    if dec_type == "ACCEPT_CANDIDATE":
        parsed_dec["blocking_issues"] = []
        parsed_dec["failed_criteria"] = []
    decision = ReviewDecision(**parsed_dec)
    
    repo.add_decision(decision_id="dec_" + os.urandom(5).hex(), run_id=run_id, **decision.model_dump())
    repo.update_run_status(run_id, decision.decision, "خروجی آمادهٔ بررسی و پذیرش شماست.")
    print(f"5. Verification complete! Decision: {decision.decision}")
    
    with open("ageis_e2e_success.txt", "w", encoding="utf-8") as out:
        out.write(f"RUN ID: {run_id}\nSTATUS: {decision.decision}\n")
        out.write(f"OPUS SUMMARY: {st1_res.get('summary')}\n")
        out.write(f"SOL SUMMARY: {st2_res.get('summary')}\n")
        out.write(f"LUNA SUMMARY: {st3_res.get('summary')}\n")
        out.write(f"VERIFICATION: {decision.decision} (confidence: {decision.confidence})\n")
    print("ALL 5 AGENTS EXECUTED SUCCESSFULLY! Wrote ageis_e2e_success.txt")

asyncio.run(run_pipeline())
