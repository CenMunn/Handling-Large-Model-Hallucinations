import unittest
from unittest.mock import patch
from engine import Engine, is_fact


class EmpiricalQuantityTests(unittest.TestCase):
    def test_counts_and_ranges_require_evidence(self):
        for q in [
            '负责产生ATP且具有自身DNA的细胞结构，其人体细胞数量通常达到什么范围？',
            '成年人每日平均饮水量通常是多少毫升？',
            '这种材料的密度一般是多少千克每立方米？',
            '每个肝细胞中的线粒体通常有多少个？',
        ]:
            with self.subTest(q=q): self.assertTrue(is_fact(q))

    def test_calculation_and_hypothesis_are_not_empirical_counts(self):
        for q in ['如果六艺新增一艺，则共有几艺？', '箱中共有4个球，又放入3个，共多少个？']:
            self.assertFalse(is_fact(q))

    def test_empirical_question_cannot_reach_free_generation(self):
        e=Engine.__new__(Engine)
        e.fact=lambda q,end,audit: ('统计口径尚未核实。',dict(audit,route='external_evidence'))
        e.llm=lambda *args,**kwargs: self.fail('empirical numerical fact reached ungrounded generation')
        answer,audit=e.answer('负责产生ATP且具有自身DNA的细胞结构，其人体细胞数量通常达到什么范围？')
        self.assertEqual(audit['route'],'external_evidence')
        self.assertNotIn('10,000',answer)

    def test_material_scope_keeps_priority_over_external_fact_routing(self):
        e=Engine.__new__(Engine)
        e.llm=lambda *args,**kwargs: ('材料没有给出统计范围。',{})
        e.fact=lambda *args: self.fail('closed materials must not use external facts')
        answer,audit=e.answer('仅根据给定材料回答：材料为样品编号甲。其密度一般是多少？')
        self.assertEqual(audit['route'],'closed_scope')


if __name__=='__main__': unittest.main()
