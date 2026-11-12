"""Authenticated localhost gateway. All model/evidence/computation work runs here."""
import hashlib,hmac,json,subprocess,sys,threading,time,urllib.request
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from engine import Engine,KEY_PATH
from request_compat import parse_messages

HERE=Path(__file__).resolve().parent
LIMIT=threading.BoundedSemaphore(4);LOCK=threading.Lock()

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def send(self,status,body):
  encoded=json.dumps(body,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(encoded)));self.end_headers()
  try:self.wfile.write(encoded)
  except OSError:pass
 def authorized(self):return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+KEY_PATH.read_text().strip())
 def do_GET(self):
  if self.path=='/health':
   try:
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/health',timeout=2) as r:healthy=r.status==200
   except Exception:healthy=False
   self.send(200 if healthy else 503,{'status':'ok' if healthy else 'raw_model_unavailable','gateway':'qwen-v512-dev'});return
  if not self.authorized():self.send(401,{'error':'unauthorized'});return
  if self.path=='/v1/models':self.send(200,{'object':'list','data':[{'id':'qwen3-8b','object':'model'}]})
  else:self.send(404,{'error':'not found'})
 def do_POST(self):
  if not self.authorized():self.send(401,{'error':'unauthorized'});return
  if self.path!='/v1/chat/completions':self.send(404,{'error':'not found'});return
  if not LIMIT.acquire(blocking=False):self.send(503,{'error':'gateway capacity reached (4)'});return
  started=time.monotonic();audit={};question=''
  try:
   n=int(self.headers.get('Content-Length','0'))
   if not 0<n<=2_000_000:raise ValueError('request size')
   body=json.loads(self.rfile.read(n));messages=body['messages']
   if body.get('model')!='qwen3-8b':raise ValueError('only qwen3-8b is served')
   parsed=parse_messages(messages)
   question=parsed['question']
   child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker'],input=json.dumps({'question':question},ensure_ascii=False),text=True,encoding='utf-8',capture_output=True,timeout=45,env=__import__('os').environ.copy()|{'PYTHONIOENCODING':'utf-8'})
   if child.returncode:raise RuntimeError(child.stderr[-500:])
   result=json.loads(child.stdout);audit=result['audit'];audit['input_shape']=parsed['input_shape']
   if result.get('error_type'):
    audit.update(processing_status='failed',error_type=result['error_type'])
    self.send(504 if 'Timeout' in result['error_type'] else 502,{'error':'processing failed','error_type':result['error_type'],'phase':audit.get('phase')})
    return
   answer=result['answer']
   self.send(200,{'id':'qwen-evidence-'+str(time.time_ns()),'object':'chat.completion','model':'qwen3-8b','choices':[{'index':0,'message':{'role':'assistant','content':answer},'finish_reason':'stop'}],'usage':audit.get('usage',{}),'evidence_route':audit.get('route')})
  except Exception as e:
   audit.update(error=type(e).__name__+': '+str(e),processing_status='failed');self.send(502,{'error':'processing failed','error_type':type(e).__name__})
  finally:
   row={'recorded_at':datetime.now(timezone.utc).isoformat(),'question_sha256':hashlib.sha256(question.encode()).hexdigest(),'seconds':round(time.monotonic()-started,3),**audit}
   (HERE/'.local').mkdir(exist_ok=True)
   with LOCK,(HERE/'.local/audit.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
   LIMIT.release()

if __name__=='__main__':
 if '--worker' in sys.argv:
  question=json.load(sys.stdin)['question']
  instance=None
  try:
   instance=Engine();answer,audit=instance.answer(question);audit['model_stages']=instance.timing_events;print(json.dumps({'answer':answer,'audit':audit},ensure_ascii=False))
  except Exception as e:
   audit=getattr(instance,'last_audit',{}).copy();audit['model_stages']=getattr(instance,'timing_events',[])
   print(json.dumps({'error_type':type(e).__name__,'audit':audit},ensure_ascii=False))
 else:ThreadingHTTPServer(('127.0.0.1',8090),Handler).serve_forever()
