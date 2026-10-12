"""Evidence contracts and bounded adapter behavior; no external service calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'core/scripts'
sys.path.insert(0, str(SCRIPTS))
import notebooklm_research as engine
from research_contract import make_brief, parse_packet, validate_packet


def packet(kind='architecture'):
    return {
        'schema_version': 1, 'kind': kind,
        'questions': [{'id': 'Q1', 'status': 'answered', 'claim_ids': ['C1'], 'gap': ''}],
        'claims': [{'id': 'C1', 'text': 'A database choice depends on workload and operational constraints.',
                    'kind': 'reported', 'citations': ['1'], 'locator': 'Appropriate uses / concurrency',
                    'applicability': 'Single application deployment; verify concurrent writes.',
                    'counterevidence': 'A write-heavy distributed workload can require another design.'}],
        'options': [{'option': 'Retain the database pending measurement', 'tradeoff': 'Measure writer contention first.'}],
        'decision': {'recommendation': 'Do not infer scale solely from database name.', 'claim_ids': ['C1'],
                     'validation': 'Inspect topology and measure workload against the actual SLO.'},
        'limitations': ['No production measurements are provided.']}


def response(value=None, citations=None):
    return MagicMock(returncode=0, stdout=json.dumps({'answer': json.dumps(value or packet()),
                                                   'citations': citations if citations is not None else {'1': 'source-1'}}))


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.brief = make_brief('Assess database workload', 'architecture')

    def test_non_ui_qualitative_evidence_is_valid_but_not_truth_checked(self):
        self.assertEqual(validate_packet(packet(), {'1': 'source-1'}, self.brief), [])

    def test_persian_qualitative_evidence(self):
        value = packet()
        value['claims'][0]['text'] = 'انتخاب پایگاه داده به بار و نیاز عملیاتی وابسته است.'
        self.assertEqual(validate_packet(value, {'1': 'منبع-۱'}, self.brief), [])

    def test_decorative_keywords_do_not_establish_evidence(self):
        with self.assertRaises(ValueError):
            parse_packet('WCAG OKLCH 44px 7:1 layout source W3C [1]')

    def test_missing_source_mapping_is_rejected(self):
        self.assertTrue(validate_packet(packet(), {}, self.brief))

    def test_fabricated_citation_reference_is_rejected(self):
        value = packet()
        value['claims'][0]['citations'] = ['999']
        self.assertTrue(validate_packet(value, {'1': 'source-1'}, self.brief))

    def test_non_object_packet_reports_error(self):
        for value in ([], None, "text", 1):
            self.assertTrue(validate_packet(value, {}, self.brief))

    def test_citation_source_must_belong_to_selected_corpus(self):
        self.assertTrue(validate_packet(packet(), {'1': 'outside'}, self.brief, ['source-1']))
        self.assertEqual(validate_packet(packet(), {'1': 'source-1'}, self.brief, ['source-1']), [])

    def test_wrong_task_kind_is_rejected(self):
        self.assertTrue(validate_packet(packet('ui'), {'1': 'source-1'}, self.brief))

    def test_dangling_claim_reference_is_rejected(self):
        value = packet()
        value['decision']['claim_ids'] = ['not-present']
        self.assertTrue(validate_packet(value, {'1': 'source-1'}, self.brief))

    def test_question_omission_or_duplication_is_rejected(self):
        for questions in ([], [packet()['questions'][0]] * 2):
            value = packet()
            value['questions'] = questions
            self.assertTrue(validate_packet(value, {'1': 'source-1'}, self.brief))

    def test_honest_no_evidence_is_valid_unanswered_packet(self):
        value = packet()
        value['claims'] = []
        value['questions'] = [{'id': 'Q1', 'status': 'unanswered', 'claim_ids': [], 'gap': 'No applicable sources'}]
        value['options'] = []
        value['decision']['claim_ids'] = []
        value['decision']['recommendation'] = 'Defer until evidence is available.'
        self.assertEqual(validate_packet(value, {}, self.brief), [])
        value['questions'][0]['gap'] = ''
        self.assertTrue(validate_packet(value, {}, self.brief))

    def test_malformed_nested_values_fail_without_crash(self):
        for key, value in [('claims', [None]), ('questions', [None]), ('decision', []), ('limitations', 12), ('options', {})]:
            bad = packet()
            bad[key] = value
            self.assertTrue(validate_packet(bad, {'1': 'source-1'}, self.brief))

    def test_brief_allowlist_excludes_private_metadata(self):
        brief = make_brief('Public query', supplied={'private_code': 'SECRET', 'questions': [
            {'id': 'Q1', 'question': 'Public question', 'private_notes': 'SECRET'}]})
        self.assertNotIn('private_code', brief)
        self.assertNotIn('private_notes', brief['questions'][0])
        with self.assertRaises(ValueError):
            make_brief('task', supplied={'questions': [{'id': 'Q', 'question': 'a'}, {'id': 'Q', 'question': 'b'}]})

    def test_artifact_intent_precedes_technology_cues(self):
        brief, prompt = engine.prepare_research('رزومه CTO با پروژه SQLite و رابط کاربری')
        self.assertEqual(brief['kind'], 'professional-content')
        self.assertNotIn('Color Engine', prompt)

    def test_explicit_kind_wins(self):
        brief, _ = engine.prepare_research('portfolio system architecture', kind='backend')
        self.assertEqual(brief['kind'], 'backend')

    def test_default_does_not_read_project_context(self):
        with patch.object(engine, 'extract_codebase_context') as extract:
            engine.prepare_research('Review target audience', project_dir='/private-project')
            extract.assert_not_called()

    def test_project_hints_do_not_leak_paths_or_tokens_into_backend(self):
        context = {'domain': 'service', 'framework': 'Python', 'project_path': '/SECRET',
                   'existing_tokens': ['--private-customer'], 'color_model': 'OKLCH'}
        prompt = engine.build_code_aware_prompt('API integrity', context)
        self.assertNotIn('/SECRET', prompt)
        self.assertNotIn('--private-customer', prompt)
        self.assertNotIn('OKLCH', prompt)

    def test_plan_cli_runs_without_nlm_or_network(self):
        proc = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'notebooklm_research.py'),
                               'plan', 'رزومه برای CTO', '--kind', 'professional-content'],
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        output = json.loads(proc.stdout)
        self.assertEqual(output['external_calls'], 0)
        self.assertEqual(output['brief']['kind'], 'professional-content')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.auth = patch.object(engine, 'check_auth_status', return_value={'authenticated': True})
        self.auth.start()
        self.addCleanup(self.auth.stop)
        self.inventory = MagicMock(returncode=0, stdout='[{"id":"source-1","url":"https://www.sqlite.org/whentouse.html"}]')

    def test_discovery_pending_never_counts_as_findings(self):
        with patch.object(engine, 'run_nlm_command', return_value=MagicMock(returncode=0, stdout='Notebook ID: nb\nTask ID: task')) as run:
            result = engine.execute_research_pipeline('architecture')
        self.assertFalse(result['success'])
        self.assertTrue(result['pending'])
        self.assertEqual(result['task_id'], 'task')
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('--auto-import', run.call_args.args[0])

    def test_resume_no_import_or_new_notebook_and_selected_sources(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[self.inventory, response()]) as run:
            result = engine.execute_research_pipeline('architecture', notebook_id='existing', source_ids=['source-1'])
        self.assertEqual(result['status'], 'packet_valid')
        self.assertTrue(result['success'])
        self.assertFalse(result['research_verified'])
        calls = [c.args[0] for c in run.call_args_list]
        self.assertFalse(any(c[:2] == ['research', 'start'] for c in calls))
        self.assertIn('--source-ids', calls[-1])
        self.assertIn('--new-conversation', calls[-1])

    def test_query_rejects_citations_outside_inventory(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[self.inventory, response(citations={'1': 'outside'})]):
            result = engine.execute_research_pipeline('architecture', notebook_id='nb', max_retries=0)
        self.assertEqual(result['status'], 'invalid_packet')

    def test_unknown_selected_source_stops_before_query(self):
        with patch.object(engine, 'run_nlm_command', return_value=self.inventory) as run:
            result = engine.execute_research_pipeline('architecture', notebook_id='nb', source_ids=['outside'])
        self.assertEqual(result['status'], 'invalid_source_selection')
        self.assertEqual(run.call_count, 1)

    def test_selection_remains_enforced_when_inventory_unavailable(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[MagicMock(returncode=1, stdout=''), response(citations={'1': 'outside'})]):
            result = engine.execute_research_pipeline('architecture', notebook_id='nb', source_ids=['source-1'], max_retries=0)
        self.assertEqual(result['status'], 'invalid_packet')

    def test_repair_reuses_notebook_and_preserves_kind(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[
            MagicMock(returncode=0, stdout='Notebook ID: nb'), self.inventory,
            MagicMock(returncode=0, stdout='progress'), response()]) as run:
            result = engine.execute_research_pipeline('architecture', import_sources=True)
        self.assertTrue(result['success'])
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(sum(c.args[0][:2] == ['research', 'start'] for c in run.call_args_list), 1)
        self.assertEqual(result['brief']['kind'], 'architecture')
        self.assertNotIn('ergonomic layout', run.call_args.args[0][3])

    def test_invalid_query_budget_is_bounded(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[self.inventory,
            MagicMock(returncode=0, stdout='{}'), MagicMock(returncode=0, stdout='{}')]) as run:
            result = engine.execute_research_pipeline('architecture', notebook_id='nb')
        self.assertFalse(result['success'])
        self.assertEqual(result['attempts'], 2)
        self.assertEqual(run.call_count, 3)

    def test_timeout_preserves_partial_ids_and_does_not_retry_start(self):
        error = subprocess.TimeoutExpired('nlm', 900, output=b'Notebook ID: nb\nTask ID: task')
        with patch.object(engine, 'run_nlm_command', side_effect=error) as run:
            result = engine.execute_research_pipeline('architecture', import_sources=True)
        self.assertTrue(result['pending'])
        self.assertEqual(result['notebook_id'], 'nb')
        self.assertEqual(result['task_id'], 'task')
        self.assertEqual(run.call_count, 1)

    def test_missing_citations_never_pass(self):
        with patch.object(engine, 'run_nlm_command', side_effect=[self.inventory, response(citations={})]):
            result = engine.execute_research_pipeline('architecture', notebook_id='nb', max_retries=0)
        self.assertFalse(result['success'])

    def test_challenge_does_not_mutate_or_verify_original(self):
        original = {'status': 'packet_valid', 'brief': make_brief('architecture'), 'packet': packet()}
        before = copy.deepcopy(original)
        with patch.object(engine, 'run_nlm_command', return_value=MagicMock(returncode=0, stdout='{"answer":"Check writer contention [1]","citations":{"1":"source-1"}}')):
            result = engine.challenge_packet('nb', original)
        self.assertEqual(original, before)
        self.assertFalse(result['research_verified'])
        self.assertEqual(result['status'], 'challenge_received')

    def test_challenge_preserves_selection_and_rejects_wrong_notebook(self):
        saved = {'status': 'packet_valid', 'notebook_id': 'nb', 'selected_source_ids': ['source-1'],
                 'brief': make_brief('architecture'), 'packet': packet()}
        with patch.object(engine, 'query_packet', return_value=MagicMock(returncode=0, stdout='{"answer":"critique"}')) as query:
            engine.challenge_packet('nb', saved)
            self.assertEqual(query.call_args.args[2], ['source-1'])
            with self.assertRaises(ValueError):
                engine.challenge_packet('other', saved)
            self.assertEqual(query.call_count, 1)

    def test_save_does_not_overwrite_previous_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = engine.save_research({'success': False}, tmp)
            b = engine.save_research({'success': True}, tmp)
            self.assertNotEqual(a, b)
            self.assertFalse(json.loads(a.read_text())['success'])


if __name__ == '__main__':
    unittest.main()
