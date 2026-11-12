import importlib.util
import unittest


class QuantityTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('quantities'), 'Grounded quantity checker is missing')
        import quantities
        return quantities

    def test_ratio_is_not_mass(self):
        m=self.module();p=m.prepare('新货物每箱质量是原来的2.4倍，共9箱，总质量是多少千克？')
        self.assertEqual(p['status'],'missing')

    def test_complete_mass_and_ratio(self):
        m=self.module();p=m.prepare('原来每箱质量为2千克，新每箱质量变为原来的2.4倍，共9箱，总质量是多少千克？')
        self.assertEqual(p['status'],'ready')
        r=m.compute('q0*q1*q2',p)
        self.assertAlmostEqual(r['value'],43.2)

    def test_dimensionless_expression_cannot_return_mass(self):
        m=self.module();p=m.prepare('每箱质量2千克，共9箱，总质量是多少千克？')
        with self.assertRaises(ValueError):m.compute('q1',p)

    def test_unit_conversion(self):
        m=self.module();p=m.prepare('每瓶装500毫升，共4瓶，总体积是多少升？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],2)
        p=m.prepare('每袋质量250克，共6袋，总质量是多少千克？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],1.5)

    def test_delta_price_not_original_price(self):
        m=self.module();p=m.prepare('每件商品涨价2元，买7件总价是多少元？')
        self.assertEqual(p['status'],'missing')
        p=m.prepare('每件商品涨价2元，买7件比原来多花多少元？')
        self.assertEqual(p['status'],'ready')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],14)

    def test_original_price_and_delta(self):
        m=self.module();p=m.prepare('原来每件10元，每件涨价2元，买7件总价是多少元？')
        self.assertAlmostEqual(m.compute('(q0+q1)*q2',p)['value'],84)

    def test_unknown_speed_and_known_speed(self):
        m=self.module();p=m.prepare('汽车速度是原来的1.3倍，行驶4小时，共走多少公里？')
        self.assertEqual(p['status'],'missing')
        p=m.prepare('汽车原速度50公里/小时，现在是原来的1.3倍，行驶4小时，共走多少公里？')
        self.assertAlmostEqual(m.compute('q0*q1*q2',p)['value'],260)

    def test_area_density_and_electric_power(self):
        m=self.module();p=m.prepare('长3米，宽4米，矩形面积是多少平方米？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],12)
        p=m.prepare('液体密度2千克/升，体积3升，总质量是多少千克？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],6)
        p=m.prepare('电压12伏，电流2安，功率是多少瓦？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],24)

    def test_addition_requires_compatible_dimensions(self):
        m=self.module();p=m.prepare('速度为5米/秒，行驶3秒，路程是多少米？')
        with self.assertRaises(ValueError):m.compute('q0+q1',p)
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],15)

    def test_no_fabricated_constant_or_code(self):
        m=self.module();p=m.prepare('每箱质量2千克，共9箱，总质量是多少千克？')
        for expression in ['q0*100','q0*q99',"__import__('os')",'q0[0]','q0**999']:
            with self.assertRaises(ValueError):m.compute(expression,p)

    def test_calendar_and_historical_facts_unaffected(self):
        m=self.module()
        self.assertIsNone(m.prepare('2020年中尼公布的珠峰海拔是多少米？'))
        self.assertIsNone(m.prepare('若平年增加10天，则一年多少天？'))

    def test_chinese_count_and_ratio_are_not_lost(self):
        m=self.module();p=m.prepare('每箱质量2千克，共三箱，总质量是多少千克？')
        self.assertAlmostEqual(m.compute('q0*q1',p)['value'],6)
        p=m.prepare('新质量是原来的两倍，共九箱，总质量是多少千克？')
        self.assertEqual(p['status'],'missing')

    def test_per_item_price_cannot_be_added_once_to_total_delta(self):
        m=self.module();p=m.prepare('每件原价9元，涨价4元，买6件总价是多少元？')
        with self.assertRaises(ValueError):m.compute('q0+q1*q2',p)
        self.assertAlmostEqual(m.compute('(q0+q1)*q2',p)['value'],78)

    def test_more_than_original_is_delta_not_absolute(self):
        m=self.module();p=m.prepare('每袋比原来多70克，共3袋，总质量是多少千克？')
        self.assertEqual(p['status'],'missing')
        p=m.prepare('每袋原来180克，每袋比原来多70克，共3袋，总质量是多少千克？')
        self.assertEqual(p['status'],'ready')
        self.assertAlmostEqual(m.compute('(q0+q1)*q2',p)['value'],.75)

    def test_cheaper_than_original_still_needs_original_price(self):
        m=self.module();p=m.prepare('每件比原来便宜2元，共买3件，总价是多少元？')
        self.assertEqual(p['status'],'missing')
        p=m.prepare('原来每件9元，每件比原来便宜2元，共买3件，总价是多少元？')
        self.assertAlmostEqual(m.compute('(q0-q1)*q2',p)['value'],21)


if __name__=='__main__':unittest.main()
