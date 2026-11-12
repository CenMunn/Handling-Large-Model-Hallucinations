import unittest
from selection_semantics import evaluation_mode,select_records

class SelectionTests(unittest.TestCase):
 def test_statement_truth_is_not_selection(self):
  options=[{'label':x} for x in 'ABCD']
  records=[{'label':x,'statement_true':x!='A'} for x in 'ABCD']
  self.assertEqual(select_records(options,records,'false_statements',False),'A')
  self.assertEqual(select_records(options,records,'true_statements',False),'B,C,D')
 def test_negative_word_in_option_does_not_reverse_stem(self):
  self.assertEqual(evaluation_mode('下列说法正确的是\nA.甲不是乙\nB.乙是丙'),'true_statements')
 def test_reverse_variants(self):
  for stem in ('关于免疫细胞的叙述，错误的是','哪些等式不成立？','下列说法不正确的是'):
   self.assertEqual(evaluation_mode(stem),'false_statements')
 def test_criterion_keeps_its_own_meaning(self):
  opts=[{'label':'A'},{'label':'B'}]
  records=[{'label':'A','matches_requirement':False},{'label':'B','matches_requirement':True}]
  self.assertEqual(select_records(opts,records,'criterion',True),'B')
  with self.assertRaises(ValueError):select_records(opts,[{'label':'A','verdict':True},{'label':'B','verdict':False}],'criterion',True)
 def test_unknown_and_nested_negation_stay_explicit(self):
  self.assertEqual(evaluation_mode('下列不是错误的是'),'criterion')
  with self.assertRaises(ValueError):select_records([{'label':'A'}],[{'label':'A','statement_true':'unknown'}],'false_statements',True)

if __name__=='__main__':unittest.main()
