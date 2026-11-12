"""Independent bounded read for registered genetics/library/publication adapters.

URLs must already be retrieval results. Registered hosts are not a guarantee of
truth or independent origin. No search API body is accepted as the
independently read page. No redirects, auth headers, scripts or subresources.
"""
import hashlib,json,os,re,subprocess,sys,time,urllib.parse,urllib.request,uuid
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime,timezone
from persistent_rate import acquire

HERE=Path(__file__).resolve().parent


def canonical(url):
    p=urllib.parse.urlsplit(url)
    profiles={'medlineplus.gov':'/genetics/','www.zzhvc.cn':'/tsg/','news.cnr.cn':'/native/gd/','se.zhangyue.com':'/book/detail',
              'stroustrup.com':'/','www.stroustrup.com':'/'}
    if p.hostname not in profiles or not p.path.startswith(profiles[p.hostname]) or p.username or p.password or len(url)>8192:
        raise ValueError('Unregistered source host/path')
    if not (p.scheme=='https' and p.port in (None,443)) and not (p.hostname=='news.cnr.cn' and p.scheme=='http' and p.port in (None,80)):
        raise ValueError('Source requires canonical HTTPS')
    query=''
    if p.hostname=='se.zhangyue.com':
        values=urllib.parse.parse_qs(p.query)
        if not re.fullmatch(r'\d{1,15}',values.get('bookId',[''])[0]):raise ValueError('Missing public book identifier')
        pairs={k:values[k][0] for k in ('bookId','bookType','appId') if k in values and re.fullmatch(r'[A-Za-z0-9]{1,40}',values[k][0])}
        query=urllib.parse.urlencode(pairs)
    return urllib.parse.urlunsplit(('https',p.hostname,p.path,query,''))


def decode_html(raw,content_type):
    match=re.search(r'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',content_type,re.I)
    if not match:match=re.search(rb'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',raw[:8192],re.I)
    encoding=match[1] if match else 'utf-8'
    if isinstance(encoding,bytes):encoding=encoding.decode('ascii')
    encoding=encoding.lower().replace('_','-')
    if encoding in ('gbk','gb2312','gb18030'):encoding='gb18030'
    if encoding not in ('utf-8','utf8','gb18030'):raise ValueError('Unsupported primary-source charset')
    return raw.decode(encoding)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Primary-source redirects disabled')


class PlainText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0;self.links=[];self.anchor=None
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if not self.skip and tag=='a':
            href=dict(attrs).get('href')
            self.anchor={'href':href,'text':''} if href else None
        if not self.skip and tag in ('p','div','br','li','h1','h2','h3','h4'):
            self.parts.append('\n### ' if tag.startswith('h') else '\n')
    def handle_endtag(self,tag):
        if tag=='a' and self.anchor:
            self.links.append(self.anchor);self.anchor=None
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if not self.skip and tag in ('p','div','li','h1','h2','h3','h4'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data)
            if self.anchor:self.anchor['text']+=data


def fetch(url,end):
    url=canonical(url);cache=HERE/'.local/primary-cache';cache.mkdir(parents=True,exist_ok=True)
    path=cache/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    def cached():
        try:
            row=json.loads(path.read_text(encoding='utf-8'))
            if row['url']==url and 0<=time.time()-row['epoch']<86400 and row.get('transport')=='independent_https':return row
        except (OSError,ValueError,KeyError,TypeError):pass
    row=cached()
    if row:return row
    acquire(cache/'rate.sqlite',urllib.parse.urlsplit(url).hostname,1,end)
    row=cached()
    if row:return row
    remaining=end-time.monotonic()
    if remaining<.2:raise TimeoutError('Primary-source deadline')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies_environment()),NoRedirect())
    request=urllib.request.Request(url,headers={'User-Agent':'HallucinationResearch/0.1 (read-only source verification)','Accept':'text/html','Accept-Encoding':'identity'})
    with opener.open(request,timeout=min(5,remaining)) as response:
        if response.status!=200:raise ValueError('Primary-source HTTP status')
        content_type=response.headers.get('Content-Type','')
        if 'text/html' not in content_type:raise ValueError('Unexpected primary-source media type')
        raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Primary-source response limit')
    if time.monotonic()>=end:raise TimeoutError('Primary-source body deadline')
    parser=PlainText();parser.feed(decode_html(raw,content_type));text=''.join(parser.parts)
    links=[{'url':urllib.parse.urljoin(url,a['href']),'text':a['text']} for a in parser.links]
    row={'url':url,'text':text,'links':links,'raw_sha256':hashlib.sha256(raw).hexdigest(),
         'retrieved_at':datetime.now(timezone.utc).isoformat(),'epoch':time.time(),'transport':'independent_https'}
    temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8');os.replace(temp,path)
    return row


def bounded_fetch(url,end):
    canonical(url)
    budget=min(8,end-time.monotonic())
    if budget<.3:return {'status':'timeout'}
    try:
        proc=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],
            input=json.dumps({'url':url,'budget':max(.1,budget-.25)}),capture_output=True,text=True,encoding='utf-8',timeout=budget,
            env=os.environ.copy()|{'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
        if proc.returncode:return {'status':'unavailable','error_type':'WorkerError'}
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:return {'status':'timeout','deadline_enforced':True}
    except (OSError,ValueError):return {'status':'unavailable','error_type':'WorkerPayloadError'}


if __name__=='__main__':
    body=json.load(sys.stdin)
    try:result={'status':'ok','source':fetch(body['url'],time.monotonic()+min(8,float(body['budget'])))}
    except Exception as error:result={'status':'unavailable','error_type':type(error).__name__}
    print(json.dumps(result,ensure_ascii=False))
