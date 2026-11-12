import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path


class DeepSeekTests(unittest.TestCase):
    def client_module(self):
        self.assertIsNotNone(importlib.util.find_spec('deepseek_search'), 'DeepSeek evidence client is not implemented')
        import deepseek_search
        return deepseek_search

    def test_source_body_not_generated_summary(self):
        m = self.client_module()
        page = {'title': 'Title', 'url': 'https://example.org/page#fragment', 'content': 'Source body states 123.', 'summary': 'Generated summary says 999.', 'authority': 4}
        docs = m.documents([page], 'query')
        self.assertEqual(len(docs), 1)
        self.assertIn('123', docs[0]['text'])
        self.assertNotIn('999', docs[0]['text'])
        self.assertEqual(docs[0]['url'], 'https://example.org/page')
        self.assertEqual(docs[0]['source_kind'], 'external_webpage_unclassified')
        self.assertTrue(docs[0]['text_sha256'])
        self.assertEqual(m.documents([{**page, 'content': ''}], 'query'), [])

    def test_untrusted_urls_rejected(self):
        m = self.client_module()
        for url in ['file:///secret', 'http://127.0.0.1/a', 'http://localhost/a', 'http://169.254.169.254/', 'https://user:password@example.org/a', 'http://[::1]/']:
            with self.assertRaises(ValueError):
                m.public_url(url)

    def test_source_excerpt_and_response_bounded(self):
        m = self.client_module()
        doc = m.documents([{'url': 'https://example.org/a', 'title': 'title', 'content': 'a' * 10000 + ' born in City Z.'}], 'query')[0]
        self.assertLessEqual(len(doc['text']), 4200)
        self.assertIn('City Z', doc['text'])
        with self.assertRaises(ValueError):
            m.decode_response(b' ' * (m.MAX_RESPONSE + 1))

    def test_empty_and_auth_error_are_visible(self):
        m = self.client_module()
        class Fake(m.Client):
            def request(self, endpoint, body, deadline):
                return {'results': []}
        with tempfile.TemporaryDirectory() as directory:
            docs, errors = Fake(key='unit-test-token', state=Path(directory)).retrieve(['example'], time.monotonic() + 2)
        self.assertEqual(docs, [])
        self.assertEqual(errors[0]['error'], 'empty_search_results')
        err = m.APIError(401)
        self.assertEqual(str(err), 'DeepSeek HTTP 401')
        self.assertNotIn('Bearer', str(err))

    def test_cache_reuse_and_max_two_searches(self):
        m = self.client_module()
        class Response:
            status = 200
            def __init__(self, query):
                self.query = query
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self, limit):
                return json.dumps({'results': [{'url': 'https://example.org/' + self.query, 'title': self.query, 'content': 'Actual source text.'}]}).encode()
        class FakeOpener:
            calls = 0
            def open(self, request, timeout):
                self.calls += 1
                return Response(json.loads(request.data)['query'])
        with tempfile.TemporaryDirectory() as directory:
            c = m.Client(key='unit-test-token', state=Path(directory))
            c.opener = FakeOpener()
            docs, errors = c.retrieve(['a', 'b', 'c'], time.monotonic() + 2)
            self.assertEqual(c.opener.calls, 2)
            self.assertEqual(len(docs), 2)
            self.assertEqual(errors, [])
            c.retrieve(['a'], time.monotonic() + 2)
            self.assertEqual(c.opener.calls, 2)

    def test_summary_only_triggers_fetch_once(self):
        m = self.client_module()
        class Fake(m.Client):
            endpoints = []
            def request(self, endpoint, body, deadline):
                self.endpoints.append(endpoint)
                if endpoint == 'search':
                    return {'results': [{'url': 'https://example.org/a', 'title': 'title', 'summary': 'Not source evidence.'}]}
                return {'title': 'title', 'content': 'Fetched source body.'}
        with tempfile.TemporaryDirectory() as directory:
            c = Fake(key='unit-test-token', state=Path(directory))
            docs, errors = c.retrieve(['a', 'b'], time.monotonic() + 2)
            self.assertEqual(c.endpoints.count('fetch'), 1)
            self.assertEqual(len(docs), 1)
            self.assertIn('Fetched source body.', docs[0]['text'])

    def test_rate_wait_cannot_exceed_deadline(self):
        m = self.client_module()
        with tempfile.TemporaryDirectory() as directory:
            rate = m.RateGate(Path(directory) / 'rate.sqlite')
            rate.acquire('search', time.monotonic() + 2)
            with self.assertRaises(TimeoutError):
                rate.acquire('search', time.monotonic() + .02)

    def test_api_redirect_cannot_forward_credentials(self):
        m = self.client_module()
        self.assertTrue(hasattr(m, 'NoRedirect'), 'Authenticated API redirects must be disabled')
        handler = m.NoRedirect()
        with self.assertRaises(ValueError):
            handler.redirect_request(None, None, 302, 'redirect', {}, 'https://another.example/')

    def test_http_error_body_never_persists_secret(self):
        m = self.client_module()
        import io
        import urllib.error
        class FailingOpener:
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, 401, 'failure', {}, io.BytesIO(b'unit-test-token must not leak'))
        with tempfile.TemporaryDirectory() as directory:
            c = m.Client(key='unit-test-token', state=Path(directory))
            c.opener = FailingOpener()
            docs, errors = c.retrieve(['query'], time.monotonic() + 2)
            self.assertEqual(docs, [])
            self.assertEqual(errors[0]['error'], 'DeepSeek HTTP 401')
            for path in Path(directory).rglob('*.json*'):
                self.assertNotIn('unit-test-token', path.read_text())

    def test_rate_limit_is_shared_across_worker_processes(self):
        self.client_module()
        import subprocess
        import sys
        code = "import sys,time; from pathlib import Path; from deepseek_search import RateGate; RateGate(Path(sys.argv[1])).acquire('search',time.monotonic()+8); print(time.monotonic())"
        with tempfile.TemporaryDirectory() as directory:
            children = [subprocess.Popen([sys.executable, '-c', code, str(Path(directory)/'shared.sqlite')], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(4)]
            starts = []
            for child in children:
                output, error = child.communicate(timeout=10)
                self.assertEqual(child.returncode, 0, error)
                starts.append(float(output))
            starts.sort()
            self.assertTrue(all(right-left >= .45 for left,right in zip(starts,starts[1:])), starts)


if __name__ == '__main__':
    unittest.main()
