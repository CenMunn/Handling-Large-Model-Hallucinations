import unittest
from unittest.mock import patch

from test_binding_integration import FakeEngine, claim, document


class EvidencePrefixTests(unittest.TestCase):
    def test_narrow_retrieval_prefix_reaches_bound_evidence(self):
        prefixes = ['依据检索资料，', '根据检索资料，', '仅根据检索资料，', '只依据检索资料：']
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                with patch('engine.retrieve', return_value=([document('s1', '青国的首都是竹城。')], [])) as retrieve:
                    answer, audit = FakeEngine([claim('s1', '竹城')]).answer(prefix + '青国的首都是什么？')
                self.assertTrue(retrieve.called)
                self.assertEqual(answer, '竹城')
                self.assertEqual(audit['route'], 'external_evidence')

    def test_no_evidence_does_not_fall_back_to_model_knowledge(self):
        with patch('engine.retrieve', return_value=([], [])) as retrieve:
            answer, audit = FakeEngine([]).answer('仅根据检索资料，青国的首都是什么？')
        self.assertTrue(retrieve.called)
        self.assertEqual(audit['evidence_status'], 'unavailable')
        self.assertNotEqual(answer, '竹城')

    def test_identity_qualifier_remains_in_retrieved_evidence_path(self):
        docs = [document('s1', '演员林舟出生于青城。')]
        with patch('engine.retrieve', return_value=(docs, [])) as retrieve:
            answer, audit = FakeEngine([]).answer('依据检索资料，演员林舟的出生地是什么？')
        self.assertTrue(retrieve.called)
        self.assertEqual(answer, '青城')
        self.assertEqual(audit['relation_checks']['target']['entity'], '林舟')
        self.assertEqual(audit['evidence_status'], 'literal_relation_bound')

    def test_given_material_stays_closed_scope(self):
        class ClosedFake(FakeEngine):
            def llm(self, messages, end, max_tokens=320, json_mode=False):
                return '材料没有该信息。', {}
        for prefix in ['仅根据所给材料，', '根据下列材料，', '依据提供的资料，']:
            with self.subTest(prefix=prefix):
                with patch('engine.retrieve') as retrieve:
                    answer, audit = ClosedFake([]).answer(prefix + '青国的首都是什么？')
                retrieve.assert_not_called()
                self.assertEqual(audit['route'], 'closed_scope')

    def test_retrieval_prefix_fetches_but_does_not_guess_multihop(self):
        with patch('engine.retrieve',return_value=([],[])) as retrieve:
            answer, audit = FakeEngine([]).answer('根据检索资料，阿青出生国家的首都是什么？')
        retrieve.assert_called_once()
        self.assertEqual(audit['evidence_status'], 'unavailable')

    def test_explicit_search_does_not_require_preparsed_entity(self):
        class EmptySearchEngine(FakeEngine):
            def llm(self,messages,end,max_tokens=320,json_mode=False):
                return '{"queries":["示例问题"]}', {}
        questions=['请依据检索资料回答：某作品的负责人获得什么奖？',
                   '仅根据检索结果作答：某机构后来迁往哪一座城市？']
        for question in questions:
            with self.subTest(question=question),patch('engine.retrieve',return_value=([],[])) as retrieve:
                answer,audit=EmptySearchEngine([]).answer(question)
                retrieve.assert_called_once()
                self.assertEqual(audit['evidence_status'],'unavailable')


if __name__ == '__main__':
    unittest.main()
