"""Synthetic, rule-derived development cases. Not official test data."""
import json
from pathlib import Path

def build():
 rows=[]
 def add(cat,prompt,expected,abstain=False,pair=None):
  rows.append({'id':str(len(rows)+1),'category':cat,'问题':prompt,'expected':expected,'should_abstain':abstain,'pair_id':pair,'provenance':'synthetic-rule-derived; manual review pending'})
 for i in range(20):
  tag=f'测试站X{i+1:02}';code=f'K{7301+i*17}'
  add('evidence',f'只根据材料回答。【材料】{tag}的访问代码为{code}，负责人是小林。【问题】{tag}的访问代码是什么？只回答代码。',[code],pair=str(i))
  add('missing_evidence',f'只根据材料回答。【材料】{tag}的负责人是小林，开放时间为周一。【问题】{tag}的访问代码是什么？',['不足','无法确定','未提供','不知道','未知','无相关信息'],True,pair=str(i))
  add('revision',f'只根据对话回答。【对话记录】最初：订单{8100+i}送至青港。更正：改送松湾。最终更正：前述松湾地址作废，最终改送白岭。【最终问题】订单{8100+i}最终送到哪里？只回答地点。',['白岭'])
  add('false_premise',f'只根据材料回答。【材料】虚构赛事“晨星杯{i+1}”因场地问题取消，从未举办，也未颁奖。【问题】该赛事冠军是谁？',['未举办','从未举办','取消','没有冠军','未产生','不存在冠军'])
  add('counterfactual',f'【世界设定】本题为虚构世界。城市A{i}属于星岚国，星岚国首都为月砂城，现实世界资料不适用。【最终问题】城市A{i}所属国家的首都是什么？只回答城市名。',['月砂城'])
 knowledge=[('12乘以13等于多少？只回答数字。','156'),('法国的首都是哪里？','巴黎'),('一米等于多少厘米？只回答数字。','100'),('水的化学式是什么？','H2O'),('太阳系中距离太阳最近的行星是什么？','水星'),('三角形有几条边？只回答数字。','3'),('9的平方是多少？只回答数字。','81'),('中国的首都是哪里？','北京')]
 for q,a in knowledge:add('knowledge',q,[a])
 for i in range(4):
  filler='\n'.join(f'背景记录{j}：本条仅为无关的噪声信息。' for j in range(100))
  fact=f'\n关键记录：设备Z{i}的最终密钥为R{9120+i}。\n'
  add('long_context','仅根据记录回答。\n'+filler[:len(filler)//2]+fact+filler[len(filler)//2:]+f'\n【最终问题】设备Z{i}的最终密钥是什么？只回答密钥。',[f'R{9120+i}'])
 for i in range(8):
  add('unresolvable',f'仅根据材料回答。【材料】截至2026年10月30日，虚构项目“雨石{i}”尚未开奖，结果没有产生。【问题】这个项目最终中奖号码是多少？',['未开奖','尚未','未产生','没有产生','未知','无法确定','不足'],True)
 return rows

if __name__=='__main__':
 root=Path(__file__).resolve().parent;rows=build()
 (root/'dev_cases.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 p=root/'local_input';p.mkdir(exist_ok=True)
 (p/'smoke.json').write_text(json.dumps([{'id':r['id'],'问题':r['问题']} for r in rows[:4]],ensure_ascii=False,indent=2),encoding='utf-8')
 print('generated',len(rows),'synthetic cases')
