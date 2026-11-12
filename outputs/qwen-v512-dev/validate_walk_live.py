"""Small named-entity acceptance probes; never submits a competition entry."""
import argparse,concurrent.futures,json,time
from pathlib import Path
from wikibase_walk import bounded_lookup

CASES=[
 ('demo-work','创作《堂吉诃德》并被誉为西班牙文学巨匠的作家，其出生国家的首都是什么？'),
 ('new-work-1','创作小说《百年孤独》的作家，其出生地现今所属国家的首都是什么？'),
 ('new-work-2','创作《老人与海》的作家，其出生地现今所属国家的首都是什么？'),
 ('new-capital','法国的首都是什么？'),
 ('demo-founder','提出了生态化反的乐视网创始人，其出生县位于哪个省份？'),
 ('new-founder','京东创始人的出生地位于哪个省份？'),
]
def run(case):
 name,q=case;start=time.monotonic();out=bounded_lookup(q,start+20)
 return {'name':name,'question':q,'seconds':round(time.monotonic()-start,3),'result':out}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=1);p.add_argument('--workers',type=int,default=1);args=p.parse_args()
 rows=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
  for row in pool.map(run,CASES[:args.limit]):
   rows.append(row);out=row['result'];print(json.dumps({'name':row['name'],'seconds':row['seconds'],'status':out['status'],'answer':out.get('answer'),'detail':out.get('detail'),'error':out.get('error_type'),'http_status':out.get('http_status'),'requests':[(x.get('status'),x.get('seconds')) for x in out.get('network_requests',[])]},ensure_ascii=False),flush=True)
 dest=Path('.local')/('walk-live-'+str(time.time_ns())+'.json');dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8');print('Output:',dest)
