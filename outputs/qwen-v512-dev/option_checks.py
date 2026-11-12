"""Option accounting and independent checks for pure numeric equalities."""
import math,re
from mathcheck import arithmetic

def parse_options(question):
 matches=list(re.finditer(r'(?m)^\s*([A-H])[.．、)）]\s*',question))
 if len(matches)<2 and re.search(r'选择题|选项|多选|单选',question):
  matches=list(re.finditer(r'(?:^|[\s:：])([A-H])[.．、)）]\s*',question))
 if len(matches)<2:return []
 if len({m[1] for m in matches})!=len(matches):return []
 return [{'label':m[1],'text':question[m.end():matches[i+1].start() if i+1<len(matches) else len(question)].strip()} for i,m in enumerate(matches)]

def check_equation(text):
 value=text.strip().rstrip('。；;')
 value=value.translate(str.maketrans({'−':'-','×':'*','÷':'/','＝':'='}))
 if not re.fullmatch(r'[\d\s.+*/()=\-]+',value) or value.count('=')!=1:return None
 left,right=value.split('=')
 try:return math.isclose(arithmetic(left),arithmetic(right),rel_tol=1e-10,abs_tol=1e-10)
 except (ValueError,TypeError,ZeroDivisionError,OverflowError):return None

def truth_question(stem):
 """Only override arithmetic when the question asks whether equations hold."""
 if re.search(r'设定|假设|规定|定义|表示|材料|如果|假如|大于|小于|结果|推出',stem):return False
 return bool(re.search(r'(?:等式|算式).{0,8}(?:正确|成立|错误|相等)|(?:正确|错误|不正确|成立|不成立)的(?:等式|算式)',stem))

def assemble(options,records,single):
 labels=[o['label'] for o in options]
 if not isinstance(records,list) or not all(isinstance(r,dict) for r in records):raise ValueError('invalid option records')
 if len(records)!=len(labels) or [r.get('label') for r in records]!=labels:raise ValueError('option records must include every original label once in order')
 if any(type(r.get('verdict')) is not bool for r in records):raise ValueError('unresolved option verdict')
 chosen=[r['label'] for r in records if r['verdict']]
 if not chosen or single and len(chosen)!=1:raise ValueError('no valid complete selection')
 return ','.join(chosen)
