"""Four-worker local replay of known diagnostic questions, not hidden accuracy."""
import concurrent.futures,hashlib,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE/'review50-local'
if OUT.exists():raise SystemExit('Do not overwrite replay results')
OUT.mkdir()
files=sorted(p for p in HERE.glob('*.py') if not p.name.startswith(('test_','evaluate_','replay_')))
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(OUT/'code-sha256.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
spec=importlib.util.spec_from_file_location('adapter',HERE.parent/'qwen-deepseek-v5/platform/model.py');client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)
rows=json.loads(Path(r'D:\下载\wKgAB2rkuqSAN9HhAATvyKyWFWk53.json').read_text(encoding='utf-8-sig'))
def work(row):
 result=client.call_llm(row['问题'],base_url='http://127.0.0.1:8086/v1')
 return {'id':str(row['id']),**result}
started=time.monotonic();results=[]
with (OUT/'results.jsonl').open('x',encoding='utf8') as stream,concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 futures=[pool.submit(work,row) for row in rows]
 for future in concurrent.futures.as_completed(futures):
  result=future.result();results.append(result);stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
  print(result['id'],result.get('ok'),result.get('elapsed_seconds'),flush=True)
assert all(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==value for name,value in manifest.items()),'Code changed during replay'
summary={'count':len(results),'success':sum(r.get('ok') is True for r in results),'failed':sum(r.get('ok') is not True for r in results),'wall_seconds':round(time.monotonic()-started,3),'max_seconds':max(r.get('elapsed_seconds',0) for r in results),'scope':'Known 50-question diagnostic set, local HTTP, not a hidden test or platform submission.'}
(OUT/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf8');print(json.dumps(summary),flush=True)
