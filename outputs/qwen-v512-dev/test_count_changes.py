import unittest
from engine import Engine


class CountChanges(unittest.TestCase):
    def solve(self,q):
        engine=Engine.__new__(Engine)
        def forbidden(*args,**kwargs):raise AssertionError('Unambiguous count must not require model interpretation')
        engine.llm=forbidden
        answer,audit=engine.answer(q)
        self.assertEqual(audit['route'],'verified_count_change')
        self.assertTrue(audit['math']['interpretation_verified'])
        return answer

    def test_added_is_not_total(self):
        self.assertEqual(self.solve('【设问知识】三角形角数量\n----------------------------------\n如果几何规则规定三角形增加4个角，那么三角形有多少个角？'),'7个角')

    def test_new_shapes_and_chinese_numerals(self):
        self.assertEqual(self.solve('如果几何规则规定五边形增加六个角，那么五边形有多少个角？'),'11个角')
        self.assertEqual(self.solve('如果几何规则规定四边形减少2个角，那么四边形有多少个角？'),'2个角')

    def test_explicit_baseline_overrides_ordinary_geometry(self):
        self.assertEqual(self.solve('三角形原有5个角，增加4个角后，共有多少个角？'),'9个角')
        self.assertEqual(self.solve('某图形原有八个角，减少三个角后，共有多少个角？'),'5个角')

    def test_ambiguous_patterns_decline(self):
        from count_changes import solve
        for q in [
            '三角形增加到4个角，那么三角形有多少个角？',
            '三角形增加4个角，又减少2个角，那么三角形有多少个角？',
            '如果几何规则规定三角形增加4个角，那么四边形有多少个角？',
            '如果几何规则规定三角形增加4个角，那么原来有多少个角？',
            '三角形每个角增加4度，那么三角形有多少个角？',
            '三角形原有5个角，原有6个角，增加4个角后，共有多少个角？',
            '三角形原有3个角，减少4个角后，共有多少个角？',
        ]:
            with self.subTest(q=q):self.assertIsNone(solve(q))


if __name__=='__main__':unittest.main()
