"""Literal, narrowly supported work/director verification. No answer lookup."""
import re
def neutral_queries(question):
 q=re.sub(r'^我了解到(?:一件事)?[，,:：]?','',question)
 work=re.search(r'《([^》]{1,40})》',q)
 director=re.search(r'^([^，,。:：]{2,40}?)的导演',q)
 if work and re.search(r'导演|执导|播出',q):return [work[1]+' 导演 首播 官方',work[1]+' 演职员 播出平台']
 if director:return [director[1]+' 导演 演职员 官方',director[1]+' 电视剧 节目资料']
 if work and '作者' in q:return [work[1]+' 作者 官方 馆藏',work[1]+' 作者 作品资料']
 place=re.search(r'^([^，,。]{2,30}?)位于',q)
 if place:return [place[1]+' 所在地 官方',place[1]+' 地理位置']
 return []
def verify(question,docs):
 simple=verify_simple_relation(question,docs)
 if simple is not None:return simple
 work=re.search(r'《([^》]{1,40})》',question)
 direct=re.search(r'(?:我了解到[，,:：]?)?([^，,。:：]{2,40}?)的导演(?:是|为)([\u4e00-\u9fff·]{2,5})',question)
 inverted=re.search(r'([\u4e00-\u9fff·]{2,4})执导.{0,10}《([^》]{1,40})》',question)
 if direct:
  title=work[1] if work else direct[1].strip('《》');claimed=direct[2]
 elif inverted:title=inverted[2];claimed=inverted[1]
 else:return {'status':'unsupported'}
 edges=[]
 for d in docs:
  text=d.get('text','');header=d.get('title','')
  patterns=[]
  if title in header:
   patterns.append(r'(?:^|[\n。])\s*导演\s*(?:[：:|｜]|\n)\s*([\u4e00-\u9fff·、,， ]{2,40}?)(?=主演|编剧|简介|类型|[\n。]|$)')
   patterns.append(r'(?:^|[。\n，,])(?:该剧)?(?:由)?([\u4e00-\u9fff·]{2,5})执导')
  patterns.append(r'《'+re.escape(title)+r'》(?:由|的导演是)([\u4e00-\u9fff·、,， ]{2,30}?)(?:执导|担任导演|[。\n])')
  for pattern in patterns:
   for m in re.finditer(pattern,text):
    names=[s.strip() for s in re.split(r'[、,， ]+',m[1]) if s.strip()]
    if names and all(re.fullmatch(r'[\u4e00-\u9fff·]{2,5}',x) for x in names):
     edges.append({'source_id':d.get('id'),'source_url':d.get('url'),'title_anchor':header,'quote':m[0],'directors':names})
 if not edges:return {'status':'unresolved','reason':'no explicit work-director evidence'}
 values={tuple(sorted(e['directors'])) for e in edges}
 if len(values)!=1:return {'status':'unresolved','reason':'director sources disagree','evidence':edges}
 names=next(iter(values));base={'evidence':edges,'limitation':'Checks director subclaim only; no source authority or compound-event proof.'}
 if claimed not in names:return dict(base,status='refuted',answer='该说法不正确。检索来源列出的导演是'+ '、'.join(names)+'。')
 if re.search(r'\d{4}年|播出|平台|获奖|首播',question):return dict(base,status='unresolved',reason='other event subclaims not independently verified')
 return dict(base,status='supported',answer='来源支持该导演信息；列出的导演为'+ '、'.join(names)+'。')

def verify_simple_relation(question,docs):
 q=re.sub(r'^我了解到(?:一件事)?[，,:：]?','',question)
 author=re.search(r'《([^》]{1,40})》的作者(?:一般认为)?是(?:[^，,。]{0,12}?(?:画家|作家|诗人))?([\u4e00-\u9fff·]{2,5})[。？，,?]',q)
 located=re.search(r'^([^，,。]{2,30}?)位于([^，,。？?]{1,20})',q)
 if not author and not located:return None
 subject,claimed=author.groups() if author else located.groups()
 attribute='作者' if author else '所在地';edges=[]
 pattern=(r'《'+re.escape(subject)+r'》的作者(?:是|为)([\u4e00-\u9fff·]{2,5})(?=[。\n，,]|$)' if author else re.escape(subject)+r'位于([^，,。；;\n]{1,30})')
 for d in docs:
  patterns=[pattern]
  if author and re.sub(r'(?:卷|册)$','',d.get('title','').strip())==subject:
   patterns.append(r'作者(?:是|为)([\u4e00-\u9fff·]{2,5})(?=[。\n，,]|$)')
  for m in (m for p in patterns for m in re.finditer(p,d.get('text',''))):
   if re.search(r'不是|并非|传闻|可能|据说',m[0]):continue
   edges.append({'source_id':d.get('id'),'source_url':d.get('url'),'quote':m[0],'value':m[1]})
 if not edges:return {'status':'unresolved','reason':'no literal predicate evidence'}
 values={e['value'] for e in edges}
 if len(values)!=1:return {'status':'unresolved','reason':'predicate sources differ','evidence':edges}
 actual=next(iter(values))
 # Matching only one predicate is insufficient to validate dates or other
 # event details embedded elsewhere in a compound assertion.
 if claimed==actual:
  if re.search(r'\d{4}年|获奖|首播',q):return {'status':'unresolved','evidence':edges,'reason':'compound claim'}
  return {'status':'supported','answer':'来源支持该说法。','evidence':edges}
 if claimed in actual or actual in claimed:return {'status':'unresolved','evidence':edges,'reason':'scope or granularity differs'}
 return {'status':'refuted','answer':'该说法不正确。来源中的'+attribute+'为'+actual+'。','evidence':edges}
