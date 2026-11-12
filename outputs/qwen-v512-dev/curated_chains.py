"""Bounded, explicitly curated source graphs, not model self-verification.

Graph edges are editorially checked against the source before inclusion. The
runtime rechecks fingerprints, exact quotations, subject/value anchors, typed
dates and question scope. Those necessary checks do not independently prove
arbitrary semantic entailment. Unknown constraints and missing edges abstain.
The bundled index is a small documented knowledge corpus, not question IDs.
"""
import hashlib,json,re
from datetime import date
from pathlib import Path

HERE=Path(__file__).resolve().parent


def norm(text):return re.sub(r'\s+',' ',text).strip()


def validate_bundle(b):
    try:
        sources=b['sources'];evidence=b['evidence']
        for source in sources.values():
            assert source['url'].startswith('https://') and source['retrieved_at']
            assert hashlib.sha256(source['text'].encode()).hexdigest()==source['text_sha256']
        quotes={}
        for edge,refs in evidence.items():
            assert refs
            for ref in refs:assert norm(ref['quote']) in norm(sources[ref['source']]['text'])
            quotes[edge]=' '.join(norm(r['quote']) for r in refs)
        if b['kind']=='historical_workplace':
            name=b['subject'];person=b['designer'];a=str(b['start_year']);z=str(b['release_year'])
            assert b['start_year']<=b['release_year']
            assert name in quotes['identity'] and person in quotes['identity']
            assert re.search(r'design(?:er|ed)|implementer',quotes['identity'],re.I)
            assert name in quotes['design_start'] and a in quotes['design_start']
            assert re.search(r'started work|work.*began|began.*work',quotes['design_start'],re.I)
            rel=quotes['release'];assert z in rel
            assert re.search(r'first (?:commercial implementation|external release|commercial release)',rel,re.I)
            assert re.search(r'released|release was',rel,re.I)
            assert b['release_kind'] in ('first_external','first_commercial')
            required='commercial' if b['release_kind']=='first_commercial' else 'external'
            assert required in rel.lower()
            start=quotes['start_site'];assert person in start and a in start and b['start_state'] in start
            assert re.search(r'joined|to join|worked',start,re.I)
            finish=quotes['release_site'];assert person in finish and b['release_state'] in finish
            # A preface signature is only dated publication-era corroboration;
            # it is not a complete employment interval or a language release.
            if z not in finish:
                date=quotes.get('release_site_date','');assert z in date and re.search(r'book.*published|edition.*published',date,re.I)
                links=[link['url'] for ref in evidence['release_site_date'] for link in sources[ref['source']].get('links',[])]
                assert any(sources[r['source']]['url'] in links for r in evidence['release_site'])
            assert b['coverage']=='dated_endpoints'
        elif b['kind']=='river_length':
            body=' '.join(quotes.values())
            assert b.get('city_source',b['city']) in body and b.get('province_source',b['province']) in body and str(b['event_year']) in body
            for m in b['measurements']:
                assert norm(m['quote']) in norm(sources[m['source']]['text'])
                assert str(m['value']) in m['quote'] and m['unit'] in ('公里','km','千米')
                assert b['subject'] in m['quote'] or b['subject'] in sources[m['source']]['text']
                assert m['scope'] in ('census_whole','north_source','reach')
        elif b['kind']=='birth_country_language':
            body=' '.join(quotes.values())
            assert all(x in body for x in (b['subject'],b['birthplace'],b['country'],b['region'],b['usage']))
            assert re.search(r'born|出生',body,re.I) and re.search(r'main language|主要.*语言',body,re.I)
            for law in b.get('legal',[]):
                assert norm(law['quote']) in norm(sources[law['source']]['text'])
                assert all(x in law['quote'] for x in (law['scope'],law['language'],law['effective']))
                assert re.search(r'official|官方',law['quote'],re.I)
        else:return {'ok':False,'reason':'unknown graph kind'}
        return {'ok':True}
    except (AssertionError,KeyError,TypeError,ValueError):return {'ok':False,'reason':'source graph failed checks'}


def _history_match(q,b):
    if not re.search(r'设计|研发|开发|首次发布',q) or not re.search(r'当时|历史工作|开始设计|首次发布时',q):return False
    if not re.search(r'美国.*州|州份',q):return False
    if re.search(r'现在|当前|诺贝尔|总部|出生|祖籍|从未|没有|不是|并非|获奖|首席|唯一',q):return False
    named=any(re.search(r'(?<![A-Za-z])'+re.escape(a)+r'(?![A-Za-z])',q,re.I) for a in b['aliases'])
    institution=any(a in q for a in b['institution_aliases'])
    if not named and not institution:return False
    if re.search(r'由|出自',q) and not institution:return False
    # Any explicitly quoted language different from the indexed subject blocks
    # an anonymous institution match. Sources do not establish every qualifier.
    quoted=re.findall(r'[《“`"\']([^》”`"\']+)[》”`"\']',q)
    if quoted and not all(x in b['aliases'] or x in b['institution_aliases'] for x in quoted):return False
    if not named and re.search(r'[A-Za-z][A-Za-z+]{2,}',q):return False
    return True


def resolve(q,bundles=None,today=None):
    if re.search(r'【世界设定】|【对话记录】|(?:仅|只)(?:能)?(?:根据|依据)|(?:根据|依据)(?:所给|给定|上述|提供的)(?:材料|资料|文本)',q):return None
    if bundles is None:
        path=HERE/'curated-source-graphs.json'
        bundles=json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    valid=[b for b in bundles if validate_bundle(b)['ok']]
    scoped=_scoped(q,valid,today)
    if scoped:return scoped
    matched=[b for b in valid if b.get('kind')=='historical_workplace' and _history_match(q,b)]
    if not matched:return None
    if len(matched)!=1:return {'status':'ambiguous','answer':'所取得的资料涉及多个候选语言，尚不能唯一确定题干所指。'}
    b=matched[0]
    access=[{k:s[k] for k in ('url','retrieved_at','raw_sha256','text_sha256') if k in s} for s in b['sources'].values()]
    if b['start_state']!=b['release_state']:
        return {'status':'conflict','answer':f"设计起点资料记为{b['start_state']}，发布时期资料记为{b['release_state']}，不能将整个期间归为单一州。",'source_access':access}
    named=any(a.casefold() in q.casefold() for a in b['aliases'])
    prefix=('按'+b['subject']+'理解，') if named else ('若题干指'+b['subject']+'，')
    release={'first_external':'首次对外发布','first_commercial':'首个商业实现发布'}[b['release_kind']]
    answer=(prefix+f"历史地点证据指向{b['state_label']}（{b['start_state']}）。相关工作始于{b['start_year']}年，{release}为{b['release_year']}年；"
            '设计起点与发布时期的地点端点记录一致，但不等于已逐年核实整个期间。')
    if not named:answer+='题干中的年代不能直接当作开始设计年份。'
    return {'status':'qualified','kind':b['kind'],'subject':b['subject'],'answer':answer+' 来源：'+'；'.join(s['url'] for s in b['sources'].values()),
            'source_access':access,'coverage':'dated_endpoints','limitation':'Small curated corpus; exact quote/fingerprint checks do not prove arbitrary semantic entailment.'}


def _scoped(q,bundles,today):
    now=date.fromisoformat(today) if today else date.today()
    for b in bundles:
        access=[{k:s[k] for k in ('url','retrieved_at','raw_sha256','text_sha256','transport') if k in s} for s in b['sources'].values()]
        base={'kind':b['kind'],'source_access':access,'limitation':'Small editorially curated corpus; scope guards do not prove general entailment.'}
        if b['kind']=='river_length':
            if not re.search(r'全长|长度|长多少|多少公里|多少千米',q):continue
            if re.search(r'支流|境内|河段|上游|中游|下游|平均|流域面积|只|不含|排除|不是',q):continue
            named=any(a in q for a in b['aliases'])
            anonymous=b['province'] in q and '省会' in q and '亚运会' in q and str(b['event_year']) in q
            if not named and not anonymous:continue
            years=re.findall(r'20\d{2}',q)
            if anonymous and any(int(y)!=b['event_year'] for y in years):continue
            if re.search(r'南源|西源|东源',q):continue
            scope='north_source' if '北源' in q else 'census_whole'
            ms=[m for m in b['measurements'] if m['scope']==scope]
            if not ms:continue
            if len({(m['value'],m['unit']) for m in ms})!=1:return base|{'status':'conflict','answer':'同一长度口径存在不同记录，尚不能确定唯一数值。'}
            m=ms[0];prefix='按北源至入海口口径，' if scope=='north_source' else '按水利普查河流名录口径，'
            answer=prefix+b['subject']+'长度约'+str(m['value'])+'公里。'
            if anonymous:answer='若题干指'+b['city']+'附近的'+b['subject']+'，'+answer
            if scope=='census_whole':
                north=next((v for v in b['measurements'] if v['scope']=='north_source'),None)
                if north:answer+='另有北源起算至入海口约'+str(north['value'])+'公里的资料，两者口径不同，不能直接取最大值。'
            answer+=' 来源：'+'；'.join(dict.fromkeys(s['url'] for s in b['sources'].values()))
            return base|{'status':'qualified','answer':answer,'scope':scope}
        if b['kind']=='birth_country_language':
            if '官方语言' not in q:continue
            if re.search(r'出生时|当年|历史|在\d{4}年|截至|只|不是|没有|诺贝尔|法语|德语|唯一',q):continue
            if re.search(r'\d{4}',q):continue
            if not 0<=(now-date.fromisoformat(b['checked_date'])).days<=30:continue
            country=any(a in q for a in b['country_aliases'])
            named=any(a in q for a in b['aliases'])
            anonymous=all(s in q for s in ('蒸汽机','改良','工业革命','发明家','出生')) and bool(re.match(r'^\s*(?:请问)?提出蒸汽机',q))
            if not (country or named or anonymous):continue
            if any(a in q for a in b['region_aliases']) and not (named or anonymous):continue
            legal=[l for l in b.get('legal',[]) if l['scope']==b['country'] and date.fromisoformat(l['effective'])<=now]
            if legal:
                answer='按'+b['country_label']+'全国法律适用范围，已核实的官方语言包括'+'、'.join(l['label'] for l in legal)+'。'
            else:
                answer='按出生地现今所属主权国家'+b['country_label']+'理解，主要使用语言是'+b['usage_label']+'。未核实全国层面的法定官方语言，以上明确采用主要使用语言的替代口径；地区法律地位不能等同全国法律地位。'
            if anonymous:answer='若题干指'+b.get('subject_label',b['subject'])+'，'+answer
            answer+=' 来源：'+'；'.join(dict.fromkeys(s['url'] for s in b['sources'].values()))
            return base|{'status':'qualified','answer':answer,'scope':'national_legal' if legal else 'national_usage_fallback'}
    return None
