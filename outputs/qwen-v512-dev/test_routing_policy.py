import unittest
from routing_policy import evidence_request
class RoutingTests(unittest.TestCase):
 def test_real_claims_cannot_bypass_evidence(self):
  for q in ['我了解到，某电视剧的导演是某人，它对吗？','某飞行器已经获欧洲认证，是真的吗？','这个说法是否属实？']:
   self.assertEqual(evidence_request(q),'claim_verification')
 def test_current_and_exact_names_need_evidence(self):
  for q in ['现任某机构总裁是谁？','最新发布的文件完整名称是什么？','截至目前该标准的完整编号和名称是什么？']:
   self.assertEqual(evidence_request(q),'time_sensitive')
 def test_materials_and_worlds_keep_local_scope(self):
  for q in ['【世界设定】最新负责人是甲，它对吗？','仅根据材料：现任负责人是谁？','【对话记录】某人称甲正确，它对吗？']:
   self.assertIsNone(evidence_request(q))
 def test_arithmetic_does_not_require_web(self):
  self.assertIsNone(evidence_request('这个算式2+3=5对吗？'))
if __name__=='__main__':unittest.main()
