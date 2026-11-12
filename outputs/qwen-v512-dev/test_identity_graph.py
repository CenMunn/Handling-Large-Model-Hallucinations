import unittest

from identity_graph import bind_identity


class IdentityGraphTests(unittest.TestCase):
    @staticmethod
    def doc(text, url='https://example.invalid/a'):
        return {'text': text, 'url': url}

    def test_occupation_and_birth_in_same_clause(self):
        result = bind_identity('演员林舟的出生地是什么？', [self.doc('演员林舟出生于青城。')])
        self.assertEqual((result['status'], result['value']), ('supported', '青城'))
        self.assertIn('演员林舟出生于青城', result['evidence'][0]['quote'])

    def test_work_and_ancestry(self):
        result = bind_identity('创作《松屿》的林舟的籍贯是什么？', [self.doc('创作《松屿》的林舟的籍贯是木县。')])
        self.assertEqual((result['status'], result['value']), ('supported', '木县'))

    def test_affiliation(self):
        result = bind_identity('任职于云台研究院的许松的出生地是什么？', [self.doc('任职于云台研究院的许松出生于白市。')])
        self.assertEqual((result['status'], result['value']), ('supported', '白市'))

    def test_ancestry_is_not_birth(self):
        result = bind_identity('演员林舟的出生地是什么？', [self.doc('演员林舟的祖籍是青城。')])
        self.assertEqual(result['status'], 'unresolved')

    def test_same_name_different_identity_is_not_joined(self):
        result = bind_identity('演员林舟的出生地是什么？', [self.doc('演员林舟的祖籍是青城。作家林舟出生于白城。')])
        self.assertEqual(result['status'], 'unresolved')

    def test_do_not_join_separate_sentences_or_sources(self):
        docs = [self.doc('林舟是演员。林舟出生于青城。'), self.doc('演员林舟在演出。')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_pronoun_not_bound(self):
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', [self.doc('演员林舟是演出者。他出生于青城。')])['status'], 'unresolved')

    def test_explicit_negation_and_hedging_declined(self):
        for text in ['演员林舟并非出生于青城。', '演员林舟出生于青城的说法是假的。', '据说演员林舟出生于青城。', '演员林舟可能出生于青城。', '演员林舟出生于青城，但这一说法是错误的。', '演员林舟出生于青城，未经证实。']:
            with self.subTest(text=text):
                self.assertEqual(bind_identity('演员林舟的出生地是什么？', [self.doc(text)])['status'], 'unresolved')

    def test_direct_conflict_declined(self):
        docs = [self.doc('演员林舟出生于青城。'), self.doc('演员林舟出生于白城。', 'https://example.invalid/b')]
        result = bind_identity('演员林舟的出生地是什么？', docs)
        self.assertEqual(result['status'], 'conflict')
        self.assertNotIn('value', result)

    def test_alias_or_ungrounded_target_never_invented(self):
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', [self.doc('演员小舟出生于青城。')])['status'], 'unresolved')
        self.assertEqual(bind_identity('一位知名演员的出生地是什么？', [self.doc('演员林舟出生于青城。')])['status'], 'unsupported')

    def test_work_and_affiliation_require_exact_identity(self):
        self.assertEqual(bind_identity('创作《松屿》的林舟的出生地是什么？', [self.doc('创作《风屿》的林舟出生于青城。')])['status'], 'unresolved')
        self.assertEqual(bind_identity('任职于云台研究院的许松的出生地是什么？', [self.doc('任职于山台研究院的许松出生于青城。')])['status'], 'unresolved')

    def test_explainer_must_not_create_value(self):
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', [self.doc('演员林舟出生于青城的哥哥。')])['status'], 'unresolved')

    def test_other_source_with_unqualified_same_name_blocks_support(self):
        docs = [self.doc('演员林舟出生于青城。'), self.doc('林舟出生于白城。', 'https://example.invalid/b')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_other_source_with_unbound_same_name_blocks_support(self):
        docs = [self.doc('演员林舟出生于青城。'), self.doc('林舟出生地有争议。', 'https://example.invalid/b')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_same_source_has_both_bound_and_unbound_name(self):
        docs = [self.doc('演员林舟出生于青城。林舟出生于白城。')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_unrelated_source_does_not_block_support(self):
        docs = [self.doc('演员林舟出生于青城。'), self.doc('画家白果出生于木城。')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'supported')

    def test_unresolved_pronoun_claim_in_same_source_blocks_support(self):
        docs = [self.doc('演员林舟出生于青城。他出生于白城。')]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_unreadable_source_cannot_be_silently_discarded(self):
        docs = [self.doc('演员林舟出生于青城。'), {'url': 'https://example.invalid/b'}]
        self.assertEqual(bind_identity('演员林舟的出生地是什么？', docs)['status'], 'unresolved')

    def test_work_title_director_and_natural_ancestry_question(self):
        q='依据检索资料，电影《微山》的导演陈月籍贯是哪个县？'
        result=bind_identity(q, [self.doc('电影《微山》的导演陈月的籍贯是兰溪县。')])
        self.assertEqual((result['status'], result['value']), ('supported', '兰溪县'))

    def test_author_and_natural_birth_question(self):
        q='依据检索资料，《远星》的作者文沐出生于哪个城市？'
        result=bind_identity(q, [self.doc('《远星》的作者文沐出生于清泉市。')])
        self.assertEqual((result['status'], result['value']), ('supported', '清泉市'))

    def test_affiliation_and_occupation_both_are_essential(self):
        q='依据检索资料，在石湾考古中心工作的研究员秦晓出生于哪个城市？'
        s='在石湾考古中心工作的研究员秦晓出生于青竹市。'
        self.assertEqual(bind_identity(q, [self.doc(s)])['status'], 'supported')
        for wrong in ['在星湾考古中心工作的研究员秦晓出生于青竹市。',
                      '在石湾考古中心工作的音乐家秦晓出生于青竹市。',
                      '研究员秦晓出生于青竹市。',
                      '在石湾考古中心工作的研究员秦晓并非出生于青竹市。']:
            with self.subTest(wrong=wrong):
                self.assertEqual(bind_identity(q, [self.doc(wrong)])['status'], 'unresolved')

    def test_explicit_identity_qualifiers_cannot_be_cross_joined(self):
        q='《远星》的作者文沐出生于哪个城市？'
        for text in ['《远星》的作者文沐在工作。文沐出生于清泉市。',
                     '《远星》的作者文沐的籍贯是木县。画家文沐出生于清泉市。',
                     '《远星》的作者文沐出生于清泉市的说法是假的。']:
            with self.subTest(text=text):
                self.assertEqual(bind_identity(q, [self.doc(text)])['status'], 'unresolved')

    def test_natural_question_detects_conflicting_qualified_sources(self):
        q='《远星》的作者文沐出生于哪个城市？'
        docs=[self.doc('《远星》的作者文沐出生于清泉市。'),
              self.doc('《远星》的作者文沐出生于安澜市。', 'https://example.invalid/b')]
        self.assertEqual(bind_identity(q, docs)['status'], 'conflict')

    def test_ancestry_subtypes_are_not_interchangeable(self):
        result=bind_identity('画家谢然的籍贯是哪个县？', [self.doc('画家谢然的祖籍是松溪县。')])
        self.assertEqual(result['status'], 'unresolved')
        result=bind_identity('画家谢然的祖籍是哪个县？', [self.doc('画家谢然的籍贯是松溪县。')])
        self.assertEqual(result['status'], 'unresolved')

    def test_work_type_and_performer_are_both_anchored(self):
        q='舞台剧《春林》的表演者沈北出生于哪个城市？'
        self.assertEqual(bind_identity(q,[self.doc('舞台剧《春林》的表演者沈北出生于清溪市。')])['status'],'supported')
        for text in ['舞台剧《秋林》的表演者沈北出生于清溪市。',
                     '舞台剧《春林》的导演沈北出生于清溪市。',
                     '表演者沈北出生于清溪市。']:
            self.assertEqual(bind_identity(q,[self.doc(text)])['status'],'unresolved')

    def test_named_research_field_is_an_exact_required_qualifier(self):
        q='研究园艺的李雨的籍贯是哪个县？'
        self.assertEqual(bind_identity(q,[self.doc('研究园艺的李雨的籍贯是龙城县。')])['status'],'supported')
        self.assertEqual(bind_identity(q,[self.doc('研究天文的李雨的籍贯是龙城县。')])['status'],'unresolved')

    def test_institution_type_and_work_word_are_not_dropped(self):
        q='在松峰图书馆任职的馆员何川出生于哪个城市？'
        self.assertEqual(bind_identity(q,[self.doc('在松峰图书馆任职的馆员何川出生于白石市。')])['status'],'supported')
        self.assertEqual(bind_identity(q,[self.doc('在竹峰图书馆任职的馆员何川出生于白石市。')])['status'],'unresolved')

    def test_organization_predecessor_and_suborganization_are_distinct(self):
        q='竹原环境研究所的前身叫什么？'
        good=self.doc('竹原环境研究所的前身是雪原实验站。')
        self.assertEqual(bind_identity(q,[good])['value'],'雪原实验站')
        other=self.doc('竹原环境研究所下属风原资料馆。风原资料馆的前身是蓝汀档案馆。')
        self.assertEqual(bind_identity(q,[other])['status'],'unresolved')
        bad=self.doc('竹原环境研究所的前身不是雪原实验站。')
        self.assertEqual(bind_identity(q,[bad])['status'],'unresolved')

    def test_organization_predecessor_conflict_is_not_guessed(self):
        q='竹原环境研究所的前身叫什么？'
        docs=[self.doc('竹原环境研究所的前身是雪原实验站。'),
              self.doc('竹原环境研究所的前身是河湾实验站。')]
        self.assertEqual(bind_identity(q,docs)['status'],'conflict')


if __name__ == '__main__':
    unittest.main()
