"""Bounded count grammar: independently bind baseline, change and final target.

Returns None outside the complete accepted grammar. No partial matching of long
materials, extra rules, another entity or a request for the original quantity.
"""
import re,unicodedata
from calendar_rules import _number

NUM=r'(?:\d{1,4}|[一二两三四五六七八九]?十[一二三四五六七八九]?|[零一二两三四五六七八九])'
ENTITY=r'[\u4e00-\u9fff]{2,12}'
ORDINARY={'三角形':3,'四边形':4,'五边形':5,'六边形':6,'七边形':7,'八边形':8}


def solve(question):
    q=unicodedata.normalize('NFKC',question).strip()
    q=re.sub(r'^【设问知识】[^\n]*\n\s*-{3,}\s*\n','',q)
    if len(q)>200:return None
    explicit=re.fullmatch(r'(?P<entity>'+ENTITY+r')原有(?P<base>'+NUM+r')个角[，,。]\s*'
                          r'(?P<op>增加|减少)(?P<delta>'+NUM+r')个角后[，,]\s*'
                          r'(?:那么|则)?(?:共|总共)?有(?:多少个角|几个角)[?？。]?',q)
    ordinary=re.fullmatch(r'(?:如果|假如)(?:几何规则规定)?(?P<entity>'+ENTITY+r')'
                          r'(?P<op>增加|减少)(?P<delta>'+NUM+r')个角[，,]\s*'
                          r'(?:那么|则)(?P<target>'+ENTITY+r')有(?:多少个角|几个角)[?？。]?',q)
    match=explicit or ordinary
    if not match:return None
    data=match.groupdict()
    if explicit:base=_number(data['base']);source='explicit_count'
    else:
        if data['entity']!=data['target'] or data['entity'] not in ORDINARY:return None
        base=ORDINARY[data['entity']];source='ordinary_polygon_vertex_count'
    delta=_number(data['delta'])*(1 if data['op']=='增加' else -1)
    value=base+delta
    if not(0<=base<=10000 and 0<=value<=10000):return None
    return {'answer':str(value)+'个角','value':value,'base':base,'delta':delta,'entity':data['entity'],
            'baseline_source':source,'independent_computation':True,'interpretation_verified':True,
            'method':'complete count-change grammar; baseline plus signed change'}
