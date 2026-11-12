import time,unittest
import test_wikibase_walk as fixtures
from test_wikibase_walk import FakeClient,entity
from wikibase_walk import Walker


class PartialProgress(unittest.TestCase):
    def test_identified_author_without_birthplace_is_reported_specifically(self):
        items=fixtures.WalkTests().fixture();items['Q201']['claims'].pop('P19')
        out=Walker(FakeClient(items,[('Q101','竹影')])).answer('创作小说《竹影》的作家，其出生地目前所属国家的首都是什么？',time.monotonic()+4)
        self.assertEqual(out['status'],'insufficient')
        self.assertIn('阿青',out.get('partial_answer',''));self.assertIn('出生地',out.get('partial_answer',''))
        self.assertNotIn('柳城',out.get('partial_answer',''));self.assertNotIn('首都是',out.get('partial_answer',''))

    def test_founder_province_gap_keeps_confirmed_birthplace(self):
        items={'Q601':entity('Q601','青木公司',P112=['Q602']),'Q602':entity('Q602','阿松',P19=['Q603']),'Q603':entity('Q603','桃县')}
        out=Walker(FakeClient(items,[('Q601','青木公司')])).answer('青木公司创始人的出生县位于哪个省份？',time.monotonic()+4)
        self.assertEqual(out['status'],'insufficient');self.assertIn('阿松',out.get('partial_answer',''));self.assertIn('桃县',out.get('partial_answer',''))
        self.assertIn('行政',out.get('partial_answer',''))

    def test_ambiguous_person_never_appears_as_confirmed_progress(self):
        items=fixtures.WalkTests().fixture();items['Q101']=entity('Q101','竹影',P31=['Q8261'],P50=['Q201','Q202'])
        out=Walker(FakeClient(items,[('Q101','竹影')])).answer('创作小说《竹影》的作家，其出生地目前所属国家的首都是什么？',time.monotonic()+4)
        self.assertEqual(out['status'],'identity_unresolved');self.assertNotIn('partial_answer',out)

if __name__=='__main__':unittest.main()
