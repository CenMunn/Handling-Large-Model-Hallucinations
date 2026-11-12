$ErrorActionPreference = 'Stop'
$ngrokExe = 'D:/北大金融比赛/复赛深化/公网运行-v17-ngrok-20261012/tools/ngrok.exe'
$stateDir = Join-Path $PSScriptRoot '.local'
New-Item -ItemType Directory -Force -Path $stateDir | Out-Null
if (Get-Process ngrok -ErrorAction SilentlyContinue) { throw 'An ngrok process is already running. Check it before starting another session.' }
$response = Invoke-WebRequest 'http://127.0.0.1:8080/health' -TimeoutSec 3
if ($response.StatusCode -ne 200) { throw 'Local model is not ready.' }
$process = Start-Process -FilePath $ngrokExe -ArgumentList @('http','--url=YOUR_GATEWAY_DOMAIN','http://127.0.0.1:8080','--log=stdout','--log-format=json') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $stateDir 'ngrok.stdout.log') -RedirectStandardError (Join-Path $stateDir 'ngrok.stderr.log')
@{pid=$process.Id; publicUrl='https://YOUR_GATEWAY_DOMAIN'; target='http://127.0.0.1:8080'} | ConvertTo-Json | Set-Content (Join-Path $stateDir 'ngrok-process.json') -Encoding utf8
Write-Output 'ngrok started. Verify the public API before platform submission.'
