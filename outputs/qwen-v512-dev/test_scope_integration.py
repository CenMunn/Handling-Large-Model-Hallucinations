import json,time,unittest
from unittest.mock import patch
from engine import Engine
from test_cell_source import QUESTION,BODY


class Fake(Engine):
    def __init__(self):self.calls=0
    def token_count(self,*args):return 200
    def llm(self,*args,**kwargs):
        self.calls+=1
        if self.calls>1:raise AssertionError('Literal scoped evidence should not need another model pass')
        return json.dumps({'queries':['主体 属性']}),{}


def doc(text,url='https://www.legislation.gov.uk/example'):
    return {'id':'s','title':'资料','url':url,'text':text}


class ScopeIntegration(unittest.TestCase):
    def test_explicit_language_selects_legal_source_before_usage(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([doc('青国法律规定：青国的法定官方语言为青语。青国主要使用蓝语。')],[])):
            answer,audit=engine.answer('青国的官方语言是什么？')
        self.assertEqual(audit['route'],'scoped_evidence');self.assertIn('青语',answer);self.assertNotIn('蓝语',answer)
        self.assertEqual(engine.calls,1)

    def test_unsupported_anonymous_identity_is_not_promoted_by_keyword_match(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([doc('青国法律规定：青国的法定官方语言为青语。')],[])):
            answer,audit=engine.answer('某语言设计者所在国家的官方语言是什么？')
        self.assertNotIn('青语',answer);self.assertEqual(audit['evidence_status'],'binding_unresolved')
        self.assertEqual(engine.calls,1);self.assertIn('factual_scope',audit)

    def test_nonlegal_source_does_not_fall_through_to_unqualified_old_extractor(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([doc('青国的官方语言为青语。','https://news.example/page')],[])):
            answer,audit=engine.answer('青国的官方语言是什么？')
        self.assertEqual(engine.calls,1);self.assertEqual(audit['evidence_status'],'scoped_binding_insufficient');self.assertNotIn('青语',answer)

    def test_mainstem_and_named_reach_do_not_become_whole_length(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([doc('白溪的干流长度为86公里。白溪的乙段长度为90公里。','https://water.gov.cn/example')],[])):
            answer,audit=engine.answer('白溪全长多少公里？')
        self.assertEqual(audit['route'],'scoped_evidence');self.assertIn('86公里',answer);self.assertIn('干流',answer);self.assertNotIn('90公里',answer)

    def test_birthplace_missing_partial_information_is_preserved(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([],[])),patch('engine.structured_lookup',return_value={'status':'insufficient','partial_answer':'资料已识别《竹影》作者为阿青；但未找到可核实的出生地。','edges':[{'subject':'Q101','property':'P50','object':'Q201','source_url':'https://www.wikidata.org/wiki/Q101'}]}):
            answer,audit=engine.answer('创作小说《竹影》的作家，其出生地目前所属国家的首都是什么？')
        self.assertEqual(audit['route'],'structured_partial');self.assertIn('阿青',answer);self.assertIn('出生地',answer)

    def test_literal_per_cell_count_does_not_need_model_self_review(self):
        engine=Fake()
        with patch('engine.retrieve',return_value=([doc('人体一般细胞中，每个细胞的乙细胞器通常有80至600个。','https://bio.edu.cn/example')],[])):
            answer,audit=engine.answer('乙细胞器在人体细胞中的数量通常是什么范围？')
        self.assertEqual(audit['route'],'scoped_evidence');self.assertIn('80至600个',answer);self.assertIn('每个',answer)

    def test_anonymous_functional_count_uses_independently_fetched_body(self):
        engine=Fake();url='https://medlineplus.gov/genetics/example/'
        # Search response text deliberately disagrees. The source adapter must
        # independently read the primary body, not confirm the provider text.
        docs=[doc('每个细胞有900万个。',url)]
        source={'url':url,'text':BODY,'transport':'independent_https','raw_sha256':'fixture'}
        with patch('engine.retrieve',return_value=(docs,[])),patch('cell_source.bounded_fetch',return_value={'status':'ok','source':source}) as fetch:
            answer,audit=engine.answer(QUESTION)
        self.assertEqual(audit['route'],'functional_cell_evidence');self.assertIn('数十至数百',answer);self.assertNotIn('900万',answer)
        self.assertEqual(engine.calls,1);fetch.assert_called_once();self.assertEqual(len(audit['queries']),2)

if __name__=='__main__':unittest.main()
