import json,time
from wikibase_http import Client
from wikibase_walk import read_edges,label
with Client() as c:
 end=time.monotonic()+18
 roots=c.entities(['Q480','Q727793'],end)
 authors={edge['object'] for root in roots.values() for edge in read_edges(root,'P50')['edges']}
 people=c.entities(list(authors),end)
 countries={edge['object'] for e in people.values() for edge in read_edges(e,'P27')['edges']}
 country_items=c.entities(list(countries),end) if countries else {}
 print(json.dumps([{'id':qid,'label':label(e),'nationalities':[(x['object'],label(country_items[x['object']])) for x in read_edges(e,'P27')['edges']]} for qid,e in people.items()],ensure_ascii=False))
