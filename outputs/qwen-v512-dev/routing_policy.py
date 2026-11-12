"""Questions requiring externally dated or claim-specific evidence."""
import re

def empirical_quantity(q):
 # Empirical counts need measurements or sources, even when no entity-name
 # keyword from the older factual router occurs. Supplied-material handling
 # and explicit numerical tools run before this policy in Engine.
 return bool(re.search(r'通常|一般|平均|典型|正常|统计',q) and
             re.search(r'多少|数量|范围|密度|比例|含量|体积|质量|寿命|发生率|饮水量',q))
def evidence_request(q):
 if re.search(r'【世界设定】|【对话记录】|(?:仅|只)(?:能)?(?:根据|依据)|(?:根据|依据)(?:所给|给定|下列|提供的).*?(?:材料|资料|记录|信息)',q):return None
 if re.search(r'最新|现任|截至目前|截至现在|当前|目前|完整(?:编号|名称)|正式文件名',q):return 'time_sensitive'
 if re.search(r'它对吗|对不对|是否正确|是否属实|是真的吗|说法.*对吗|说法.*正确|这对吗',q):
  if re.search(r'算式|等式|计算结果|数学推导',q):return None
  return 'claim_verification'
 return None
