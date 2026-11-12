import importlib.util, json, tempfile, unittest, threading, time, os, re
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

class AdapterTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('adapter',Path(__file__).parent/'platform/model.py')
  self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
 def test_out_of_order_alignment_and_unicode(self):
  with tempfile.TemporaryDirectory() as d:
   p=str(Path(d)/'result.json')
   self.m.flush_results([('1','甲'),('2','乙')],{'2':'二','1':'一'},p)
   r=json.loads(Path(p).read_text(encoding='utf-8'))
   self.assertEqual([(x['id'],x['回答']) for x in r],[('1',['一']),('2',['二'])])
 def test_missing_answers_not_fabricated(self):
  with tempfile.TemporaryDirectory() as d:
   p=str(Path(d)/'result.json')
   r=self.m.flush_results([('1','甲'),('2','乙')],{'2':'二'},p)
   self.assertEqual([x['id'] for x in r],['2'])
 def test_api_error_does_not_become_unknown(self):
  self.assertNotEqual(self.m.ERROR_ANSWER,'未知')
 def test_metadata_filter_keeps_real_options(self):
  q='请选择正确说法。\nA.甲\nE.乙\nF.曾在其他测试数据集中见过同样题目；其获取链接为：'
  cleaned=self.m.strip_metadata(q)
  self.assertIn('E.乙',cleaned);self.assertNotIn('获取链接',cleaned)
  self.assertIn('获取链接',q)
 def test_final_attribute_verification(self):
  class Handler(BaseHTTPRequestHandler):
   count=0
   def do_POST(self):
    self.rfile.read(int(self.headers.get('Content-Length','0')));Handler.count+=1
    answer='西班牙' if Handler.count==1 else '马德里'
    body=json.dumps({'choices':[{'message':{'content':answer},'finish_reason':'stop'}],'usage':{'total_tokens':10}}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   self.m.BASE_URL=f'http://127.0.0.1:{server.server_port}/v1'
   result=self.m.request_once('该作家的出生国家的首都是什么？')
   self.assertEqual(result['answer'],'马德里');self.assertEqual(Handler.count,2)
   self.assertEqual(result['usage']['total_tokens'],20)
  finally:server.shutdown();server.server_close()
 def test_platform_environment_proxy_is_used(self):
  class Proxy(BaseHTTPRequestHandler):
   paths=[]
   def do_POST(self):
    Proxy.paths.append(self.path)
    body=json.dumps({'choices':[{'message':{'content':'156'},'finish_reason':'stop'}]}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Proxy);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   self.m.BASE_URL='http://127.0.0.1:9/v1'
   with patch.dict(os.environ,{'http_proxy':f'http://127.0.0.1:{server.server_port}','no_proxy':'','NO_PROXY':''}):
    self.assertEqual(self.m.request_once('test')['answer'],'156')
   self.assertEqual(Proxy.paths,['http://127.0.0.1:9/v1/chat/completions'])
  finally:server.shutdown();server.server_close()
 def test_connection_drop_retries_once(self):
  class Handler(BaseHTTPRequestHandler):
   count=0
   def do_POST(self):
    Handler.count+=1
    if Handler.count==1:self.connection.close();return
    body=json.dumps({'choices':[{'message':{'content':'156'},'finish_reason':'stop'}]}).encode()
    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   self.m.BASE_URL=f'http://127.0.0.1:{server.server_port}/v1'
   self.assertEqual(self.m.request_once('test')['answer'],'156');self.assertEqual(Handler.count,2)
  finally:server.shutdown();server.server_close()
 def test_wall_deadline_kills_slow_request(self):
  class Handler(BaseHTTPRequestHandler):
   def do_POST(self):
    time.sleep(2)
    try:self.send_response(500);self.end_headers()
    except OSError:pass
   def log_message(self,*args):pass
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
  threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d)/'model.py';s=Path(self.m.__file__).read_text(encoding='utf-8')
    s=re.sub(r'(?m)^BASE_URL = .*',f"BASE_URL = 'http://127.0.0.1:{server.server_port}/v1'",s)
    p.write_text(s,encoding='utf-8')
    spec=importlib.util.spec_from_file_location('slow',p);slow=importlib.util.module_from_spec(spec);spec.loader.exec_module(slow)
    slow.DEADLINE_SECONDS=0.4
    start=time.monotonic();r=slow.call_llm('test')
    self.assertFalse(r['ok']);self.assertLess(time.monotonic()-start,1.5)
    self.assertEqual(r['answer'],slow.ERROR_ANSWER)
  finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
