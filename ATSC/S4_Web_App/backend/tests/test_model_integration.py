import asyncio
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from app.main import app
from app.model_results import PublishedRun
from pydantic import ValidationError

EXAMPLE = Path(__file__).resolve().parents[2] / 'docs' / 'example-model-run.json'


async def get(url):
    parsed = urlsplit(url)
    messages = []
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'scheme': 'http', 'path': parsed.path, 'raw_path': parsed.path.encode(), 'query_string': parsed.query.encode(), 'headers': [], 'server': ('testserver', 80), 'client': ('testclient', 123)}
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        messages.append(message)
    await app(scope, receive, send)
    status = next(message['status'] for message in messages if message['type'] == 'http.response.start')
    body = b''.join(message.get('body', b'') for message in messages if message['type'] == 'http.response.body')
    return status, json.loads(body)


class ModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {'ATSC_MODEL_RESULTS_DIR': self.directory.name})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.example = json.loads(EXAMPLE.read_text())

    def publish(self, value=None, name='run.json'):
        Path(self.directory.name, name).write_text(json.dumps(value or self.example))

    def request(self, path):
        return asyncio.run(get('/api/v1/' + path))

    def test_empty_install_returns_no_invented_results(self):
        self.assertEqual(self.request('runs'), (200, []))
        self.assertEqual(self.request('sites?run_id=missing')[0], 404)

    def test_valid_run_sites_and_explicit_zero_and_false(self):
        self.publish()
        status, runs = self.request('runs')
        self.assertEqual(status, 200)
        self.assertTrue(runs[0]['is_demo'])
        self.assertEqual(runs[0]['site_count'], 2)
        status, sites = self.request('sites?run_id=example-run-001&flagged=false')
        self.assertEqual(status, 200)
        self.assertEqual(len(sites['features']), 1)
        self.assertEqual(sites['features'][0]['properties']['fsi_rate'], 0)

    def test_run_and_site_isolation(self):
        self.publish()
        second = copy.deepcopy(self.example)
        second['run_id'] = 'second-run'
        second['sites'], second['memos'], second['backtest'] = [], {}, None
        self.publish(second, 'second.json')
        self.assertEqual(self.request('sites/example-site-1?run_id=second-run')[0], 404)
        self.assertEqual(self.request('sites/example-site-1/memo?run_id=second-run')[0], 404)
        self.assertEqual(self.request('backtest?run_id=second-run')[1]['status'], 'pending')

    def test_published_backtest_and_memo_and_missing_memo(self):
        self.publish()
        self.assertEqual(len(self.request('backtest?run_id=example-run-001')[1]['backtest']['methods']), 3)
        self.assertEqual(self.request('sites/example-site-1/memo?run_id=example-run-001')[1]['status'], 'published')
        self.assertEqual(self.request('sites/example-site-2/memo?run_id=example-run-001')[1]['status'], 'pending')

    def test_bad_new_file_preserves_valid_published_run(self):
        self.publish()
        Path(self.directory.name, 'broken.json').write_text('{bad json')
        with self.assertLogs('app.model_results', level='WARNING'):
            self.assertEqual(len(self.request('runs')[1]), 1)

    def test_only_invalid_files_returns_structured_error(self):
        Path(self.directory.name, 'broken.json').write_text('{}')
        with self.assertLogs('app.model_results', level='WARNING'):
            status, body = self.request('runs')
        self.assertEqual(status, 503)
        self.assertEqual(body['error'], 'invalid_model_output')

    def test_required_run_and_invalid_bbox(self):
        self.publish()
        self.assertEqual(self.request('sites')[0], 422)
        self.assertEqual(self.request('sites?run_id=example-run-001&bbox=nan,0,1,2')[0], 422)
        self.assertEqual(self.request('sites?run_id=example-run-001&bbox=0,0,1,1')[1]['features'], [])

    def test_rejects_bad_model_data(self):
        for mutation in ['negative_risk', 'duplicate_sites', 'duplicate_mapping', 'bad_coordinates', 'ungrounded_memo', 'invalid_interval']:
            with self.subTest(mutation=mutation):
                run = copy.deepcopy(self.example)
                if mutation == 'negative_risk': run['sites'][0]['properties']['fsi_rate'] = -1
                if mutation == 'duplicate_sites': run['sites'].append(copy.deepcopy(run['sites'][0]))
                if mutation == 'duplicate_mapping': run['sites'][1]['properties']['map_segment_id'] = run['sites'][0]['properties']['map_segment_id']
                if mutation == 'bad_coordinates': run['sites'][0]['geometry']['coordinates'][0] = [1000, 1000]
                if mutation == 'ungrounded_memo': run['memos']['example-site-1']['grounding_passed'] = False
                if mutation == 'invalid_interval': run['backtest']['methods'][0]['confidence_interval'] = [0.9, 0.2]
                with self.assertRaises(ValidationError): PublishedRun.model_validate(run)


if __name__ == '__main__':
    unittest.main()
