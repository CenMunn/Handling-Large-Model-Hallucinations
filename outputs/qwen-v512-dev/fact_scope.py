"""User-approved factual scopes over literal, independently bound records.

This is a bounded lexical selector, not a semantic truth verifier. A proposed
entity must be in the question or supplied by an already checked external
identity chain. A model-provided `verified` flag never authorizes a record.
"""
import re,unicodedata,urllib.parse

NEG=re.compile(r'不是|并非|未曾|从未|未经证实|不确定|没有规定|未规定|未明确|传闻|据说|可能|疑似|\bnot\b',re.I)
RELATIVE=re.compile(r'其父|其母|其弟|其兄|父亲|母亲|哥哥|弟弟|姐姐|妹妹|妻子|丈夫|儿子|女儿|\bhis (?:father|brother|wife)\b',re.I)
REACH=re.compile(r'河段|上游|中游|下游|\breach\b|\bsection\b',re.I)
INACTIVE_LAW=re.compile(r'已废止|已失效|尚未生效|未生效|草案|\brepealed\b|\bexpired\b|\bprospective\b|\bdraft\b',re.I)


def norm(s):return re.sub(r'\s+','',unicodedata.normalize('NFKC',s)).casefold()


def policy(q):
    if re.search(r'【世界设定】|【对话记录】|(?:仅|只)(?:能)?(?:根据|依据)|(?:根据|依据)(?:给定|所给|提供的|上述|下列)(?:材料|资料|文本|记录)',q):return None
    if '官方语言' in q:
        return {'kind':'language','preferred_scopes':['legal','usage'],'retrieval_hint':'法定官方语言 法律地位 主要使用语言','instruction':'优先核查具有法律地位的官方语言。未取得法律地位证据时，主要使用语言只能标注为替代口径；检索不到不代表法律上不存在。'}
    if re.search(r'河流|河|江|溪',q) and re.search(r'全长|长度|长多少|多少公里|多少千米',q):
        reach=bool(re.search(r'河段|上游|中游|下游|[甲乙丙丁]段',q))
        return {'kind':'length','preferred_scopes':['reach'] if reach else ['whole','mainstem','reach'],
                'retrieval_hint':'全河 源头至河口 干流 长度 测量口径',
                'instruction':'优先全河或水系干流长度；同一范围的不同值要核查冲突，不能直接取最大。仅有河段时说明河段名与范围，不将它当作全河长度。'}
    if re.search(r'设计|研发|开发|首次发布',q) and re.search(r'当时|工作地点|工作地|任职|研究机构',q):
        return {'kind':'workplace','preferred_scopes':['employment'],'retrieval_hint':'开始设计 首次发布 任职 起止时间 历史工作地点',
                'instruction':'优先开始设计到首次发布期间的工作地点。核查时间窗，区分设计、命名、发布和图书出版日期；不使用当前工作地点代替。期间发生变动应保留多个地点及日期。'}
    if re.search(r'人体|人类|human',q,re.I) and re.search(r'细胞|cell',q,re.I) and re.search(r'数量|总数|多少|范围',q):
        whole=bool(re.search(r'全身|整体|人体细胞总|人体内共有|全部人体细胞',q))
        return {'kind':'count','preferred_scopes':['whole_body'] if whole else ['per_human_cell'],
                'retrieval_hint':'每个人体细胞 细胞器 数量范围 细胞类型',
                'instruction':'默认问每个人体细胞中该结构的数量，明确问全身总数时尊重原题。核对物种、分母、细胞类型和数量范围，不将特殊细胞类型推广到所有细胞。'}
    if '出生' in q:
        return {'kind':'birthplace','preferred_scopes':['birthplace'],'retrieval_hint':'出生地 born in 传记',
                'instruction':'出生地、祖籍、籍贯和住所是不同属性。缺少出生地证据时保留已确认身份，明确缺失出生地，不能用祖籍替代。'}
    return None


def legal_source(source):
    try:host=(urllib.parse.urlsplit(source.get('url','')).hostname or '').lower()
    except ValueError:return False
    # These are hosts for official legal/government publications, not a provider
    # authority score or an LLM-asserted primary-source flag.
    return (host=='legislation.gov.uk' or host.endswith('.legislation.gov.uk') or
            host=='gov.cn' or host.endswith('.gov.cn') or host=='npc.gov.cn' or host.endswith('.npc.gov.cn'))


def source_text(source):
    full=source.get('full_text')
    return full if isinstance(full,str) and full.strip() else source.get('text','')


def explicit_subject(q,p):
    patterns={'language':r'^([\u4e00-\u9fffA-Za-z·]{2,24}?)(?:的)?官方语言',
              'length':r'^([\u4e00-\u9fffA-Za-z·]{2,24}?)(?:的)?(?:全长|干流|上游|中游|下游|长度)',
              'count':r'^([\u4e00-\u9fffA-Za-z·]{2,24}?)(?:在|的)?人体',
              'workplace':r'^([\u4e00-\u9fffA-Za-z·]{2,24}?)(?:设计|研发|开发)',
              'birthplace':r'^([\u4e00-\u9fffA-Za-z·]{2,24}?)(?:的)?出生'}
    m=re.search(patterns[p['kind']],q.strip())
    if not m:return None
    entity=m[1]
    return None if re.search(r'某|其|该|这个|那个|所在|出生|国家|谁|哪|的',entity) else entity


def collect(q,sources,verified_subjects=()):
    """Extract literal candidate records, without another generation pass.

    Explicit subject parsing is deliberately narrow. It does not infer a name
    from anonymous clues. Extraction failure remains visible instead of
    permitting a model's `irrelevant` label to erase source conflicts.
    """
    p=policy(q)
    if not p:return [],[]
    subject=explicit_subject(q,p)
    subjects=list(dict.fromkeys(([subject] if subject else [])+list(verified_subjects)))
    records=[];errors=[]
    markers={'language':r'官方语言|主要使用|主要通用|最广泛使用',
             'length':r'全长|长度','count':r'数量|通常有|约有',
             'workplace':r'工作|任职','birthplace':r'出生于|出生在|出生地'}
    for source in sources:
        body=source_text(source)
        if not isinstance(body,str):continue
        for quote in re.findall(r'[^。！？\n]+[。！？]?',body):
            for entity in subjects:
                if entity not in quote or not re.search(markers[p['kind']],quote):continue
                if len(quote)>700:
                    errors.append({'source_id':source['id'],'reason':'relevant clause exceeds lexical limit'});continue
                compact=re.sub(r'\s+','',quote);e=re.escape(entity);items=[]
                if p['kind']=='language':
                    for scope,pattern in [('legal',e+r'(?:的)?(?:唯一(?:的)?)?(?:法定)?官方语言(?:是|为|包括|有|：|:)([^，,。；;！？]{1,40})'),('usage',e+r'(?:的)?(?:主要使用|主要通用|最广泛使用的语言(?:是|为))([^，,。；;！？]{1,40})')]:
                        for m in re.finditer(pattern,compact):items.append({'value':m[1],'scope':scope})
                elif p['kind']=='length':
                    value=r'([0-9]+(?:\.[0-9]+)?(?:公里|千米|米|km|m))'
                    patterns=[('whole',e+r'(?:的)?(?:全河(?:从源头至河口的)?(?:长度|全长)|全长)(?:约|为|是)?'+value),
                              ('mainstem',e+r'(?:的)?干流(?:长度|全长)(?:约|为|是)?'+value),
                              ('reach',e+r'(?:的)?([^，,。；;！？]{1,12}?段)(?:的)?(?:长度|全长)(?:约|为|是)?'+value)]
                    for scope,pattern in patterns:
                        for m in re.finditer(pattern,compact):
                            items.append({'value':m[2] if scope=='reach' else m[1],'scope':scope,**({'scope_detail':m[1]} if scope=='reach' else {})})
                elif p['kind']=='count':
                    m=re.search(e+r'(?:的)?(?:数量(?:为|是)|通常有|约有|有)([0-9零一二两三四五六七八九十百千万数至到—–~～\-]+个)',compact)
                    if m:
                        specific=re.search(r'人体([^，,。；;]{1,18}?细胞)中',compact)
                        cell_type=specific[1] if specific and specific[1]!='一般细胞' else 'general'
                        items.append({'value':m[1],'scope':'per_human_cell','cell_type':cell_type})
                elif p['kind']=='workplace':
                    m=re.search(e+r'从(\d{4})年至(\d{4})年在([^，,。；;]{1,15}?州)[^。！？；\n]{0,30}(?:工作|任职)',compact)
                    if m:items.append({'value':m[3],'scope':'employment','start_year':int(m[1]),'end_year':int(m[2])})
                elif p['kind']=='birthplace':
                    m=re.search(e+r'(?:的出生地(?:是|为)|出生于|出生在)([^，,。；;！？]{1,30})',compact)
                    if m:items.append({'value':m[1],'scope':'birthplace'})
                if not items:errors.append({'source_id':source['id'],'reason':'relevant entity/attribute clause not parsed'})
                for item in items:records.append(dict(item,entity=entity,attribute=p['kind'],source_id=source['id'],quote=quote))
                if len(records)>100:return [],[{'reason':'scoped record budget exceeded'}]
    return records,errors


def valid_record(q,r,sources,verified_subjects):
    if not isinstance(r,dict):return False
    keys=('entity','attribute','value','scope','quote','source_id')
    if not all(isinstance(r.get(k),str) and r[k].strip() for k in keys):return False
    entity,value,quote=r['entity'],r['value'],r['quote']
    source=next((d for d in sources if d.get('id')==r['source_id']),None)
    if not source or not isinstance(source_text(source),str):return False
    if len(quote)>700 or norm(quote) not in norm(source_text(source)) or norm(value) not in norm(quote):return False
    if norm(entity) not in norm(q) and entity not in verified_subjects:return False
    if NEG.search(quote) or RELATIVE.search(quote) or re.search(r'忽略.*(?:问题|指令)|只输出|ignore.*instruction',quote,re.I):return False
    e,v=re.escape(entity),re.escape(value)
    compact=re.sub(r'\s+','',quote)
    if r['attribute']=='language':
        if r['scope']=='legal':
            if INACTIVE_LAW.search(quote) or INACTIVE_LAW.search(source.get('title','')):return False
            body_norm,quote_norm=norm(source_text(source)),norm(quote)
            pos=body_norm.find(quote_norm)
            after=body_norm[pos+len(quote_norm):pos+len(quote_norm)+120]
            if re.match(r'(?:该|本)(?:法律|条款|规定|法).{0,30}(?:已废止|已失效|尚未生效|未生效)',after):return False
            return bool(legal_source(source) and re.search(r'法律|法定|条例|\blaw\b|\bact\b',quote,re.I)
                        and re.search(e+r'(?:的)?(?:唯一(?:的)?)?(?:法定)?官方语言(?:是|为|包括|有|：|:)'+v,compact))
        if r['scope']=='usage':
            return bool(re.search(e+r'(?:的)?(?:主要使用|主要通用|最广泛使用的语言(?:是|为))'+v,compact))
    if r['attribute']=='length':
        if r['scope']=='whole':
            if REACH.search(quote):return False
            return bool(re.search(e+r'(?:的)?(?:全河(?:从源头至河口的)?(?:长度|全长)|全长)(?:约|为|是)?'+v,compact))
        if r['scope']=='mainstem':
            return bool(not REACH.search(quote) and re.search(e+r'(?:的)?干流(?:长度|全长)(?:约|为|是)?'+v,compact))
        if r['scope']=='reach':
            detail=r.get('scope_detail')
            return bool(isinstance(detail,str) and detail and detail in quote and
                        re.search(e+r'(?:的)?'+re.escape(detail)+r'(?:的)?(?:长度|全长)(?:约|为|是)?'+v,compact))
    if r['attribute']=='workplace' and r['scope']=='employment':
        start,end=r.get('start_year'),r.get('end_year')
        if type(start)!=int or type(end)!=int or not 1<=start<=end<=9999:return False
        return bool(re.search(e+r'从'+str(start)+r'年至'+str(end)+r'年在'+v+r'[^。！？；\n]{0,30}(?:工作|任职)',compact))
    if r['attribute']=='count':
        if r['scope']=='whole_body':
            return bool(re.search(r'人体|人类',quote) and re.search(r'全身|总数|总量',quote)
                        and re.search(e+r'(?:的)?(?:总数|总量)(?:是|为)?'+v,compact))
        if r['scope']=='per_human_cell':
            if not re.search(r'人体|人类|\bhuman',quote,re.I) or re.search(r'小鼠|大鼠|植物|酵母|\bmice\b|\bmouse\b',quote,re.I):return False
            if not re.search(r'每个细胞|每一个细胞|一个细胞|\beach cell\b|\bper cell\b',quote,re.I):return False
            cell_type=r.get('cell_type')
            if cell_type=='general':
                if not re.search(r'一般|多数|通常|典型|\bmost\b|\btypical',quote,re.I):return False
            elif not isinstance(cell_type,str) or not cell_type or cell_type not in quote:return False
            return bool(re.search(e+r'(?:的)?(?:数量(?:为|是)|通常有|约有|有)'+v,compact))
    if r['attribute']=='birthplace' and r['scope']=='birthplace':
        return bool(re.search(e+r'(?:的出生地(?:是|为)|出生于|出生在)'+v,compact))
    return False


def length_km(value):
    m=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)\s*(公里|千米|米|km|m)',value,re.I)
    if not m:return None
    return float(m[1])*(.001 if m[2].lower() in ('米','m') else 1)


def select(q,records,sources,*,verified_subjects=(),design_window=None):
    p=policy(q)
    if not p:return {'status':'unsupported'}
    if p['kind']=='language' and re.search(r'\d{4}年',q):return {'status':'missing_time_scope','policy':p}
    rows=[r for r in records if valid_record(q,r,sources,verified_subjects) and r['attribute']==p['kind']]
    base={'policy':p,'accepted_records':rows,'limitation':'Literal source/subject/scope binding, not comprehensive semantic or source-truth verification.'}
    if p['kind']=='workplace':
        if not (isinstance(design_window,(tuple,list)) and len(design_window)==2 and all(type(x)==int for x in design_window) and 1<=design_window[0]<=design_window[1]<=9999):return dict(base,status='missing_design_window')
        start,end=design_window
        rows=[r for r in rows if r['start_year']<=end and r['end_year']>=start]
        covered={year for r in rows for year in range(max(start,r['start_year']),min(end,r['end_year'])+1)}
        if len(covered)!=end-start+1:return dict(base,status='insufficient',missing='employment window coverage')
        for year in covered:
            if len({r['value'] for r in rows if r['start_year']<=year<=r['end_year']})>1:return dict(base,status='conflict')
        values={r['value'] for r in rows}
        if len(values)==1:return dict(base,status='supported',value=next(iter(values)),scope='employment',answer=next(iter(values)),records=rows)
        answer='设计开始到首次发布期间的工作地点有变动：'+'；'.join(f'{r["start_year"]}—{r["end_year"]}年：{r["value"]}' for r in rows)+'。'
        return dict(base,status='qualified',scope='employment',answer=answer,records=rows)
    for scope in p['preferred_scopes']:
        group=[r for r in rows if r['scope']==scope]
        if not group:continue
        others=[r for r in rows if r['scope']!=scope]
        if scope=='reach':
            if any(length_km(r['value']) is None for r in group):return dict(base,status='insufficient')
            for name in {r['scope_detail'] for r in group}:
                if len({length_km(r['value']) for r in group if r['scope_detail']==name})>1:return dict(base,status='conflict')
            chosen=max(group,key=lambda r:length_km(r['value']))
            return dict(base,status='qualified',value=chosen['value'],scope=scope,records=group,other_scopes=others,
                        answer=f'仅查到具体河段；已检索记录中最长的明确命名河段为{chosen["scope_detail"]}，长{chosen["value"]}，不代表全河长度。')
        if scope=='per_human_cell':
            general=[r for r in group if r.get('cell_type')=='general']
            if not general:
                for cell_type in {r['cell_type'] for r in group}:
                    if len({r['value'] for r in group if r['cell_type']==cell_type})>1:return dict(base,status='conflict')
                return dict(base,status='qualified',scope=scope,records=group,
                            answer='仅查到特定细胞类型：'+'；'.join(r['cell_type']+'：'+r['value'] for r in group)+'。不能据此确定一般人体细胞的数量范围。')
            group=general
        values={length_km(r['value']) if scope in ('whole','mainstem') else norm(r['value']) for r in group}
        if None in values:return dict(base,status='insufficient')
        if len(values)!=1:
            if scope=='legal' and not any('唯一' in r['quote'] for r in group):
                return dict(base,status='qualified',scope=scope,records=group,other_scopes=others,
                            answer='法律资料分别提及以下官方语言：'+'、'.join(dict.fromkeys(r['value'] for r in group))+'；尚未核实是否为完整名单。')
            return dict(base,status='conflict',scope=scope,records=group)
        value=group[0]['value'];status='qualified' if scope=='usage' else 'supported'
        answer=('未取得法律地位的充分证据；已检索资料显示主要使用'+value+'。') if scope=='usage' else value
        return dict(base,status=status,value=value,scope=scope,answer=answer,records=group,other_scopes=others)
    return dict(base,status='insufficient')
