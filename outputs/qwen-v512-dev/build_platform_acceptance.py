"""Build one uploadable lab test file; never touches competition inputs."""
import json
from pathlib import Path
from acceptance_cases import cases

DEST=Path(__file__).resolve().parent.parent/'qwen-v59-launcher'
RUNNER=r'''
import argparse,concurrent.futures,datetime,json,re,secrets,time
from pathlib import Path

def screen(row,answer):
    if row['kind']=='choices':return set(re.findall(r'[A-H]',answer))==set(row['expected'])
    return all(x in answer for x in row['expected']) and not any(('不是'+x) in answer or ('并非'+x) in answer for x in row['expected'])

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    if args.dry_run:
        print(json.dumps({'cases':len(CASES),'mixed_requests':6,'long_requests':4,'input_bytes':[len(r['question'].encode('utf-8')) for r in CASES]},ensure_ascii=False));return
    from platform_stress import load_adapter,gateway_health
    adapter=load_adapter(Path('model/model.py'))
    version=gateway_health(adapter,'qwen-v59-dev')
    destination=Path('output')/('v59-acceptance-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3))
    destination.mkdir(parents=True,exist_ok=False)
    rounds=[]
    def call(row):
        start=time.monotonic()
        try:
            value=adapter.call_llm(row['question']);answer=value.get('answer','');ok=value.get('ok') is True
            usage=value.get('usage') or {}
            return {'id':row['id'],'ok':ok,'content_check':ok and screen(row,answer),'answer':answer,
                    'seconds':round(time.monotonic()-start,3),'route':value.get('route'),
                    'prompt_tokens':usage.get('prompt_tokens'),'finish_reason':value.get('finish_reason'),
                    'error_type':None if ok else 'service_error'}
        except Exception as error:
            return {'id':row['id'],'ok':False,'content_check':False,'seconds':round(time.monotonic()-start,3),'error_type':type(error).__name__}
    base=CASES[-1]
    long_cases=[dict(base,id='long-history-'+str(i),question=base['question']+'\n记录编号：'+str(i)) for i in range(4)]
    print('Gateway:',version,flush=True);print('Output:',destination,flush=True)
    for name,rows in [('mixed',CASES),('long_history',long_cases)]:
        start=time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(call,rows))
        record={'name':name,'workers':4,'count':len(results),'success':sum(r['ok'] for r in results),
                'content_checks':sum(r['content_check'] for r in results),'failures':sum(not r['ok'] for r in results),
                'finish_length':sum(r.get('finish_reason')=='length' for r in results),
                'max_seconds':max(r['seconds'] for r in results),'wall_seconds':round(time.monotonic()-start,3),
                'max_prompt_tokens':max((r.get('prompt_tokens') or 0 for r in results),default=0),'cases':results}
        rounds.append(record)
        (destination/'summary.json').write_text(json.dumps({'gateway':version,'rounds':rounds,
            'scope':'Lab acceptance only; does not replace organizer input or submit a competition entry.',
            'limitations':['Expected-text/option checks need answer review.','Queries and caches may be warm.','Small samples do not establish hidden accuracy or worst-case capacity.']},ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in record.items() if k!='cases'},ensure_ascii=False),flush=True)
        for row in results:
            print(json.dumps({k:row[k] for k in ('id','answer','content_check') if k in row},ensure_ascii=False),flush=True)
    print('Done. Review',destination/'summary.json',flush=True)
    if any(r['failures'] or r['content_checks']!=r['count'] or r['finish_length'] for r in rounds):raise SystemExit(1)

if __name__=='__main__':main()
'''

if __name__=='__main__':
    DEST.mkdir(exist_ok=True)
    # An ordinary Python literal keeps the one-file script independent of any
    # new module upload. No client credentials or endpoint secrets are bundled.
    source='# Lab-only v5.9 acceptance: ten requests, no submission.\nCASES = '+repr(cases())+'\n'+RUNNER
    compile(source,'platform_v59_acceptance.py','exec')
    path=DEST/'platform_v59_acceptance.py';path.write_text(source,encoding='utf-8');print(path)
