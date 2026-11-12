"""DeepSeek evidence adapter retaining v4 literal-quote checks."""
import json,re,time,unicodedata
from pathlib import Path
from deepseek_search import Client
from source_cache import candidates as cached_source_candidates

HERE=Path(__file__).resolve().parent

def norm(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))

def validate_claim(claim,docs,question=''):
 source=next((s for s in docs if s['id']==claim.get('source_id')),None)
 if not source or claim.get('supported') is not True:raise ValueError('no supporting source')
 quote=claim.get('quote','');value=claim.get('source_value','');answer=claim.get('answer','')
 if not all(isinstance(x,str) and x.strip() for x in [quote,value,answer]):raise ValueError('empty evidence field')
 if len(quote)>700 or norm(quote) not in norm(source['text']):raise ValueError('quote not found in retrieved source')
 if norm(value) not in norm(quote):raise ValueError('source value not in quote')
 # Literal anchoring is a necessary condition for same-language values, not a
 # proof of entity, relation or translated meaning. Do not infer translations.
 answer_normal=norm(answer).strip('。.,，;；').casefold()
 value_normal=norm(value).strip('。.,，;；').casefold()
 answer_numbers=re.findall(r'\d+(?:\.\d+)?',answer_normal)
 value_numbers=re.findall(r'\d+(?:\.\d+)?',value_normal)
 if answer_numbers and not all(number in value_numbers for number in answer_numbers):
  raise ValueError('answer number absent from source value')
 if re.search(r'[\u4e00-\u9fff]',answer_normal) and re.search(r'[\u4e00-\u9fff]',value_normal):
  minimal=re.sub(r'(?:特别行政区|自治区|省|州|市)$','',answer_normal)
  if minimal and minimal not in value_normal:
   raise ValueError('answer absent from same-language source value')
 if '出生' in question:
  birth=re.search(r'\bborn\s+in\s+([^.;\n]+)',quote,re.I)
  if birth and norm(value).lower() not in norm(birth.group(1)).lower():raise ValueError('value describes origin rather than explicit birthplace')
 return {'answer':answer.strip(),'source_id':source['id'],'source_url':source['url'],'quote':quote,'source_value':value,
         'evidence_check':'literal_quote_and_value_present; semantic linkage/translation model-dependent'}


def aggregate_claims(claims, docs, question=''):
    if not isinstance(claims, list) or not all(isinstance(c, dict) for c in claims):
        raise ValueError('source accounting invalid')
    ids = [c.get('source_id') for c in claims]
    if not all(isinstance(source_id, str) for source_id in ids):
        raise ValueError('invalid source identifier')
    if len(ids) != len(docs) or len(set(ids)) != len(ids) or set(ids) != {d['id'] for d in docs}:
        raise ValueError('source accounting missing, duplicate or invented')
    checked = []
    for claim in claims:
        status = claim.get('status')
        if status == 'uncertain':
            raise ValueError('uncertain relevant evidence')
        if status == 'irrelevant':
            continue
        if status != 'supports':
            raise ValueError('invalid source status')
        checked.append(validate_claim({**claim, 'supported': True}, docs, question))
    if not checked:
        raise ValueError('no supporting source')
    # Require model-normalized answers to agree. Do not merge different units,
    # aliases or place scopes on the assumption that they probably mean the same.
    keys = {norm(c['answer']).strip('。.,，;；').casefold() for c in checked}
    answer=checked[0]['answer']
    alias_rule=None
    if len(keys) != 1:
        canonical=[]
        if re.search(r'谁|人名|作者|设计者|创始人',question):
            for candidate in checked:
                name=candidate['answer'].strip()
                parts=re.split(r'[·・•\s]+',name)
                if len(parts)>=2 and len(parts[-1])>=2:
                    whole=norm(name).casefold();surname=norm(parts[-1]).casefold()
                    if keys<={whole,surname}:canonical.append(name)
        if len(set(canonical))!=1:raise ValueError('conflicting source-bound answers')
        answer=canonical[0];alias_rule='single_full_name_and_exact_surname_only; heuristic, not identity proof'
    return {'answer': answer, 'claims': checked,'alias_rule':alias_rule,
            'evidence_status': 'source_bound_consensus' if len(checked) > 1 else 'source_bound_single',
            'note': 'Agreement of extracted answers; source independence and semantic correctness are not proven.'}


def source_spans(text):
    spans=[]
    for match in re.finditer(r'[^。！？；\n]+[。！？；\n]*',text):
        sentence=match.group(0)
        for start in range(0,len(sentence),200):
            value=sentence[start:start+240]
            if value.strip():spans.append({'id':f'p{len(spans)}','text':value})
            if len(spans)>=12:return spans
    return spans


def materialize_claim(claim, source):
    if claim.get('source_id')!=source['id']:raise ValueError('source identifier mismatch')
    if claim.get('status')!='supports':return dict(claim)
    span=next((s for s in source['spans'] if s['id']==claim.get('span_id')),None)
    if not span:raise ValueError('unknown source span')
    actual={**claim,'quote':span['text']}
    validate_claim({**actual,'supported':True},[source])
    return actual


def inspect_span_claims(claims, docs, question=''):
    claims=claims if isinstance(claims,list) else []
    valid={};errors=[]
    for source in docs:
        candidates=[c for c in claims if isinstance(c,dict) and c.get('source_id')==source['id']]
        try:
            if len(candidates)!=1:raise ValueError('missing or duplicate source entry')
            claim=candidates[0]
            if claim.get('status') not in ['supports','irrelevant','uncertain']:raise ValueError('invalid source status')
            actual=materialize_claim(claim,source)
            if actual.get('status')=='supports':validate_claim({**actual,'supported':True},[source],question)
            valid[source['id']]=actual
        except (ValueError,TypeError) as error:
            errors.append({'source_id':source['id'],'reason':str(error)})
    return valid,errors


def evidence_window(source, question, limit=1300):
    text = source['text']
    patterns = []
    if re.search(r'出生|籍贯', question): patterns.append(r'出生|诞生|born|birth|家乡|native')
    if re.search(r'全长|河流|公里|海拔|半径', question): patterns.append(r'全长|总长|公里|千米|海拔|半径|length|km')
    if '首都' in question: patterns.append(r'首都|capital')
    if re.search(r'州份|所在.*州', question): patterns.append(r'Jersey|州|located|迁|moved')
    if re.search(r'奖|获奖|领域',question):patterns.append(r'诺贝尔|諾貝爾|奖|獎|Nobel|Prize|awarded')
    if re.search(r'设计|建筑',question):patterns.append(r'设计|設計|建筑|建築|architect|designed')
    if re.search(r'发射|年份|成立',question):patterns.append(r'发射|發射|成立|launch|founded')
    if re.search(r'总部|位于|所在.*城市',question):patterns.append(r'总部|總部|位于|位於|headquarters|located')
    pieces = []
    if patterns:
        for match in list(re.finditer('|'.join(patterns), text, re.I))[:5]:
            part = text[max(0, match.start()-100):match.end()+220]
            if part not in pieces: pieces.append(part)
    # Keep snippets verbatim; omission is marked and no rewritten text is evidence.
    pieces.append(text[:450] if patterns else text[:1000])
    return '\n'.join(pieces)[:limit]


def retrieve(queries, deadline=None):
    deadline = min(deadline if deadline is not None else time.monotonic() + 12, time.monotonic() + 12)
    queries = list(dict.fromkeys(q.strip()[:128] for q in queries if isinstance(q, str) and q.strip()))[:2]
    docs, errors, seen = [], [], set()
    for source in cached_source_candidates(queries,HERE/'.local/primary-cache'):
        docs.append(source);seen.add(source['id'])
    corpus = HERE / 'primary-sources.json'
    if corpus.exists():
        for source in json.loads(corpus.read_text(encoding='utf-8')):
            if any(tag.lower() in query.lower() for tag in source.get('entity_tags', []) for query in queries):
                docs.append(source)
                seen.add(source['id'])
    try:
        web, errors = Client().retrieve(queries, deadline)
        for source in web:
            if source['id'] not in seen:
                docs.append(source)
                seen.add(source['id'])
    except Exception as error:
        errors.append({'error': type(error).__name__, 'stage': 'deepseek_client_setup'})
    return docs, errors

