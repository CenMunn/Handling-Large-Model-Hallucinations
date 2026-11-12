"""Local Engine acceptance; no public switch, container mutation or submission."""
import argparse,concurrent.futures,hashlib,json,time
from pathlib import Path
from engine import Engine
from acceptance_cases import cases

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--suite',choices=['demo21','new'],required=True);args=parser.parse_args()
    if args.suite=='demo21':
        order=['10','26','30','35','39','42','46','47','4','5','9','14','15','22','31','36','1','3','7','11','23']
        data=json.loads(Path('D:/下载/wKgAB2rkuqSAN9HhAATvyKyWFWk53.json').read_text(encoding='utf-8-sig'))
        indexed={str(r['id']):r for r in data};rows=[{'id':i,'question':indexed[i]['问题']} for i in order]
    else:
        rows=[{'id':'cell-functional-paraphrase','question':'拥有自身DNA且能够生成ATP的细胞器在每个人体细胞中，数量一般是多少？','expected':['数百至数千']},
              {'id':'extra-condition','question':'负责产生ATP且具有自身DNA、没有细胞膜的细胞结构，其人体细胞数量通常达到什么范围？','forbidden':['数百至数千','100至1000'],'expected_abstention':True},
              {'id':'wrong-named-structure','question':'叶绿体负责产生ATP且具有自身DNA，其人体细胞数量通常达到什么范围？','forbidden':['数百至数千','100至1000'],'expected_abstention':True},
              {'id':'new-choice-direction','question':'本题为不定项选择题，下列等式中错误的有哪些？\nA. 2+5=8\nB. 8/2=4\nC. 3*7=21\nD. 10-4=5','choices':['A','D']},
              cases()[-1]]
    out=HERE/'.local'/('acceptance-'+args.suite+'-'+str(time.time_ns()));out.mkdir()
    manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
    def run(row):
        engine=Engine();start=time.monotonic()
        try:
            answer,audit=engine.answer(row['question'])
            return dict(row,ok=True,answer=answer,audit=audit,seconds=round(time.monotonic()-start,3))
        except Exception as error:
            return dict(row,ok=False,error_type=type(error).__name__,seconds=round(time.monotonic()-start,3))
    start=time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run,rows))
    for r in results:
        r['content_check']=r['ok'] and all(x in r.get('answer','') for x in r.get('expected',[])) and not any(x in r.get('answer','') for x in r.get('forbidden',[]))
        if 'choices' in r:
            import re
            r['content_check'] &= set(re.findall(r'[A-H]',r.get('answer','')))==set(r['choices'])
        if r.get('expected_abstention'):
            import re
            r['content_check'] &= bool(re.search(r'无法|不足|尚未|不能确定',r.get('answer',''))) and r.get('audit',{}).get('route')!='functional_cell_evidence'
        if args.suite=='demo21':r['content_check']=None
        print(json.dumps({k:r.get(k) for k in ('id','ok','answer','seconds','content_check')}|{'route':r.get('audit',{}).get('route')},ensure_ascii=False),flush=True)
    assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v for n,v in manifest.items())
    summary={'suite':args.suite,'count':len(results),'calls_ok':sum(r['ok'] for r in results),'max_seconds':max(r['seconds'] for r in results),'wall_seconds':round(time.monotonic()-start,3),
             'content_checks':sum(r['content_check'] for r in results) if args.suite=='new' else None,
             'scope':'Small local four-worker Engine replay; caches partly warm. Not public/container acceptance, independent hidden accuracy or human scoring.'}
    for name,value in [('results',results),('manifest',manifest),('summary',summary)]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary));print('Output:',out)


if __name__=='__main__':main()
