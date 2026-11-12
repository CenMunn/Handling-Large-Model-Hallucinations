"""Bounded arithmetic and validated degree <=2 survival distributions. Never eval()."""
import ast,math,re,unicodedata

def expression_tree(expr):
 if len(expr)>500:raise ValueError('expression too long')
 try:tree=ast.parse(expr,mode='eval')
 except (SyntaxError,RecursionError) as e:raise ValueError('invalid expression') from e
 if len(list(ast.walk(tree)))>100:raise ValueError('expression too complex')
 return tree.body

def arithmetic(expr):
 def walk(n):
  if isinstance(n,ast.Constant) and type(n.value) in [int,float]:v=float(n.value)
  elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):v=walk(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
  elif isinstance(n,ast.BinOp):
   a,b=walk(n.left),walk(n.right)
   if isinstance(n.op,ast.Add):v=a+b
   elif isinstance(n.op,ast.Sub):v=a-b
   elif isinstance(n.op,ast.Mult):v=a*b
   elif isinstance(n.op,ast.Div):
    if b==0:raise ValueError('division by zero')
    v=a/b
   elif isinstance(n.op,ast.Pow) and abs(b)<=10 and abs(a)<=1e6:v=a**b
   else:raise ValueError('unsupported operation')
  elif isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='sqrt' and len(n.args)==1 and not n.keywords:
   a=walk(n.args[0])
   if a<0:raise ValueError('negative square root')
   v=math.sqrt(a)
  else:raise ValueError('unsafe expression')
  if not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e15:raise ValueError('numeric range exceeded')
  return v
 return walk(expression_tree(expr))

def polynomial(expr):
 def add(a,b,sign=1):
  out=[0.0]*max(len(a),len(b))
  for i,x in enumerate(a):out[i]+=x
  for i,x in enumerate(b):out[i]+=sign*x
  return trim(out)
 def trim(v):
  while len(v)>1 and abs(v[-1])<1e-14:v.pop()
  if len(v)>3:raise ValueError('only degree <=2 is supported')
  return v
 def mul(a,b):
  out=[0.0]*(len(a)+len(b)-1)
  for i,x in enumerate(a):
   for j,y in enumerate(b):out[i+j]+=x*y
  return trim(out)
 def walk(n):
  if isinstance(n,ast.Constant) and type(n.value) in [int,float]:return [float(n.value)]
  if isinstance(n,ast.Name) and n.id=='x':return [0,1]
  if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):return [x*(-1 if isinstance(n.op,ast.USub) else 1) for x in walk(n.operand)]
  if isinstance(n,ast.BinOp):
   a=walk(n.left)
   if isinstance(n.op,ast.Pow):
    if not isinstance(n.right,ast.Constant) or n.right.value not in [0,1,2]:raise ValueError('invalid polynomial power')
    return [1] if n.right.value==0 else a if n.right.value==1 else mul(a,a)
   b=walk(n.right)
   if isinstance(n.op,ast.Add):return add(a,b)
   if isinstance(n.op,ast.Sub):return add(a,b,-1)
   if isinstance(n.op,ast.Mult):return mul(a,b)
   if isinstance(n.op,ast.Div) and len(b)==1 and b[0]!=0:return [x/b[0] for x in a]
  raise ValueError('unsupported polynomial')
 return walk(expression_tree(expr))

def normalize(text):
 text=unicodedata.normalize('NFKC',text).replace('−','-').replace('≤','<=').replace('^','**')
 for token in ['\\leqslant','\\leq','\\le']:text=text.replace(token,'<=')
 text=text.replace('\\times','*').replace('×','*').replace('\\cdot','*').replace('$','')
 text=re.sub(r'(?<=\d)\s*(?=x\b)','*',text)
 return re.sub(r'\s+','',text)

def solve_survival(question):
 if not ('生存函数' in question and '中值' in question and any(s in question for s in ['未来','末来','剩余'])):return None
 q=normalize(question)
 eq=re.search(r'S\(x\)=([^，,。;；]+)',q)
 bounds=re.search(r'([0-9.]+)<=x<=([0-9.]+)',q)
 if not eq or not bounds:raise ValueError('cannot parse survival formula or support')
 coeff=polynomial(eq.group(1));a,b=map(float,bounds.groups())
 if not 0<=a<b<=1e6:raise ValueError('invalid support')
 def s(x):return sum(c*x**i for i,c in enumerate(coeff))
 def ds(x):return sum(i*c*x**(i-1) for i,c in enumerate(coeff) if i)
 if abs(s(a)-1)>1e-6 or abs(s(b))>1e-6 or max(ds(a),ds(b))>1e-10:raise ValueError('not a normalized decreasing survival function on support')
 lo,hi=a,b
 for _ in range(70):
  mid=(lo+hi)/2
  if s(mid)>.5:lo=mid
  else:hi=mid
 median=(lo+hi)/2
 integral=sum(c*(b**(i+1)-median**(i+1))/(i+1) for i,c in enumerate(coeff))
 value=integral/s(median)
 if not 0<=value<=b-median+1e-8:raise ValueError('residual lifetime sanity check failed')
 answer=f'约{value:.6g}'
 choices=[(letter,float(v)) for letter,v in re.findall(r'(?:^|[\n\s])([A-Z])[.．、]\s*([0-9]+(?:\.[0-9]+)?)',question)]
 if choices:
  letter,v=min(choices,key=lambda item:abs(item[1]-value))
  if abs(v-value)>max(.001,abs(value)*.001):raise ValueError('no option agrees with computed value')
  matches=[label for label,option_value in choices if option_value==v]
  if len(matches)>1 and not re.search(r'单选|单项选择',question):answer=','.join(matches)
  else:answer=letter
 return {'answer':answer,'value':value,'median':median,'coefficients':coeff,'support':[a,b],
         'method':'analytic polynomial integration and monotone bisection','formula':'integral_m^b S(t)dt / S(m)','independent_computation':True}
