import copy,hashlib,unittest
from curated_chains import resolve,validate_bundle

def source(text):return {'url':'https://example.org/source','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest(),'retrieved_at':'2026-11-01T00:00:00+00:00'}
def river():
    text='青城是青省省会，承办2027年亚运会。青河流经青城。水利普查名录：青河河流长度402公里。青河北源至入海口长度455公里。'
    return {'kind':'river_length','subject':'青河','aliases':['青河'],'city':'青城','province':'青省','event_year':2027,
      'sources':{'s':source(text)},'evidence':{'city':[{'source':'s','quote':text}]},
      'measurements':[{'scope':'census_whole','value':402,'unit':'公里','quote':'水利普查名录：青河河流长度402公里。','source':'s'},
                      {'scope':'north_source','value':455,'unit':'公里','quote':'青河北源至入海口长度455公里。','source':'s'}]}
def language():
    t='Ari Bell improved the steam engine. Ari Bell was born in Fern, Westland, Unionland. The main language in Unionland is Amber.'
    return {'kind':'birth_country_language','subject':'Ari Bell','aliases':['Ari Bell'],'birthplace':'Fern','region':'Westland','country':'Unionland','country_label':'联国',
      'country_aliases':['联国','Unionland'],'region_aliases':['西区','Westland'],'usage':'Amber','usage_label':'琥珀语','checked_date':'2026-11-01',
      'sources':{'s':source(t)},'evidence':{'identity':[{'source':'s','quote':t}]},'legal':[]
      }

class CuratedScopeTests(unittest.TestCase):
    def test_full_river_does_not_take_largest_number(self):
        r=resolve('青河全长多少公里？',[river()]);self.assertIn('402公里',r['answer']);self.assertIn('北源',r['answer'])
    def test_explicit_north_scope_uses_north(self):
        r=resolve('青河北源至入海口全长多少公里？',[river()]);self.assertTrue(r['answer'].startswith('按北源'));self.assertIn('455公里',r['answer'])
    def test_reach_question_never_gets_whole_length(self):
        self.assertIsNone(resolve('青河在青城境内河段长多少公里？',[river()]))
    def test_same_scope_conflict_blocks_unique_answer(self):
        b=river();b['sources']['s']['text']+='青河河流长度405公里。';b['sources']['s']['text_sha256']=hashlib.sha256(b['sources']['s']['text'].encode()).hexdigest()
        b['measurements'].append({'scope':'census_whole','value':405,'unit':'公里','quote':'青河河流长度405公里。','source':'s'})
        self.assertEqual(resolve('青河全长多少公里？',[b])['status'],'conflict')
    def test_wrong_event_year_and_unknown_extra_condition_do_not_match(self):
        for q in ['举办了2028年亚运会的青省省会，其河流全长多少公里？','青河最长支流全长多少公里？']:
            self.assertIsNone(resolve(q,[river()]))
    def test_missing_value_quote_is_rejected(self):
        b=river();b['measurements'][0]['value']=999;self.assertFalse(validate_bundle(b)['ok'])
    def test_language_usage_is_labeled_and_absence_is_not_legal_negative(self):
        r=resolve('Ari Bell出生地所在国家的官方语言主要是什么？',[language()],today='2026-11-01')
        self.assertIn('主要使用语言',r['answer']);self.assertIn('琥珀语',r['answer']);self.assertIn('未核实',r['answer']);self.assertNotIn('没有官方语言',r['answer'])
    def test_historical_and_regional_scope_never_become_national_usage(self):
        for q in ['Ari Bell出生时所在国家的官方语言是什么？','西区的官方语言是什么？']:
            self.assertIsNone(resolve(q,[language()],today='2026-11-01'))
    def test_legal_membership_and_effective_dates_are_kept(self):
        b=language();b['sources']['s']['text']+='Unionland law: Azure is an official language of Unionland, effective 2026-10-01.';b['sources']['s']['text_sha256']=hashlib.sha256(b['sources']['s']['text'].encode()).hexdigest()
        b['legal']=[{'scope':'Unionland','language':'Azure','label':'天青语','effective':'2026-10-01','source':'s','quote':'Unionland law: Azure is an official language of Unionland, effective 2026-10-01.'}]
        r=resolve('联国的官方语言是什么？',[b],today='2026-11-01');self.assertIn('天青语',r['answer']);self.assertNotIn('琥珀语',r['answer'])
        b['legal'][0]['scope']='Westland'
        b['legal'][0]['quote']=b['legal'][0]['quote'].replace('Unionland','Westland')
        b['sources']['s']['text']+=' '+b['legal'][0]['quote'];b['sources']['s']['text_sha256']=hashlib.sha256(b['sources']['s']['text'].encode()).hexdigest()
        r=resolve('联国的官方语言是什么？',[b],today='2026-11-01');self.assertNotIn('天青语',r['answer'])
    def test_stale_legal_snapshot_cannot_assert_current_law(self):
        self.assertIsNone(resolve('联国的官方语言是什么？',[language()],today='2027-12-01'))

if __name__=='__main__':unittest.main()
