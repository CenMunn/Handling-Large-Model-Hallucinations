import unittest
from unittest.mock import patch
from test_scope_integration import Fake
import test_curated_chains as fixtures


class CuratedIntegrationTests(unittest.TestCase):
    def test_source_index_answers_after_retrieval_even_when_search_has_no_result(self):
        import curated_chains
        real=curated_chains.resolve
        with patch('engine.retrieve',return_value=([],[])),patch('engine.resolve_curated',side_effect=lambda q:real(q,[fixtures.fixture()])):
            answer,audit=Fake().answer('Nacre设计开始到首次发布时，设计者的历史工作地点属于美国哪个州？')
        self.assertIn('俄勒冈州',answer);self.assertEqual(audit['route'],'curated_historical_workplace')
        self.assertTrue(audit['retrieval_performed']);self.assertTrue(audit['curated_evidence']['source_access'])


if __name__=='__main__':unittest.main()
