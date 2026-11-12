import unittest
import importlib.util


class ScopeTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('fact_scope'),'scope-aware evidence policy is missing')
        import fact_scope
        return fact_scope

    def record(self,value,scope,quote,entity='青国',attribute='language',**extra):
        return dict(entity=entity,attribute=attribute,value=value,scope=scope,quote=quote,source_id='s',**extra)

    def choose(self,q,records,**kwargs):
        docs=[{'id':'s','url':'https://www.legislation.gov.uk/example','text':'\n'.join(r['quote'] for r in records)}]
        return self.module().select(q,records,docs,**kwargs)

    def test_official_language_prefers_law_over_usage(self):
        rows=[self.record('青语','legal','青国法律规定：青国的法定官方语言为青语。'),self.record('蓝语','usage','青国主要使用蓝语。')]
        r=self.choose('青国的官方语言是什么？',rows)
        self.assertEqual(r['status'],'supported');self.assertEqual(r['value'],'青语');self.assertEqual(r['scope'],'legal')

    def test_usage_fallback_does_not_assert_absence_of_legal_languages(self):
        r=self.choose('青国的官方语言是什么？',[self.record('蓝语','usage','青国主要使用蓝语。')])
        self.assertEqual(r['status'],'qualified');self.assertIn('法律',r['answer']);self.assertIn('主要使用',r['answer'])
        self.assertNotIn('没有官方语言',r['answer'])

    def test_conflicting_legal_values_do_not_fall_back_to_majority_usage(self):
        rows=[self.record('青语','legal','青国法律规定：青国的唯一法定官方语言为青语。'),self.record('红语','legal','青国法律规定：青国的唯一法定官方语言为红语。'),self.record('蓝语','usage','青国主要使用蓝语。')]
        self.assertEqual(self.choose('青国的官方语言是什么？',rows)['status'],'conflict')

    def test_nonexclusive_legal_mentions_do_not_create_false_conflict(self):
        rows=[self.record('青语','legal','青国法律规定：青国的法定官方语言包括青语。'),self.record('红语','legal','青国法律规定：青国的法定官方语言包括红语。')]
        r=self.choose('青国的官方语言是什么？',rows)
        self.assertEqual(r['status'],'qualified');self.assertIn('青语',r['answer']);self.assertIn('红语',r['answer']);self.assertIn('完整',r['answer'])

    def test_named_joint_legal_language_sets_are_preserved(self):
        r=self.choose('青国的官方语言是什么？',[self.record('青语和红语','legal','青国法律规定：青国的法定官方语言为青语和红语。')])
        self.assertEqual(r['value'],'青语和红语')

    def test_repealed_or_draft_law_does_not_establish_current_language(self):
        for suffix in ['，该条款已废止。','，该规定尚未生效。','。该法律于2019年已废止。']:
            with self.subTest(suffix=suffix):
                row=self.record('青语','legal','青国法律规定：青国的法定官方语言为青语'+suffix)
                self.assertEqual(self.choose('青国的官方语言是什么？',[row])['status'],'insufficient')

    def test_explicit_historical_language_question_requires_temporal_binding(self):
        row=self.record('青语','legal','青国法律规定：青国的法定官方语言为青语。')
        self.assertEqual(self.choose('青国的官方语言在1990年是什么？',[row])['status'],'missing_time_scope')

    def test_untrusted_flag_or_nonliteral_quote_does_not_establish_law(self):
        m=self.module();row=self.record('青语','legal','青国法律规定官方语言为青语。')
        for source in [dict(id='s',url='https://news.example/law',text=row['quote']),dict(id='s',url='https://www.legislation.gov.uk/example',text='青国主要使用蓝语。')]:
            self.assertEqual(m.select('青国的官方语言是什么？',[row],[source])['status'],'insufficient')

    def test_river_whole_precedes_larger_reach(self):
        rows=[self.record('120公里','whole','青河全河从源头至河口的长度为120公里。',entity='青河',attribute='length'),self.record('900公里','reach','青河的乙段长度为900公里。',entity='青河',attribute='length',scope_detail='乙段')]
        r=self.choose('青河全长多少公里？',rows)
        self.assertEqual(r['value'],'120公里');self.assertEqual(r['scope'],'whole')

    def test_river_differing_whole_definitions_are_not_resolved_by_maximum(self):
        rows=[self.record('120公里','whole','青河全河长度为120公里。',entity='青河',attribute='length'),self.record('160公里','whole','青河全河长度为160公里。',entity='青河',attribute='length')]
        self.assertEqual(self.choose('青河全长多少公里？',rows)['status'],'conflict')

    def test_longest_available_named_reach_is_explicitly_not_whole_river(self):
        rows=[self.record('20公里','reach','青河的甲段长度为20公里。',entity='青河',attribute='length',scope_detail='甲段'),self.record('35公里','reach','青河的乙段长度为35公里。',entity='青河',attribute='length',scope_detail='乙段')]
        r=self.choose('青河全长多少公里？',rows)
        self.assertEqual(r['status'],'qualified');self.assertEqual(r['value'],'35公里');self.assertIn('乙段',r['answer']);self.assertIn('不代表全河',r['answer'])

    def test_river_units_are_compared_after_conversion(self):
        rows=[self.record('800米','reach','青河的甲段长度为800米。',entity='青河',attribute='length',scope_detail='甲段'),self.record('2公里','reach','青河的乙段长度为2公里。',entity='青河',attribute='length',scope_detail='乙段')]
        self.assertEqual(self.choose('青河全长多少公里？',rows)['value'],'2公里')

    def test_reach_cannot_be_labeled_as_whole(self):
        row=self.record('900公里','whole','青河下游河段全长900公里。',entity='青河',attribute='length')
        self.assertEqual(self.choose('青河全长多少公里？',[row])['status'],'insufficient')

    def test_mainstem_and_whole_length_are_not_silently_merged(self):
        rows=[self.record('120公里','whole','青河全河长度为120公里。',entity='青河',attribute='length'),self.record('80公里','mainstem','青河干流长度为80公里。',entity='青河',attribute='length')]
        r=self.choose('青河全长多少公里？',rows)
        self.assertEqual(r['scope'],'whole');self.assertTrue(r['other_scopes'])

    def test_employment_requires_design_window_and_rejects_current_only(self):
        row=self.record('青州','employment','林杉从1980年至1990年在青州的青竹实验室工作。',entity='林杉',attribute='workplace',start_year=1980,end_year=1990)
        r=self.choose('林杉设计该语言当时的工作地点在哪个州？',[row],design_window=(1982,1987))
        self.assertEqual(r['status'],'supported');self.assertEqual(r['value'],'青州')
        current=self.record('蓝州','employment','林杉从2000年至2020年在蓝州的蓝竹实验室工作。',entity='林杉',attribute='workplace',start_year=2000,end_year=2020)
        self.assertEqual(self.choose('林杉设计该语言当时的工作地点在哪个州？',[current],design_window=(1982,1987))['status'],'insufficient')

    def test_employment_cannot_invent_dates_or_design_window(self):
        row=self.record('青州','employment','林杉目前在青州工作。',entity='林杉',attribute='workplace',start_year=1980,end_year=1990)
        q='林杉设计该语言当时的工作地点在哪个州？'
        self.assertEqual(self.choose(q,[row],design_window=(1982,1987))['status'],'insufficient')
        self.assertEqual(self.choose(q,[row])['status'],'missing_design_window')

    def test_employment_changes_preserve_both_locations_and_dates(self):
        rows=[self.record('青州','employment','林杉从1980年至1984年在青州工作。',entity='林杉',attribute='workplace',start_year=1980,end_year=1984),self.record('蓝州','employment','林杉从1985年至1990年在蓝州工作。',entity='林杉',attribute='workplace',start_year=1985,end_year=1990)]
        r=self.choose('林杉设计该语言当时的工作地点在哪个州？',rows,design_window=(1982,1987))
        self.assertEqual(r['status'],'qualified');self.assertIn('青州',r['answer']);self.assertIn('蓝州',r['answer'])

    def test_per_cell_count_does_not_use_whole_body_or_other_species(self):
        rows=[self.record('100至200个','per_human_cell','人体一般细胞中，每个细胞的甲细胞器通常有100至200个。',entity='甲细胞器',attribute='count',cell_type='general'),self.record('900万个','whole_body','人体全身的甲细胞器总数为900万个。',entity='甲细胞器',attribute='count'),self.record('700个','per_human_cell','小鼠每个细胞的甲细胞器通常有700个。',entity='甲细胞器',attribute='count',cell_type='general')]
        r=self.choose('甲细胞器在人体细胞中的数量通常是什么范围？',rows)
        self.assertEqual(r['value'],'100至200个')

    def test_zero_count_is_not_missing_and_specific_cell_type_is_not_generalized(self):
        row=self.record('0个','per_human_cell','人体成熟红细胞中，每个细胞的甲细胞器数量为0个。',entity='甲细胞器',attribute='count',cell_type='成熟红细胞')
        r=self.choose('甲细胞器在人体细胞中的数量通常是什么范围？',[row])
        self.assertEqual(r['status'],'qualified');self.assertIn('成熟红细胞',r['answer']);self.assertIn('0个',r['answer'])

    def test_birthplace_does_not_accept_ancestry(self):
        row=self.record('青城','birthplace','林杉祖籍青城。',entity='林杉',attribute='birthplace')
        self.assertEqual(self.choose('林杉出生在哪里？',[row])['status'],'insufficient')

    def test_unverified_name_guessed_from_documents_cannot_become_bound_subject(self):
        row=self.record('青城','birthplace','作家林杉出生于青城。',entity='林杉',attribute='birthplace')
        self.assertEqual(self.choose('某本书作者出生在哪里？',[row])['status'],'insufficient')

    def test_question_scope_overrides_default_and_materials_are_excluded(self):
        m=self.module()
        self.assertEqual(m.policy('甲河下游乙段长多少公里？')['preferred_scopes'],['reach'])
        self.assertEqual(m.policy('甲细胞器在人体全身的总数是多少？')['preferred_scopes'],['whole_body'])
        self.assertIsNone(m.policy('仅根据给定材料，青国官方语言是什么？'))


if __name__=='__main__':unittest.main()
