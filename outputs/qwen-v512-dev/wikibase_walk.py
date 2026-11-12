"""Typed local walks over complete Wikibase entity claims, never SPARQL.

Question interpretation is deliberately limited; unsupported questions retain
normal web retrieval. Community data and bounded search do not prove truth or
global uniqueness. Every supported hop retains its statement and revision.
"""
import calendar,json,os,re,subprocess,sys,time,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from wikibase_http import Client,APIError

HERE=Path(__file__).resolve().parent
REGION_SOURCE='https://www.lswz.gov.cn/html/ywpd/bzzl/2024-01/26/275402/files/29d04adc161148c0bc313cffbfecc401.pdf'
REGIONS=dict(zip('北京市 天津市 河北省 山西省 内蒙古自治区 辽宁省 吉林省 黑龙江省 上海市 江苏省 浙江省 安徽省 福建省 江西省 山东省 河南省 湖北省 湖南省 广东省 广西壮族自治区 海南省 重庆市 四川省 贵州省 云南省 西藏自治区 陕西省 甘肃省 青海省 宁夏回族自治区 新疆维吾尔自治区 香港特别行政区 澳门特别行政区 台湾省'.split(),
                 '京 津 冀 晋 内蒙古 辽 吉 黑 沪 苏 浙 皖 闽 赣 鲁 豫 鄂 湘 粤 桂 琼 渝 川 黔 滇 藏 陕 甘 青 宁 新 港 澳 台'.split()))
BENIGN_QUALIFIERS={'P1932','P1810','P1545','P7452'} # spelling/ordering/rank explanation, never identity aliases
CURRENT_PROPERTIES={'P17','P36','P131','P31','P279'}

def norm(x):return re.sub(r'\s+','',unicodedata.normalize('NFKC',x)).casefold()
def names(e):
    values=[v.get('value','') for v in e.get('labels',{}).values() if isinstance(v,dict)]
    values += [v.get('value','') for group in e.get('aliases',{}).values() for v in group if isinstance(v,dict)]
    return {x for x in values if isinstance(x,str) and x.strip()}
def label(e):
    labels=e.get('labels',{})
    for lang in ('zh-hans','zh-cn','zh','en'):
        value=labels.get(lang,{}).get('value')
        if isinstance(value,str) and value.strip():return value
    return None

def plan(q):
    if re.search(r'【世界设定】|【对话记录】|根据.*材料|依据.*材料|仅根据|只根据|截至|出生时|当时|历史|是否|对吗|说法|有人说|据说|最新|现任',q):return None
    works=re.findall(r'《([^》]{1,70})》',q)
    if (len(works)==1 and re.search(r'主演|出演',q) and '导演' in q and '出生' in q
            and re.search(r'省级行政区|省份|哪个省',q) and '简称' in q):
        return {'anchor':works[0],'kind':'film_actor_director_birth_region','types':['Q11424'],
                'scope':'current_birthplace_administration',
                'role_scope':'cast member and director intersection; cast does not establish lead billing'}
    if len(works)==1 and re.search(r'创作|作者|作家',q) and '出生' in q and '国家' in q and '首都' in q:
        return {'anchor':works[0],'kind':'work_birth_capital','types':['Q8261','Q47461344'] if re.search(r'小说|作家|著作',q) else [],'scope':'current_birthplace_country'}
    if '创始人' in q and '出生' in q and re.search(r'省份|哪个省|哪一省',q):
        stem=q.split('创始人',1)[0].strip().rstrip('的');anchor=stem.rsplit('的',1)[-1].strip('“”" ')
        if re.fullmatch(r'[\u4e00-\u9fffA-Za-z0-9·]{2,35}',anchor):
            return {'anchor':anchor,'kind':'founder_birth_province','types':[],'scope':'current_birthplace_administration','unverified_prefix':stem[:-len(anchor)]}
    m=re.fullmatch(r'\s*([\u4e00-\u9fffA-Za-z· ]{2,35}?)(?:的)?首都(?:是|为|在)?(?:什么|哪里|哪(?:个|座)城市)[？?。]?\s*',q)
    if m and not re.search(r'其|他|她|这|那|出生|所在|作者|的',m[1]):return {'anchor':m[1],'kind':'capital','types':['Q6256'],'scope':'current'}
    return None

def date_interval(snak):
    v=snak.get('datavalue',{}).get('value',{})
    if not isinstance(v,dict):return None
    m=re.fullmatch(r'\+?(\d{4})-(\d{2})-(\d{2})T.*',v.get('time',''))
    if not m:return None
    y,month,day=map(int,m.groups());precision=v.get('precision',0)
    if y<1 or precision<9:return None
    try:
        if precision==9:return datetime(y,1,1,tzinfo=timezone.utc),datetime(y,12,31,23,59,59,tzinfo=timezone.utc)
        if precision==10:return datetime(y,month,1,tzinfo=timezone.utc),datetime(y,month,calendar.monthrange(y,month)[1],23,59,59,tzinfo=timezone.utc)
        return datetime(y,month,day,tzinfo=timezone.utc),datetime(y,month,day,23,59,59,tzinfo=timezone.utc)
    except ValueError:return None

def read_edges(e,prop):
    found=[];uncertain=False;now=datetime.now(timezone.utc)
    claims=e.get('claims',{}).get(prop,[])
    if not isinstance(claims,list):return {'status':'invalid_source','edges':[]}
    for claim in claims:
        if not isinstance(claim,dict):return {'status':'invalid_source','edges':[]}
        if claim.get('rank')=='deprecated':continue
        if claim.get('rank') not in ('normal','preferred'):uncertain=True;continue
        snak=claim.get('mainsnak',{});v=snak.get('datavalue',{}).get('value',{})
        if snak.get('snaktype')!='value' or not isinstance(v,dict) or not re.fullmatch(r'Q[1-9]\d*',v.get('id','')):
            uncertain=True;continue
        inactive=False;local_unknown=False
        qualifiers=claim.get('qualifiers',{})
        if not isinstance(qualifiers,dict):uncertain=True;continue
        for p,items in qualifiers.items():
            if p in BENIGN_QUALIFIERS:continue
            if prop=='P161' and p=='P453':
                if not items or any(not re.fullmatch(r'Q[1-9]\d*',s.get('datavalue',{}).get('value',{}).get('id','')) for s in items):local_unknown=True
                continue
            # A country attached to a birthplace statement describes that
            # historical assertion. It does not invalidate the place ID and
            # must never replace the separately queried current P17 edge.
            if prop=='P19' and p=='P17':
                if not items or any(not re.fullmatch(r'Q[1-9]\d*',s.get('datavalue',{}).get('value',{}).get('id','')) for s in items):local_unknown=True
                continue
            if p not in ('P580','P582') or prop not in CURRENT_PROPERTIES:local_unknown=True;continue
            for item in items:
                interval=date_interval(item)
                if interval is None:local_unknown=True;continue
                lower,upper=interval
                if (p=='P580' and lower>now) or (p=='P582' and upper<now):inactive=True
                elif lower<=now<=upper:local_unknown=True
        if inactive:continue
        if local_unknown:uncertain=True;continue
        sid=claim.get('id','');qid=e.get('id','')
        if not isinstance(sid,str) or '$' not in sid or sid.split('$',1)[0].upper()!=qid or snak.get('property')!=prop:uncertain=True;continue
        trace=e.get('_trace',{})
        found.append({'subject':qid,'property':prop,'object':v['id'],'statement_id':sid,'rank':claim['rank'],
                      'qualifiers':qualifiers,'references':claim.get('references',[]),'revision':e.get('lastrevid'),
                      'source_url':'https://www.wikidata.org/wiki/'+qid,
                      'accessed_at':trace.get('accessed_at'),'response_sha256':trace.get('response_sha256')})
    return {'status':'qualified_unresolved' if uncertain else 'ok','edges':found}

class WalkFailure(Exception):
    def __init__(self,status,detail=''):self.status=status;self.detail=detail

class Walker:
    def __init__(self,client):self.client=client;self.items={};self.edges=[];self.details=[]
    def load(self,ids,end):
        ids=list(dict.fromkeys(ids));missing=[i for i in ids if i not in self.items]
        if time.monotonic()>=end:raise WalkFailure('timeout')
        if len(self.items)+len(missing)>64:raise WalkFailure('incomplete','entity budget')
        if missing:
            data=self.client.entities(missing,end)
            for i in missing:
                e=data.get(i)
                if not isinstance(e,dict) or e.get('id')!=i:raise WalkFailure('invalid_source','entity identity mismatch')
                self.items[i]=e
        return [self.items[i] for i in ids]
    def one(self,qid,prop,end,identity=False):
        e=self.load([qid],end)[0];result=read_edges(e,prop)
        if result['status']!='ok':raise WalkFailure(result['status'],prop)
        ids={edge['object'] for edge in result['edges']}
        if not ids:raise WalkFailure('insufficient',prop)
        if len(ids)>1:raise WalkFailure('identity_unresolved' if identity else 'conflict',prop)
        self.edges.extend(result['edges']);return next(iter(ids))
    def has_type(self,qid,targets,end):
        if not targets:return True
        e=self.load([qid],end)[0];result=read_edges(e,'P31')
        if result['status']!='ok':return False
        frontier={edge['object'] for edge in result['edges']};visited=set()
        for _ in range(3):
            if frontier & set(targets):return True
            frontier-=visited
            if not frontier:return False
            if len(frontier)>20:raise WalkFailure('incomplete','type frontier')
            visited|=frontier;next_ids=set()
            for item in self.load(list(frontier),end):
                parents=read_edges(item,'P279')
                if parents['status']=='ok':next_ids.update(edge['object'] for edge in parents['edges'])
            frontier=next_ids
        return bool(frontier & set(targets))
    def typed_matches(self,ids,targets,end):
        if not targets:return list(ids)
        frontier={qid:{edge['object'] for edge in read_edges(self.items[qid],'P31')['edges']} for qid in ids}
        visited={qid:set() for qid in ids};matched=set()
        for _ in range(3):
            for qid,nodes in frontier.items():
                if nodes & set(targets):matched.add(qid)
            pending={qid:nodes-visited[qid] for qid,nodes in frontier.items() if qid not in matched}
            batch=set().union(*pending.values()) if pending else set()
            if not batch:break
            if len(batch)>20:raise WalkFailure('incomplete','type frontier')
            self.load(list(batch),end)
            next_frontier={}
            for qid,nodes in pending.items():
                visited[qid]|=nodes;parents=set()
                for node in nodes:
                    result=read_edges(self.items[node],'P279')
                    if result['status']=='ok':parents.update(edge['object'] for edge in result['edges'])
                next_frontier[qid]=parents
            frontier=next_frontier
        for qid,nodes in frontier.items():
            if nodes & set(targets):matched.add(qid)
        for qid in ids:
            if qid not in matched:self.details.append({'id':qid,'status':'type_not_supported'})
        return [qid for qid in ids if qid in matched]
    def active(self,e):
        for claim in e.get('claims',{}).get('P576',[]):
            if claim.get('rank')=='deprecated':continue
            interval=date_interval(claim.get('mainsnak',{}))
            if interval and interval[1]<datetime.now(timezone.utc):return False
        return True
    def province(self,qid,end):
        paths=[(qid,[],set())]
        for _ in range(7):
            if len(paths)>8:raise WalkFailure('incomplete','administrative branching')
            self.load([node for node,_,_ in paths],end)
            completed=[];next_paths=[]
            for node,edges,visited in paths:
                if node in visited:raise WalkFailure('insufficient','administrative cycle')
                e=self.items[node];matches=names(e)&set(REGIONS)
                if len(matches)==1 and self.active(e):completed.append((next(iter(matches)),edges));continue
                result=read_edges(e,'P131')
                if result['status']!='ok':raise WalkFailure(result['status'],'P131')
                if not result['edges']:raise WalkFailure('insufficient','no current province-level ancestor')
                for edge in result['edges']:next_paths.append((edge['object'],edges+[edge],visited|{node}))
            if completed:
                # An unfinished branch could lead to another region. Do not
                # take the first finished branch or silently discard others.
                if next_paths:raise WalkFailure('qualified_unresolved','mixed administrative depths')
                if len({x[0] for x in completed})!=1:raise WalkFailure('conflict','administrative regions')
                self.edges.extend(completed[0][1]);return completed[0][0]
            paths=next_paths
        raise WalkFailure('incomplete','administrative depth')
    def partial_answer(self,p,failure):
        # Only preserve a positively traversed, single-valued role. Merely
        # appearing in search results must never become an identified person.
        if failure.status!='insufficient':return None
        role={'work_birth_capital':'P50','founder_birth_province':'P112','film_actor_director_birth_region':'P57'}.get(p['kind'])
        people={e['object'] for e in self.edges if e['property']==role}
        if len(people)!=1:return None
        person=next(iter(people));name=label(self.items.get(person,{}))
        if not name:return None
        identity=(f'资料已识别《{p["anchor"]}》作者为{name}' if role=='P50' else
                  f'资料已识别{p["anchor"]}创始人为{name}' if role=='P112' else
                  f'资料中的《{p["anchor"]}》导演、演员交集为{name}')
        births=[e['object'] for e in self.edges if e['subject']==person and e['property']=='P19']
        if not births:return identity+'；但未找到可核实的出生地，不能用祖籍、籍贯或国籍替代，暂无法继续确定所问属性。'
        birth_name=label(self.items.get(births[0],{}))
        if not birth_name:return identity+'；出生地记录缺少可核实名称，暂无法继续确定所问属性。'
        if failure.detail in ('P131','no current province-level ancestor','administrative cycle','administrative depth'):
            return identity+f'，出生地记录为{birth_name}；但缺少其当前行政归属证据，暂无法确定省级行政区。'
        missing={'P17':'出生地所属国家','P36':'该国家首都'}.get(failure.detail,'后续关系')
        return identity+f'，出生地记录为{birth_name}；但缺少可核实的{missing}证据，暂无法确定最终答案。'
    def answer(self,q,end):
        p=plan(q)
        if not p:return {'status':'unsupported'}
        base={'plan':p,'scope':p['scope'],'provider':'wikidata','identity_limitation':'Positive typed matches among at most five exact-name candidates; not globally exhaustive.',
              'source_limitation':'Community-maintained structured evidence, not authoritative independent truth verification.'}
        try:
            search=self.client.search(p['anchor'],end);hits=search.get('search',[])
            ids=[]
            for h in hits[:5]:
                match=h.get('match') or {};texts=[h.get('label','')]
                if match.get('type') in ('label','alias'):texts.append(match.get('text',''))
                qid=h.get('id','')
                # Search display/match fields are candidate generation only.
                # Some exact aliases are absent from the chosen display hit.
                if re.fullmatch(r'Q[1-9]\d*',qid) and qid not in ids:ids.append(qid)
            if not ids:raise WalkFailure('identity_unresolved')
            self.load(ids,end);active=[]
            for qid in ids:
                e=self.items[qid]
                if norm(p['anchor']) not in {norm(x) for x in names(e)}:
                    self.details.append({'id':qid,'status':'exact_alias_not_found'});continue
                if not self.active(e):self.details.append({'id':qid,'status':'dissolved'});continue
                active.append(qid)
            role={'work_birth_capital':'P50','founder_birth_province':'P112','capital':'P36','film_actor_director_birth_region':'P57'}[p['kind']]
            if p['kind']=='film_actor_director_birth_region':
                # Role and type are independent positive requirements. Inspect
                # the required role first to avoid traversing an unrelated
                # martial-art/song namesake's unbounded taxonomy. Missing data
                # is unsupported, not proof the namesake cannot exist.
                eligible=[]
                for qid in active:
                    found=read_edges(self.items[qid],role)
                    if found['status']=='ok' and found['edges']:eligible.append(qid)
                    else:self.details.append({'id':qid,'status':'requested_role_not_supported','property':role})
                active=eligible
            typed=self.typed_matches(active,p['types'],end)
            positive=[]
            for qid in typed:
                roles=read_edges(self.items[qid],role)
                if roles['status']=='ok' and roles['edges']:positive.append(qid)
                else:self.details.append({'id':qid,'status':'requested_role_not_supported','property':role})
            typed=positive
            if len(typed)!=1:raise WalkFailure('identity_unresolved','multiple or no type-backed exact matches')
            root=typed[0];base.update(root=root,candidate_ids=ids,search_exhaustive=search.get('search-continue') is None)
            if p['kind']=='capital':
                capital=self.one(root,'P36',end);answer=label(self.load([capital],end)[0])
            elif p['kind']=='work_birth_capital':
                author=self.one(root,'P50',end,True);birth=self.one(author,'P19',end);country=self.one(birth,'P17',end);capital=self.one(country,'P36',end)
                author_name,country_name,capital_name=[label(e) for e in self.load([author,country,capital],end)]
                if not all((author_name,country_name,capital_name)):raise WalkFailure('insufficient','missing labels')
                answer=f'按《{p["anchor"]}》作者{author_name}的出生地现今所属国家查询：{country_name}的首都是{capital_name}。'
            elif p['kind']=='film_actor_director_birth_region':
                directors=read_edges(self.items[root],'P57');cast=read_edges(self.items[root],'P161')
                if directors['status']!='ok' or cast['status']!='ok':raise WalkFailure('qualified_unresolved','director/cast qualifiers')
                common={e['object'] for e in directors['edges']}&{e['object'] for e in cast['edges']}
                if len(common)!=1:raise WalkFailure('identity_unresolved','director/cast intersection not unique')
                person=next(iter(common))
                self.edges.extend([e for e in directors['edges'] if e['object']==person])
                self.edges.extend([e for e in cast['edges'] if e['object']==person])
                birth=self.one(person,'P19',end);region=self.province(birth,end)
                person_name=label(self.load([person],end)[0])
                if not person_name:raise WalkFailure('insufficient','missing person label')
                answer=f'按《{p["anchor"]}》演员表与导演记录共同匹配的{person_name}查询，其出生地现今所属省级行政区为{region}，简称“{REGIONS[region]}”。'
                base['administrative_name_source']=REGION_SOURCE
            else:
                founder=self.one(root,'P112',end,True);birth=self.one(founder,'P19',end);region=self.province(birth,end)
                founder_name=label(self.load([founder],end)[0])
                if not founder_name:raise WalkFailure('insufficient','missing founder label')
                answer=f'按{p["anchor"]}创始人{founder_name}出生地的现今行政归属查询：{region}。'
                base['administrative_name_source']=REGION_SOURCE
            if not answer:raise WalkFailure('insufficient','missing answer label')
            return dict(base,status='supported',answer=answer+' 来源：Wikidata（https://www.wikidata.org/wiki/'+root+'）。',edges=self.edges,disambiguation=self.details)
        except WalkFailure as e:
            out=dict(base,status=e.status,detail=e.detail,edges=self.edges,disambiguation=self.details)
            partial=self.partial_answer(p,e)
            if partial:out['partial_answer']=partial
            return out

def bounded_lookup(q,deadline,command=None):
    if command is None and plan(q) is None:return {'status':'unsupported'}
    timeout=min(20,deadline-time.monotonic())
    if timeout<.2:return {'status':'timeout'}
    command=command or [sys.executable,str(Path(__file__).resolve()),'--worker']
    try:
        proc=subprocess.run(command,input=json.dumps({'question':q,'budget':max(.1,timeout-.25)},ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',timeout=timeout,
                            env=os.environ.copy()|{'PYTHONIOENCODING':'utf-8','PYTHONUTF8':'1'})
        if proc.returncode:return {'status':'unavailable','error_type':'WorkerError'}
        result=json.loads(proc.stdout)
        if not isinstance(result,dict):raise ValueError('invalid worker payload')
        return result
    except subprocess.TimeoutExpired:return {'status':'timeout','deadline_enforced':True}
    except (ValueError,OSError):return {'status':'unavailable','error_type':'WorkerPayloadError'}

if __name__=='__main__':
    body=json.load(sys.stdin);end=time.monotonic()+min(20,max(.1,float(body['budget'])))
    with Client() as client:
        try:result=Walker(client).answer(body['question'],end)
        except APIError as e:result={'status':'unavailable','error_type':'APIError','http_status':e.status}
        except (OSError,ValueError,TypeError,KeyError) as e:result={'status':'unavailable','error_type':type(e).__name__}
        result['network_requests']=client.traces
        print(json.dumps(result,ensure_ascii=False))
