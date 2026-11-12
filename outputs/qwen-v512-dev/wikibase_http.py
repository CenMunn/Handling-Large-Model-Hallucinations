"""Read-only Wikibase transport with pooled TLS, gzip and per-entity caching.

The caller must impose a process-wide deadline: socket timeouts alone are not
an overall time limit. No SPARQL, retries, or third-party Python dependencies.
"""
import hashlib,http.client,json,os,re,sqlite3,ssl,time,urllib.parse,urllib.request,uuid,zlib
from datetime import datetime,timezone
from contextlib import closing
from pathlib import Path
from persistent_rate import acquire as acquire_rate
from access_gate import gate
from email.utils import parsedate_to_datetime

HERE=Path(__file__).resolve().parent
HOST='www.wikidata.org'
MAX_WIRE=2_000_000
MAX_BODY=4_000_000

class APIError(RuntimeError):
    def __init__(self,status):self.status=status;super().__init__('Wikibase HTTP '+str(status))

def retry_delay(value,now=None):
    now=time.time() if now is None else now
    try:return max(0,float(value))
    except (TypeError,ValueError):
        try:return max(0,parsedate_to_datetime(value).timestamp()-now)
        except (TypeError,ValueError,OverflowError):return 0

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    try:
        tmp.write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

class Client:
    def __init__(self,cache_dir=None,connection_factory=None,interactive=True):
        self.cache=Path(cache_dir) if cache_dir else HERE/'.local/wikibase-cache'
        self.factory=connection_factory or self.connection;self.conn=None;self.traces=[];self.calls=0
        self.state=self.cache if cache_dir is not None else HERE.parents[1]/'.local/evidence-access/wikidata'
        self.interactive=interactive
    def __enter__(self):return self
    def __exit__(self,*a):self.close()
    def close(self):
        if self.conn:self.conn.close();self.conn=None
    def connection(self):
        proxy=urllib.parse.urlsplit(urllib.request.getproxies().get('https',''))
        context=ssl.create_default_context()
        if proxy.hostname:
            if proxy.scheme!='http' or proxy.username or proxy.password:raise ValueError('unsupported system proxy')
            c=http.client.HTTPSConnection(proxy.hostname,proxy.port or 80,timeout=7,context=context);c.set_tunnel(HOST,443);return c
        return http.client.HTTPSConnection(HOST,timeout=7,context=context)
    def cached(self,path):
        try:
            x=json.loads(path.read_text(encoding='utf-8'))
            if 0<=time.time()-x['epoch']<86400:return x['value']
        except (OSError,ValueError,KeyError,TypeError):pass
        return None
    def request(self,params,deadline):
        with gate(self.state/'http.lock',deadline):return self._request(params,deadline)
    def _request(self,params,deadline):
        if time.monotonic()+.1>=deadline:raise TimeoutError('Wikibase deadline')
        if self.calls>=14:raise ValueError('Wikibase request budget exhausted')
        circuit=self.state/'circuit.json'
        try:
            state=json.loads(circuit.read_text(encoding='utf-8'))
            if time.time()<state['until'] and not (self.interactive and state.get('api_error_code')=='maxlag'):
                raise APIError(state['status'])
        except (OSError,ValueError,KeyError,TypeError):pass
        # One shared reservation schedule across all gateway worker processes.
        # Queue time is charged to the same absolute evidence deadline.
        self.cache.mkdir(parents=True,exist_ok=True)
        acquire_rate(self.state/'rate.sqlite','wikibase',1.25,deadline)
        # MediaWiki explicitly permits interactive (user-waiting) requests to
        # omit maxlag. Background refreshes retain it. Neither mode bypasses
        # actual HTTP/API rate limiting, provider cooldowns or Retry-After.
        params={'format':'json',**({} if self.interactive else {'maxlag':5}),**params};path='/w/api.php?'+urllib.parse.urlencode(params)
        if self.conn is None:self.conn=self.factory()
        self.conn.timeout=max(.1,min(7,deadline-time.monotonic()))
        if self.conn.sock:self.conn.sock.settimeout(self.conn.timeout)
        start=time.monotonic();self.calls+=1
        trace={'endpoint':'https://'+HOST+'/w/api.php','parameters':params,'accessed_at':datetime.now(timezone.utc).isoformat()}
        self.traces.append(trace)
        try:
            self.conn.request('GET',path,headers={'User-Agent':'HallucinationResearch/0.1 (bounded read-only evaluation)','Accept':'application/json','Accept-Encoding':'gzip,deflate'})
            response=self.conn.getresponse();trace['status']=response.status
            if response.status!=200:
                cooldown=3600 if response.status==403 else 60 if response.status==429 else 15
                retry=response.getheader('Retry-After','')
                trace['retry_after']=retry[:80]
                cooldown=max(cooldown,min(retry_delay(retry),86400))
                atomic_json(circuit,{'until':time.time()+cooldown,'status':response.status})
                self.close();raise APIError(response.status)
            raw=bytearray()
            while True:
                remaining=deadline-time.monotonic()
                if remaining<.05:raise TimeoutError('Wikibase body deadline')
                if self.conn.sock:self.conn.sock.settimeout(min(7,remaining))
                block=response.read(min(65536,MAX_WIRE+1-len(raw)))
                raw.extend(block)
                if len(raw)>MAX_WIRE:raise ValueError('Wikibase wire size limit')
                if not block:break
            encoding=response.getheader('Content-Encoding','').lower()
            if encoding in ('gzip','deflate'):
                d=zlib.decompressobj(16+zlib.MAX_WBITS if encoding=='gzip' else zlib.MAX_WBITS)
                body=d.decompress(bytes(raw),MAX_BODY+1)
                if len(body)>MAX_BODY or not d.eof:raise ValueError('Wikibase decompression limit or incomplete response')
            elif encoding:raise ValueError('unsupported content encoding')
            else:body=bytes(raw)
            if len(body)>MAX_BODY:raise ValueError('Wikibase body limit')
            trace['response_sha256']=hashlib.sha256(body).hexdigest()
            trace['content_type']=response.getheader('Content-Type','')[:120]
            try:obj=json.loads(body)
            except (ValueError,UnicodeError):
                trace['payload_error']='invalid_json';self.close();raise ValueError('Wikibase non-JSON payload') from None
            if not isinstance(obj,dict):raise ValueError('Wikibase API payload shape')
            if 'error' in obj:
                error=obj['error'] if isinstance(obj['error'],dict) else {}
                code=str(error.get('code','unknown'))[:80];trace['api_error_code']=code
                if code in ('ratelimited','maxlag','readonly'):
                    status=429 if code=='ratelimited' else 503
                    delay=max(60 if status==429 else 5,min(retry_delay(response.getheader('Retry-After','')),86400))
                    atomic_json(circuit,{'until':time.time()+delay,'status':status,'api_error_code':code})
                    self.close();raise APIError(status)
                self.close();raise ValueError('Wikibase API error: '+code)
            return obj,trace
        except (OSError,http.client.HTTPException,ValueError):self.close();raise
        finally:trace['seconds']=round(time.monotonic()-start,3)
    def search(self,name,deadline):
        with gate(self.state/'logical.lock',deadline):return self._search(name,deadline)
    def _search(self,name,deadline):
        if not isinstance(name,str) or not name.strip() or len(name)>80:raise ValueError('invalid search name')
        path=self.cache/('search-'+hashlib.sha256(name.encode()).hexdigest()+'.json')
        cached=self.cached(path)
        if cached is not None:return cached
        obj,trace=self.request({'action':'wbsearchentities','search':name,'language':'zh','uselang':'zh-hans','limit':5},deadline)
        if not isinstance(obj.get('search'),list):raise ValueError('invalid search response')
        obj['_trace']=trace;atomic_json(path,{'epoch':time.time(),'value':obj});return obj
    def entities(self,ids,deadline):
        with gate(self.state/'logical.lock',deadline):return self._entities(ids,deadline)
    def _entities(self,ids,deadline):
        ids=list(dict.fromkeys(ids))
        if not ids or len(ids)>20 or any(not isinstance(i,str) or not re.fullmatch(r'Q[1-9]\d*',i) for i in ids):raise ValueError('invalid entity batch')
        out={};missing=[]
        for qid in ids:
            cached=self.cached(self.cache/('entity-'+qid+'.json'))
            if cached is not None:out[qid]=cached
            else:missing.append(qid)
        if missing:
            data,trace=self.request({'action':'wbgetentities','ids':'|'.join(missing),'props':'info|labels|aliases|descriptions|claims','languages':'zh|zh-hans|zh-hant|zh-cn|zh-tw|zh-sg|en'},deadline)
            records=data.get('entities')
            if not isinstance(records,dict):raise ValueError('invalid entities response')
            for qid in missing:
                item=records.get(qid)
                if not isinstance(item,dict) or item.get('id')!=qid or 'missing' in item or not isinstance(item.get('claims'),dict):raise ValueError('entity ID mismatch or missing payload')
                item=dict(item,_trace=trace);out[qid]=item
            # Validate the entire batch before committing any entity.
            for qid in missing:atomic_json(self.cache/('entity-'+qid+'.json'),{'epoch':time.time(),'value':out[qid]})
        return out
