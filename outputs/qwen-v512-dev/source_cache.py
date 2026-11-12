"""Rediscover still-fresh independent page reads as RAG candidates, not answers."""
import hashlib,json,re,time
from pathlib import Path
from primary_fetch import canonical

def candidates(queries,directory):
 grams=set()
 for query in queries:
  for token in re.findall(r'[\u4e00-\u9fff]{2,}|[A-Za-z+]{3,}',query):
   if re.search('[\u4e00-\u9fff]',token):grams.update(token[i:i+2] for i in range(len(token)-1))
   else:grams.add(token.lower())
 grams-={'如果','那么','什么','多少','是谁','是否','问题','根据','资料','信息'}
 ranked=[]
 for path in sorted(Path(directory).glob('*.json'))[:400]:
  try:
   row=json.loads(path.read_text(encoding='utf-8'))
   if row.get('transport')!='independent_https' or not 0<=time.time()-row['epoch']<86400:continue
   url=canonical(row['url']);text=row['text']
   if not isinstance(text,str) or not re.fullmatch('[a-f0-9]{64}',row.get('raw_sha256','')):continue
   score=sum(g in text.lower() for g in grams)
   if score<3:continue
   ranked.append((score,{'id':'independent-cache-'+hashlib.sha256(url.encode()).hexdigest()[:16],
       'url':url,'title':'Previously independently read source','text':text,'source_kind':'fresh_independent_body_cache',
       'retrieved_at':row.get('retrieved_at'),'raw_sha256':row['raw_sha256'],'discovery':'local lexical retrieval; relevance is not verified entailment'}))
  except (OSError,ValueError,KeyError,TypeError):continue
 return [r for _,r in sorted(ranked,key=lambda r:r[0],reverse=True)[:6]]
