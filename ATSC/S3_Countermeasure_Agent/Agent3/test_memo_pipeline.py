import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import memo_pipeline as m


class MemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        site = json.loads((m.ROOT / 'example_sites.json').read_text())[0]
        cls.ev = m.match_site(site, m.load_library(m.ROOT / 'fixtures' / 'countermeasure_library_2026-11-03.csv'))

    def setUp(self):
        self.draft = m.offline_draft(self.ev)

    def test_valid_offline_contract(self):
        self.assertEqual(m.validate(self.draft, self.ev), [])

    def test_tampered_responses_blocked(self):
        # Independent seeded failure cases for contract enforcement, not a semantic benchmark.
        bad = []
        def add(change):
            d = copy.deepcopy(self.draft)
            change(d)
            bad.append(d)
        add(lambda d: d.update(site_id='WRONG_SITE'))
        add(lambda d: d.update(cmf=0.1))
        add(lambda d: d.pop('site_summary'))
        add(lambda d: d['candidates'].pop())
        add(lambda d: d['candidates'].append(d['candidates'][0]))
        add(lambda d: d['candidates'].reverse())
        add(lambda d: d['candidates'][0].update(cm_id='CM999'))
        add(lambda d: d['candidates'].append(d['engineering_review'].pop()))
        add(lambda d: d['candidates'][0].update(cmf=0.1))
        add(lambda d: d['candidates'][0].update(source_url='https://wrong.example'))
        add(lambda d: d['candidates'][0].update(summary='Prevents 50% of crashes.'))
        add(lambda d: d['candidates'][0].update(summary='See https://wrong.example'))
        add(lambda d: d['candidates'][0].update(summary='Cost is $ten.'))
        add(lambda d: d['candidates'][0].update(summary='<script>bad</script>'))
        add(lambda d: d['candidates'][0].update(summary=''))
        add(lambda d: d['candidates'][0].update(summary='x' * 701))
        add(lambda d: d.update(site_summary=3))
        add(lambda d: d.update(engineering_review={}))
        add(lambda d: d['engineering_review'].__setitem__(0, 'bad'))
        add(lambda d: d.update(site_summary='The site had 20 crashes.'))
        self.assertEqual(len(bad), 20)
        for i, d in enumerate(bad):
            with self.subTest(case=i + 1):
                self.assertTrue(m.validate(d, self.ev))

    def test_all_evidence_and_references_preserved(self):
        memo = m.render(self.draft, self.ev, 'offline')
        for group in m.GROUPS:
            for row in self.ev[group]:
                for item in row['review_needed']:
                    self.assertIn(item, memo)
                for key in ['source_url', 'study_reference', 'limitations']:
                    self.assertIn(row['evidence'][key], memo)
        self.assertIn('Signalized site mapping is inferred', memo)

    def test_semantic_limit_is_explicit(self):
        self.draft['site_summary'] = 'This treatment will eliminate all crashes.'
        self.assertEqual(m.validate(self.draft, self.ev), [])
        self.assertIn('do not verify narrative claims', m.render(self.draft, self.ev, 'offline'))

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            m.parse_json('{"site_id":"a","site_id":"b"}')

    def test_missing_api_config_rejected(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ValueError):
                m.call_api(self.ev, 1, 60)

    def test_api_request_response_mock(self):
        class Reply:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self):
                return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {
                    'content': json.dumps(MemoTests.response)}}], 'usage': {'total_tokens': 100}}).encode()
        MemoTests.response = self.draft
        with patch.dict('os.environ', {'MEMO_API_URL': 'https://provider.example/v1/chat/completions',
                                      'MEMO_MODEL': 'gpt-4.1', 'MEMO_API_KEY': 'test-only'}):
            with patch('urllib.request.OpenerDirector.open', return_value=Reply()) as send:
                raw, log = m.call_api(self.ev, 1, 60)
                self.assertEqual(m.parse_json(raw), self.draft)
                body = json.loads(send.call_args.args[0].data)
                self.assertEqual(body['model'], 'gpt-4.1')
                self.assertIn('source_url', body['messages'][1]['content'])
                self.assertEqual(log['attempts'], 1)


if __name__ == '__main__':
    unittest.main()
