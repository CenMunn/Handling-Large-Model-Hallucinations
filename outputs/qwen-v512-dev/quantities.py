"""Bind explicit numerical measurements to SI values and check expression dimensions.

Not a general natural-language proof system: applicability and interpretation are
bounded, and a model still chooses the expression. No text is executed as code.
"""
import ast
import math
import re
import unicodedata
from itertools import product
from mathcheck import expression_tree

# mass, length, time, currency, electric current, counted items
ZERO=(0,0,0,0,0,0)
M=(1,0,0,0,0,0);L=(0,1,0,0,0,0);T=(0,0,1,0,0,0);C=(0,0,0,1,0,0);I=(0,0,0,0,1,0);N=(0,0,0,0,0,1)
UNITS={}


def register(names,scale,dimensions):
    if len(dimensions)==5:dimensions=(*dimensions,0)
    for name in names.split('|'):UNITS[name]=(scale,dimensions)


register('千克|公斤|kg',1,M);register('克|g',.001,M);register('吨',1000,M)
register('米|m',1,L);register('厘米|cm',.01,L);register('毫米|mm',.001,L);register('千米|公里|km',1000,L)
register('秒|s',1,T);register('分钟|min',60,T);register('小时|h',3600,T)
register('元',1,C);register('万元',10000,C)
register('平方米|m²|m2',1,(0,2,0,0,0));register('平方厘米|cm²|cm2',.0001,(0,2,0,0,0))
register('立方米|m³|m3',1,(0,3,0,0,0));register('升|L|l',.001,(0,3,0,0,0));register('毫升|mL|ml',.000001,(0,3,0,0,0))
register('安培|安|A',1,I);register('伏特|伏|V',1,(1,2,-3,0,-1));register('瓦特|瓦|W',1,(1,2,-3,0,0));register('千瓦|kW',1000,(1,2,-3,0,0))
register('倍',1,ZERO);register('箱|件|个|瓶|包|袋|盏|台|人',1,N);register('%|％',.01,ZERO)

for numerator,denominator in [('公里','小时'),('千米','小时'),('米','秒'),('千克','升'),('克','毫升'),('千克','立方米'),('元','千克'),('元','件'),('元','箱')]:
    a,b=UNITS[numerator],UNITS[denominator]
    UNITS[numerator+'/'+denominator]=(a[0]/b[0],tuple(x-y for x,y in zip(a[1],b[1])))
for name,base in [('km/h','公里/小时'),('m/s','米/秒'),('kg/L','千克/升'),('g/mL','克/毫升'),('kg/m3','千克/立方米')]:UNITS[name]=UNITS[base]

UNIT_PATTERN='|'.join(re.escape(u) for u in sorted(UNITS,key=len,reverse=True))
NUMBER=re.compile(r'(?<![A-Za-z0-9_.])([-+]?\d+(?:\.\d+)?)\s*('+UNIT_PATTERN+r')?')
CHINESE=re.compile(r'([零〇一二两三四五六七八九十百千万]+)\s*('+UNIT_PATTERN+r')')
TASK=re.compile(r'原来|原先|原有|倍|%|％|涨价|降价|每|行驶|密度|电压|电流|矩形|水箱|长\d|宽\d')
TARGET=re.compile(r'(?:多少|几|计算)[^，。？?]{0,18}?('+UNIT_PATTERN+r')(?=[？?。\s]|$)')


def chinese_number(text):
    digits={'零':0,'〇':0,'一':1,'二':2,'两':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    if all(c in digits for c in text):return float(''.join(str(digits[c]) for c in text))
    number=section=total=0
    for char in text:
        if char in digits:number=digits[char]
        elif char=='万':total+=(section+number)*10000;section=number=0
        else:section+=(number or 1)*{'十':10,'百':100,'千':1000}[char];number=0
    return float(total+section+number)


def prepare(question):
    q=unicodedata.normalize('NFKC',question).replace('／','/')
    if not (re.search(r'\d',q) or CHINESE.search(q)) or not TASK.search(q):return None
    targets=list(TARGET.finditer(q))
    if not targets:return None
    target=targets[-1].group(1)
    scale,target_dimension=UNITS[target]
    # Calendar/common-knowledge questions retain the original nonmeasurement path.
    if target_dimension==T and not re.search(r'行驶|速度|路程|工作|流量',q):return None
    if target_dimension in (ZERO,N):return None
    quantities=[]
    before=q[:targets[-1].start()]
    arabic=list(NUMBER.finditer(before))
    matches=[(match.start(),float(match.group(1)),match.group(2) or '',match.group(0)) for match in arabic]
    matches += [(match.start(),chinese_number(match.group(1)),match.group(2),match.group(0)) for match in CHINESE.finditer(before)
                if match.group(0) not in UNITS and not any(match.start()<other.end() and match.end()>other.start() for other in arabic)]
    for position,value,unit,literal in sorted(matches):
        factor,dimension=UNITS.get(unit,(1,ZERO))
        prefix=q[max(0,position-12):position]
        delta=bool(re.search(r'涨价|降价|增加|减少|多花|少花|上涨|下调|上调|比[^，。]{0,8}(?:多|少|贵|便宜)',prefix))
        quantities.append({'id':f'q{len(quantities)}','literal':literal,'value':value,'unit':unit,
                           'si_value':value*factor,'dimensions':dimension,'base_dimensions':dimension,'delta':delta,'position':position})
    # For explicit per-item measurements, retain the counted-item dimension.
    # A per-item original and per-item increment must be combined before their
    # multiplication by item count can produce an absolute total.
    per_item=bool(re.search(r'每(?:箱|件|个|瓶|包|袋|盏|台|人)',q))
    has_count=any(item['dimensions']==N for item in quantities)
    if per_item and has_count:
        for item in quantities:
            if item['base_dimensions']==target_dimension:
                local=q[max(0,item['position']-12):item['position']]
                if not re.search(r'总[价重质额]|合计',local):
                    item['dimensions']=tuple(x-y for x,y in zip(item['dimensions'],N))
                    item['per_item']=True
    result={'status':'ready','quantities':quantities,'target_unit':target,'target_scale':scale,'target_dimensions':target_dimension}
    vectors={ZERO}
    for item in quantities:
        if item['dimensions']!=ZERO:vectors.add(item['dimensions'])
    # Bounded combinations prove simple dimension availability, not formula meaning.
    reachable=set(vectors)
    for a,b in product(vectors,repeat=2):
        reachable.add(tuple(x+y for x,y in zip(a,b)))
        reachable.add(tuple(x-y for x,y in zip(a,b)))
    for a in vectors:reachable.add(tuple(x*2 for x in a));reachable.add(tuple(x*3 for x in a))
    tail=q[max(q.rfind('，'),q.rfind('。'))+1:]
    asks_delta=bool(re.search(r'多花|少花|相差|差额|增量|增加多少|减少多少|变化多少',tail))
    relevant=[x for x in quantities if x['base_dimensions']==target_dimension]
    if target_dimension not in reachable:
        result.update(status='missing',reason='题目没有提供可构成所问单位的原始测量值。')
    elif relevant and all(x['delta'] for x in relevant) and not asks_delta:
        result.update(status='missing',reason='只给出了变化量，未给出计算绝对总量所需的原值。')
    return result


def compute(expression,prepared):
    if prepared['status']!='ready':raise ValueError('missing quantitative premise')
    bindings={q['id']:q for q in prepared['quantities']}

    def walk(node):
        if isinstance(node,ast.Name) and node.id in bindings:
            q=bindings[node.id];return q['si_value'],tuple(q['dimensions'])
        if isinstance(node,ast.Constant) and type(node.value) in (int,float) and node.value in (0,1):return float(node.value),ZERO
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value,dimension=walk(node.operand);return value*(-1 if isinstance(node.op,ast.USub) else 1),dimension
        if isinstance(node,ast.BinOp):
            a,da=walk(node.left);b,db=walk(node.right)
            if isinstance(node.op,(ast.Add,ast.Sub)):
                if da!=db:raise ValueError('incompatible dimensions for addition')
                value=a+b if isinstance(node.op,ast.Add) else a-b;dimension=da
            elif isinstance(node.op,ast.Mult):value=a*b;dimension=tuple(x+y for x,y in zip(da,db))
            elif isinstance(node.op,ast.Div):
                if b==0:raise ValueError('division by zero')
                value=a/b;dimension=tuple(x-y for x,y in zip(da,db))
            elif isinstance(node.op,ast.Pow) and db==ZERO and b in (-2,-1,0,1,2,3):
                value=a**b;dimension=tuple(x*b for x in da)
            else:raise ValueError('unsupported grounded operation')
            if not math.isfinite(value) or abs(value)>1e15:raise ValueError('grounded numeric range exceeded')
            return value,dimension
        raise ValueError('expression contains ungrounded constants or unsafe syntax')

    value,dimension=walk(expression_tree(expression))
    if dimension!=tuple(prepared['target_dimensions']):raise ValueError('result dimensions do not match requested unit')
    value/=prepared['target_scale']
    if not math.isfinite(value):raise ValueError('invalid result')
    return {'value':value,'answer':f'{value:.9g}{prepared["target_unit"]}','expression':expression,
            'independent_computation':True,'dimensions_checked':True,'interpretation_verified':False,
            'bindings':prepared['quantities'],'target_unit':prepared['target_unit']}
