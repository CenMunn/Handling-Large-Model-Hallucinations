import json,tempfile,time,unittest
from pathlib import Path
from source_cache import candidates

class SourceCacheTests(unittest.TestCase):
 def test_valid_cached_body_can_be_rediscovered_without_search_provider(self):
  row={'url':'https://www.zzhvc.cn/tsg/a.html','text':'《青灯》描写荒野庄园的情感纠葛。作者阿青。','transport':'independent_https','epoch':time.time(),'raw_sha256':'a'*64,'retrieved_at':'2026-11-01'}
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.json';p.write_text(json.dumps(row),encoding='utf-8')
   r=candidates(['荒野庄园小说真实作者'],Path(d));self.assertEqual(len(r),1);self.assertEqual(r[0]['text'],row['text'])
   row['epoch']-=90000;p.write_text(json.dumps(row),encoding='utf-8');self.assertEqual(candidates(['荒野庄园小说作者'],Path(d)),[])
 def test_unregistered_host_or_provider_summary_cannot_enter_independent_cache(self):
  with tempfile.TemporaryDirectory() as d:
   for host,transport in [('evil.example','independent_https'),('www.zzhvc.cn','search_summary')]:
    row={'url':'https://'+host+'/tsg/a','text':'荒野庄园小说作者阿青','epoch':time.time(),'transport':transport,'raw_sha256':'a'*64}
    (Path(d)/'a.json').write_text(json.dumps(row),encoding='utf-8')
    self.assertEqual(candidates(['荒野庄园小说作者'],Path(d)),[])
