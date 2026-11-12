import time,unittest
from unittest.mock import patch
from test_scope_integration import Fake
import test_bibliographic_chain as fixtures


class BibliographicIntegration(unittest.TestCase):
    def test_descriptive_author_after_retrieval_without_extra_model_verification(self):
        pages=fixtures.BibliographicTests().books();docs=[{'id':str(i),'title':'书目','url':p['url'],'text':p['text']} for i,p in enumerate(pages)]
        e=Fake()
        with patch('engine.retrieve',return_value=(docs,[])),patch('bibliographic_chain.bounded_fetch',side_effect=[{'status':'ok','source':p} for p in pages]):
            answer,audit=e.answer(fixtures.AUTHOR_Q)
        self.assertEqual(audit['route'],'bibliographic_evidence');self.assertIn('阿柳',answer);self.assertNotIn('阿竹',answer);self.assertEqual(e.calls,1)

    def test_publication_and_organization_chain_is_used(self):
        page=fixtures.BibliographicTests().historical();page['text']=page['text'].replace('新岸会','新岸同盟')
        docs=[{'id':'s','title':'历史资料','url':page['url'],'text':page['text']}];e=Fake()
        with patch('engine.retrieve',return_value=(docs,[])),patch('bibliographic_chain.bounded_fetch',return_value={'status':'ok','source':page}):
            answer,audit=e.answer(fixtures.HISTORY_Q)
        self.assertEqual(audit['route'],'bibliographic_evidence');self.assertIn('1924年',answer);self.assertNotIn('1926年',answer);self.assertEqual(e.calls,1)

if __name__=='__main__':unittest.main()
