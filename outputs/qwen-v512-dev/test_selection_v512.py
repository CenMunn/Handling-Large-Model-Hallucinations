import unittest
from selection_semantics import evaluation_mode
from option_checks import truth_question

class SelectionOrderTests(unittest.TestCase):
 def test_adjective_before_equation_noun_keeps_selection_direction(self):
  for word,mode in [('错误','false_statements'),('正确','true_statements')]:
   for stem in [f'选出所有{word}的等式。',f'请选择{word}的算式。']:
    with self.subTest(stem=stem):
     self.assertEqual(evaluation_mode(stem),mode);self.assertTrue(truth_question(stem))
 def test_double_negative_and_fictional_operator_remain_guarded(self):
  self.assertEqual(evaluation_mode('选出不是错误的说法。'),'criterion')
  self.assertFalse(truth_question('按材料重新定义加号，选出所有正确的等式。'))

if __name__=='__main__':unittest.main()
