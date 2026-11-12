import importlib.util
import sys,time,unittest

def snak(value):
    if isinstance(value,str) and value.startswith('Q'):
        return {'snaktype':'value','datavalue':{'type':'wikibase-entityid','value':{'id':value,'entity-type':'item'}}}
    return {'snaktype':'value','datavalue':{'type':'time','value':{'time':value,'precision':11}}}

def entity(qid,name,**claims):
    return {'id':qid,'lastrevid':123,'labels':{'zh':{'value':name}},'aliases':{},'claims':{
        p:[{'id':qid+'$'+p+'-'+str(i),'rank':'normal','mainsnak':dict(snak(v),property=p)} for i,v in enumerate(vals)] for p,vals in claims.items()}}

class FakeClient:
    def __init__(self,items,hits):self.items=items;self.hits=hits;self.requested=[]
    def search(self,name,deadline):return {'search':[{'id':i,'label':n,'match':{'type':'label','text':n}} for i,n in self.hits],'search-continue':5}
    def entities(self,ids,deadline):
        self.requested.append(list(ids))
        return {i:self.items[i] for i in ids if i in self.items}

class WalkTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('wikibase_walk'),'local typed walker missing')
        import wikibase_walk
        return wikibase_walk

    def fixture(self):
        return {'Q101':entity('Q101','竹影',P31=['Q8261'],P50=['Q201']),
                'Q102':entity('Q102','竹影',P31=['Q1344'],P50=['Q202']),
                'Q1344':entity('Q1344','歌剧'),
                'Q201':entity('Q201','阿青',P19=['Q301'],P27=['Q999']),
                'Q202':entity('Q202','阿蓝',P19=['Q302']),
                'Q301':entity('Q301','竹县',P17=['Q401']),
                'Q302':entity('Q302','柳县',P17=['Q402']),
                'Q401':entity('Q401','青国',P36=['Q501'],P31=['Q6256']),
                'Q402':entity('Q402','蓝国',P36=['Q502'],P31=['Q6256']),
                'Q501':entity('Q501','竹城'),'Q502':entity('Q502','柳城')}

    def solve(self,items=None,hits=None,question='创作小说《竹影》的作家，其出生地目前所属国家的首都是什么？'):
        m=self.module();c=FakeClient(items or self.fixture(),hits or [('Q102','竹影'),('Q101','竹影')])
        return m.Walker(c).answer(question,time.monotonic()+5),c

    def test_homonymous_opera_is_not_a_novel_even_when_ranked_first(self):
        out,_=self.solve()
        self.assertEqual(out['status'],'supported')
        self.assertIn('竹城',out['answer']);self.assertNotIn('柳城',out['answer'])
        self.assertEqual(out['root'],'Q101')
        self.assertEqual([e['property'] for e in out['edges']],['P50','P19','P17','P36'])

    def test_two_type_matching_namesakes_remain_ambiguous(self):
        items=self.fixture();items['Q102']['claims']['P31'][0]['mainsnak']=dict(snak('Q8261'),property='P31')
        out,_=self.solve(items)
        self.assertEqual(out['status'],'identity_unresolved');self.assertNotIn('answer',out)

    def test_type_candidates_are_loaded_in_a_shared_batch(self):
        items=self.fixture();items['Q103']=entity('Q103','竹影',P31=['Q11424']);items['Q11424']=entity('Q11424','电影')
        out,c=self.solve(items,[('Q102','竹影'),('Q103','竹影'),('Q101','竹影')])
        self.assertEqual(out['status'],'supported')
        self.assertTrue(any({'Q1344','Q11424'} <= set(batch) for batch in c.requested))

    def test_missing_relation_cannot_be_replaced_with_nationality(self):
        items=self.fixture();items['Q201']['claims'].pop('P19')
        out,_=self.solve(items)
        self.assertEqual(out['status'],'insufficient');self.assertNotIn('answer',out)

    def test_conflicting_countries_are_not_merged_by_same_capital(self):
        items=self.fixture();items['Q301']=entity('Q301','竹县',P17=['Q401','Q402']);items['Q402']['claims']['P36'][0]['mainsnak']=dict(snak('Q501'),property='P36')
        out,_=self.solve(items)
        self.assertEqual(out['status'],'conflict');self.assertNotIn('answer',out)

    def test_country_at_birth_is_not_current_country(self):
        m=self.module()
        for q in ['创作《竹影》的作家出生时所在国家的首都是什么？','截至1900年，青国首都是什么？','仅根据给定材料，青国首都是什么？']:
            self.assertIsNone(m.plan(q))

    def test_temporal_qualifiers_and_unknown_scope(self):
        m=self.module();e=entity('Q301','竹县',P17=['Q401','Q402'])
        e['claims']['P17'][1]['qualifiers']={'P582':[snak('+1990-01-01T00:00:00Z')]}
        out=m.read_edges(e,'P17');self.assertEqual(out['status'],'ok');self.assertEqual([x['object'] for x in out['edges']],['Q401'])
        e['claims']['P17'][0]['qualifiers']={'P518':[snak('Q777')]}
        self.assertEqual(m.read_edges(e,'P17')['status'],'qualified_unresolved')

    def test_rank_explanation_is_not_an_attribute_scope_change(self):
        m=self.module();e=entity('Q401','青国',P36=['Q501'])
        e['claims']['P36'][0]['qualifiers']={'P7452':[snak('Q777')]}
        out=m.read_edges(e,'P36')
        self.assertEqual(out['status'],'ok');self.assertEqual(out['edges'][0]['object'],'Q501')

    def test_birth_country_qualifier_is_retained_without_becoming_current_country(self):
        m=self.module();items=self.fixture()
        items['Q201']['claims']['P19'][0]['qualifiers']={'P17':[snak('Q999')]}
        out,_=self.solve(items)
        self.assertEqual(out['status'],'supported');self.assertIn('青国',out['answer'])
        birth=next(e for e in out['edges'] if e['property']=='P19')
        self.assertIn('P17',birth['qualifiers'])

    def test_provenance_contains_revision_and_raw_statement(self):
        out,_=self.solve()
        for e in out['edges']:
            self.assertTrue(e['statement_id']);self.assertEqual(e['revision'],123);self.assertIn('wikidata.org',e['source_url'])
        self.assertIn('current',out['scope']);self.assertIn('Wikidata',out['answer'])

    def test_legacy_lowercase_statement_subject_is_valid_but_other_id_is_not(self):
        m=self.module();e=entity('Q101','竹影',P50=['Q201'])
        e['claims']['P50'][0]['id']='q101$legacy-statement'
        self.assertEqual(m.read_edges(e,'P50')['status'],'ok')
        self.assertEqual(len(m.read_edges(e,'P50')['edges']),1)
        e['claims']['P50'][0]['id']='q102$other-subject'
        self.assertNotEqual(m.read_edges(e,'P50')['status'],'ok')

    def test_organization_founder_birthplace_province(self):
        m=self.module();items={'Q601':entity('Q601','青木公司',P112=['Q602']),
            'Q602':entity('Q602','阿松',P19=['Q603']), 'Q603':entity('Q603','桃县',P131=['Q604']),
            'Q604':entity('Q604','甲市',P131=['Q605']),'Q605':entity('Q605','浙江省')}
        c=FakeClient(items,[('Q601','青木公司')]);out=m.Walker(c).answer('青木公司创始人的出生县位于哪个省份？',time.monotonic()+5)
        self.assertEqual(out['status'],'supported');self.assertIn('浙江省',out['answer'])

    def test_joint_founders_do_not_become_a_single_person(self):
        m=self.module();items={'Q601':entity('Q601','青木公司',P112=['Q602','Q606'])}
        out=m.Walker(FakeClient(items,[('Q601','青木公司')])).answer('青木公司创始人的出生县位于哪个省份？',time.monotonic()+5)
        self.assertEqual(out['status'],'identity_unresolved');self.assertNotIn('answer',out)

    def test_search_display_name_is_not_a_gate_when_entity_has_exact_alias(self):
        m=self.module();items={'Q601':entity('Q601','青木有限公司',P112=['Q602']),
            'Q602':entity('Q602','阿松',P19=['Q603']),'Q603':entity('Q603','浙江省')}
        items['Q601']['aliases']={'zh':[{'value':'青木'}]}
        out=m.Walker(FakeClient(items,[('Q601','青木有限公司')])).answer('青木创始人的出生地位于哪个省份？',time.monotonic()+5)
        self.assertEqual(out['status'],'supported');self.assertIn('浙江省',out['answer'])

    def test_fuzzy_search_prefix_is_not_an_identity_match(self):
        m=self.module();items={'Q601':entity('Q601','青木大学',P112=['Q602'])}
        out=m.Walker(FakeClient(items,[('Q601','青木大学')])).answer('青木创始人的出生地位于哪个省份？',time.monotonic()+5)
        self.assertEqual(out['status'],'identity_unresolved')

    def test_client_cannot_substitute_other_entity_content(self):
        items=self.fixture();items['Q101']['id']='Q102'
        out,_=self.solve(items)
        self.assertEqual(out['status'],'invalid_source')

    def test_parent_deadline_terminates_a_stalled_network_worker(self):
        m=self.module();start=time.monotonic()
        out=m.bounded_lookup('青国首都是什么？',start+.25,command=[sys.executable,'-c','import time;time.sleep(3)'])
        self.assertEqual(out['status'],'timeout');self.assertLess(time.monotonic()-start,2)

    def test_chinese_question_survives_real_worker_pipe(self):
        m=self.module();q='创作《竹影》的作者出生地属于哪个国家？'
        code='import json,sys;x=json.load(sys.stdin);print(json.dumps(dict(status="supported" if "竹影" in x["question"] else "wrong_encoding",question=x["question"]),ensure_ascii=False))'
        out=m.bounded_lookup(q,time.monotonic()+3,command=[sys.executable,'-c',code])
        self.assertEqual(out.get('question'),q)
        self.assertEqual(out.get('status'),'supported')

if __name__=='__main__':unittest.main()
