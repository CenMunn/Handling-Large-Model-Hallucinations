import unittest
from engine import Engine

class CalendarIntegrationTests(unittest.TestCase):
    def test_explicit_baseline_is_used_before_model_or_closed_scope(self):
        engine = Engine.__new__(Engine)
        answer, audit = engine.answer('仅根据设定：平年二月有33天。特殊年份二月比平年少4天。特殊年份二月有多少天？')
        self.assertEqual(answer, '29天')
        self.assertEqual(audit['route'], 'explicit_calendar')
        self.assertEqual(audit['math']['base'], 33)
        self.assertEqual(audit['math']['delta'], -4)

    def test_ambiguous_change_does_not_call_model(self):
        engine = Engine.__new__(Engine)
        answer, audit = engine.answer('平年二月有33天。特殊年份二月比平年多4天，后来又增加2天。特殊年份二月有多少天？')
        self.assertEqual(audit['route'], 'explicit_calendar')
        self.assertEqual(audit['math']['status'], 'unresolved')
        self.assertIn('无法', answer)

if __name__ == '__main__':
    unittest.main()
