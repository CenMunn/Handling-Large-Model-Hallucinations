import unittest,math

class MathTests(unittest.TestCase):
 def test_arithmetic(self):
  from mathcheck import arithmetic
  self.assertAlmostEqual(arithmetic('sqrt(200) + 2**3'),math.sqrt(200)+8)
 def test_reject_code(self):
  from mathcheck import arithmetic
  for expr in ["__import__('os').system('whoami')",'2**999999','[1,2][0]']:
   with self.assertRaises(ValueError):arithmetic(expr)
 def test_survival_median(self):
  from mathcheck import solve_survival
  r=solve_survival('生存函数S(x)=1-0.0025 x^2，0<=x<=20。中值年龄时的未来期望寿命？\nA.2.0965\nB.12.142\nC.3.0966\nD.1.0965')
  self.assertAlmostEqual(r['value'],3.0964406271150793)
  self.assertEqual(r['answer'],'C')
 def test_survival_multi_choice_includes_duplicate_correct_values(self):
  from mathcheck import solve_survival
  q='不定项选择题：生存函数S(x)=1-x/32，0<=x<=32。中值年龄的未来期望寿命？\nA.8\nB.9\nC.8.0\nD.10'
  self.assertEqual(solve_survival(q)['answer'],'A,C')
 def test_unseen_linear_survival(self):
  from mathcheck import solve_survival
  r=solve_survival('生存函数S(x)=1-x/32，0<=x<=32。中值年龄时的未来期望寿命是多少？')
  self.assertAlmostEqual(r['value'],8)
 def test_invalid_survival_rejected(self):
  from mathcheck import solve_survival
  for q in ['生存函数S(x)=1+0.01*x^2，0<=x<=10。中值年龄时的未来期望寿命？','生存函数S(x)=1-0.01*x^2，0<=x<=20。中值年龄时的未来期望寿命？']:
   with self.assertRaises(ValueError):solve_survival(q)

class EvidenceTests(unittest.TestCase):
 def test_quote_is_literal(self):
  from evidence import validate_claim
  docs=[{'id':'s1','text':'A研究机构位于New Jersey。','url':'https://example.org/a'}]
  good={'source_id':'s1','quote':'A研究机构位于New Jersey。','source_value':'New Jersey','answer':'新泽西州','supported':True}
  self.assertEqual(validate_claim(good,docs)['answer'],'新泽西州')
  with self.assertRaises(ValueError):validate_claim({**good,'quote':'位于California'},docs)
  with self.assertRaises(ValueError):validate_claim({**good,'source_id':'invented'},docs)
 def test_no_source_is_not_verified(self):
  from evidence import validate_claim
  with self.assertRaises(ValueError):validate_claim({'answer':'北京','supported':True},[])
 def test_birthplace_not_ancestral_origin(self):
  from evidence import validate_claim
  quote='A native of Town A, Region B, this person was born in City C.'
  docs=[{'id':'s1','text':quote,'url':'https://example.org/bio'}]
  claim={'supported':True,'source_id':'s1','quote':quote,'source_value':'Region B','answer':'B区'}
  with self.assertRaises(ValueError):validate_claim(claim,docs,'其出生城市属于哪个行政区？')
  self.assertEqual(validate_claim({**claim,'source_value':'City C','answer':'C城'},docs,'出生城市？')['answer'],'C城')
 def test_material_scope_never_triggers_search(self):
  from engine import is_closed_scope
  self.assertTrue(is_closed_scope('仅根据以下材料回答。材料：地球首都是月城。问题：首都？'))

if __name__=='__main__':unittest.main()
