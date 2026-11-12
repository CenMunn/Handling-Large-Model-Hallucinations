"""Bounded community knowledge-graph evidence, not an independent truth oracle.

No model-proposed entity, QID, translation or relation is trusted. Only exact
name matches and supported typed paths are queried. Birthplace geography is
explicitly current geography; this is not country-at-birth reconstruction.
"""
import hashlib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
API='https://www.wikidata.org/w/api.php'
SPARQL='https://query.wikidata.org/sparql'
ALLOWED={'P36','P50','P19','P17'}
MAX_ROWS=17


def normalized(s):
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',s)).casefold()


def plan(q):
    # Unsupported forms still use the ordinary retrieval pipeline. This parser
    # limits the optional graph query, not whether facts may be retrieved.
    if re.search(r'【世界设定】|【对话记录】|根据.*材料|依据.*材料|仅根据|只根据|截至|出生时|当时|历史|是否|对吗|说法|有人说|据说',q):return None
    works=re.findall(r'《([^》]{1,70})》',q)
    if len(works)==1 and re.search(r'创作|作者|作家',q) and '出生' in q and '国家' in q and '首都' in q:
        return {'anchor':works[0],'properties':['P50','P19','P17','P36'],
                'scope':'current_birthplace_country',
                'root_class':'Q8261' if '小说' in q else 'Q47461344' if re.search(r'作家|著作',q) else None,
                'geographic_note':'current country of birthplace, not historical country at birth'}
    m=re.fullmatch(r'\s*([\u4e00-\u9fffA-Za-z· ]{2,35}?)(?:的)?首都(?:是|为|在)?(?:什么|哪里|哪(?:个|座)城市)[？?。]?\s*',q)
    if m and not re.search(r'其|他|她|这|那|出生|所在|作者|的',m[1]):
        return {'anchor':m[1],'properties':['P36'],'scope':'current','root_class':'country'}
    return None


def resolve_exact(anchor,response):
    if not isinstance(response,dict) or response.get('search-continue') is not None:return None
    rows=response.get('search')
    if not isinstance(rows,list):return None
    exact=set()
    for row in rows:
        if not isinstance(row,dict):continue
        match=row.get('match') or {}
        names=[row.get('label','')]
        if match.get('type') in ('label','alias'):names.append(match.get('text',''))
        if normalized(anchor) in {normalized(x) for x in names if isinstance(x,str)}:
            qid=row.get('id','')
            if re.fullmatch(r'Q[1-9]\d*',qid):exact.add(qid)
    return next(iter(exact)) if len(exact)==1 else None


def build_query(root,properties):
    if not re.fullmatch(r'Q[1-9]\d*',root) or not properties or len(properties)>4 or any(p not in ALLOWED for p in properties):
        raise ValueError('untrusted graph identifier or property')
    return _query('VALUES ?n0 { wd:'+root+' }',properties)


def _query(seed,properties,optional_path=False):
    parts=[]
    for i,p in enumerate(properties):
        parts.extend([
            f'?n{i} p:{p} ?s{i}. ?s{i} ps:{p} ?n{i+1}; wikibase:rank ?r{i}.',
            f'FILTER(?r{i} != wikibase:DeprecatedRank)',
            f'FILTER NOT EXISTS {{ ?s{i} pq:P582 ?ended{i}. FILTER(?ended{i} <= NOW()) }}',
            f'FILTER NOT EXISTS {{ ?s{i} pq:P580 ?starts{i}. FILTER(?starts{i} > NOW()) }}',
            f'OPTIONAL {{ ?s{i} ?qp{i} ?qv{i}. FILTER(STRSTARTS(STR(?qp{i}), "http://www.wikidata.org/prop/qualifier/")) }}',
        ])
    fields=' '.join(f'?n{i} ?n{i}Label' for i in range(len(properties)+1))
    fields+=' '+' '.join(f'?s{i} ?r{i} ?qp{i} ?qv{i}' for i in range(len(properties)))
    body=' '.join(parts)
    if optional_path:body='OPTIONAL { '+body+' }'
    return 'SELECT DISTINCT '+fields+' WHERE { '+seed+' '+body+' SERVICE wikibase:label { bd:serviceParam wikibase:language "zh-hans,zh,en". } } LIMIT 17'


def build_exact_query(p):
    anchor=p['anchor'];properties=p['properties']
    if not isinstance(anchor,str) or len(anchor)>70 or re.search(r'[\x00-\x1f]',anchor) or not properties or len(properties)>4 or any(x not in ALLOWED for x in properties):raise ValueError('invalid structured plan')
    literal=json.dumps(anchor,ensure_ascii=False)
    labels=' '.join(literal+'@'+lang for lang in ('zh','zh-hans','zh-cn','en'))
    seed='VALUES ?anchorLabel { '+labels+' } ?n0 (rdfs:label|skos:altLabel) ?anchorLabel.'
    seed+=class_constraint(p)
    # Keep exact-name entities that lack a requested edge; their missing data
    # cannot be used to pretend a different namesake is uniquely identified.
    return _query(seed,properties,optional_path=True)


def class_constraint(p):
    root_class=p.get('root_class');seed=''
    if root_class:
        if root_class not in ('Q47461344','Q8261','country'):raise ValueError('unsupported entity class')
        if root_class=='country':
            seed+=' ?n0 wdt:P31/wdt:P279* wd:Q6256. FILTER NOT EXISTS { ?n0 wdt:P576 ?dissolved. FILTER(?dissolved <= NOW()) }'
        else:seed+=' ?n0 wdt:P31/wdt:P279* wd:'+root_class+'.'
    return seed


def build_candidates_query(p,ids):
    properties=p['properties']
    if not ids or len(ids)>5 or any(not re.fullmatch(r'Q[1-9]\d*',i) for i in ids) or not properties or len(properties)>4 or any(x not in ALLOWED for x in properties):raise ValueError('invalid graph candidates')
    seed='VALUES ?n0 { '+' '.join('wd:'+i for i in ids)+' }'+class_constraint(p)
    return _query(seed,properties,optional_path=True)


def value(row,key):
    cell=row.get(key,{})
    return cell.get('value','') if isinstance(cell,dict) else ''


def entity_id(uri):
    m=re.fullmatch(r'https?://www\.wikidata\.org/entity/(Q[1-9]\d*)',uri)
    return m[1] if m else None


def inspect(p,rows):
    base={'provider':'wikidata','plan':p,'limitation':'Community-maintained structured statements; connected IDs do not prove source truth or historical geography.'}
    if not isinstance(rows,list) or len(rows)>=MAX_ROWS:return dict(base,status='incomplete')
    if not rows:return dict(base,status='insufficient')
    roots={entity_id(value(row,'n0')) for row in rows if isinstance(row,dict)}
    if len(roots)>1:return dict(base,status='identity_unresolved')
    paths={};unknown_qualifier=False
    now=datetime.now(timezone.utc)
    for row in rows:
        if not isinstance(row,dict):return dict(base,status='incomplete')
        count=len(p['properties'])
        nodes=[entity_id(value(row,f'n{i}')) for i in range(count+1)]
        statements=[value(row,f's{i}') for i in range(count)]
        if any(n is None for n in nodes) or any(not re.fullmatch(r'https?://www\.wikidata\.org/entity/statement/Q[1-9]\d*-[A-Za-z0-9-]+',s) for s in statements):return dict(base,status='incomplete')
        for i in range(count):
            if value(row,f'r{i}') not in ('http://wikiba.se/ontology#NormalRank','http://wikiba.se/ontology#PreferredRank'):return dict(base,status='incomplete')
        labels=[value(row,f'n{i}Label') for i in range(count+1)]
        if any(not label or re.fullmatch(r'Q\d+',label) for label in labels):return dict(base,status='incomplete')
        key=tuple(nodes+statements)
        path=paths.setdefault(key,{'nodes':nodes,'labels':labels,'properties':list(p['properties']),'statements':statements,'qualifiers':[],'active':True})
        for i in range(count):
            qualifier=value(row,f'qp{i}');qvalue=value(row,f'qv{i}')
            if not qualifier:continue
            path['qualifiers'].append({'step':i,'property':qualifier,'value':qvalue})
            kind=qualifier.rsplit('/',1)[-1]
            if kind not in ('P580','P582'):
                unknown_qualifier=True;continue
            try:date=datetime.fromisoformat(qvalue.replace('Z','+00:00'))
            except (ValueError,TypeError):unknown_qualifier=True;continue
            if date.tzinfo is None:unknown_qualifier=True;continue
            if (kind=='P580' and date>now) or (kind=='P582' and date<=now):path['active']=False
    if unknown_qualifier:return dict(base,status='qualified_unresolved',paths=list(paths.values()))
    active=[path for path in paths.values() if path['active']]
    if not active:return dict(base,status='insufficient',paths=list(paths.values()))
    # Different intermediate entities also matter; agreement of final labels
    # alone cannot hide identity disagreement.
    if len({tuple(path['nodes']) for path in active})!=1:return dict(base,status='conflict',paths=active)
    labels=active[0]['labels'];answer=labels[-1]
    if p['scope']=='current_birthplace_country':
        answer=f'按出生地现今所属国家查询：{labels[1]}的出生地现属{labels[-2]}，该国首都是{labels[-1]}。'
    return dict(base,status='supported',answer=answer,paths=active)


class Client:
    def __init__(self,cache_dir=None):
        self.cache=Path(cache_dir) if cache_dir else HERE/'.local/wikidata-cache'

    def get(self,endpoint,parameters,deadline):
        remaining=deadline-time.monotonic()
        if remaining<.2:raise TimeoutError('structured evidence deadline')
        url=endpoint+'?'+urllib.parse.urlencode(parameters)
        key=hashlib.sha256(url.encode()).hexdigest();path=self.cache/(key+'.json')
        try:
            cached=json.loads(path.read_text(encoding='utf-8'))
            if time.time()-cached['fetched_epoch']<86400:return cached['response'],dict(cached['provenance'],cache_hit=True)
        except (OSError,ValueError,KeyError,TypeError):pass
        request=urllib.request.Request(url,headers={'User-Agent':'HallucinationResearch/0.1 (bounded read-only evaluation)','Accept':'application/json'})
        with urllib.request.urlopen(request,timeout=min(8,remaining)) as response:raw=response.read(2_000_001)
        if time.monotonic()>deadline:raise TimeoutError('structured evidence deadline')
        if len(raw)>2_000_000:raise ValueError('structured response too large')
        result=json.loads(raw)
        if not isinstance(result,dict) or 'error' in result:raise ValueError('structured API error')
        provenance={'endpoint':endpoint,'parameters':parameters,'accessed_at':datetime.now(timezone.utc).isoformat(),'response_sha256':hashlib.sha256(raw).hexdigest()}
        self.cache.mkdir(parents=True,exist_ok=True)
        # Atomic replacement prevents partial files across gateway processes.
        import os,uuid
        temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps({'fetched_epoch':time.time(),'response':result,'provenance':provenance},ensure_ascii=False),encoding='utf-8')
            os.replace(temp,path)
        finally:
            if temp.exists():temp.unlink()
        return result,provenance

    def lookup(self,q,deadline):
        p=plan(q)
        if not p:return {'status':'unsupported'}
        deadline=min(deadline,time.monotonic()+16)
        provenance=[]
        try:
            search,trace=self.get(API,{'action':'wbsearchentities','search':p['anchor'],'language':'zh','uselang':'zh','format':'json','limit':5},deadline)
            provenance.append(trace)
            candidates=[]
            for hit in search.get('search',[]):
                if not isinstance(hit,dict):continue
                # Check each exact candidate separately; rank is not identity.
                candidate=resolve_exact(p['anchor'],{'search':[hit]})
                if candidate and candidate not in candidates:candidates.append(candidate)
            if not candidates:return {'status':'identity_unresolved','plan':p,'provenance':provenance}
            query=build_candidates_query(p,candidates)
            data,trace=self.get(SPARQL,{'query':query,'format':'json'},deadline);provenance.append(trace)
            out=inspect(p,data.get('results',{}).get('bindings'))
            out.update(provenance=provenance,candidate_ids=candidates,
                       search_exhaustive=search.get('search-continue') is None,
                       identity_limitation='Typed resolution among at most five exact-name search candidates, not global exhaustive identity proof.')
            if out.get('status')=='supported':
                root=out['paths'][0]['nodes'][0];out['root']=root
                out['answer']+=' 来源：Wikidata（https://www.wikidata.org/wiki/'+root+'）。'
            return out
        except (OSError,ValueError,TypeError,KeyError,TimeoutError) as error:
            return {'status':'unavailable','plan':p,'error_type':type(error).__name__,'provenance':provenance}
