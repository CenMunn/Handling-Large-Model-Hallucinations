import time,unittest
from test_wikibase_walk import entity,FakeClient,snak
from wikibase_walk import Walker,plan


class FilmBinding(unittest.TestCase):
    def fixture(self):
        return {'Q101':entity('Q101','竹影',P31=['Q11424'],P57=['Q201'],P161=['Q202','Q201']),
                'Q102':entity('Q102','竹影',P31=['Q8261'],P50=['Q203']),
                'Q8261':entity('Q8261','小说'),
                'Q201':entity('Q201','阿青',P19=['Q301']),
                'Q202':entity('Q202','阿蓝',P19=['Q302']),
                'Q301':entity('Q301','香港特别行政区'),
                'Q302':entity('Q302','广东省')}

    def solve(self,items=None):
        items=items or self.fixture()
        return Walker(FakeClient(items,[('Q102','竹影'),('Q101','竹影')])).answer(
            '主演《竹影》的演员兼导演，其出生城市所属省级行政区的简称是什么？',time.monotonic()+4)

    def test_joint_director_and_cast_not_first_cast_member(self):
        out=self.solve()
        self.assertEqual(out['status'],'supported');self.assertIn('港',out['answer']);self.assertNotIn('粤',out['answer'])
        self.assertEqual([e['property'] for e in out['edges']],['P57','P161','P19'])

    def test_unrelated_namesake_taxonomy_cannot_exhaust_film_type_budget(self):
        items=self.fixture()
        items['Q102']=entity('Q102','竹影',P31=['Q800'])
        items['Q800']=entity('Q800','无关分类',P279=['Q'+str(900+i) for i in range(25)])
        self.assertEqual(self.solve(items)['status'],'supported')

    def test_actor_only_cannot_substitute_for_director(self):
        items=self.fixture();items['Q101']['claims']['P57'][0]['mainsnak']=dict(snak('Q203'),property='P57')
        out=self.solve(items);self.assertNotEqual(out['status'],'supported');self.assertNotIn('answer',out)

    def test_two_joint_matches_are_ambiguous(self):
        items=self.fixture();items['Q101']=entity('Q101','竹影',P31=['Q11424'],P57=['Q201','Q202'],P161=['Q202','Q201'])
        self.assertEqual(self.solve(items)['status'],'identity_unresolved')

    def test_character_qualifier_does_not_change_cast_members_identity(self):
        items=self.fixture();items['Q101']['claims']['P161'][1]['qualifiers']={'P453':[snak('Q401')]}
        out=self.solve(items);self.assertEqual(out['status'],'supported')
        self.assertIn('P453',next(e for e in out['edges'] if e['property']=='P161')['qualifiers'])

    def test_material_historical_and_unsupported_director_questions_are_excluded(self):
        for q in ['仅根据给定材料，主演《竹影》的演员兼导演出生地所属省级行政区简称是什么？',
                  '主演《竹影》的演员兼导演出生时所属省级行政区简称是什么？',
                  '主演《竹影》的演员兼导演现在担任什么职务？']:
            self.assertIsNone(plan(q))


if __name__=='__main__':unittest.main()
