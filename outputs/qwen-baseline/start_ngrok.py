import json,subprocess,time,urllib.request
from pathlib import Path

HERE=Path(__file__).resolve().parent
exe=Path('D:/北大金融比赛/复赛深化/公网运行-v17-ngrok-20261012/tools/ngrok.exe')
try:
 with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels',timeout=2) as r:data=json.load(r)
 if any(t.get('public_url')=='https://YOUR_GATEWAY_DOMAIN' and str(t.get('config',{}).get('addr','')).endswith(':8080') for t in data.get('tunnels',[])):
  print('Existing competition tunnel reused');raise SystemExit(0)
 raise RuntimeError('An existing ngrok tunnel needs review')
except urllib.error.URLError:pass
with (HERE/'.local/ngrok.stdout.log').open('w') as out,(HERE/'.local/ngrok.stderr.log').open('w') as err:
 p=subprocess.Popen([str(exe),'http','--url=YOUR_GATEWAY_DOMAIN','http://127.0.0.1:8080','--log=stdout','--log-format=json'],stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
(HERE/'.local/ngrok-process.json').write_text(json.dumps({'pid':p.pid,'public_url':'https://YOUR_GATEWAY_DOMAIN'}),encoding='utf-8')
for _ in range(30):
 if p.poll() is not None:raise SystemExit('ngrok exited. Inspect local log.')
 try:
  with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels',timeout=2) as r:data=json.load(r)
  if data.get('tunnels'):print('ngrok ready');break
 except urllib.error.URLError:pass
 time.sleep(1)
else:raise SystemExit('ngrok startup timeout')
