import argparse,concurrent.futures,hashlib,importlib.util,json,re,time
from pathlib import Path
from acceptance_cases import cases

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('acceptance_adapter',HERE.parent/'qwen-deepseek-v5/platform/model.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

def run(row):
    start=time.monotonic();out=adapter.call_llm(row['question'],base_url='http://127.0.0.1:8087/v1')
    answer=out.get('answer','')
    if row['kind']=='choices':screen=set(re.findall(r'[A-H]',answer))==set(row['expected'])
    else:screen=all(x in answer for x in row['expected'])
    return {'id':row['id'],'input_bytes':len(row['question'].encode()),'expected':row['expected'],'screen_match':screen,'seconds':round(time.monotonic()-start,3),**out}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--long-only',action='store_true');args=parser.parse_args()
    outdir=HERE/'.local'/('engine-acceptance-'+str(time.time_ns()));outdir.mkdir()
    rows=cases()
    if args.long_only:
        base=rows[-1];rows=[dict(base,id='history-long-'+str(i),question=base['question']+'\n记录编号：'+str(i)) for i in range(4)]
    (outdir/'questions.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
    started=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,rows))
    for row in results:print(json.dumps(row,ensure_ascii=False),flush=True)
    assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in manifest.items()),'source changed during acceptance'
    summary={'count':len(results),'success':sum(r.get('ok') is True for r in results),'screen_matches':sum(r['screen_match'] for r in results),'wall_seconds':round(time.monotonic()-started,3),'max_seconds':max(r['seconds'] for r in results),'note':'Contains/set screen requires answer review; local warm/cold mixed caches, not hidden accuracy or container acceptance.'}
    (outdir/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');(outdir/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');(outdir/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(summary));print('Output:',outdir)
