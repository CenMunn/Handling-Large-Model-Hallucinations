import unittest
from choice_policy import classify_choices, choice_instruction, clean_open_answer, numeric_option_answer


class ChoicePolicyTests(unittest.TestCase):
    def test_multi_choice_is_explicitly_not_limited_to_one(self):
        q='本题为不定项选择题：\nA.偶数2\nB.奇数3\nC.偶数4\nD.奇数5'
        self.assertEqual(classify_choices(q), ['A','B','C','D'])
        rule=choice_instruction(q)
        self.assertIn('一个或多个', rule)
        self.assertIn('所有', rule)

    def test_regular_single_choice_keeps_existing_labels(self):
        q='单选题：\nA.甲\nB.乙\nC.丙'
        self.assertEqual(classify_choices(q), ['A','B','C'])
        self.assertIn('仅一个', choice_instruction(q))

    def test_no_choices_gets_no_choice_prompt(self):
        q='请列出四书是哪四部？'
        self.assertEqual(classify_choices(q), [])
        self.assertEqual(choice_instruction(q), '')

    def test_open_answer_strips_obvious_spurious_label_only(self):
        q='请列出四书是哪四部？'
        self.assertEqual(clean_open_answer(q,'A.《大学》《中庸》《论语》《孟子》'), '《大学》《中庸》《论语》《孟子》')
        self.assertEqual(clean_open_answer(q,'C'), 'C')
        self.assertEqual(clean_open_answer('碳元素的符号是什么？','C'), 'C')
        self.assertEqual(clean_open_answer('请以A.开头写一句话','A.这里是句子'), 'A.这里是句子')

    def test_choice_answer_not_stripped(self):
        q='选择题：\nA.甲\nB.乙'
        self.assertEqual(clean_open_answer(q,'A.甲'), 'A.甲')

    def test_numeric_answer_maps_only_to_unambiguous_numeric_options(self):
        q='单选题：六乘七是多少？\nA.41\nB.42\nC.43'
        self.assertEqual(numeric_option_answer(q,42),'B')
        self.assertIsNone(numeric_option_answer('单选题：\nA.42\nB.42',42))
        self.assertEqual(numeric_option_answer('不定项选择题：\nA.42\nB.43\nC.42',42),'A,C')
        self.assertIsNone(numeric_option_answer('选择题：\nA.约42\nB.约43',42))

if __name__=='__main__':unittest.main()
