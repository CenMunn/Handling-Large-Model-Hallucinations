import unittest
from unittest.mock import patch
from test_binding_integration import FakeEngine, claim, document

class RetrievalFirstTests(unittest.TestCase):
    def test_unrecognized_multihop_retrieves_without_trusting_guessed_entity(self):
        docs=[document('s1','青国的首都是竹城。')]
        with patch('engine.retrieve',return_value=(docs,[])) as retrieve:
            answer,audit=FakeEngine([claim('s1','竹城')]).answer('阿青出生国家的首都是什么？')
        retrieve.assert_called_once()
        self.assertTrue(audit['retrieval_performed'])
        self.assertEqual(audit['evidence_status'],'binding_unresolved')
        self.assertNotEqual(answer,'竹城')
        self.assertEqual(audit['binding_checks'][0]['entity'],'unresolved')

    def test_unrecognized_with_no_sources_is_not_source_conflict(self):
        with patch('engine.retrieve',return_value=([],[])) as retrieve:
            answer,audit=FakeEngine([]).answer('阿青出生国家的首都是什么？')
        retrieve.assert_called_once()
        self.assertTrue(audit['retrieval_performed'])
        self.assertEqual(audit['evidence_status'],'unavailable')
        self.assertNotIn('冲突',answer)

    def test_unknown_relation_cannot_trust_irrelevant_labels_to_hide_conflict(self):
        docs=[document('s1','青国的首都是竹城。'),document('s2','青国的首都是柳城。')]
        claims=[claim('s1','竹城'),{'source_id':'s2','status':'irrelevant'}]
        with patch('engine.retrieve',return_value=(docs,[])):
            answer,audit=FakeEngine(claims).answer('阿青出生国家的首都是什么？')
        self.assertEqual(audit['evidence_status'],'binding_unresolved')
        self.assertNotEqual(answer,'竹城')
        self.assertEqual(len(audit['binding_checks']),2)

if __name__ == '__main__': unittest.main()
