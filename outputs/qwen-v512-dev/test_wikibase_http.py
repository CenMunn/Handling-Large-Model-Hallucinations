import gzip,importlib.util,json,tempfile,time,unittest

class Response:
    def __init__(self,obj,status=200):self.body=gzip.compress(json.dumps(obj).encode());self.status=status;self.offset=0
    def getheader(self,k,default=''):return 'gzip' if k=='Content-Encoding' else default
    def read(self,n):v=self.body[self.offset:self.offset+n];self.offset+=len(v);return v

class Connection:
    def __init__(self,replies):self.replies=replies;self.headers=[];self.sock=None
    def request(self,method,path,headers):self.headers.append(headers)
    def getresponse(self):return self.replies.pop(0)
    def close(self):pass

class HTTPTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('wikibase_http'),'pooled bounded transport missing')
        import wikibase_http
        return wikibase_http

    def test_connection_reused_and_compression_honors_robot_policy(self):
        m=self.module();conn=Connection([Response({'search':[]}),Response({'search':[]})]);created=[]
        def factory():created.append(1);return conn
        with tempfile.TemporaryDirectory() as tmp:
            with m.Client(tmp,connection_factory=factory) as c:
                c.search('甲',time.monotonic()+2);c.search('乙',time.monotonic()+2)
        self.assertEqual(len(created),1)
        self.assertIn('gzip',conn.headers[0]['Accept-Encoding'])

    def test_entity_batch_cache_is_reusable_per_entity(self):
        m=self.module();item=lambda q:{'id':q,'lastrevid':123,'labels':{},'aliases':{},'claims':{}}
        conn=Connection([Response({'entities':{'Q101':item('Q101'),'Q102':item('Q102')}})])
        with tempfile.TemporaryDirectory() as tmp:
            with m.Client(tmp,connection_factory=lambda:conn) as c:
                c.entities(['Q101','Q102'],time.monotonic()+2)
                data=c.entities(['Q102'],time.monotonic()+2)
        self.assertEqual(len(conn.headers),1);self.assertEqual(data['Q102']['lastrevid'],123)

    def test_403_opens_circuit_instead_of_repeating_requests(self):
        m=self.module();conn=Connection([Response({},403),Response({'search':[]})])
        with tempfile.TemporaryDirectory() as tmp:
            with m.Client(tmp,connection_factory=lambda:conn) as c:
                with self.assertRaises(m.APIError) as error:c.search('甲',time.monotonic()+2)
                self.assertEqual(error.exception.status,403)
                with self.assertRaises(m.APIError):c.search('乙',time.monotonic()+2)
        self.assertEqual(len(conn.headers),1)

    def test_response_identity_mismatch_cannot_poison_cache(self):
        m=self.module();conn=Connection([Response({'entities':{'Q101':{'id':'Q102','labels':{},'claims':{}}}})])
        with tempfile.TemporaryDirectory() as tmp:
            with m.Client(tmp,connection_factory=lambda:conn) as c:
                with self.assertRaises(ValueError):c.entities(['Q101'],time.monotonic()+2)

    def test_another_client_cannot_overbook_remaining_request_budget(self):
        m=self.module();conn=Connection([Response({'search':[]}),Response({'search':[]})])
        with tempfile.TemporaryDirectory() as tmp:
            with m.Client(tmp,connection_factory=lambda:conn) as first:first.search('甲',time.monotonic()+2)
            with m.Client(tmp,connection_factory=lambda:conn) as second:
                with self.assertRaises(TimeoutError):second.search('乙',time.monotonic()+.3)
        self.assertEqual(len(conn.headers),1)

if __name__=='__main__':unittest.main()
