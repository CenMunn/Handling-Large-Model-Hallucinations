"""Idempotent manual start/recovery. Services continue in background."""
import json,socket,subprocess,sys,time,urllib.error,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEV=ROOT/'outputs/qwen-v510-dev'
STATE=DEV/'.local'
DOMAIN='YOUR_GATEWAY_DOMAIN'
VERSION='qwen-v510-dev'
LOCAL=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def local_json(url):
    with LOCAL.open(url,timeout=3) as r:return json.load(r)

def healthy():
    try:
        v=local_json('http://127.0.0.1:8088/health')
        return v.get('status')=='ok' and v.get('gateway')==VERSION
    except (OSError,ValueError):return False

def spawn(args,name):
    STATE.mkdir(exist_ok=True)
    with (STATE/(name+'.stdout.log')).open('ab') as out,(STATE/(name+'.stderr.log')).open('ab') as err:
        return subprocess.Popen(args,cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)

def public_health():
    request=urllib.request.Request('https://'+DOMAIN+'/health',headers={'ngrok-skip-browser-warning':'true'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request,timeout=5) as r:public=json.load(r)
        except (OSError,ValueError):
            if attempt:raise
            time.sleep(.25)
            continue
        if public.get('status')!='ok' or public.get('gateway')!=VERSION:raise RuntimeError('Public version check failed')
        return

def main():
    subprocess.run([sys.executable,str(ROOT/'outputs/qwen-baseline/launch.py'),'--context','12288'],cwd=ROOT,check=True)
    key=(ROOT/'outputs/qwen-baseline/.local/api-key.txt').read_text().strip()
    request=urllib.request.Request('http://127.0.0.1:8080/props',headers={'Authorization':'Bearer '+key})
    with LOCAL.open(request,timeout=3) as r:props=json.load(r)
    if props.get('default_generation_settings',{}).get('n_ctx')!=12288:
        raise RuntimeError('Raw model context must be 12288; existing model was not stopped.')
    if not healthy():
        with socket.socket() as s:
            s.settimeout(.5)
            if s.connect_ex(('127.0.0.1',8088))==0:
                raise RuntimeError('Port 8088 is occupied by an unhealthy or different service; no process was stopped.')
        proc=spawn([sys.executable,str(DEV/'gateway.py')],'launcher-gateway')
        (STATE/'test-gateway-process.json').write_text(json.dumps({'pid':proc.pid,'port':8088,'script':str(DEV/'gateway.py')}),encoding='utf-8')
        for _ in range(40):
            if proc.poll() is not None:raise RuntimeError('v5.10 gateway exited; see .local/launcher-gateway.stderr.log')
            if healthy():break
            time.sleep(.25)
        else:raise RuntimeError('v5.10 gateway startup timeout')
    try:tunnels=local_json('http://127.0.0.1:4040/api/tunnels').get('tunnels',[])
    except OSError:tunnels=[]
    matching=[t for t in tunnels if t.get('public_url','').rstrip('/')=='https://'+DOMAIN]
    if matching:
        if any(t.get('config',{}).get('addr','').rstrip('/')!='http://127.0.0.1:8088' for t in matching):
            raise RuntimeError('The ngrok domain still points to another version. Existing tunnel was left running.')
    else:
        if tunnels:raise RuntimeError('An existing ngrok session uses another endpoint; it was left running.')
        exe=Path('D:/北大金融比赛/复赛深化/公网运行-v17-ngrok-20261012/tools/ngrok.exe')
        proc=spawn([str(exe),'http','--url='+DOMAIN,'http://127.0.0.1:8088','--log=stdout','--log-format=json'],'launcher-ngrok')
        (STATE/'tunnel-process.json').write_text(json.dumps({'pid':proc.pid,'upstream':'http://127.0.0.1:8088','domain':DOMAIN}),encoding='utf-8')
        for _ in range(40):
            if proc.poll() is not None:raise RuntimeError('ngrok exited; see .local/launcher-ngrok logs')
            try:
                if any(t.get('public_url','').rstrip('/')=='https://'+DOMAIN for t in local_json('http://127.0.0.1:4040/api/tunnels').get('tunnels',[])):break
            except OSError:pass
            time.sleep(.25)
        else:raise RuntimeError('ngrok startup timeout')
    public_health()
    print('READY V510: https://'+DOMAIN+'/v1',flush=True)
    print('Services run in background. Keep this PC awake and connected. Closing this window does not stop services.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print('START FAILED: '+str(error),flush=True)
        raise SystemExit(1)
