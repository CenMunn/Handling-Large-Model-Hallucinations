"""Freeze and compare v53/v55 on an isolated blind set; no platform submission.

Only question and optional source text enter the model process. Automatic scores
are screening labels and require human review; fixture use is separately tracked.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / 'validation-v58.json'
OUT = HERE / 'validation-new-run'
VARIANTS = {'v57': ROOT / 'qwen-v57-dev', 'v58': HERE}
REFUSAL = re.compile(r'信息不足|资料不足|证据不足|无法(?:确定|回答|确认|可靠|判断|提供|计算|根据)|不能确定|未(?:给出|提供|记载|说明|能确认|能可靠确认)|没有(?:给出|提供|记载)|缺少|未能取得|存在冲突', re.I)
HEDGE = re.compile(r'可能(?:是|为)|猜测|猜想|大概|也许|或许|推测', re.I)
NEGATION = re.compile(r'不是|并非|不属于|不正确|错误|排除|不选|不是答案|并不是', re.I)
UNJUSTIFIED_CHOICE = re.compile(r'^\s*(?:答案\s*[:：]\s*)?[A-HＡ-Ｈ]\s*[.．、:：)）]\s*', re.I)

def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', str(value))).casefold()

def check(row, answer):
    """Conservative screen only, never an assertion of semantic correctness."""
    if not isinstance(answer, str) or not answer.strip():
        return {'grade': 'fail_empty', 'review': True}
    has_refusal = bool(REFUSAL.search(answer))
    has_hedge = bool(HEDGE.search(answer))
    format_error = bool(row.get('forbid_unjustified_letter') and UNJUSTIFIED_CHOICE.search(answer))
    kind, expected = row['scorer'], row['expected']
    detail = {'review': True, 'format_error': format_error,
              'refusal_detected': has_refusal, 'hedge_detected': has_hedge}
    if format_error:
        detail['grade'] = 'fail_unjustified_choice_prefix'
        return detail
    if kind == 'abstain':
        if not has_refusal:
            detail['grade'] = 'fail_no_explicit_abstention'
        elif has_hedge:
            detail['grade'] = 'review_mixed_abstention_and_guess'
        else:
            # Could still include a specific unsupported assertion, so do not
            # mark as pass on the presence of a refusal substring alone.
            detail['grade'] = 'review_abstention'
        return detail
    if has_refusal:
        detail['grade'] = 'review_false_refusal_or_mixed'
        return detail
    if has_hedge or NEGATION.search(answer):
        detail['grade'] = 'review_hedged_or_negated'
        return detail
    if kind == 'choices':
        text = unicodedata.normalize('NFKC', answer).upper()
        selected = set(re.findall(r'(?<![A-Z])([A-H])(?![A-Z])', text))
        compact = re.sub(r'[\s、,，。.]', '', text)
        if re.fullmatch(r'[A-H]+', compact):
            selected = set(compact)
        detail.update(selected=sorted(selected), expected=sorted(expected))
        detail['grade'] = 'review_choice_set_match' if selected == set(expected) else 'fail_choice_set'
    elif kind == 'exact':
        cleaned = normalized(answer).strip('。.,，;；')
        detail['grade'] = 'review_exact_match' if cleaned in {normalized(x).strip('。.,，;；') for x in expected} else 'fail_exact'
    elif kind == 'contains':
        detail['grade'] = 'review_contains_match' if any(normalized(x) in normalized(answer) for x in expected) else 'fail_missing_expected'
    elif kind == 'numeric':
        nums = re.findall(r'[-+]?\d+(?:\.\d+)?', unicodedata.normalize('NFKC', answer).replace(',', ''))
        value = float(expected)
        detail['grade'] = ('review_numeric_match' if nums and abs(float(nums[-1])-value) <= max(.001,abs(value)*.00001) else 'fail_numeric')
    else:
        detail['grade'] = 'unscored'
    return detail

def worker():
    payload = json.load(sys.stdin)
    sys.path.insert(0, str(VARIANTS[payload['variant']]))
    import engine
    fixture_calls = []
    if 'evidence' in payload:
        documents = payload['evidence']
        def fixture_retrieve(queries, deadline=None):
            fixture_calls.append(True)
            return documents, []
        engine.retrieve = fixture_retrieve
    try:
        instance = engine.Engine()
        answer, audit = instance.answer(payload['question'])
        print(json.dumps({'ok':True, 'answer':answer, 'audit':audit,
                          'fixture_used':bool(fixture_calls)}, ensure_ascii=False))
    except Exception as exc:
        # Record the type only: exception strings can include endpoint details.
        print(json.dumps({'ok':False,'error_type':type(exc).__name__,
                          'fixture_used':bool(fixture_calls)}))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def manifest():
    code = {}
    for name, folder in VARIANTS.items():
        candidates = sorted(p for p in folder.iterdir() if p.is_file() and (
            (p.suffix == '.py' and not p.name.startswith(('test_', 'evaluate_', 'benchmark_'))) or p.name == 'primary-sources.json'))
        code[name] = {p.name:digest(p) for p in candidates}
    return {'dataset_sha256':digest(DATA), 'runner_sha256':digest(Path(__file__)), 'variants':code}

def main():
    if OUT.exists():
        raise SystemExit('Output directory already exists; do not repeat this frozen blind set.')
    rows = json.loads(DATA.read_text(encoding='utf-8'))
    frozen = manifest()
    OUT.mkdir()
    (OUT/'manifest.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/'results.jsonl').open('x',encoding='utf-8') as stream:
        for row in rows:
            for name in VARIANTS:
                payload={'variant':name,'question':row['question']}
                if row['eval_mode']=='injected_evidence':
                    payload['evidence']=row['evidence']
                started=time.monotonic()
                try:
                    child=subprocess.run([sys.executable,__file__,'--worker'],
                        input=json.dumps(payload,ensure_ascii=False),capture_output=True,
                        text=True,encoding='utf-8',errors='replace',timeout=50,
                        env={**os.environ,'PYTHONIOENCODING':'utf-8'})
                    value=json.loads(child.stdout) if child.returncode==0 else {'ok':False,'error_type':'worker_failed'}
                except subprocess.TimeoutExpired:
                    value={'ok':False,'error_type':'worker_timeout'}
                except (ValueError,TypeError):
                    value={'ok':False,'error_type':'invalid_worker_output'}
                result={'id':row['id'],'category':row['category'],'related_group':row['related_group'],
                        'eval_mode':row['eval_mode'],'variant':name,'ok':value.get('ok') is True,
                        'seconds':round(time.monotonic()-started,3),'answer':value.get('answer',''),
                        'fixture_used':value.get('fixture_used',False),'audit':value.get('audit',{}),
                        'error_type':value.get('error_type')}
                result['score']=check(row,result['answer']) if result['ok'] else {'grade':'service_failure','review':True}
                stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
                # Report progress only: do not echo questions, answers or secrets.
                print(name, row['id'], result['ok'], result['score']['grade'],flush=True)
    if frozen != manifest():
        raise SystemExit('Code or dataset changed during evaluation; results invalid.')
    print('Finished; grades are provisional and require human review.',flush=True)

if __name__=='__main__':
    worker() if '--worker' in sys.argv else main()
