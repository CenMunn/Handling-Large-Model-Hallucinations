"""Source-chain regression cases use changed names, dates and locations."""
import copy,hashlib,unittest
from curated_chains import resolve,validate_bundle


def fixture():
    texts={
        'identity':'Ada Vale designed the Nacre programming language at Tide Laboratories.',
        'timeline':'Work on Nacre began in 1992. Its first external release was in 1996.',
        'start':'In 1992 Ada Vale joined Tide Laboratories in Oregon.',
        'end':'Nacre first edition, 1996. Author: Ada Vale. Portland, Oregon.',
    }
    sources={k:{'url':'https://example.org/'+k,'text':v,'raw_sha256':'a'*64,'text_sha256':hashlib.sha256(v.encode()).hexdigest(),'retrieved_at':'2026-10-31T00:00:00+00:00'} for k,v in texts.items()}
    refs=lambda k:[{'source':k,'quote':texts[k]}]
    return {'kind':'historical_workplace','subject':'Nacre','aliases':['Nacre'],'designer':'Ada Vale',
            'institution':'Tide Laboratories','institution_aliases':['潮汐实验室','Tide Laboratories'],
            'start_year':1992,'release_year':1996,'release_kind':'first_external',
            'start_state':'Oregon','release_state':'Oregon','state_label':'俄勒冈州',
            'coverage':'dated_endpoints','sources':sources,
            'evidence':{'identity':refs('identity'),'design_start':refs('timeline'),'release':refs('timeline'),
                        'start_site':refs('start'),'release_site':refs('end')}}


class CuratedChainTests(unittest.TestCase):
    def test_historical_endpoints_are_qualified_not_continuous_employment(self):
        r=resolve('Nacre设计开始到首次发布时，设计者的历史工作地点属于美国哪个州？',[fixture()])
        self.assertEqual(r['status'],'qualified');self.assertIn('俄勒冈州',r['answer'])
        self.assertIn('1992',r['answer']);self.assertIn('1996',r['answer']);self.assertIn('端点',r['answer'])
        self.assertNotIn('始终',r['answer'])

    def test_current_location_and_course_venue_are_not_historical_workplace(self):
        b=fixture();b['sources']['start']['text']+=' Now Ada works in Texas. A course was held in Ohio in 1996.'
        b['sources']['start']['text_sha256']=hashlib.sha256(b['sources']['start']['text'].encode()).hexdigest()
        r=resolve('Nacre设计到首次发布时的工作地点是美国哪个州？',[b])
        self.assertIn('俄勒冈州',r['answer']);self.assertNotIn('Texas',r['answer']);self.assertNotIn('Ohio',r['answer'])

    def test_conflicting_endpoints_are_not_collapsed(self):
        b=fixture();b['release_state']='Washington';b['sources']['end']['text']=b['sources']['end']['text'].replace('Oregon','Washington')
        b['sources']['end']['text_sha256']=hashlib.sha256(b['sources']['end']['text'].encode()).hexdigest()
        b['evidence']['release_site'][0]['quote']=b['sources']['end']['text']
        r=resolve('Nacre开始设计到首次发布时，工作地点属于美国哪个州？',[b])
        self.assertEqual(r['status'],'conflict');self.assertIn('Oregon',r['answer']);self.assertIn('Washington',r['answer'])

    def test_book_publication_is_not_a_language_release(self):
        b=fixture();b['evidence']['release']=b['evidence']['release_site']
        self.assertFalse(validate_bundle(b)['ok'])

    def test_quote_value_and_document_fingerprint_are_checked(self):
        for mutate in ('quote','hash','state','year','person'):
            b=fixture()
            if mutate=='quote':b['evidence']['start_site'][0]['quote']='invented'
            if mutate=='hash':b['sources']['start']['text_sha256']='b'*64
            if mutate=='state':b['start_state']='California'
            if mutate=='year':b['release_year']=1998
            if mutate=='person':b['designer']='Other Person'
            with self.subTest(mutate=mutate):self.assertFalse(validate_bundle(b)['ok'])

    def test_different_language_and_extra_qualifier_cannot_reuse_bundle(self):
        for q in ['Pebble开始设计到首次发布时，设计者工作地点在哪个美国州？',
                  '获得诺贝尔奖的Nacre设计者当时工作地点属于哪个美国州？',
                  'Nacre设计者现在的工作地点属于美国哪个州？',
                  '仅根据材料，Nacre设计者当时工作地点属于美国哪个州？']:
            with self.subTest(q=q):self.assertIsNone(resolve(q,[fixture()]))

    def test_anonymous_institution_clue_is_conditional_and_dates_corrected(self):
        q='设计于20世纪90年代中期并由潮汐实验室研究人员开发的程序设计语言，其设计者当时所在研究机构所属美国州份是什么？'
        r=resolve(q,[fixture()]);self.assertIn('若题干指',r['answer']);self.assertIn('1992',r['answer'])

    def test_ambiguous_candidates_do_not_select_first(self):
        b=fixture();c=copy.deepcopy(b);c['subject']='Other';c['aliases']=['Other']
        q='设计于20世纪90年代并由潮汐实验室研究人员开发的程序设计语言，其设计者当时工作地点在美国哪个州？'
        # A malformed second source chain is rejected; a valid competing one blocks uniqueness.
        for s in c['sources'].values():s['text']=s['text'].replace('Nacre','Other');s['text_sha256']=hashlib.sha256(s['text'].encode()).hexdigest()
        for refs in c['evidence'].values():
            for ref in refs:ref['quote']=ref['quote'].replace('Nacre','Other')
        r=resolve(q,[b,c]);self.assertEqual(r['status'],'ambiguous')


if __name__=='__main__':unittest.main()
