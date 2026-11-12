"""Run from the user's console so services survive a Codex tool session ending."""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
os.chdir(ROOT)

def health():
 with urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8080/health',timeout=3) as r:
  return r.status==200

if __name__=='__main__':
 print('Starting Qwen3-8B and ngrok. Keep this window open.',flush=True)
 owned=[]
 try:
  for script,state in [('launch.py','server-process.json'),('start_ngrok.py','ngrok-process.json')]:
   previous=None;p=HERE/'.local'/state
   if p.exists():previous=json.loads(p.read_text(encoding='utf-8-sig')).get('pid')
   subprocess.run([sys.executable,str(HERE/script)],check=True,cwd=ROOT)
   if p.exists():
    current=json.loads(p.read_text(encoding='utf-8-sig')).get('pid')
    if current and current!=previous:owned.append(current)
  print('\nREADY: https://YOUR_GATEWAY_DOMAIN/v1',flush=True)
  print('Keep this laptop awake, connected, and this window open. Ctrl+C stops this session.',flush=True)
  while True:
   time.sleep(15)
   try:
    if not health():print('MODEL HEALTH CHECK FAILED',flush=True)
   except Exception as e:print('MODEL OFFLINE:',type(e).__name__,flush=True)
 except KeyboardInterrupt:print('\nStopping owned services.',flush=True)
 except Exception as e:print('STARTUP FAILED:',str(e),flush=True);raise
 finally:
  for pid in reversed(owned):
   subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
