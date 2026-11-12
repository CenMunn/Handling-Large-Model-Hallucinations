import unittest
from claim_evidence import verify,neutral_queries
class ClaimTests(unittest.TestCase):
 def test_director_false_is_refuted_from_literal_metadata(self):
  docs=[{'id':'s','title':'石桥往事节目页','url':'https://station.example','text':'导演：江沅、林石\n主演：甲、乙'}]
  r=verify('我了解到，石桥往事的导演是秦叶，它对吗？',docs)
  self.assertEqual(r['status'],'refuted');self.assertIn('江沅',r['answer'])
 def test_unrelated_metadata_cannot_verify(self):
  r=verify('我了解到，石桥往事的导演是秦叶，它对吗？',[{'id':'s','title':'另一部电视剧','text':'导演：江沅'}])
  self.assertNotEqual(r['status'],'refuted')
 def test_one_matching_subclaim_cannot_confirm_whole_compound_claim(self):
  q='2022年，江沅执导的古装剧《石桥往事》在甲平台播出，它对吗？'
  docs=[{'id':'s','title':'石桥往事','text':'导演：江沅'}]
  self.assertEqual(verify(q,docs)['status'],'unresolved')
 def test_disagreeing_director_sources_stay_unresolved(self):
  q='《石桥往事》的导演是秦叶，它对吗？'
  docs=[{'id':str(i),'title':'石桥往事','text':'导演：'+v} for i,v in enumerate(['秦叶','江沅'])]
  self.assertEqual(verify(q,docs)['status'],'unresolved')
 def test_author_and_place_claims_need_literal_relations(self):
  r=verify('我了解到，《石桥图》的作者是秦叶，它对吗？',[{'id':'s','title':'石桥图介绍','text':'《石桥图》的作者是江沅。'}])
  self.assertEqual(r['status'],'refuted')
 def test_neutral_query_does_not_repeat_unverified_director(self):
  queries=neutral_queries('我了解到，石桥往事的导演是秦叶，它对吗？')
  self.assertTrue(queries);self.assertIn('石桥往事',queries[0]);self.assertNotIn('秦叶',' '.join(queries))
 def test_compound_event_queries_use_work_and_properties(self):
  queries=neutral_queries('2022年，秦叶执导的古装剧《石桥往事》在甲平台播出，它对吗？')
  self.assertIn('石桥往事',queries[0]);self.assertNotIn('秦叶',' '.join(queries));self.assertNotIn('甲平台',' '.join(queries))
  r=verify('我了解到，蓝亭塔位于甲国。它对吗？',[{'id':'s','title':'蓝亭塔','text':'蓝亭塔位于乙国。'}])
  self.assertEqual(r['status'],'refuted')
 def test_title_anchored_catalog_author_and_table_director(self):
  r=verify('《石桥图》的作者是秦叶，它对吗？',[{'id':'s','title':'石桥图卷','text':'本卷无款，根据题跋，作者是江沅。'}])
  self.assertEqual(r['status'],'refuted')
  r=verify('《石桥往事》的导演是秦叶，它对吗？',[{'id':'s','title':'石桥往事 - 节目资料','text':'导演 | 江沅\n主演 | 甲'}])
  self.assertEqual(r['status'],'refuted')
if __name__=='__main__':unittest.main()
