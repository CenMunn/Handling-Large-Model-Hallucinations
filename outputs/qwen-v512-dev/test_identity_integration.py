import json
import unittest
from unittest.mock import patch
from engine import Engine

class IdentityIntegrationTests(unittest.TestCase):
    def run_fact(self, docs):
        engine = Engine.__new__(Engine)
        engine.llm = lambda *args, **kwargs: (json.dumps({'queries':['person birthplace']}), {})
        with patch('engine.retrieve', return_value=(docs, [])):
            return engine.fact('作家叶虹的出生地是什么？', 10**12, {})

    def test_lexically_bound_source_is_used(self):
        answer, audit = self.run_fact([{'id':'s1','title':'fixture','url':'https://one.example','text':'作家叶虹出生于枫城市。'}])
        self.assertEqual(answer, '枫城市')
        self.assertEqual(audit['evidence_status'], 'literal_relation_bound')
        self.assertEqual(audit['relation_checks']['evidence'][0]['source_url'], 'https://one.example')

    def test_conflicting_sources_do_not_pick_one(self):
        docs = [{'id':str(i), 'title':'fixture','url':f'https://s{i}.example','text':f'作家叶虹出生于{place}。'} for i, place in enumerate(['枫城市','柳城市'])]
        answer, audit = self.run_fact(docs)
        self.assertEqual(audit['evidence_status'], 'conflicting_sources')
        self.assertIn('冲突', answer)

    def test_same_name_unbound_cannot_be_ignored(self):
        docs=[{'id':'s1','title':'fixture','url':'https://one.example','text':'作家叶虹出生于枫城市。'},
              {'id':'s2','title':'fixture','url':'https://two.example','text':'叶虹的出生地点尚待确认。'}]
        answer,audit=self.run_fact(docs)
        self.assertEqual(audit['evidence_status'],'binding_unresolved')
        self.assertIn('无法确定',answer)

    def test_no_source_does_not_guess(self):
        answer,audit=self.run_fact([])
        self.assertEqual(audit['evidence_status'],'unavailable')
        self.assertIn('无法',answer)

    def test_predecessor_without_sources_does_not_guess(self):
        engine=Engine.__new__(Engine)
        engine.llm=lambda *args,**kwargs:(json.dumps({'queries':['institute predecessor']}),{})
        with patch('engine.retrieve',return_value=([],[])):
            answer,audit=engine.answer('海青研究所的前身是什么机构？')
        self.assertEqual(audit['route'],'external_evidence')
        self.assertEqual(audit['evidence_status'],'unavailable')
        self.assertIn('无法',answer)

if __name__ == '__main__': unittest.main()
