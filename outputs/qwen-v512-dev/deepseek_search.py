"""Bounded DeepSeek Search/Fetch evidence; never calls a chat model."""
import ctypes
import hashlib
import ipaddress
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from persistent_rate import acquire as acquire_rate

HERE = Path(__file__).resolve().parent
BASE = 'https://api.deepseek.com/v1/tools/'
MAX_RESPONSE = 2_000_000


def load_key():
    key = os.environ.get('DEEPSEEK_API_KEY', '').strip()
    if key:
        return key
    encrypted = HERE.parents[1] / '.local/deepseek-api-key.dpapi'
    if os.name != 'nt' or not encrypted.exists():
        raise RuntimeError('DeepSeek credential unavailable; configure DEEPSEEK_API_KEY')
    class Blob(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    raw = encrypted.read_bytes()
    buffer = ctypes.create_string_buffer(raw)
    incoming = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    crypt.CryptUnprotectData.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    crypt.CryptUnprotectData.restype = ctypes.c_int
    if not crypt.CryptUnprotectData(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)):
        raise RuntimeError('Cannot decrypt DeepSeek credential for this Windows user')
    kernel = ctypes.WinDLL('kernel32')
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        key = ctypes.string_at(outgoing.data, outgoing.size).decode('utf-8').strip()
    finally:
        ctypes.memset(outgoing.data, 0, outgoing.size)
        kernel.LocalFree(ctypes.cast(outgoing.data, ctypes.c_void_p))
    if not key:
        raise RuntimeError('Empty DeepSeek credential')
    return key


class APIError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__(f'DeepSeek HTTP {status}')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError('Authenticated API redirects are disabled')


def public_url(url):
    if not isinstance(url, str) or len(url) > 8192:
        raise ValueError('Invalid evidence URL')
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    if parsed.scheme not in ('http', 'https') or not host or parsed.username or parsed.password:
        raise ValueError('Invalid evidence URL')
    if host.lower().rstrip('.').endswith(('.localhost', '.local', '.internal')) or host.lower().rstrip('.') == 'localhost':
        raise ValueError('Non-public evidence host')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError('Non-public evidence address')
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ''))


def decode_response(raw):
    if len(raw) > MAX_RESPONSE:
        raise ValueError('DeepSeek response exceeds byte limit')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('DeepSeek returned invalid JSON shape')
    return result


def documents(results, query):
    docs = []
    for result in results[:3]:
        if not isinstance(result, dict):
            continue
        try:
            url = public_url(result.get('url'))
        except ValueError:
            continue
        body = result.get('content')
        if not isinstance(body, str) or not body.strip():
            continue
        body = body[:100_000]
        excerpts = [body[:1800]]
        for match in list(re.finditer(r'出生|诞生|全长|总长|公里|首都|频率|光速|born|birth|located|Jersey', body, re.I))[:8]:
            part = body[max(0, match.start() - 100):match.end() + 280]
            if part not in excerpts:
                excerpts.append(part)
        docs.append({
            'id': 'web-' + hashlib.sha256(url.encode()).hexdigest()[:16],
            'title': str(result.get('title') or '')[:250], 'url': url,
            'text': '\n'.join(excerpts)[:4200], 'full_text': body,
            'text_sha256': hashlib.sha256(body.encode()).hexdigest(),
            'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'source_kind': 'external_webpage_unclassified',
            'provider': 'deepseek_search_fetch', 'query': query,
            'provider_authority': result.get('authority'),
            'provider_rerank_score': result.get('rerank_score'),
            'page_date': result.get('date'),
            'note': 'Provider scores do not verify a claim; source semantics require checking.'
        })
    return docs


class RateGate:
    """Reserve request start slots across gateway worker processes."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def acquire(self, endpoint, deadline):
        acquire_rate(self.path,endpoint,.5,deadline)


class Client:
    def __init__(self, key=None, state=None):
        self.key = key if key is not None else load_key()
        self.state = Path(state) if state is not None else HERE / '.local'
        self.cache = self.state / 'deepseek-cache'
        self.cache.mkdir(parents=True, exist_ok=True)
        self.gate = RateGate(self.state / 'retrieval-rate.sqlite')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies()), NoRedirect())

    def request(self, endpoint, body, deadline):
        if endpoint not in ('search', 'fetch'):
            raise ValueError('Only Search and Fetch endpoints are allowed')
        canonical = json.dumps(body, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256((endpoint + canonical).encode()).hexdigest()
        path = self.cache / (digest + '.json')
        if path.exists():
            cached = json.loads(path.read_text(encoding='utf-8'))
            if time.time() - cached['fetched_epoch'] < 86400:
                return cached['response']
        for attempt in range(2):
            self.gate.acquire(endpoint, deadline)
            remaining = deadline - time.monotonic()
            if remaining < .1:
                raise TimeoutError('Retrieval deadline before HTTP request')
            request = urllib.request.Request(BASE + endpoint, data=canonical.encode(), headers={
                'Authorization': 'Bearer ' + self.key,
                'Content-Type': 'application/json', 'Accept': 'application/json',
            })
            started = time.monotonic()
            status = 'transport_error'
            try:
                with self.opener.open(request, timeout=min(7, remaining)) as response:
                    status = response.status
                    raw = response.read(MAX_RESPONSE + 1)
                if time.monotonic() >= deadline:
                    raise TimeoutError('Retrieval deadline while reading response')
                result = decode_response(raw)
                temporary = path.with_suffix('.' + str(os.getpid()) + '.tmp')
                temporary.write_text(json.dumps({'fetched_epoch': time.time(), 'endpoint': BASE + endpoint, 'parameters': body, 'response': result}, ensure_ascii=False), encoding='utf-8')
                os.replace(temporary, path)
                return result
            except urllib.error.HTTPError as error:
                status = error.code
                try:
                    wait = min(max(float(error.headers.get('Retry-After', '0.5')), .25), 2)
                except (TypeError, ValueError):
                    wait = .5
                error.close()
                if attempt == 0 and status in (408, 429, 500, 502, 503, 504) and deadline - time.monotonic() > wait + 1:
                    time.sleep(wait)
                    continue
                raise APIError(status) from None
            except urllib.error.URLError:
                raise RuntimeError('DeepSeek transport error') from None
            finally:
                record = {'endpoint': endpoint, 'request_sha256': digest, 'status': status,
                          'seconds': round(time.monotonic() - started, 3),
                          'retrieved_at': datetime.now(timezone.utc).isoformat()}
                with (self.state / 'search-metrics.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(record) + '\n')

    def fetch(self, url, deadline):
        url = public_url(url)
        result = self.request('fetch', {'url': url}, deadline)
        return {'url': url, 'title': result.get('title', ''), 'content': result.get('content', '')}

    def retrieve(self, queries, deadline):
        docs, errors, seen = [], [], set()
        used_fetch = False
        queries = list(dict.fromkeys(q.strip()[:128] for q in queries if isinstance(q, str) and q.strip()))[:2]
        for query in queries:
            if time.monotonic() + .1 >= deadline:
                errors.append({'query': query, 'error': 'retrieval_deadline'})
                break
            try:
                result = self.request('search', {'query': query, 'count': 3, 'need_content': True}, deadline)
                results = result.get('results')
                if not isinstance(results, list):
                    raise ValueError('Invalid search results shape')
                if not results:
                    errors.append({'query': query, 'error': 'empty_search_results'})
                    continue
                found = documents(results, query)
                if not found and not used_fetch:
                    for candidate in results[:3]:
                        try:
                            url = public_url(candidate.get('url'))
                        except (ValueError, AttributeError):
                            continue
                        used_fetch = True
                        found = documents([self.fetch(url, deadline)], query)
                        break
                if not found:
                    errors.append({'query': query, 'error': 'no_page_body_available'})
                for doc in found:
                    if doc['id'] not in seen:
                        docs.append(doc)
                        seen.add(doc['id'])
            except Exception as error:
                # Never persist server bodies, auth headers or credential values.
                detail = str(error) if isinstance(error, (APIError, TimeoutError)) else type(error).__name__
                errors.append({'query': query, 'error': detail})
        return docs, errors
