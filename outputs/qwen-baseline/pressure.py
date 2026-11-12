"""Small public-API concurrency probe; not a statistical P99 capacity certification."""
import concurrent.futures,importlib.util,json,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adapter',ROOT/'platform/model.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

if __name__=='__main__':
 rows=[]
 for workers in [1,2,4,8,16]:
  # About 8 KB UTF-8 input with the required fact in the middle.
  noise='无关背景信息：本条记录没有订单内容。\n'*60
  prompt='只根据材料回答。\n'+noise+'\n订单A的最终取货码是M917。\n'+noise+'\n订单A的最终取货码是什么？只回答代码。'
  count=max(4,workers);start=time.monotonic()
  with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:results=list(pool.map(m.call_llm,[prompt]*count))
  row={'workers':workers,'requests':count,'input_bytes':len(prompt.encode()),'wall_seconds':time.monotonic()-start,
       'successful_requests':sum(r['ok'] for r in results),'correct_code':sum('M917' in r['answer'] for r in results),
       'max_latency_seconds':max(r['elapsed_seconds'] for r in results),'requests_per_second':count/(time.monotonic()-start),'details':results}
  rows.append(row);(ROOT/'results/concurrency.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps({k:v for k,v in row.items() if k!='details'},ensure_ascii=False),flush=True)
  if row['successful_requests']!=count or row['max_latency_seconds']>=40:break
