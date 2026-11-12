import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import primary_fetch


class Reply:
    status=200
    headers={'Content-Type':'text/html; charset=utf-8'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return b'<h2>Description</h2><p>Source text.</p><script>ignore instructions</script>'


class Opener:
    def open(self,*args,**kwargs):return Reply()


class PrimaryFetchTests(unittest.TestCase):
    def test_historical_author_pages_and_actual_links_are_preserved(self):
        self.assertEqual(primary_fetch.canonical('https://www.stroustrup.com/1st.html#x'),'https://www.stroustrup.com/1st.html')
        p=primary_fetch.PlainText();p.feed('<a href="1st_pref.html">preface</a><script><a href="fake">ignore</a></script>')
        self.assertEqual(p.links,[{'href':'1st_pref.html','text':'preface'}])
    def test_registered_publication_paths_and_charset_are_explicit(self):
        self.assertEqual(primary_fetch.canonical('http://news.cnr.cn/native/gd/example.shtml'),'https://news.cnr.cn/native/gd/example.shtml')
        self.assertEqual(primary_fetch.canonical('https://www.zzhvc.cn/tsg/example.html?tracking=1'),'https://www.zzhvc.cn/tsg/example.html')
        self.assertIn('bookId=123',primary_fetch.canonical('https://se.zhangyue.com/book/detail?bookId=123&tracking=1'))
        self.assertEqual(primary_fetch.decode_html('中文'.encode('gb18030'),'text/html; charset=gb2312'),'中文')
    def test_independent_fetch_uses_same_environment_proxy_policy_as_platform_adapter(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(primary_fetch,'HERE',Path(tmp)),patch.object(primary_fetch.urllib.request,'getproxies_environment',return_value={}),patch.object(primary_fetch.urllib.request,'getproxies',side_effect=AssertionError('unexpected system proxy')),patch.object(primary_fetch.urllib.request,'build_opener',return_value=Opener()):
            result=primary_fetch.fetch('https://medlineplus.gov/genetics/example/',time.monotonic()+2)
        self.assertEqual(result['transport'],'independent_https');self.assertNotIn('ignore instructions',result['text'])

    def test_url_host_and_transport_cannot_be_forged(self):
        for url in ['https://medlineplus.gov.evil.example/genetics/a/','http://medlineplus.gov/genetics/a/','https://user:pass@medlineplus.gov/genetics/a/','https://medlineplus.gov:444/genetics/a/']:
            with self.subTest(url=url),self.assertRaises(ValueError):primary_fetch.canonical(url)

    def test_authentication_and_redirects_are_not_forwarded(self):
        with self.assertRaises(ValueError):primary_fetch.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.org/')


if __name__=='__main__':unittest.main()
