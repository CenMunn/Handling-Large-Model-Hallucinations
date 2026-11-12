"""Literal bibliographic chains from bounded, independently read source pages.

No stored demo facts. Parsing/description coverage is incomplete and does not
prove global identity or the truth/independence of a published source.
"""
import re,time,urllib.parse
from primary_fetch import canonical,bounded_fetch

BAD=re.compile(r'不是|并非|从未|没有|未经证实|身份未公开|忽略.*(?:问题|指令)|只输出|ignore.*instruction',re.I)
COUNTRIES={'英':'英国','美':'美国','法':'法国','中':'中国','俄':'俄罗斯','德':'德国','日':'日本'}
POLITICAL=r'政治组织|政党|共产党组织|政治团体|无产阶级政党'
NAME=r'[\u4e00-\u9fffA-Za-z·・]{2,35}'

def norm(x):return re.sub(r'\s+','',x).replace('・','·').casefold()

def plan(q):
    if re.search(r'【世界设定】|【对话记录】|仅根据|只根据|是否|对吗|前身|译者是谁|本名|原名',q):return None
    m=re.fullmatch(r'(?:如果)?(?:(?P<country>英国|美国|法国|中国|俄罗斯|德国|日本)?文学数据库规定[，,])?(?:那部)?(?:围绕|讲述|描写)(?P<clues>[^，,。？?]{2,50})的(?:长篇)?小说(?:应直接以真实作者命名条目[，,](?:那么)?条目应使用谁的名字|[，,]?(?:其)?真实作者是谁)[？?。]?',q.strip())
    if m and not BAD.search(m['clues']) and not re.search(r'\d',m['clues']):return {'kind':'descriptive_author',**m.groupdict()}
    m=re.fullmatch(r'(\d{4})年首次(?:出版|发表)并由(?:政治)?组织(?:推动发行|委托起草|委托撰写)的(?:理论著作|著作|作品)[，,]其(?:相关政治组织|相关组织|委托组织)(?:成立|创建|创立)年份(?:是多少|是哪年|是哪一年)[？?。]?',q.strip())
    if m:return {'kind':'publication_organization','year':int(m[1])}
    return None

def clue_cover(clues,text):
    if BAD.search(text):return None
    clues=re.sub(r'[与和及的、\s]','',clues);body=norm(text);memo={len(clues):[]}
    alternatives={'强烈':('强烈','浓烈','炽热','狂暴')}
    for pos in range(len(clues)-1,-1,-1):
        for size in range(2,min(12,len(clues)-pos)+1):
            token=clues[pos:pos+size]
            hit=next((s for s in alternatives.get(token,(token,)) if norm(s) in body),None)
            if hit and pos+size in memo:memo[pos]=[(token,hit)]+memo[pos+size];break
    return memo.get(0)

def books(source):
    text=source['text'];hits=list(re.finditer(r'《([^》\n]{1,50})》',text));out=[];seen=set()
    for i,m in enumerate(hits):
        work=m[1]
        if work in seen:continue
        seen.add(work)
        stop=next((h.start() for h in hits[i+1:] if h[1]!=work),min(len(text),m.start()+1800))
        block=text[m.start():stop]
        if BAD.search(block):continue
        w=re.escape(work);credits=[]
        header=re.search(r'《'+w+r'》\s*\n\s*(?:\(([^)]{1,12})\)\s*)?('+NAME+r')著(?:[;；]|\s*$)',block,re.M)
        if header:credits.append({'author':header[2],'country':COUNTRIES.get(header[1],header[1]),'quote':header[0]})
        genres=r'(?:唯一(?:一部)?(?:长篇)?(?:代表作|小说)|传世经典|作品|(?:长篇)?(?:科幻|历史|爱情|悲剧)?小说)'
        prefix=r'《'+w+r'》是(?:由)?(?:(英国|美国|法国|中国|俄罗斯|德国|日本)(?:著名)?(?:作家|小说家)|(?:作家|小说家))?'
        for suffix in [r'的'+genres,r'(?:创作|撰写|所著)的'+genres]:
            intro=re.search(prefix+'('+NAME+r'?)'+suffix,block)
            if intro and not re.search(r'妻子|丈夫|儿子|女儿|父亲|母亲|译者|编辑|作者|作家|小说家|创作|撰写|所著|的',intro[2]):
                credits.append({'author':intro[2],'country':intro[1],'quote':intro[0]})
        unresolved=not credits and bool(re.search(r'《'+w+r'》是[^。\n]{0,100}(?:创作|撰写|作者|著)',block))
        out.append({'work':work,'block':block,'credits':credits,'unresolved_credit':unresolved,'source_url':source['url']})
    return out

def publications(text):
    out=[];seen=set()
    patterns=[r'(\d{4})年[^。\n]{0,30}(?:。这一天[，,])?《([^》\n]{1,50})》([^。\n]{0,45}(?:首次出版|首次发表|问世))',
              r'《([^》\n]{1,50})》(?:于|在)(\d{4})年([^。\n]{0,30}(?:首次出版|首次发表|问世))']
    for i,pattern in enumerate(patterns):
        for m in re.finditer(pattern,text):
            year,work=(int(m[1]),m[2]) if i==0 else (int(m[2]),m[1])
            if re.search(r'译本|译文|翻译|再版|重印|第二版|第三版|不是|并非',m[0]):continue
            key=work,year
            if key not in seen:out.append({'work':work,'year':year,'quote':m[0]});seen.add(key)
    return out

def foundations(text):
    out=[]
    for match in re.finditer(r'[^。！？\n]+[。！？]?',text):
        sentence=match[0]
        if BAD.search(sentence):continue
        reorganized=re.search(r'(\d{4})年[^。\n]{0,25}[“"]('+NAME+r')[”"][^。\n]{0,30}改组为[“"]('+NAME+r')[”"][^。\n]{0,35}(?:'+POLITICAL+r')',sentence)
        if reorganized:
            out.append({'organization':reorganized[3],'year':int(reorganized[1]),'kind':'reorganized','predecessor':reorganized[2],'quote':sentence,'position':match.start(),'end':match.end()})
        direct=re.search(r'^\s*('+NAME+r')(?:于|在)(\d{4})年(?:正式)?成立[，,](?:是|为)(?:一个|一个新的)?(?:'+POLITICAL+r')',sentence)
        if direct:out.append({'organization':direct[1],'year':int(direct[2]),'kind':'founded','quote':sentence,'position':match.start(),'end':match.end()})
    return out

def commissions(text,found):
    out=[]
    patterns=[r'《([^》\n]{1,50})》[，,]?(?:是|正是)[^。\n]{0,25}?受('+NAME+r')委托(?:起草|撰写)的(?:党纲|纲领)',
              r'《([^》\n]{1,50})》是('+NAME+r')委托(?:起草|撰写)的(?:党纲|纲领)']
    for pattern in patterns:
        for m in re.finditer(pattern,text):
            if BAD.search(m[0]):continue
            named=m[2];known={r['organization'] for r in found}
            if named not in known:
                nearby=[r for r in found if r['kind']=='reorganized' and 0<=m.start()-r['end']<=300 and r['organization'].endswith(named)]
                # Restrict abbreviated reference to the immediately preceding
                # positively typed reconstitution; never a predecessor/year.
                if len(nearby)!=1 or re.search(r'前者|旧组织|前身',text[nearby[0]['end']:m.start()]):continue
                named=nearby[0]['organization']
            out.append({'work':m[1],'organization':named,'quote':m[0]})
    return out

def analyze(q,sources):
    p=plan(q)
    if not p:return {'status':'unsupported'}
    if p['kind']=='descriptive_author':
        records=[r for s in sources for r in books(s)];matching=[]
        for r in records:
            cover=clue_cover(p['clues'],r['block'])
            if cover and '小说' in r['block']:matching.append({**r,'clue_coverage':cover})
        names={norm(r['work']) for r in matching}
        if len(names)>1:return {'status':'ambiguous','matching_works':[r['work'] for r in matching]}
        if not matching:return {'status':'insufficient','missing':'complete descriptive clue coverage'}
        work=matching[0]['work'];credits=[dict(c,source_url=r['source_url']) for r in records if norm(r['work'])==norm(work) for c in r['credits']]
        if any(r['unresolved_credit'] for r in records if norm(r['work'])==norm(work)):return {'status':'needs_verification','missing':'relevant authorship statement not unambiguously parsed'}
        if p.get('country') and p['country'] not in {c.get('country') for c in credits}:return {'status':'insufficient','missing':'national-literature hint'}
        authors={norm(c['author']) for c in credits}
        if len(authors)>1:return {'status':'conflict','work':work,'credit_sources':credits}
        owners={urllib.parse.urlsplit(c['source_url']).hostname.removeprefix('www.') for c in credits}
        if not credits or len(owners)<2:return {'status':'insufficient','missing':'corroborating author credits from distinct registered publishers/libraries'}
        author=credits[0]['author'];urls=list(dict.fromkeys(c['source_url'] for c in credits))
        return {'status':'supported','work':work,'author':author,'clue_matches':matching,'credit_sources':credits,
                'answer':f'根据检索到的情节描述，所指应为《{work}》，其作者是{author}。 来源：'+'；'.join(urls[:2]),
                'limitation':'Bounded lexical clue matching and source-credit agreement; neither global identity nor independent origins of sources are proven.'}
    pub=[];found=[];comm=[]
    for s in sources:
        local=foundations(s['text']);found.extend(dict(r,source_url=s['url']) for r in local)
        pub.extend(dict(r,source_url=s['url']) for r in publications(s['text']))
        comm.extend(dict(r,source_url=s['url']) for r in commissions(s['text'],local))
    works={r['work'] for r in pub if r['year']==p['year']}
    chains=[(a,b) for a in comm if a['work'] in works for b in found if b['organization']==a['organization']]
    if not chains:return {'status':'insufficient','missing':'publication, commission and political organization inception chain','publication_records':pub,'foundation_records':found,'commission_records':comm}
    if any(len({r['year'] for r in pub if r['work']==a['work']})>1 for a,b in chains):return {'status':'conflict','publication_records':pub}
    if any(b['year']>p['year'] for a,b in chains):return {'status':'invalid_source','reason':'organization inception follows claimed publication/commission year'}
    if len({a['work'] for a,b in chains})>1 or len({a['organization'] for a,b in chains})>1:return {'status':'ambiguous'}
    if len({b['year'] for a,b in chains})>1:return {'status':'conflict','chains':chains}
    a,b=chains[0];urls=list(dict.fromkeys([a['source_url'],b['source_url']]+[r['source_url'] for r in pub if r['work']==a['work']]))
    qualifier='按该组织改组成立的口径，' if b['kind']=='reorganized' else ''
    return {'status':'supported','work':a['work'],'organization':a['organization'],'year':b['year'],
            'publication_records':[r for r in pub if r['work']==a['work']],'commission':a,'foundation':b,
            'answer':f'{qualifier}《{a["work"]}》相关组织{a["organization"]}的成立年份为{b["year"]}年。 来源：'+'；'.join(urls),
            'limitation':'Bounded literal publication/commission/inception relations; not a general historical or source-truth proof.'}

def lookup(q,docs,end):
    if not plan(q):return {'status':'unsupported'}
    urls=[]
    for d in docs:
        try:url=canonical(d.get('url',''))
        except (ValueError,TypeError):continue
        if urllib.parse.urlsplit(url).hostname=='medlineplus.gov':continue
        if url not in urls:urls.append(url)
    fetched=[];errors=[]
    for url in urls[:2]:
        if end-time.monotonic()<.3:break
        r=bounded_fetch(url,end)
        if r.get('status')=='ok':fetched.append(r['source'])
        else:errors.append({'url':url,**r})
    result=analyze(q,fetched)
    if result.get('status')=='supported':
        probe=analyze(q,[{'url':d.get('url',''),'text':d.get('full_text',d.get('text',''))} for d in docs])
        if probe.get('status') in ('conflict','ambiguous'):
            result={'status':'needs_verification','reason':'unfetched retrieval text raises a potential contradictory credit/identity; not an independently established source conflict','retrieval_alert_status':probe['status']}
    result.update(fetch_errors=errors,source_access=[{k:s.get(k) for k in ('url','raw_sha256','retrieved_at','transport')} for s in fetched])
    return result
