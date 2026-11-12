"""Constrained Chinese relation extraction over retrieved text, not a truth oracle.

Only literal edges are accepted. Source authority, unknown aliases and arbitrary
multi-hop reasoning remain outside this parser. No LLM assertions are trusted.
"""
import re

ROLE=r'(?:作家|作者|演员|导演|画家|研究员|诗人|馆员|讲解员|摄影师|科学家|工程师)'
NEG=re.compile(r'不是|并非|从未|未曾|不曾|传闻|据说|可能|疑似|未经证实|不确定')
KIN=re.compile(r'姐姐|妹妹|哥哥|弟弟|父亲|母亲|妻子|丈夫|儿子|女儿|同事|朋友')
INSTRUCTION=re.compile(r'忽略.*(?:问题|指令)|只输出|请回答|ignore.*instruction',re.I)
VALUE=r'[^，,。；;！？?\n]{1,45}?'

def target(question):
 q=re.sub(r'^\s*(?:请)?(?:仅|只)?(?:依据|根据)检索(?:资料|材料|结果)(?:回答|作答)?[，,:：]\s*','',question).strip()
 attribute=next((a for word,a in [('前身','predecessor'),('祖籍','ancestral_origin'),('籍贯','registered_origin'),('出生','birthplace')] if word in q),None)
 if not attribute:return None
 if attribute=='birthplace' and not re.search(r'出生(?:地|城市)?(?:于|在|是|为|有)?(?:哪里|哪(?:座|个)城市|什么)(?:[？?。])?$',q):return None
 if attribute in ('registered_origin','ancestral_origin') and not re.search(r'(?:籍贯|祖籍)(?:是|为|在)?(?:哪里|什么|哪个县|哪个省|哪个城市)(?:[？?。])?$',q):return None
 if attribute=='predecessor':
  m=re.fullmatch(r'([^，,。？?]{2,45}?)的前身(?:是什么(?:机构)?|叫(?:什么|啥)|是哪个机构)[？?。]?',q)
  return {'entity':m[1],'attribute':attribute,'role':None,'work':None,'organization':None} if m else None
 stem=q.split('出生',1)[0] if attribute=='birthplace' else re.split(r'籍贯|祖籍',q,1)[0]
 stem=stem.rstrip('的')
 m=re.search('('+ROLE+r')([\u4e00-\u9fff·]{2,4})$',stem)
 role=m[1] if m else None
 person=m[2] if m else stem if re.fullmatch(r'[\u4e00-\u9fff·]{2,4}',stem) else None
 if not person:return None
 work=re.findall(r'《[^》\n]{1,35}》',stem)
 org=re.search(r'在(.{2,35}?)(?:工作|任职)的',stem)
 if len(work)>1:return None
 return {'entity':person,'attribute':attribute,'role':role,'work':work[0] if work else None,'organization':org[1] if org else None}

def qualified(t,s):
 n=re.escape(t['entity'])
 if t['work']:
  w=re.escape(t['work'])
  if not (re.search(w+r'的(?:作者|作家|导演|画家|创作者)'+n,s) or re.search(n+r'(?:是|为)'+w+r'的(?:作者|作家|导演|画家|创作者)',s) or re.search(n+r'.{0,4}(?:创作|撰写|写作|执导)(?:了)?'+w,s)):return False
 elif t['role'] and not re.search(re.escape(t['role'])+n,s):return False
 if t['organization'] and not (t['organization'] in s and re.search(r'工作|任职',s)):return False
 return True

def bind(question,sources):
 t=target(question)
 if not t:return {'status':'unsupported','reason':'relation or explicit entity is unsupported'}
 evidence=[];excluded=[];unresolved=[];scanned=[]
 relation={'birthplace':r'(?:出生于|出生在|生于|的出生地(?:是|为))','registered_origin':r'(?:的)?籍贯(?:是|为|在)', 'ancestral_origin':r'(?:的)?祖籍(?:是|为|在)', 'predecessor':r'的前身(?:是|为)'}[t['attribute']]
 attrword={'birthplace':'出生','registered_origin':'籍贯','ancestral_origin':'祖籍','predecessor':'前身'}[t['attribute']]
 for index,source in enumerate(sources):
  sid=source.get('id',str(index));text=source.get('text')
  if not isinstance(text,str):unresolved.append({'source_id':sid,'reason':'unreadable source'});continue
  scanned.append(sid);context=False
  title=source.get('title','')
  bio_anchor=(t['attribute']=='birthplace' and not any(t[k] for k in ('role','work','organization')) and t['entity'] in title and bool(re.search(r'生平|年谱|传记',title)))
  for raw in re.findall(r'[^。！？!?\n]+[。！？!?]?',text):
   sentence=raw.strip();has_name=t['entity'] in sentence
   pronoun=bool(re.match(r'^(?:他|她)(?:的)?',sentence))
   dated=bool(bio_anchor and re.match(r'^[一二三四五六七八九十零〇初夏历\d年月日()（），,\s]+(?:出生于|出生在|生于)',sentence))
   if not has_name and not (pronoun and context) and not dated:context=False;continue
   if INSTRUCTION.search(sentence):unresolved.append({'source_id':sid,'reason':'instruction-like source'});context=False;continue
   if t['attribute']=='predecessor':
    # Bind the immediate grammatical subject of 前身. A parent institution
    # mentioned as an owner cannot replace that subject.
    for m in re.finditer(r'([^，,。；;]+?)'+relation+'('+VALUE+r')(?=[，,。；;]|$)',sentence):
     subject,value=m[1],m[2]
     if subject!=t['entity']:
      if t['entity'] in subject and re.search(r'下属|附属|旗下|所属',subject):excluded.append({'source_id':sid,'quote':m[0],'reason':'different subsidiary subject'});continue
      if has_name:unresolved.append({'source_id':sid,'reason':'ambiguous predecessor subject'})
      continue
     if NEG.search(m[0]):unresolved.append({'source_id':sid,'reason':'negated relation'});continue
     evidence.append({'source_id':sid,'source_url':source.get('url',''),'quote':m[0],'entity':t['entity'],'attribute':t['attribute'],'value':value})
    continue
   # Exclude only an explicitly distinguished other-person statement, never
   # an entire source or merely a different occupation.
   other=re.match('('+ROLE+')'+re.escape(t['entity']),sentence)
   explicit_other=bool(other and t['role'] and other[1]!=t['role'] and re.search(r'不是同一人|并非同一人',sentence) and (t['work'] in sentence if t['work'] else t['role'] in sentence))
   if explicit_other:
    excluded.append({'source_id':sid,'quote':sentence,'reason':'explicitly different same-name person'});context=False;continue
   confirmed=qualified(t,sentence) if has_name else context or dated
   if has_name:context=confirmed and not NEG.search(sentence) and not KIN.search(sentence)
   if attrword not in sentence and not (t['attribute']=='birthplace' and '生于' in sentence):continue
   if t['attribute']=='birthplace' and not re.search(r'出生于|出生在|出生地|生于',sentence):continue
   if re.search(r'(?:未|没有|尚未)(?:提供|公布|记录|记载)',sentence):continue
   if NEG.search(sentence) or KIN.search(sentence):
    unresolved.append({'source_id':sid,'reason':'negation, uncertainty or different relative'});continue
   if not confirmed:unresolved.append({'source_id':sid,'reason':'identity qualifier not established'});continue
   # The attribute must attach to the named subject, a local continuation or
   # a pronoun immediately following a simple identity sentence.
   m=re.search(relation+'('+VALUE+r')(?=[，,。；;]|$)',sentence)
   if not m:unresolved.append({'source_id':sid,'reason':'unparsed relevant attribute'});continue
   before=sentence[:m.start()]
   if re.search(r'其弟|其父|其母|而|另|分别',before):unresolved.append({'source_id':sid,'reason':'ambiguous intervening subject'});continue
   # Reject another explicit person between target and relation.
   if has_name and re.search(ROLE+r'[\u4e00-\u9fff·]{2,4}',before.split(t['entity'],1)[-1]):
    unresolved.append({'source_id':sid,'reason':'another named subject'});continue
   value=m[1]
   if t['attribute']=='birthplace':value=re.split(r'(?:的)?(?:一个|一户|某个).*(?:家庭|家中)',value,maxsplit=1)[0]
   if not value:unresolved.append({'source_id':sid,'reason':'empty extracted value'});continue
   evidence.append({'source_id':sid,'source_url':source.get('url',''),'quote':sentence,'entity':t['entity'],'attribute':t['attribute'],'value':value,'title_anchor':title if dated else None})
 values={e['value'] for e in evidence}
 base={'target':t,'evidence':evidence,'excluded':excluded,'unresolved':unresolved,'scanned_source_ids':scanned,
       'limitation':'Literal relation extraction; not proof of source truth, independence, aliases or arbitrary semantics.'}
 if len(values)>1:return dict(base,status='conflict')
 if unresolved:return dict(base,status='unresolved')
 if not values:return dict(base,status='insufficient')
 return dict(base,status='supported',answer=next(iter(values)))
