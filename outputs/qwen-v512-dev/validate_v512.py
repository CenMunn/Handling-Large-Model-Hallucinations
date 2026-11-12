"""New-question local replay. Keeps failures; never changes organizer input."""
import concurrent.futures,hashlib,json,time,re
from pathlib import Path
from engine import Engine

HERE=Path(__file__).resolve().parent
CASES=[
 ('historical-named','C++设计开始到首次发布时，设计者的历史工作地点属于美国哪个州？',['新泽西','1979','1985']),
 ('river-north','钱塘江从北源至入海口全长多少公里？',['668','北源']),
 ('river-census','钱塘江按水利普查名录的河流长度是多少公里？',['609']),
 ('country-usage','英国的官方语言主要是什么？',['主要使用语言','英语','未核实']),
 ('new-capital','创作《动物农场》的作者，其出生地现今所属国家的首都是什么？',['新德里']),
 ('new-capital-2','创作《变形记》的作者，其出生地现今所属国家的首都是什么？',['布拉格']),
 ('multi-wrong','本题为不定项选择题。选出所有错误的等式。\nA. 11+7=19\nB. 9*4=36\nC. 17-8=8\nD. 35/5=7',['A','C']),
 ('multi-right','本题为不定项选择题。选出所有正确的等式。\nA. 6*8=48\nB. 12/3=5\nC. 19-6=13\nD. 8+5=12',['A','C']),
 ('scope-extra','负责产生ATP且具有自身DNA、没有细胞膜的细胞结构，其人体细胞数量通常达到什么范围？',['无法']),
 ('missing','新钢管的质量是原钢管的2.8倍，现有13根，总质量是多少千克？',['信息不足']),
 ('history-new','【世界设定】【对话记录】2026年田雨任山岚项目副负责人。2028年升任负责人。2030年的宣传误写她2026年已任负责人，随后正式撤回。乙世界她2026年是会计。【最终问题】原世界中2027年田雨的职务是什么？',['副负责人']),
 ('history-missing','【世界设定】【对话记录】2027年蓝舟公司负责人为李谷，资料未给公司利润。【最终问题】仅根据材料，2027年公司的利润是多少万元？',['未','利润']),
]

def main():
 out=HERE/'.local'/('v512-new-'+str(time.time_ns()));out.mkdir()
 manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')}
 manifest['curated-source-graphs.json']=hashlib.sha256((HERE/'curated-source-graphs.json').read_bytes()).hexdigest()
 def run(row):
  id,q,expected=row;start=time.monotonic()
  try:
   answer,audit=Engine().answer(q)
   check=all(x in answer for x in expected)
   if id.startswith('multi'):check=set(re.findall('[A-H]',answer))==set(expected)
   return {'id':id,'question':q,'answer':answer,'audit':audit,'ok':True,'content_check':check,'seconds':round(time.monotonic()-start,3)}
  except Exception as e:return {'id':id,'ok':False,'content_check':False,'error_type':type(e).__name__,'seconds':round(time.monotonic()-start,3)}
 with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(run,CASES))
 assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v for n,v in manifest.items())
 for r in results:print(json.dumps({k:v for k,v in r.items() if k not in ('audit','question')},ensure_ascii=False),flush=True)
 summary={'count':len(results),'successful_calls':sum(r['ok'] for r in results),'content_checks':sum(r['content_check'] for r in results),'max_seconds':max(r['seconds'] for r in results),'limitations':'12 first-run new prompts, but 4 directly concern curated corpus; substring checks are not independent human grading or hidden accuracy.'}
 (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8');(out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False));print('Output:',out)

if __name__=='__main__':main()
