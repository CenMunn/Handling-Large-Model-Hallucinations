import importlib
import unittest


class PolicyTests(unittest.TestCase):
    def test_same_language_answer_must_be_present_in_source_value(self):
        from evidence import validate_claim
        doc={'id':'s1','url':'https://example.org','text':'该人物出生在美国路易斯安那州新奥尔良。'}
        claim={'source_id':'s1','supported':True,'quote':doc['text'],'source_value':'美国路易斯安那州新奥尔良','answer':'新泽西州'}
        with self.assertRaises(ValueError):validate_claim(claim,[doc],'出生州是哪一州？')
        good={**claim,'source_value':'路易斯安那州','answer':'路易斯安那州'}
        self.assertEqual(validate_claim(good,[doc],'出生州是哪一州？')['answer'],'路易斯安那州')

    def test_language_answer_not_supported_by_country_only(self):
        from evidence import validate_claim
        doc={'id':'s1','url':'https://example.org','text':'他出生在英国。'}
        claim={'source_id':'s1','supported':True,'quote':doc['text'],'source_value':'英国','answer':'英语'}
        with self.assertRaises(ValueError):validate_claim(claim,[doc],'其出生国家的官方语言是什么？')

    def test_genuine_options_not_material_identifiers(self):
        engine = importlib.import_module('engine')
        self.assertTrue(hasattr(engine, 'choice_labels'), 'Choice formatting must depend on actual choices')
        self.assertEqual(engine.choice_labels('材料：A库编码R7，B库编码T8。问题：B库编码是什么？'), [])
        self.assertEqual(engine.choice_labels('本题为不定项选择题\nA.甲\nB.乙\nC.丙'), ['A', 'B', 'C'])
        self.assertEqual(engine.choice_labels('选择题：A.甲 B.乙'), ['A', 'B'])

    def merger(self):
        evidence = importlib.import_module('evidence')
        self.assertTrue(hasattr(evidence, 'aggregate_claims'), 'Every visible source must be accounted for')
        return evidence.aggregate_claims

    def fixtures(self, second='东城'):
        docs = [{'id':'s1','text':'登记编号为K8的设备存放在东城。','url':'https://source-one.example/a'},
                {'id':'s2','text':f'登记编号为K8的设备存放在{second}。','url':'https://source-two.example/b'}]
        claims = [{'source_id':d['id'],'status':'supports','answer':'东城' if d['id']=='s1' else second,'quote':d['text'],'source_value':'东城' if d['id']=='s1' else second} for d in docs]
        return docs, claims

    def test_conflict_is_not_silently_selected(self):
        docs, claims = self.fixtures('西城')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.merger()(claims, docs, '设备存放在哪座城市？')

    def test_consensus_and_single_source_are_distinguished(self):
        docs, claims = self.fixtures()
        result = self.merger()(claims, docs, '设备存放在哪座城市？')
        self.assertEqual(result['answer'], '东城')
        self.assertEqual(result['evidence_status'], 'source_bound_consensus')
        single = self.merger()(claims[:1]+[{'source_id':'s2','status':'irrelevant'}],docs,'设备存放在哪座城市？')
        self.assertEqual(single['evidence_status'], 'source_bound_single')

    def test_missing_duplicate_or_invented_source_is_rejected(self):
        docs, claims = self.fixtures()
        for candidate in [claims[:1], claims+[claims[0]], claims+[{'source_id':'invented','status':'irrelevant'}]]:
            with self.assertRaises(ValueError):
                self.merger()(candidate, docs, '设备存放在哪座城市？')

    def test_every_supporting_quote_is_checked(self):
        docs, claims = self.fixtures()
        claims[1] = {**claims[1], 'quote':'不存在的引文'}
        with self.assertRaises(ValueError):
            self.merger()(claims,docs,'设备存放在哪座城市？')

    def test_uncertain_relevant_source_blocks_definite_answer(self):
        docs, claims = self.fixtures()
        claims[1] = {'source_id':'s2','status':'uncertain'}
        with self.assertRaisesRegex(ValueError,'uncertain'):
            self.merger()(claims,docs,'设备存放在哪座城市？')

    def test_person_full_name_and_unique_surname_can_agree(self):
        docs=[{'id':'s1','url':'https://one.example','text':'设计者为阿伦·诺克。'}, {'id':'s2','url':'https://two.example','text':'诺克设计了该建筑。'}]
        claims=[{'source_id':'s1','status':'supports','answer':'阿伦·诺克','quote':docs[0]['text'],'source_value':'阿伦·诺克'}, {'source_id':'s2','status':'supports','answer':'诺克','quote':docs[1]['text'],'source_value':'诺克'}]
        result=self.merger()(claims,docs,'该建筑的设计者是谁？')
        self.assertEqual(result['answer'],'阿伦·诺克')

    def test_different_people_with_shared_surname_still_conflict(self):
        docs=[{'id':'s1','url':'https://one.example','text':'设计者为阿伦·诺克。'}, {'id':'s2','url':'https://two.example','text':'设计者为贝林·诺克。'}]
        claims=[{'source_id':d['id'],'status':'supports','answer':'阿伦·诺克' if i==0 else '贝林·诺克','quote':d['text'],'source_value':'阿伦·诺克' if i==0 else '贝林·诺克'} for i,d in enumerate(docs)]
        with self.assertRaisesRegex(ValueError,'conflict'):self.merger()(claims,docs,'该建筑的设计者是谁？')


if __name__ == '__main__':
    unittest.main()
