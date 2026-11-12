import importlib.util,json,unittest
from pathlib import Path
from unittest.mock import patch

path=Path(__file__).resolve().parent.parent/'qwen-v510-launcher/start_services.py'
spec=importlib.util.spec_from_file_location('launcher_under_test',path)
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class Reply:
    def __init__(self,gateway='qwen-v510-dev'):self.body=json.dumps({'status':'ok','gateway':gateway}).encode()
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,*args):return self.body

class LauncherHealth(unittest.TestCase):
    def test_transient_public_health_error_does_not_misreport_startup(self):
        with patch.object(launcher.urllib.request,'urlopen',side_effect=[OSError('transient EOF'),Reply()]) as open_url,patch.object(launcher.time,'sleep'):
            launcher.public_health()
        self.assertEqual(open_url.call_count,2)

    def test_wrong_version_is_never_accepted(self):
        with patch.object(launcher.urllib.request,'urlopen',return_value=Reply('qwen-v59-dev')):
            with self.assertRaises(RuntimeError):launcher.public_health()

    def test_persistent_network_failure_is_bounded(self):
        with patch.object(launcher.urllib.request,'urlopen',side_effect=OSError('offline')) as open_url,patch.object(launcher.time,'sleep'):
            with self.assertRaises(OSError):launcher.public_health()
        self.assertEqual(open_url.call_count,2)

if __name__=='__main__':unittest.main()
