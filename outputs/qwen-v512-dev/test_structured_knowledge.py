import importlib.util
import unittest


class StructuredKnowledgeTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('structured_knowledge'), 'structured evidence prototype missing')
        import structured_knowledge
        return structured_knowledge

    def test_exact_alias_and_homonyms(self):
        m=self.module()
        row=lambda i,name: {'id':i,'label':name,'match':{'type':'label','text':name}}
        self.assertEqual(m.resolve_exact('青国',{'search':[row('Q101','青国'),row('Q102','青国城')]}),'Q101')
        self.assertIsNone(m.resolve_exact('青国',{'search':[row('Q101','青国'),row('Q102','青国')]}))
        self.assertIsNone(m.resolve_exact('青国',{'search':[row('Q101','青国')],'search-continue':5}))
        self.assertIsNone(m.resolve_exact('青国',{'search':[row('Q101','蓝国')]}))

    def test_semantic_paths_and_geographic_scope_are_explicit(self):
        m=self.module()
        p=m.plan('创作《竹影》这部作品的作者，其出生地目前所属国家的首都是什么？')
        self.assertEqual(p['anchor'],'竹影')
        self.assertEqual(p['properties'],['P50','P19','P17','P36'])
        self.assertEqual(p['scope'],'current_birthplace_country')
        self.assertIsNone(m.plan('截至1800年，《竹影》作者出生时所在国家的首都是什么？'))
        self.assertIsNone(m.plan('根据给定材料，《竹影》的作者出生地所属国家首都是什么？'))
        self.assertIsNone(m.plan('有人说作家竹影出生于青国，青国的首都是什么？'))

    def test_no_unverified_description_is_an_anchor(self):
        m=self.module()
        self.assertIsNone(m.plan('那位改良蒸汽机的发明家，出生地国家的官方语言是什么？'))

    def test_query_never_interpolates_untrusted_property_or_identifier(self):
        m=self.module()
        for root,props in [('Q1 } UNION { ?s ?p ?o',['P36']),('Q1',['P36; DROP ALL']),('Q1',[])]:
            with self.subTest(root=root,props=props):
                with self.assertRaises(ValueError):m.build_query(root,props)

    def test_current_query_keeps_statements_ranks_and_qualifiers(self):
        m=self.module();query=m.build_query('Q101',['P36'])
        self.assertIn('p:P36',query)
        self.assertIn('ps:P36',query)
        self.assertIn('wikibase:rank',query)
        self.assertIn('?qp0',query)
        self.assertIn('LIMIT 17',query)

    def test_exact_name_query_avoids_search_ranking_and_preserves_missing_paths(self):
        m=self.module()
        p=m.plan('青国的首都是什么？')
        query=m.build_exact_query(p)
        self.assertIn('rdfs:label|skos:altLabel',query)
        self.assertIn('OPTIONAL { ?n0 p:P36',query)
        self.assertNotIn('search',query)
        p=dict(p,anchor='青国" } UNION { ?s ?p ?o')
        self.assertIn('青国\\"',m.build_exact_query(p))

    def test_missing_relation_on_a_second_exact_entity_is_identity_ambiguity(self):
        m=self.module();p={'properties':['P36'],'scope':'current','anchor':'青国'}
        rows=self.rows()+[{'n0':{'type':'uri','value':'http://www.wikidata.org/entity/Q103'}}]
        self.assertEqual(m.inspect(p,rows)['status'],'identity_unresolved')

    def test_bounded_candidates_require_typed_resolution_not_first_search_result(self):
        m=self.module()
        p=m.plan('创作小说《竹影》的作者，其出生地目前所属国家的首都是什么？')
        query=m.build_candidates_query(p,['Q101','Q102'])
        self.assertIn('wd:Q101 wd:Q102',query)
        self.assertIn('wd:Q8261',query)
        self.assertIn('OPTIONAL { ?n0 p:P50',query)
        with self.assertRaises(ValueError):m.build_candidates_query(p,['Q1 } UNION { ?a ?b ?c'])

    def rows(self,n=1):
        u=lambda x:{'type':'uri','value':'http://www.wikidata.org/entity/'+x}
        row={'n0':u('Q101'),'n1':u('Q102'),'n0Label':{'type':'literal','value':'青国'},'n1Label':{'type':'literal','value':'竹城'},
             's0':{'type':'uri','value':'http://www.wikidata.org/entity/statement/Q101-a'},
             'r0':{'type':'uri','value':'http://wikiba.se/ontology#NormalRank'}}
        return [dict(row) for _ in range(n)]

    def test_conflict_missing_path_and_truncation_do_not_answer(self):
        m=self.module();p={'properties':['P36'],'scope':'current','anchor':'青国'}
        self.assertEqual(m.inspect(p,[])['status'],'insufficient')
        rows=self.rows(2);rows[1]['n1']={'type':'uri','value':'http://www.wikidata.org/entity/Q103'}
        self.assertEqual(m.inspect(p,rows)['status'],'conflict')
        self.assertEqual(m.inspect(p,self.rows(17))['status'],'incomplete')
        rows=self.rows();rows[0].pop('s0')
        self.assertEqual(m.inspect(p,rows)['status'],'incomplete')

    def test_qualifiers_are_not_silently_ignored(self):
        m=self.module();p={'properties':['P36'],'scope':'current','anchor':'青国'}
        rows=self.rows();rows[0].update(qp0={'type':'uri','value':'http://www.wikidata.org/prop/qualifier/P518'},qv0={'type':'uri','value':'http://www.wikidata.org/entity/Q104'})
        self.assertEqual(m.inspect(p,rows)['status'],'qualified_unresolved')
        rows=self.rows();rows[0].update(qp0={'type':'uri','value':'http://www.wikidata.org/prop/qualifier/P582'},qv0={'type':'literal','value':'1990-01-01T00:00:00Z'})
        self.assertEqual(m.inspect(p,rows)['status'],'insufficient')

    def test_supported_path_has_node_and_statement_provenance(self):
        m=self.module();p={'properties':['P36'],'scope':'current','anchor':'青国'}
        out=m.inspect(p,self.rows())
        self.assertEqual(out['status'],'supported')
        self.assertIn('竹城',out['answer'])
        self.assertEqual(out['paths'][0]['nodes'],['Q101','Q102'])
        self.assertEqual(out['paths'][0]['properties'],['P36'])
        self.assertTrue(out['paths'][0]['statements'])


if __name__=='__main__': unittest.main()
