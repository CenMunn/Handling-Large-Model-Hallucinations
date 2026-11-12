import json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
import deepseek_search,wikibase_http


class Reply:
    status=200
    def __init__(self):self.raw=b'{"search":[]}'
    def getheader(self,*args):return ''
    def read(self,n):out,self.raw=self.raw[:n],self.raw[n:];return out


class Connection:
    sock=None
    def request(self,*args,**kwargs):pass
    def getresponse(self):return Reply()
    def close(self):pass


class RebootRates(unittest.TestCase):
    def test_deepseek_legacy_previous_boot_reservation_does_not_starve(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rate.sqlite'
            with closing(sqlite3.connect(p)) as db,db:
                db.execute('CREATE TABLE slots (endpoint TEXT PRIMARY KEY,next_time REAL)')
                db.execute('INSERT INTO slots VALUES (?,?)',('search',time.monotonic()+300000))
            deepseek_search.RateGate(p).acquire('search',time.monotonic()+1)

    def test_wikibase_old_monotonic_slot_is_not_a_new_epoch_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rate.sqlite'
            with closing(sqlite3.connect(p)) as db,db:
                db.execute('CREATE TABLE slot (id INTEGER PRIMARY KEY,next_time REAL)')
                db.execute('INSERT INTO slot VALUES (1,?)',(time.monotonic()+30,))
            with wikibase_http.Client(tmp,connection_factory=Connection) as client:
                result,_=client.request({'action':'wbsearchentities'},time.monotonic()+1)
            self.assertEqual(result['search'],[])

    def test_persistent_reservation_is_epoch_time_not_uptime(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'rate.sqlite'
            deepseek_search.RateGate(p).acquire('search',time.monotonic()+1)
            with closing(sqlite3.connect(p)) as db,db:
                schemas=list(db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
                values=[v for (table,) in schemas for row in db.execute('SELECT * FROM '+table) for v in row if isinstance(v,float)]
            self.assertTrue(any(abs(value-time.time())<2 for value in values),values)

    def test_reboot_monotonic_reset_preserves_valid_short_epoch_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate=deepseek_search.RateGate(Path(tmp)/'rate.sqlite')
            gate.acquire('search',time.monotonic()+2)
            original=time.monotonic
            # A new boot has a different uptime origin; persisted epoch times survive.
            with patch('time.monotonic',side_effect=lambda:original()-1000):
                start=time.perf_counter()
                gate.acquire('search',time.monotonic()+1)
                self.assertGreater(time.perf_counter()-start,.4)


if __name__=='__main__':unittest.main()
