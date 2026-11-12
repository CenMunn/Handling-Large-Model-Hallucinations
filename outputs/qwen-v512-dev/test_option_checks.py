import unittest
from option_checks import parse_options, check_equation, assemble,truth_question

class OptionTests(unittest.TestCase):
 def test_all_true_not_limited_to_one(self):
  q='不定项选择题：\nA.2+3=5\nB.9−4=5\nC.2×4=8\nD.8÷2=4'
  options=parse_options(q)
  self.assertEqual([check_equation(o['text']) for o in options],[True]*4)
  self.assertEqual(assemble(options,[{'label':o['label'],'verdict':True} for o in options],False),'A,B,C,D')
 def test_unknown_and_missing_entries_not_silently_dropped(self):
  options=parse_options('选择题：\nA.甲\nB.乙')
  for records in [[{'label':'A','verdict':True}],[{'label':'A','verdict':True},{'label':'B','verdict':'unknown'}]]:
   with self.assertRaises(ValueError):assemble(options,records,False)
 def test_pure_equation_only(self):
  self.assertIsNone(check_equation('9−4=5，但条件另有变化'))
  self.assertIsNone(check_equation('甲为正确项'))
  self.assertFalse(check_equation('3+4=8'))
 def test_duplicate_labels_rejected(self):
  options=parse_options('多选：\nA.甲\nB.乙')
  with self.assertRaises(ValueError):assemble(options,[{'label':'A','verdict':True}]*2,False)
 def test_equation_truth_does_not_answer_other_selection_criteria(self):
  self.assertFalse(truth_question('选计算结果大于6的等式'))
  self.assertFalse(truth_question('假设加号表示乘法，哪些算式成立'))
  self.assertTrue(truth_question('下列哪些等式不成立？'))

if __name__=='__main__':unittest.main()
