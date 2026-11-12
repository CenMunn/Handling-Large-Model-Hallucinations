import argparse,concurrent.futures,importlib.util,json,statistics,time,unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adapter',ROOT/'platform/model.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def run(guarded=True,limit=None,workers=1,label='guarded'):
 rows=json.loads((ROOT/'dev_cases.json').read_text(encoding='utf-8'))
 if limit: # smoke covers categories rather than the first homogeneous cases
  rows=sorted(rows,key=lambda r:(int(r['id'])%5,int(r['id'])))[:limit] if limit>20 else [rows[i] for i in [0,1,2,3,4,100,101,108,109,112,113,114,115,116][:limit]]
 dest=ROOT/'results';dest.mkdir(exist_ok=True);records=[];started=time.monotonic()
 def task(row):return row,m.call_llm(row['问题'],guarded,base_url='http://127.0.0.1:8080/v1')
 with (dest/f'{label}.jsonl').open('w',encoding='utf-8') as f, concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
  for row,r in pool.map(task,rows):
   a=unicodedata.normalize('NFKC',r['answer']).lower().replace(' ','');r.update(id=row['id'],category=row['category'],expected=row['expected'],should_abstain=row['should_abstain'],question=row['问题'])
   expected=list(row['expected'])
   if row['should_abstain']:expected+=['未提及','没有提到','无法回答','未给出','没有给出','没有提供','未说明','没有说明']
   r['proxy_pass']=bool(r['ok'] and any(s.lower().replace(' ','') in a for s in expected))
   records.append(r);f.write(json.dumps(r,ensure_ascii=False)+'\n');f.flush()
   print(label,len(records),'/',len(rows),r['category'],r['ok'],r['proxy_pass'],r['elapsed_seconds'],flush=True)
 times=sorted(r['elapsed_seconds'] for r in records)
 summary={'label':label,'count':len(rows),'workers':workers,'wall_seconds':round(time.monotonic()-started,2),
 'successful_requests':sum(r['ok'] for r in records),'proxy_pass':sum(r['proxy_pass'] for r in records),
 'p50_seconds':statistics.median(times),'p99_seconds':times[min(len(times)-1,int(.99*len(times)))],
 'truncated':sum(r.get('finish_reason')=='length' for r in records),
 'note':'Synthetic templated development cases; substring scoring is a diagnostic proxy, not an official score or human-verified accuracy.'}
 (dest/f'{label}-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--raw',action='store_true');p.add_argument('--limit',type=int);p.add_argument('--workers',type=int,default=1);p.add_argument('--label',default='guarded');a=p.parse_args()
 if not 1<=a.workers<=16:raise SystemExit('workers must be 1..16')
 run(not a.raw,a.limit,a.workers,a.label)
