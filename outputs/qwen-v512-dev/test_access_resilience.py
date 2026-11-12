import tempfile,time,unittest,json,concurrent.futures
from pathlib import Path
from unittest.mock import patch
import wikibase_http as w
from test_wikibase_http import Connection,Response

class ResilienceTests(unittest.TestCase):
 def test_interactive_requests_omit_background_maxlag_only(self):
  c=Connection([Response({'error':{'code':'maxlag'}}),Response({'search':[]})])
  with tempfile.TemporaryDirectory() as d:
   with w.Client(d,connection_factory=lambda:c,interactive=False) as client:
    with self.assertRaises(w.APIError):client.search('甲',time.monotonic()+2)
   with w.Client(d,connection_factory=lambda:c,interactive=True) as client:
    client.search('乙',time.monotonic()+3)
    self.assertNotIn('maxlag',client.traces[0]['parameters'])
  self.assertEqual(len(c.headers),2)
 def test_simultaneous_identical_cache_miss_is_fetched_once(self):
  c=Connection([Response({'search':[]})])
  with tempfile.TemporaryDirectory() as d:
   def run(_):
    with w.Client(d,connection_factory=lambda:c) as client:return client.search('同一个实体',time.monotonic()+3)
   with concurrent.futures.ThreadPoolExecutor(2) as pool:rows=list(pool.map(run,range(2)))
  self.assertEqual(len(c.headers),1);self.assertEqual(len(rows),2)
 def test_queued_request_rechecks_cooldown(self):
  c=Connection([Response({},429)])
  with tempfile.TemporaryDirectory() as d:
   def run(name):
    with w.Client(d,connection_factory=lambda:c) as client:
     try:client.search(name,time.monotonic()+3)
     except w.APIError:return 'cooldown'
   with concurrent.futures.ThreadPoolExecutor(2) as pool:rows=list(pool.map(run,['甲','乙']))
  self.assertEqual(rows,['cooldown','cooldown']);self.assertEqual(len(c.headers),1)
 def test_api_200_ratelimit_opens_shared_circuit_and_retains_code(self):
  c=Connection([Response({'error':{'code':'ratelimited','info':'slow down'}})])
  with tempfile.TemporaryDirectory() as d,w.Client(d,connection_factory=lambda:c) as client:
   with self.assertRaises(w.APIError):client.search('甲',time.monotonic()+2)
   with self.assertRaises(w.APIError):client.search('乙',time.monotonic()+2)
   self.assertEqual(client.traces[0].get('api_error_code'),'ratelimited')
   self.assertEqual(len(c.headers),1)
 def test_cache_hit_works_during_provider_cooldown(self):
  c=Connection([Response({'search':[]}),Response({},429)])
  with tempfile.TemporaryDirectory() as d,w.Client(d,connection_factory=lambda:c) as client:
   client.search('甲',time.monotonic()+4)
   with self.assertRaises(w.APIError):client.search('乙',time.monotonic()+4)
   self.assertEqual(client.search('甲',time.monotonic()+1)['search'],[])
 def test_retry_after_http_date_is_honored(self):
  from email.utils import formatdate
  now=time.time();self.assertGreaterEqual(w.retry_delay(formatdate(now+120,usegmt=True),now),118)
 def test_gate_wait_is_bounded_and_released_on_failure(self):
  from access_gate import gate
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'lease'
   with gate(p,time.monotonic()+1):
    with self.assertRaises(TimeoutError):
     with gate(p,time.monotonic()+.1):pass
   with gate(p,time.monotonic()+1):pass

if __name__=='__main__':unittest.main()
