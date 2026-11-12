import unittest
from engine import Engine


class Fake(Engine):
 def __init__(self):self.systems=[]
 def numeric(self,question,end):return None
 def llm(self,messages,end,max_tokens=320,json_mode=False):
  system=messages[0]['content'];self.systems.append(system)
  if json_mode:
   import json
   options=json.loads(messages[-1]['content'])['options']
   field='matches_requirement' if 'matches_requirement(布尔值' in system else 'statement_true'
   return json.dumps({'options':[{'label':o['label'],field:i==0} for i,o in enumerate(options)]}),{}
  if '请直接回答' in system:return '31天',{}
  if '选择题只给选项字母' in system:return 'C',{}
  return '31天',{}


class OpenAnswerTests(unittest.TestCase):
 def test_open_question_not_misclassified_as_choice(self):
  model=Fake();answer,audit=model.answer('假如某年二月比平年多3天，则二月有多少天？')
  self.assertEqual(answer,'31天')
 def test_choice_prompt_remains_available(self):
  model=Fake();model.answer('本题为选择题：\nA.甲\nB.乙')
  self.assertTrue(any('逐一判断每个选项' in s for s in model.systems))

 def test_declared_constant_in_expression_is_safely_bound(self):
  import json,time
  class Numeric(Engine):
   def __init__(self):pass
   def llm(self,*args,**kwargs):return json.dumps({'sufficient':True,'expression':'february_nonleap_days+3','unit':'天','constants':['february_nonleap_days']}),{}
  self.assertEqual(Numeric().numeric('平年二月加3天有多少天？',time.monotonic()+20)['answer'],'31天')

 def test_explicit_changed_baseline_cannot_be_replaced_by_default(self):
  import json,time
  class Numeric(Engine):
   def __init__(self):pass
   def llm(self,*args,**kwargs):return json.dumps({'sufficient':True,'expression':'28+4','unit':'天','constants':['february_nonleap_days']}),{}
  result=Numeric().numeric('平年2月改为32天，特殊年比平年多4天，特殊年二月有多少天？',time.monotonic()+20)
  self.assertFalse(result['independent_computation'])


if __name__=='__main__':unittest.main()
