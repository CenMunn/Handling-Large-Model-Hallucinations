import unittest,json
from engine import Engine

class FakeEngine(Engine):
    def __init__(self, reply): self.reply=reply; self.systems=[]
    def llm(self,messages,end,max_tokens=320,json_mode=False):
        self.systems.append(messages[0]['content'])
        if json_mode and 'options' in messages[-1]['content']:
            options=json.loads(messages[-1]['content'])['options']
            field='matches_requirement' if 'matches_requirement(布尔值' in messages[0]['content'] else 'statement_true'
            return json.dumps({'options':[{'label':o['label'],field:o['label'] in self.reply,'reason':'fixture'} for o in options]}),{}
        return self.reply, {}

class ChoiceEngineTests(unittest.TestCase):
    def test_multi_choice_keeps_all_selected_letters(self):
        engine=FakeEngine('A,C')
        answer,audit=engine.answer('本题为不定项选择题：\nA.2\nB.3\nC.4\nD.5')
        self.assertEqual(answer,'A,C')
        self.assertIn('一个或多个',engine.systems[-1])

    def test_multi_choice_for_material_question(self):
        engine=FakeEngine('A,C')
        answer,audit=engine.answer('仅根据材料作答，以下为不定项选择题：\nA.甲\nB.乙\nC.丙')
        self.assertEqual(answer,'A,C')
        self.assertIn('一个或多个',engine.systems[-1])

    def test_open_question_extra_prefix_removed(self):
        engine=FakeEngine('A.《大学》《中庸》《论语》《孟子》')
        answer,audit=engine.answer('四书包括哪四部？')
        self.assertEqual(answer,'《大学》《中庸》《论语》《孟子》')
        self.assertNotIn('选择题只给选项字母',engine.systems[-1])

    def test_open_question_single_letter_preserved(self):
        answer,_=FakeEngine('C').answer('碳元素的化学符号是什么？')
        self.assertEqual(answer,'C')

    def test_numeric_choice_returns_matching_letter(self):
        class NumericFake(FakeEngine):
            def numeric(self,question,end):
                return {'answer':'42','value':42,'independent_computation':True}
        engine=NumericFake('B')
        answer,audit=engine.answer('单选题：6乘7等于多少？\nA.41\nB.42\nC.43')
        self.assertEqual(answer,'B')
        self.assertEqual(audit['route'],'option_checks')

if __name__=='__main__':unittest.main()
