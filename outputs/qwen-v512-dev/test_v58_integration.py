import unittest,json
from unittest.mock import patch
from engine import Engine
from test_temporal_evidence import dialogue

class IntegrationTests(unittest.TestCase):
 def test_wrong_statement_question_is_selected_by_program(self):
  e=Engine.__new__(Engine)
  def llm(messages,*args,**kwargs):
   self.assertIn('statement_true',messages[0]['content'])
   return json.dumps({'options':[{'label':x,'statement_true':x!='A','reason':'fixture'} for x in 'ABCD']}),{}
  e.llm=llm
  answer,audit=e.answer('不定项选择题：下列叙述错误的是\nA.甲\nB.乙\nC.丙\nD.丁')
  self.assertEqual(answer,'A');self.assertFalse(audit['option_records'][0]['statement_true']);self.assertTrue(audit['option_records'][0]['selected'])
 def test_latest_question_must_fetch_and_cannot_invent_title(self):
  e=Engine.__new__(Engine);e.llm=lambda *a,**k:('{"queries":["某机构最新文件"]}',{})
  with patch('engine.retrieve',return_value=([],[])) as retrieval:
   answer,audit=e.answer('某机构最新发布文件的完整名称是什么？')
  retrieval.assert_called_once();self.assertEqual(audit['route'],'external_evidence');self.assertEqual(audit['evidence_status'],'unavailable')
 def test_false_claim_uses_direct_evidence_without_second_model_call(self):
  e=Engine.__new__(Engine);calls=[]
  def llm(*a,**k):calls.append(True);return '{"queries":["石桥往事导演"]}',{}
  e.llm=llm
  docs=[{'id':'s','title':'石桥往事节目页','url':'https://station.example','text':'导演：江沅、林石'}]
  with patch('engine.retrieve',return_value=(docs,[])):
   answer,audit=e.answer('我了解到，石桥往事的导演是秦叶，它对吗？')
  self.assertLessEqual(len(calls),1);self.assertIn('不正确',answer);self.assertEqual(audit['evidence_status'],'literal_claim_refuted')
 def test_temporal_join_does_not_use_model_memory(self):
  e=Engine.__new__(Engine)
  e.llm=lambda *a,**k:(_ for _ in ()).throw(AssertionError('No model needed for explicit join'))
  q=dialogue(['2023年4月，远潮项目增加副负责人黄芦（修正为沈野），负责信号增强。','2030年2月，沈野带领团队获得海洋通讯奖。'],'2030年2月获得海洋通讯奖的团队负责人，在2023年4月时被任命为什么职务？')
  answer,audit=e.answer(q);self.assertIn('副负责人',answer);self.assertEqual(audit['route'],'temporal_evidence')
if __name__=='__main__':unittest.main()
