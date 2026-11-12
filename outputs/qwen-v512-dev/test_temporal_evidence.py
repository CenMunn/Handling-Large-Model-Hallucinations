import unittest
from temporal_evidence import resolve

def dialogue(records,question):
 return '【世界设定】虚构世界。\n【对话记录】\n'+''.join('用户：'+r+'\n助手：已记录。\n' for r in records)+'\n【最终问题】\n'+question

class TemporalTests(unittest.TestCase):
 def test_latest_before_cutoff_and_world_scope(self):
  q=dialogue(['2024年1月，寒灯模型正式名称为“寒灯引擎”。','2026年2月，建立平行镜像世界B。','2026年3月，在镜像世界B中，寒灯模型正式名称为“异界寒灯”。','2027年1月，回到原始世界。','2028年3月，寒灯模型正式名称为“寒灯计算中心”。','2032年1月，寒灯模型正式名称为“未来中心”。'],'截至2029年，寒灯模型正式名称是什么？')
  r=resolve(q);self.assertEqual(r['answer'],'寒灯计算中心');self.assertIn('2028年3月',r['evidence'][0]['text'])
 def test_historical_appointment_preserves_deputy_and_correction(self):
  q=dialogue(['2023年4月，远潮项目增加副负责人黄芦（修正为沈野），负责信号增强。','2030年2月，沈野带领团队获得海洋通讯奖。'],'2030年2月获得海洋通讯奖的团队负责人，在2023年4月时被任命为什么职务？')
  r=resolve(q);self.assertIn('副负责人',r['answer']);self.assertIn('信号增强',r['answer']);self.assertEqual(len(r['evidence']),2)
 def test_unknown_person_or_ambiguous_award_does_not_guess(self):
  q=dialogue(['2023年4月，黄芦担任负责人。','2030年2月，有团队获得海洋通讯奖。'],'2030年2月获得海洋通讯奖的团队负责人，在2023年4月时被任命为什么职务？')
  self.assertIsNone(resolve(q))
 def test_assistant_summaries_do_not_override_user_facts(self):
  q=dialogue(['2024年1月，寒灯模型正式名称为“寒灯引擎”。'],'截至2024年，寒灯模型正式名称是什么？').replace('助手：已记录。','助手：正式名称为“错误名称”。')
  self.assertEqual(resolve(q)['answer'],'寒灯引擎')
 def test_negated_name_is_not_a_new_name(self):
  q=dialogue(['2024年1月，寒灯模型正式名称为“寒灯引擎”。','2025年1月，寒灯模型的正式名称不是“未知名称”。'],'截至2025年，寒灯模型正式名称是什么？')
  self.assertEqual(resolve(q)['answer'],'寒灯引擎')
 def test_explicit_original_world_name_restores_scope(self):
  q=dialogue(['建立一个虚拟知识世界，名称为‘潮岩世界’。','2023年4月，远潮项目增加副负责人黄芦（修正为沈野），负责信号增强。','2026年1月，建立平行世界B。','回到潮岩世界。','2030年2月，沈野带领团队获得海洋通讯奖。'],'2030年2月获得海洋通讯奖的团队负责人，在2023年4月时被任命为什么职务？')
  self.assertIn('副负责人',resolve(q)['answer'])
if __name__=='__main__':unittest.main()
