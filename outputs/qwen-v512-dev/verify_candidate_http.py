"""Local four-worker candidate HTTP checks; no public route changes."""
import argparse,concurrent.futures,hashlib,importlib.util,json,re,time
from pathlib import Path
from acceptance_cases import cases

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adapter',HERE.parent/'qwen-deepseek-v5/platform/model.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--long',action='store_true');args=parser.parse_args()
    data=json.loads(Path('D:/下载/wKgAB2rkuqSAN9HhAATvyKyWFWk53.json').read_text(encoding='utf-8-sig'))
    by_id={str(r['id']):r['问题'] for r in data};base=cases()[-1]
    rows=[{'id':'author-47','question':by_id['47'],'expected':['艾米莉','勃朗特']},
          {'id':'organization-9','question':by_id['9'],'expected':['1847','共产主义者同盟']},
          {'id':'cell-count-22','question':by_id['22'],'expected':['数百至数千','每个']},cases()[3],cases()[4],base]
    if args.long:rows=[dict(base,id='long-history-'+str(i),question=base['question']+'\n记录编号：'+str(i)) for i in range(4)]
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
    def run(row):
        r=adapter.call_llm(row['question'],base_url='http://127.0.0.1:8090/v1');answer=r.get('answer','')
        good=r.get('ok') is True and all(x in answer for x in row['expected'])
        if row.get('kind')=='choices':good=r.get('ok') is True and set(re.findall(r'[A-H]',answer))==set(row['expected'])
        return dict(id=row['id'],content_check=good,**r)
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,rows))
    assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v for n,v in manifest.items())
    out=HERE/'.local'/('http-'+('long-' if args.long else 'mixed-')+str(time.time_ns()));out.mkdir()
    summary={'count':len(results),'calls_ok':sum(r.get('ok') is True for r in results),'content_checks':sum(r['content_check'] for r in results),'max_seconds':max(r.get('elapsed_seconds',0) for r in results),'wall_seconds':round(time.monotonic()-start,3),'scope':'Local HTTP, small partly warm-cache set, repeated history variants. Not hidden correctness or worst-case latency.'}
    for name,value in [('results',results),('summary',summary),('manifest',manifest)]:(out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:print(json.dumps(r,ensure_ascii=False),flush=True)
    print(json.dumps(summary));print('Output:',out)

if __name__=='__main__':main()
