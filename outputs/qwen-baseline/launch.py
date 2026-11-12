"""Start local GPU server; no firewall or public listener changes."""
import argparse,json,secrets,subprocess,time,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent

def start(parallel=1,context=8192):
 local=OUT/'.local';local.mkdir(exist_ok=True)
 if (local/'server-process.json').exists():
  try:
   with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2) as r:
    if r.status==200:print('Existing local model service is healthy');return
  except Exception:pass
 keyfile=local/'api-key.txt'
 if not keyfile.exists():keyfile.write_text(secrets.token_urlsafe(32),encoding='utf-8')
 exe=ROOT/'work/runtime/llama-vulkan/llama-server.exe'
 model=ROOT/'work/models/Qwen3-8B-Q4_K_M.gguf'
 if not model.exists():raise SystemExit('Model download not complete')
 # Native fopen on this Windows build cannot open Chinese absolute paths.
 # Use ASCII relative paths with an explicit Unicode-safe process working directory.
 args=[str(exe),'-m','work/models/Qwen3-8B-Q4_K_M.gguf','--device','Vulkan1','-ngl','99','--host','127.0.0.1','--port','8080',
  '--alias','qwen3-8b','-c',str(context*parallel),'-np',str(parallel),'--reasoning','off','--reasoning-budget','0',
  '--chat-template-kwargs','{"enable_thinking":false}','--no-context-shift','--api-key-file','outputs/qwen-baseline/.local/api-key.txt','-n','384']
 with (local/'server.stdout.log').open('w') as stdout,(local/'server.stderr.log').open('w') as stderr:
  p=subprocess.Popen(args,cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
 (local/'server-process.json').write_text(json.dumps({'pid':p.pid,'args':args},indent=2),encoding='utf-8')
 for _ in range(180):
  if p.poll() is not None:raise SystemExit('Server exited; inspect .local/server.stderr.log')
  try:
   with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=2) as r:
    if r.status==200:print('READY localhost:8080, PID',p.pid);return
  except Exception:time.sleep(1)
 raise SystemExit('Startup health timeout; inspect log before retrying')

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--parallel',type=int,default=1);a.add_argument('--context',type=int,default=8192);v=a.parse_args();start(v.parallel,v.context)
