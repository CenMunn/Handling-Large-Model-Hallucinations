import time,unittest
from unittest.mock import patch
from test_binding_integration import FakeEngine,document

QUESTION='创作《竹影》的作家，其出生地目前所属国家的首都是什么？'

class IntegrationTests(unittest.TestCase):
    def test_unknown_multihop_can_use_a_connected_audited_path(self):
        docs=[document('s','第三方网页描述一部作品，但未直接给出首都。')]
        result={'status':'supported','answer':'竹城。来源：Wikidata。','edges':[{'subject':'Q101','property':'P50','object':'Q201','source_url':'https://www.wikidata.org/wiki/Q101'}],'scope':'current_birthplace_country'}
        with patch('engine.retrieve',return_value=(docs,[])),patch('engine.structured_lookup',return_value=result) as lookup:
            answer,audit=FakeEngine([]).answer(QUESTION)
        self.assertIn('竹城',answer);self.assertEqual(audit['route'],'structured_evidence')
        self.assertEqual(audit['structured_evidence']['scope'],'current_birthplace_country');lookup.assert_called_once()

    def test_tool_timeout_does_not_create_a_fact_or_a_service_exception(self):
        with patch('engine.retrieve',return_value=([document('s','原始资料。')],[])),patch('engine.structured_lookup',return_value={'status':'timeout','deadline_enforced':True}):
            answer,audit=FakeEngine([]).answer(QUESTION)
        self.assertNotEqual(audit['evidence_status'],'source_bound')
        self.assertTrue(audit['structured_tool_failed']);self.assertNotIn('竹城',answer)

    def test_closed_material_cannot_use_external_structured_data(self):
        with patch('engine.structured_lookup') as lookup:
            answer,audit=FakeEngine([]).answer('仅根据给定材料回答：材料没有给出首都。'+QUESTION)
        lookup.assert_not_called();self.assertEqual(audit['route'],'closed_scope')

    def test_no_web_results_does_not_prevent_another_evidence_source(self):
        with patch('engine.retrieve',return_value=([],[])),patch('engine.structured_lookup',return_value={'status':'supported','answer':'竹城','edges':[],'scope':'current_birthplace_country'}):
            answer,audit=FakeEngine([]).answer(QUESTION)
        self.assertEqual(answer,'竹城');self.assertEqual(audit['route'],'structured_evidence')

if __name__=='__main__':unittest.main()
