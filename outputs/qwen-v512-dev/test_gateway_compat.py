import json,threading,unittest,urllib.error,urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from types import SimpleNamespace
import gateway
import tempfile
from pathlib import Path

class GatewayCompatTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.directory_patch=patch.object(gateway,'HERE',Path(self.temp.name));self.directory_patch.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),gateway.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:%s/v1/chat/completions'%self.server.server_port
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.directory_patch.stop();self.temp.cleanup()
    def post(self,messages):
        body={'model':'qwen3-8b','messages':messages}
        req=urllib.request.Request(self.url,data=json.dumps(body,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=3) as response:return response.status,json.load(response)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_old_and_new_clients_keep_same_question(self):
        requests=[]
        def fake_worker(*args,**kwargs):
            requests.append(json.loads(kwargs['input']))
            return SimpleNamespace(returncode=0,stdout=json.dumps({'answer':'ok','audit':{'route':'model_only'}}))
        with patch.object(gateway.Handler,'authorized',return_value=True),patch.object(gateway.subprocess,'run',side_effect=fake_worker):
            a=self.post([{'role':'user','content':'题目'}])
            b=self.post([{'role':'system','content':'旧客户端提示'}, {'role':'user','content':'题目'}])
        self.assertEqual((a[0],b[0]),(200,200))
        self.assertEqual([r['question'] for r in requests],['题目','题目'])
        self.assertTrue(all(set(r)=={'question'} for r in requests))
    def test_multiturn_is_rejected(self):
        with patch.object(gateway.Handler,'authorized',return_value=True):
            status,_=self.post([{'role':'user','content':'甲'},{'role':'assistant','content':'乙'},{'role':'user','content':'丙'}])
        self.assertEqual(status,502)
    def test_worker_timeout_keeps_phase_and_is_not_success(self):
        value={'error_type':'TimeoutError','audit':{'phase':'candidate_extraction','model_stages':[{'error_type':'TimeoutError'}]}}
        worker=SimpleNamespace(returncode=0,stdout=json.dumps(value))
        with patch.object(gateway.Handler,'authorized',return_value=True),patch.object(gateway.subprocess,'run',return_value=worker):
            status,result=self.post([{'role':'user','content':'题目'}])
        self.assertEqual(status,504)
        self.assertEqual(result['phase'],'candidate_extraction')

if __name__=='__main__':unittest.main()
