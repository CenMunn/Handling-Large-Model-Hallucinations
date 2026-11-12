"""Narrow, auditable temporal joins over original user turns, not summaries.

Unsupported wording, unresolved scope or ambiguous joins fall back to normal
material QA. No entity, date, role or answer is supplied from an answer table.
"""
import re
DATE=re.compile(r'(\d{4})年(\d{1,2})月')
ROLE=r'(?:副负责人|负责人|副主任|主任|副总经理|总经理|董事长|CEO)'

def records(question):
 body=question.split('【最终问题】',1)[0]
 markers=list(re.finditer(r'(?:^|\n)\s*(用户|助手)[：:]\s*',body))
 out=[];scope='original';original_world=None
 for i,m in enumerate(markers):
  if m[1]!='用户':continue
  text=body[m.end():markers[i+1].start() if i+1<len(markers) else len(body)].strip()
  if original_world is None and re.search(r'建立.*虚拟.*世界',text):
   world=re.search(r'名称为[“‘\'\"]([^”’\'\"]+世界)[”’\'\"]',text)
   if world:original_world=world[1]
  if re.search(r'回到(?:原始|原来|原本)',text) or original_world and ('回到'+original_world) in text:scope='original'
  elif re.search(r'(?:建立|创建|设立).{0,30}(?:镜像|平行)世界|(?:在|按照).{0,15}镜像世界',text):scope='other'
  date=DATE.search(text)
  out.append({'turn_id':f'u{len(out)}','text':text,'date':(int(date[1]),int(date[2])) if date else None,'scope':scope})
 return out

def resolve(question):
 if '【最终问题】' not in question:return None
 q=question.rsplit('【最终问题】',1)[1].strip()
 if re.search(r'镜像|平行世界',q):return None
 source=[r for r in records(question) if r['scope']=='original']
 if not source:return None
 latest=re.fullmatch(r'截至(\d{4})年[，,\s]*([^？?。]{2,40}?)的?正式名称(?:是什么|为(?:什么)?)[？?。]?',q)
 if latest:
  cutoff=(int(latest[1]),12);entity=latest[2].rstrip('的');found=[]
  for r in source:
   if not r['date'] or r['date']>cutoff or entity not in r['text']:continue
   for m in re.finditer(r'(?:正式文件(?:统一)?使用|正式名称(?:为|是))[“‘\'\"]([^”’\'\"\n]{1,60})[”’\'\"]',r['text']):
    before=r['text'][max(0,m.start()-16):m.start()]
    if re.search(r'不是|并非|不再|历史|旧称|曾经',before):continue
    found.append((r['date'],m[1],r))
  if not found:return None
  date=max(x[0] for x in found);current=[x for x in found if x[0]==date]
  values={x[1] for x in current}
  if len(values)!=1:return None
  return {'answer':next(iter(values)),'method':'latest_explicit_formal_name','cutoff':cutoff,'evidence':[x[2] for x in current]}
 dates=list(DATE.finditer(q))
 if len(dates)!=2 or not re.search(r'任命|职务',q):return None
 award=re.search(r'获得(.{2,35}?)的团队负责人',q)
 if not award:return None
 event_date=tuple(map(int,dates[0].groups()));past_date=tuple(map(int,dates[1].groups()))
 if past_date>event_date:return None
 events=[]
 for r in source:
  if r['date']!=event_date or award[1] not in r['text']:continue
  m=re.search(r'[，,]([\u4e00-\u9fff·]{2,4})(?:带领|率领)团队获得'+re.escape(award[1]),r['text'])
  if m and not re.search(r'可能|传闻|并未|没有',r['text']):events.append((m[1],r))
 if not events or len({x[0] for x in events})!=1:return None
 person=events[0][0];appointments=[]
 for r in source:
  if r['date']!=past_date or person not in r['text']:continue
  for sentence in re.split(r'[。！？\n]',r['text']):
   if person not in sentence or re.search(r'不是|并非|未任命|没有任命|可能',sentence):continue
   corrected=re.search(r'修正为([\u4e00-\u9fff·]{2,4})',sentence)
   if corrected and corrected[1]!=person:continue
   m=re.search(r'(?:增加|任命(?:为)?|聘任(?:为)?)('+ROLE+r')',sentence)
   if not m:continue
   # The role must immediately precede the named person or a corrected name;
   # later unrelated people in a sentence cannot inherit the appointment.
   after=sentence[m.end():]
   named=re.match(r'([\u4e00-\u9fff·]{2,4})(?:[（(，,]|$)',after)
   if not named or (named[1]!=person and not corrected):continue
   duty=re.search(r'[，,]负责([^，,。]{1,50})',sentence)
   answer=m[1]+('，负责'+duty[1] if duty else '')
   appointments.append((answer,r))
 if not appointments or len({x[0] for x in appointments})!=1:return None
 return {'answer':appointments[0][0],'method':'event_person_historical_appointment','person':person,
         'event_date':event_date,'appointment_date':past_date,'evidence':[events[0][1],appointments[0][1]]}
