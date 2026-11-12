"""Competition adapter. run.py remains an exact copy of the official archive."""
import concurrent.futures
import http.client
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

BASE_URL = 'https://YOUR_GATEWAY_DOMAIN/v1'
API_KEY = os.environ.get('COMPETITION_API_KEY', 'CONFIGURE_BEFORE_SUBMISSION')
MODEL = 'qwen3-8b'
DEADLINE_SECONDS = 50
MAX_OUTPUT_TOKENS = 384
ERROR_ANSWER = '服务调用失败'

try:
 from rts import Sync
except ImportError:
 class Sync:
  def __init__(self,*args): pass
  def update(self,*args): pass

def strip_metadata(prompt):
 # Remove only a recognisable dataset-source meta option, never all E options.
 return re.sub(r'(?m)(?:^|\s)[A-Z][.．、]\s*曾在其他测试数据集中见过[^\n]*','',prompt)

def request_once(prompt, guarded=True, verify=True):
 messages=[{'role':'user','content':prompt}]
 body={'model':MODEL,'messages':messages,'stream':False,'max_tokens':MAX_OUTPUT_TOKENS}
 req=urllib.request.Request(BASE_URL.rstrip('/')+'/chat/completions',data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+API_KEY,'ngrok-skip-browser-warning':'true'})
 end=time.monotonic()+DEADLINE_SECONDS-2
 opener=urllib.request.build_opener(urllib.request.ProxyHandler(urllib.request.getproxies_environment()))
 for attempt in range(2):
  try:
   with opener.open(req,timeout=max(.1,end-time.monotonic())) as r:d=json.load(r)
   break
  except (http.client.RemoteDisconnected,ConnectionResetError,ConnectionAbortedError):
   if attempt or end-time.monotonic()<2:raise
   time.sleep(.1)
 if not isinstance(d.get('evidence_route'),str) or not d['evidence_route']:raise ValueError('gateway mismatch: endpoint is serving the raw model; start the candidate gateway first')
 choice=d['choices'][0];answer=choice['message'].get('content')
 if not isinstance(answer,str) or not answer.strip():raise ValueError('empty content')
 return {'answer':answer,'usage':d.get('usage',{}),'finish_reason':choice.get('finish_reason'),'route':d.get('evidence_route')}

def call_llm(prompt,guarded=True,base_url=None):
 """A separate process enforces a wall-clock deadline, including network and queuing."""
 start=time.monotonic()
 env=dict(os.environ,PYTHONIOENCODING='utf-8')
 try:
  p=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--request'],
    input=json.dumps({'prompt':prompt,'guarded':guarded,'base_url':base_url},ensure_ascii=False),
    capture_output=True,text=True,encoding='utf-8',timeout=DEADLINE_SECONDS,env=env)
  if p.returncode:raise RuntimeError(p.stderr[-800:])
  result=json.loads(p.stdout);result.update(ok=True)
 except Exception as e:result={'ok':False,'answer':ERROR_ANSWER,'error':str(e)[:1000]}
 result['elapsed_seconds']=round(time.monotonic()-start,3)
 return result

def flush_results(items,answers,result_save_path):
 results=[{'id':qid,'问题':question,'回答':[answers[qid]]} for qid,question in items if qid in answers]
 path=Path(result_save_path);path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(results,ensure_ascii=False),encoding='utf-8');os.replace(tmp,path)
 return results

def main(to_pred_dir,result_save_path):
 items=[];seen=set()
 for p in sorted(Path(to_pred_dir).glob('*.json')):
  for q in json.loads(p.read_text(encoding='utf-8-sig')):
   qid=str(q['id'])
   if qid not in seen:items.append((qid,q['问题']));seen.add(qid)
 workers=int(os.environ.get('MAX_WORKERS','1'))
 if not 1<=workers<=16:raise ValueError('MAX_WORKERS must be 1..16')
 answers={};sync=Sync(0,len(items));pending={};it=iter(items)
 metrics=Path(result_save_path).with_name('request_metrics.jsonl')
 metrics.parent.mkdir(parents=True,exist_ok=True)
 with metrics.open('w',encoding='utf-8') as log, concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
  def refill():
   while len(pending)<workers:
    try:qid,prompt=next(it)
    except StopIteration:break
    pending[pool.submit(call_llm,prompt)]=qid
  refill()
  while pending:
   done,_=concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    qid=pending.pop(future);r=future.result();answers[qid]=r['answer']
    log.write(json.dumps({'id':qid,**r},ensure_ascii=False)+'\n');log.flush();sync.update(len(answers))
    if len(answers)%20==0:flush_results(items,answers,result_save_path)
   refill()
 return flush_results(items,answers,result_save_path)

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='--request':
  data=json.load(sys.stdin)
  if data.get('base_url'):BASE_URL=data['base_url']
  try:print(json.dumps(request_once(data['prompt'],data.get('guarded',True)),ensure_ascii=False))
  except Exception as e:print(type(e).__name__+': '+str(e),file=sys.stderr);sys.exit(1)
 else:
  result=main(sys.argv[1],sys.argv[2]);print('completed',len(result))
