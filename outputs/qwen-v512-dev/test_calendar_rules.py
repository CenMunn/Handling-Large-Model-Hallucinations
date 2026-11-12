import unittest

from calendar_rules import solve_explicit_calendar


class ExplicitCalendarTests(unittest.TestCase):
    def test_explicit_baseline_and_increment(self):
        variants = [
            '假设平年二月有27天，闰年二月比平年多4天。闰年二月有多少天？',
            '假设平年2月为27天，闰年2月比平年增加4天。闰年2月有多少天？',
            '假设平年二月是27天，特殊年份二月比平年多4天。特殊年份二月是多少天？',
            '假设平年二月改为27天，闰年二月比平年多四天。闰年二月有多少天？',
            '假设平年二月规定为27天，闰年二月比平年增加四天。闰年二月有多少天？',
        ]
        for question in variants:
            with self.subTest(question=question):
                result = solve_explicit_calendar(question)
                self.assertEqual(result['status'], 'solved')
                self.assertEqual(result['value'], 31)
                self.assertEqual(result['base'], 27)
                self.assertEqual(result['delta'], 4)

    def test_decrement_and_explicit_base(self):
        result = solve_explicit_calendar('虚构日历平年二月为32天，特别年份二月比平年少3天。特别年份二月有多少天？')
        self.assertEqual((result['base'], result['delta'], result['value']), (32, -3, 29))

    def test_ambiguous_is_not_solved(self):
        questions = [
            '平年二月有27天，也有人称平年二月有29天；闰年二月比平年多2天。闰年二月有多少天？',
            '平年二月有27天，闰年二月比平年多2天或少3天。闰年二月有多少天？',
            '平年二月有27天，闰年二月天数未知。闰年二月有多少天？',
            '平年二月不是27天，闰年二月比平年多2天。闰年二月有多少天？',
            '平年二月有27天，闰年二月比平年多2天。平年二月有多少天？',
            '最初平年二月有27天，后来平年二月改成29天；闰年二月比平年多2天。闰年二月有多少天？',
            '平年二月有27天，闰年二月比平年多2天。闰年二月有多少天，其两倍是多少？',
        ]
        for question in questions:
            with self.subTest(question=question):
                result = solve_explicit_calendar(question)
                self.assertNotEqual(result.get('status') if result else None, 'solved')

    def test_non_explicit_calendar_untouched(self):
        self.assertIsNone(solve_explicit_calendar('若闰年2月比平年多3天，闰年2月多少天？'))
        self.assertIsNone(solve_explicit_calendar('一辆车每小时行驶30千米，2小时行驶多少千米？'))


if __name__ == '__main__':
    unittest.main()
