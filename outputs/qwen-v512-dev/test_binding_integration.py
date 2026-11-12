import json
import unittest
from unittest.mock import patch

from engine import Engine, direct_fact_target, is_fact


class FakeEngine(Engine):
    def __init__(self, claims):
        self.claims = claims

    def token_count(self, messages, remaining):
        return 20

    def llm(self, messages, end, max_tokens=320, json_mode=False):
        if '检索关键词' in messages[0]['content']:
            return json.dumps({'queries': ['青国 首都']}), {}
        return json.dumps({'source_claims': self.claims}, ensure_ascii=False), {}


def document(source_id, text):
    return {'id': source_id, 'title': 'fixture', 'url': 'https://example.org/' + source_id, 'text': text}


def claim(source_id, value):
    return {'source_id': source_id, 'status': 'supports', 'span_id': 'p0', 'source_value': value, 'answer': value}


class BindingIntegrationTests(unittest.TestCase):
    def answer(self, question, docs, claims):
        with patch('engine.retrieve', return_value=(docs, [])):
            return FakeEngine(claims).answer(question)

    def test_direct_binding_has_explicit_lexical_audit(self):
        answer, audit = self.answer('青国的首都是什么？', [document('s1', '青国的首都是竹城。')], [claim('s1', '竹城')])
        self.assertEqual(answer, '竹城')
        self.assertEqual(audit['binding_checks'][0]['status'], 'supported_lexically')
        self.assertIn('lexical', audit['binding_checks'][0]['method'])

    def test_wrong_entity_does_not_create_source_conflict(self):
        docs = [document('s1', '青国的首都是竹城。'), document('s2', '蓝国的首都是雪城。')]
        answer, audit = self.answer('青国的首都是什么？', docs, [claim('s1', '竹城'), claim('s2', '雪城')])
        self.assertNotIn('冲突', answer)
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '竹城')

    def test_wrong_property_is_not_a_verified_fact(self):
        docs = [document('s1', '青国诗人逝世于竹城。')]
        answer, audit = self.answer('青国的首都是什么？', docs, [claim('s1', '竹城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '竹城')

    def test_multihop_does_not_trust_llm_guessed_entity(self):
        docs = [document('s1', '青国的首都是竹城。')]
        answer, audit = self.answer('阿青出生国家的首都是什么？', docs, [claim('s1', '竹城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertTrue(audit['retrieval_performed'])
        self.assertNotEqual(answer, '竹城')

    def test_model_cannot_hide_relevant_disagreement_as_irrelevant(self):
        docs = [document('s1', '青国的首都是竹城。'), document('s2', '青国的首都是雪城。')]
        claims = [claim('s1', '竹城'), {'source_id': 's2', 'status': 'irrelevant'}]
        answer, audit = self.answer('青国的首都是什么？', docs, claims)
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '竹城')

    def test_bound_disagreement_is_reported_as_conflict(self):
        docs = [document('s1', '青国的首都是竹城。'), document('s2', '青国的首都是雪城。')]
        answer, audit = self.answer('青国的首都是什么？', docs, [claim('s1', '竹城'), claim('s2', '雪城')])
        self.assertEqual(audit['evidence_status'], 'conflicting_sources')
        self.assertIn('冲突', answer)

    def test_common_direct_question_forms_are_routed(self):
        questions = {
            '星河研究院成立于哪一年？': ('星河研究院', 'foundation_year'),
            '星河研究院是什么时候成立的？': ('星河研究院', 'foundation_year'),
            '紫国的首都在哪里？': ('紫国', 'capital'),
            '紫国官方语言是什么？': ('紫国', 'official_language'),
            '阿月出生于哪里？': ('阿月', 'birthplace'),
            '阿月的出生地是哪里？': ('阿月', 'birthplace'),
        }
        for question, expected in questions.items():
            with self.subTest(question=question):
                self.assertTrue(is_fact(question))
                target = direct_fact_target(question)
                self.assertEqual((target['entity'], target['attribute']), expected)

    def test_multiperson_or_multihop_description_is_not_direct_target(self):
        for question in ['阿月出生国家的首都在哪里？', '创建星河研究院的人出生于哪里？', '这位作家出生在哪里？']:
            with self.subTest(question=question):
                self.assertIsNone(direct_fact_target(question))

    def test_formation_verbs_alone_do_not_route_arithmetic_to_fact(self):
        self.assertFalse(is_fact('成立一个小组，原有3人又加入2人，一共有多少人？'))

    def test_foundation_question_reaches_evidence_and_binding(self):
        docs = [document('s1', '星河研究院成立于1992年。')]
        answer, audit = self.answer('星河研究院成立于哪一年？', docs, [claim('s1', '1992')])
        self.assertEqual(answer, '1992')
        self.assertEqual(audit['binding_checks'][0]['status'], 'supported_lexically')

    def test_ancestry_and_organizational_predecessor_never_fall_back_to_guess(self):
        questions = [
            '阿桥的祖籍在哪里？',
            '阿舟的原籍是哪里？',
            '海青研究所成立前的机构名称是什么？',
            '海青研究所创立之前的组织叫什么？',
            '海青研究所建立以前的机构叫什么？',
            '海青研究所的前称是什么？',
        ]
        for question in questions:
            with self.subTest(question=question):
                with patch('engine.retrieve',return_value=([],[])) as retrieve:
                    answer, audit = FakeEngine([]).answer(question)
                retrieve.assert_called_once()
                self.assertEqual(audit['route'], 'external_evidence')
                self.assertEqual(audit['evidence_status'], 'unavailable')
                self.assertIn('无法', answer)

    def test_question_proves_distinct_subject_so_other_source_can_be_filtered(self):
        question = '已知紫国与绿国是不同国家，紫国的首都是什么？'
        docs = [document('s1', '紫国的首都是松城。'), document('s2', '绿国的首都是枫城。')]
        docs[1]['full_text'] = docs[1]['text']
        docs[1]['full_text_complete'] = True
        answer, audit = self.answer(question, docs, [claim('s1', '松城'), claim('s2', '枫城')])
        self.assertEqual(answer, '松城')
        self.assertEqual(audit['binding_checks'][1]['status'], 'excluded_unrelated')
        self.assertIn('distinct', audit['binding_checks'][1]['reason'])

    def test_unproven_other_name_is_not_automatically_unrelated(self):
        docs = [document('s1', '紫国的首都是松城。'), document('s2', '绿国的首都是枫城。')]
        answer, audit = self.answer('紫国的首都是什么？', docs, [claim('s1', '松城'), claim('s2', '枫城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '松城')

    def test_explicit_distinct_subject_does_not_hide_mixed_source(self):
        q = '已知紫国与绿国是不同国家，紫国的首都是什么？'
        docs = [document('s1', '紫国的首都是松城。'), document('s2', '绿国的首都是枫城。紫国的首都是竹城。')]
        answer, audit = self.answer(q, docs, [claim('s1', '松城'), claim('s2', '枫城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '松城')

    def test_incomplete_source_cannot_be_discarded_as_unrelated(self):
        q = '已知紫国与绿国是不同国家，紫国的首都是什么？'
        docs = [document('s1', '紫国的首都是松城。'), document('s2', '绿国的首都是枫城。')]
        answer, audit = self.answer(q, docs, [claim('s1', '松城'), claim('s2', '枫城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '松城')

    def test_full_text_field_alone_does_not_prove_completeness(self):
        q = '已知紫国与绿国是不同国家，紫国的首都是什么？'
        docs = [document('s1', '紫国的首都是松城。'), document('s2', '绿国的首都是枫城。')]
        docs[1]['full_text'] = docs[1]['text']
        answer, audit = self.answer(q, docs, [claim('s1', '松城'), claim('s2', '枫城')])
        self.assertEqual(audit['evidence_status'], 'binding_unresolved')
        self.assertNotEqual(answer, '松城')


if __name__ == '__main__':
    unittest.main()
