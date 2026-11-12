"""Bounded source adapter for human per-cell count described by function.

The lexical question coverage is deliberately limited. It will not discard a
named structure, negation or an extra qualifier to fit the source. Subject and
count are read from the source, never supplied as demo answers or model guesses.
"""
import hashlib,re,time,urllib.parse
from primary_fetch import canonical,bounded_fetch

WORDS=['细胞结构','细胞器','每个人体细胞','人类细胞','什么范围','多少个','是多少','自身DNA','自己的DNA','ATP','DNA',
       '每一个','每个','细胞','人体','人类','通常','一般','数量','范围','负责','能够','可以','产生','生成','合成','且','并且','并','同时','具有','拥有','含有','自身','的','其','它','在','中','达到','多少','什么','是','为','有']
QUANTIFIERS={'tens':'数十','hundreds':'数百','thousands':'数千','millions':'数百万'}
ORDERS={'tens':10,'hundreds':100,'thousands':1000,'millions':1000000}

def cell_url(url):
    value=canonical(url)
    if urllib.parse.urlsplit(value).hostname!='medlineplus.gov':raise ValueError('Not a registered cellular source')
    return value


def functional_question(q):
    if not ('ATP' in q and 'DNA' in q and re.search(r'自身|自己的',q) and re.search(r'人体|人类',q) and '细胞' in q and re.search(r'数量|范围',q)):return False
    remaining=re.sub(r'[，,。？?：:\s]','',q)
    for token in sorted(WORDS,key=len,reverse=True):remaining=remaining.replace(token,'')
    return not remaining


def inspect(q,source):
    if not functional_question(q):return {'status':'unsupported'}
    try:url=cell_url(source['url'])
    except (ValueError,KeyError,TypeError):return {'status':'unsupported_source'}
    text=source.get('text','')
    if not isinstance(text,str):return {'status':'invalid_source'}
    parts=re.split(r'(?im)^\s*#{1,6}\s*Description\s*$',text,maxsplit=1)
    if len(parts)!=2:return {'status':'insufficient','missing':'Description section'}
    description=re.split(r'(?m)^\s*#{1,6}\s+',parts[1],maxsplit=1)[0]
    # Only a complete positive sentence supplies the measured subject/count.
    number=r'(?:tens|hundreds|thousands|millions|\d+)'
    matches=list(re.finditer(r'(?:^|(?<=[.\n]))\s*(Each cell contains ('+number+r') to ('+number+r') of ([a-z][a-z -]{1,35}),[^.]*\.)',description,re.I))
    if len(matches)!=1:return {'status':'insufficient','missing':'unique per-cell count sentence'}
    m=matches[0];subject=m[4].strip();s=re.escape(subject)
    low=ORDERS[m[2].lower()] if m[2].lower() in ORDERS else int(m[2])
    high=ORDERS[m[3].lower()] if m[3].lower() in ORDERS else int(m[3])
    if low>high:return {'status':'invalid_source','missing':'count range order'}
    dna=re.search(s+r' also have[^.\n]{0,100}?their own DNA[^.]*\.',description,re.I)
    energy=re.search(s+r' are structures within cells that convert the energy[^.]*\.',description,re.I)
    atp=re.search(r'[^.\n]*create adenosine triphosphate\s*\(ATP\)[^.]*\.',description,re.I)
    human=re.search(r'\bIn humans\b[^.]*\.',description,re.I)
    if not all((dna,energy,atp,human)):return {'status':'insufficient','missing':'same-subject own-DNA, energy, ATP or human context'}
    for proof in (dna,energy,atp,human):
        if re.search(r'\bnot\b|\bfalse\b|\bincorrect\b|\balleged\b',proof[0],re.I):return {'status':'insufficient','missing':'unambiguous positive evidence'}
    value=QUANTIFIERS.get(m[2].lower(),m[2])+'至'+QUANTIFIERS.get(m[3].lower(),m[3])+'个'
    return {'status':'supported','subject':subject,'value':value,'scope':'per_human_cell',
            'answer':'按每个人体细胞中该结构的数量理解，通常为'+value+'；这是一般描述，不能作为所有细胞类型的统一数量。 来源：'+url,
            'source_url':url,'source_quotes':{'count':m[1],'own_dna':dna[0],'energy':energy[0],'atp':atp[0],'human_context':human[0]},
            'description_sha256':hashlib.sha256(description.encode()).hexdigest(),
            'source_access':{k:source.get(k) for k in ('retrieved_at','raw_sha256','transport')},
            'limitation':'Bounded source-section and lexical functional binding, not general biological inference or population extrema.'}


def lookup(q,docs,end):
    if not functional_question(q):return {'status':'unsupported'}
    urls=[]
    for doc in docs:
        try:url=cell_url(doc.get('url',''))
        except (ValueError,TypeError):continue
        if url not in urls:urls.append(url)
    if not urls:return {'status':'insufficient','missing':'retrieved primary-source page'}
    # One independent read only; no search API text, unlimited repair or
    # repeated fetches are used to manufacture confirmation.
    fetched=bounded_fetch(urls[0],min(end,time.monotonic()+8))
    if fetched.get('status')!='ok':return fetched
    return inspect(q,fetched['source'])
