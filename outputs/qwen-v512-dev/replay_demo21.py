"""Read-only diagnostic replay of previously downloaded organizer questions."""
import concurrent.futures,hashlib,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE/'.local'/('demo21-'+str(time.time_ns()));OUT.mkdir(parents=True)
spec=importlib.util.spec_from_file_location('adapter',HERE.parent/'qwen-deepseek-v5/platform/model.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
order=['10','26','30','35','39','42','46','47','4','5','9','14','15','22','31','36','1','3','7','11','23']
data=json.loads(Path('D:/下载/wKgAB2rkuqSAN9HhAATvyKyWFWk53.json').read_text(encoding='utf-8-sig'))
by_id={str(r['id']):r for r in data};rows=[by_id[i] for i in order]
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
def run(row):return {'id':str(row['id']),**adapter.call_llm(row['问题'],base_url='http://127.0.0.1:8088/v1')}
start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,rows))
assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v for n,v in manifest.items())
for r in results:print(json.dumps(r,ensure_ascii=False),flush=True)
summary={'calls':len(results),'success':sum(r.get('ok') is True for r in results),'max_seconds':max(r.get('elapsed_seconds',0) for r in results),'wall_seconds':round(time.monotonic()-start,3),'scope':'Known diagnostic questions, local HTTP, caches partly warm; not independent hidden accuracy.'}
for name,value in [('results',results),('manifest',manifest),('summary',summary)]:
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary));print('Output:',OUT)
