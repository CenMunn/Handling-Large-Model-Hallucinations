import unittest,json,time
from unittest.mock import patch
from engine import Engine

class BudgetTests(unittest.TestCase):
 def test_unsupported_relation_fetches_but_skips_useless_generation(self):
  class Fake(Engine):
   def __init__(self):self.calls=[]
   def llm(self,messages,end,max_tokens=320,json_mode=False):
    self.calls.append(end)
    if len(self.calls)>1:raise AssertionError('unverifiable relation should not consume extraction/repair')
    return json.dumps({'queries':['人物机构国家']}),{}
  e=Fake();before=time.monotonic()
  docs=[{'id':'s','title':'资料','text':'甲在乙机构工作。','url':'https://a.example'}]
  with patch('engine.retrieve',return_value=(docs,[])) as retrieval:
   answer,audit=e.fact('某语言设计者所在国家的官方语言是什么？',before+42,{})
  self.assertEqual(len(e.calls),1);self.assertLessEqual(e.calls[0],before+4.1)
  self.assertEqual(audit['evidence_status'],'binding_unresolved')
  self.assertTrue(audit['skipped_unverifiable_extraction']);retrieval.assert_called_once()
 def test_failed_model_call_retains_timing(self):
  e=Engine.__new__(Engine);e.timing_events=[]
  e.token_count=lambda *a:20;e.actual_context_limit=lambda *a:12288
  def fail(*a):raise TimeoutError('fixture')
  e.post=fail
  with self.assertRaises(TimeoutError):e.llm([{'role':'user','content':'q'}],time.monotonic()+2)
  self.assertEqual(e.timing_events[-1]['error_type'],'TimeoutError')
if __name__=='__main__':unittest.main()
