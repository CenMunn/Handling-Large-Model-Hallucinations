"""Separate proposition truth from the set the question asks to select."""
import re
from option_checks import assemble

def evaluation_mode(question):
 stem=re.split(r'(?m)^\s*[A-H][.．、)）]',question)[0]
 if re.search(r'不是错误|并非不正确|不能说.*不正确|不属于.*错误|不正确.*正确',stem):return 'criterion'
 if re.search(r'(?:选出|选择|请选择|选)(?:所有|全部)?(?:错误|不正确|不成立)的(?:等式|算式|说法|叙述)',stem):return 'false_statements'
 if re.search(r'(?:选出|选择|请选择|选)(?:所有|全部)?(?:正确|成立)的(?:等式|算式|说法|叙述)',stem):return 'true_statements'
 if re.search(r'错误(?:的|项|说法|叙述|等式)?(?:是|有|为)|不正确|不成立|(?:等式|算式|说法|叙述).{0,8}错误',stem):return 'false_statements'
 if re.search(r'正确(?:的|项|说法|叙述|等式)?(?:是|有|为)|等式.*成立|算式.*成立',stem):return 'true_statements'
 return 'criterion'

def select_records(options,records,mode,single):
 if mode not in ('false_statements','true_statements','criterion'):raise ValueError('unknown selection mode')
 field='matches_requirement' if mode=='criterion' else 'statement_true'
 if not isinstance(records,list):raise ValueError('missing option records')
 selected=[]
 for record in records:
  if not isinstance(record,dict) or type(record.get(field)) is not bool:raise ValueError('missing or unresolved explicit option judgment')
  truth=record[field]
  chosen=not truth if mode=='false_statements' else truth
  record['selected']=chosen
  selected.append({'label':record.get('label'),'verdict':chosen})
 return assemble(options,selected,single)
