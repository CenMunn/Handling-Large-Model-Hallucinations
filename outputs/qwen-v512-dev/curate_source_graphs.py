"""Offline source maintenance. No model generation and no question/ID answers.

The operator reviews relations and qualifications; these parsers extract only
the registered source layouts. The saved graph includes complete read bodies,
retrieval timestamps and exact evidence, so it can be audited independently.
"""
import hashlib,json,re
from pathlib import Path
from curated_chains import norm,validate_bundle

HERE=Path(__file__).resolve().parent


def history_bundle(pages):
    def source(suffix):
        s=next(v['source'] for k,v in pages.items() if k.endswith('/'+suffix) and v['status']=='ok').copy()
        s['text_sha256']=hashlib.sha256(s['text'].encode()).hexdigest();return s
    sources={k:source(p) for k,p in [('bio','bio.html'),('faq','bs_faq.html'),('book','1st.html'),('preface','1st_pref.html')]}
    bio=norm(sources['bio']['text']);faq=norm(sources['faq']['text']);book=norm(sources['book']['text']);preface=norm(sources['preface']['text'])
    ident=re.search(r'([A-Z][a-z]+ [A-Z][a-z]+) is the designer and original implementer of (\S+)',bio)
    if not ident:raise ValueError('Designer source layout changed')
    person,language=ident.groups()
    design=re.search(r'I started work on what became '+re.escape(language)+r' in (\d{4})\.',faq)
    release=re.search(r'The first commercial implementation was released [^.]+?(\d{4}) at the same time as the publication of [^.]+\.',faq)
    site=re.search(r'In (\d{4}), '+re.escape(person)+r',.*?moved to (.*?) to join the (.*?) \(',bio)
    signature=re.search(r'([A-Z][a-z]+(?: [A-Z][a-z]+)*), ([A-Z][a-z]+(?: [A-Z][a-z]+)*), '+re.escape(person),preface)
    date=re.search(r'This book was published in (\d{4})[^.]*\.',book)
    if not all([design,release,site,signature,date]):raise ValueError('Historical edge layout changed')
    def ref(key,quote):return [{'source':key,'quote':quote}]
    b={'kind':'historical_workplace','subject':language,'aliases':[language], 'designer':person,
       'institution':site[3],'institution_aliases':[site[3],'Bell Labs','Bell Laboratories','贝尔实验室'],
       'start_year':int(design[1]),'release_year':int(release[1]),'release_kind':'first_commercial',
       'start_state':site[2],'release_state':signature[2],'state_label':signature[2],
       'coverage':'dated_endpoints','sources':sources,
       'evidence':{'identity':ref('bio',ident[0]),'design_start':ref('faq',design[0]),'release':ref('faq',release[0]),
                   'start_site':ref('bio',site[0]),'release_site':ref('preface',signature[0]),'release_site_date':ref('book',date[0])},
       'curation_note':'Biography plus release-era first-edition preface. Course acknowledgement is not a worksite. Book date is only preface-date corroboration, not release evidence.'}
    # A display lexicon is not a geographic inference. The source's English
    # name always remains visible; unsupported names are not translated.
    labels={'New Jersey':'新泽西州','Oregon':'俄勒冈州','California':'加利福尼亚州','Texas':'得克萨斯州','Washington':'华盛顿州','New York':'纽约州'}
    b['state_label']=labels.get(signature[2],signature[2])
    if not validate_bundle(b)['ok']:raise ValueError('Historical source graph did not validate')
    return b


if __name__=='__main__':
    b=history_bundle(json.loads((HERE/'.local/history-pages.json').read_text(encoding='utf-8')))
    path=HERE/'curated-source-graphs.json'
    previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    path.write_text(json.dumps([b]+[r for r in previous if r.get('kind')!='historical_workplace'],ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:b[k] for k in ('subject','designer','start_year','release_year','start_state','release_state')},ensure_ascii=False))
