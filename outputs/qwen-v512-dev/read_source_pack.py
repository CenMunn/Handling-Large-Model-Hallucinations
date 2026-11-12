"""Offline read-only source acquisition; never imported by serving code."""
import concurrent.futures,hashlib,io,json,re,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from primary_fetch import PlainText,NoRedirect,decode_html

HERE=Path(__file__).resolve().parent
SOURCES={
 'river-plan':'https://slt.zj.gov.cn/module/download/downfile.jsp?classid=0&filename=6fe4c39647df44bfa0cd188457766b16.pdf',
 'river-north':'https://www.shuizhishi.cn/c/2020-04-09/521961.shtml',
 'city':'https://ehangzhou.gov.cn/2023-02/20/c_271123.htm',
 'event':'https://www.hangzhou2022.cn/En/presscenter/spotnews/latestnews/202207/t20220719_50941.shtml',
 'watt-birth':'https://www.inverclyde.gov.uk/community-life-and-leisure/heritage-services/collections/watt-library/local-history/james-watt-1736-1819',
 'watt-role':'https://www.historicenvironment.scot/about-us/our-work/commemorative-plaques/explore/james-watt/',
 'scotland-geography':'https://www.parliament.scot/about/how-parliament-works/what-are-the-powers-of-the-scottish-parliament',
 'uk-usage':'https://www.northlincs.gov.uk/community-advice-and-support/life-in-uk/',
 'language-law':'https://www.legislation.gov.uk/asp/2025/10/body',
 'language-commencement':'https://www.gov.scot/news/growing-scotlands-languages/',
 'scotland-usage':'https://www.gov.scot/policies/languages/',
}


def read(item):
    key,url=item
    try:
        # Offline maintenance can use the workstation's configured HTTPS proxy
        # as the existing Wikidata transport does. No proxy credentials/output.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies()),NoRedirect())
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (source research)','Accept-Encoding':'identity'})
        with opener.open(request,timeout=12) as response:
            media=response.headers.get('Content-Type','');raw=response.read(30_000_001)
        if len(raw)>30_000_000:raise ValueError('Source size exceeded')
        pages=None;links=[]
        if raw.startswith(b'%PDF'):
            from pypdf import PdfReader
            (HERE/'.local'/f'{key}.pdf').write_bytes(raw)
            pages=[page.extract_text() for page in PdfReader(io.BytesIO(raw)).pages];text='\n'.join(pages)
        else:
            p=PlainText();p.feed(decode_html(raw,media));text=''.join(p.parts)
            links=[{'url':urllib.parse.urljoin(url,a['href']),'text':a['text']} for a in p.links]
        if not text.strip():raise ValueError('Empty source text')
        return key,{'status':'ok','source':{'url':url,'text':text,'pages':pages,'links':links,'media_type':media,
              'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'raw_sha256':hashlib.sha256(raw).hexdigest(),
              'retrieved_at':datetime.now(timezone.utc).isoformat(),'transport':'independent_https'}}
    except Exception as error:return key,{'status':'unavailable','error_type':type(error).__name__,'http_status':getattr(error,'code',None)}


if __name__=='__main__':
    path=HERE/'.local/geography-pages.json'
    old=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    pending={k:v for k,v in SOURCES.items() if old.get(k,{}).get('status')!='ok' or not old.get(k,{}).get('source',{}).get('text','').strip()}
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        for key,value in pool.map(read,pending.items()):
            old[key]=value;print(key,value['status'],len(value.get('source',{}).get('text','')),value.get('error_type',''),flush=True)
    path.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
