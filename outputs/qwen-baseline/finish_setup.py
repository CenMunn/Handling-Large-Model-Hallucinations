"""Resume local acceptance once verified model weights are available."""
import hashlib,json,subprocess,sys,time,urllib.request,zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STATUS=HERE/'status.json'
def status(phase,**extra):
 STATUS.write_text(json.dumps({'phase':phase,**extra},ensure_ascii=False,indent=2),encoding='utf-8');print(phase,flush=True)
def run(*args):subprocess.run([sys.executable,*map(str,args)],check=True,cwd=ROOT)

if __name__=='__main__':
 try:
  status('waiting_for_model_download')
  model=ROOT/'work/models/Qwen3-8B-Q4_K_M.gguf'
  while not (ROOT/'outputs/qwen-baseline/provenance.json').exists():time.sleep(5)
  h=hashlib.sha256()
  with model.open('rb') as f:
   while b:=f.read(8*1024*1024):h.update(b)
  assert h.hexdigest()=='d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785'
  status('starting_local_gpu_server');run(HERE/'launch.py')
  status('testing_platform_adapter');run(HERE/'platform/run.py',HERE/'local_input',HERE/'results/local_result.json')
  status('evaluating_raw_smoke');run(HERE/'evaluate.py','--raw','--limit','14','--label','raw-smoke')
  status('evaluating_guarded_smoke');run(HERE/'evaluate.py','--limit','14','--label','guarded-smoke')
  summary=json.loads((HERE/'results/guarded-smoke-summary.json').read_text())
  if summary['successful_requests']!=14:raise RuntimeError('Smoke requests failed; inspect logs before public access')
  status('starting_authorized_ngrok')
  run(HERE/'start_ngrok.py')
  time.sleep(5)
  status('verifying_public_api')
  key=(HERE/'.local/api-key.txt').read_text().strip()
  body={'model':'qwen3-8b','messages':[{'role':'user','content':'12乘以13等于多少？只回答数字。'}],'max_tokens':32,'chat_template_kwargs':{'enable_thinking':False}}
  req=urllib.request.Request('https://YOUR_GATEWAY_DOMAIN/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key,'ngrok-skip-browser-warning':'true'})
  started=time.monotonic()
  with urllib.request.urlopen(req,timeout=45) as r:data=json.load(r)
  assert '156' in data['choices'][0]['message']['content']
  (HERE/'results/public-smoke.json').write_text(json.dumps({'elapsed_seconds':time.monotonic()-started,'response':data},ensure_ascii=False,indent=2),encoding='utf-8')
  adapter=HERE/'platform/model.py';s=adapter.read_text(encoding='utf-8');s=s.replace("BASE_URL = 'http://127.0.0.1:8080/v1'","BASE_URL = 'https://YOUR_GATEWAY_DOMAIN/v1'");adapter.write_text(s,encoding='utf-8')
  with zipfile.ZipFile(HERE/'platform-model.zip','w',zipfile.ZIP_DEFLATED) as z:
   for n in ['run.py','run.sh','model.py','requirements.txt']:z.write(HERE/'platform'/n,'model/'+n)
  status('public_smoke_verified_ready_for_platform_test',public_url='https://YOUR_GATEWAY_DOMAIN/v1',warning='Platform submission and concurrency capacity still unverified; ZIP contains a private API key.')
 except Exception as e:
  status('failed_needs_review',error=type(e).__name__+': '+str(e));raise
