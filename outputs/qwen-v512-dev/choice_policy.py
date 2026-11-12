"""Format guidance for actual choices; it cannot verify their correctness."""
import math,re

def classify_choices(question):
    labels=re.findall(r'(?m)^\s*([A-H])[.．、)）]\s*\S',question)
    if len(set(labels))<2 and re.search(r'选择题|选项',question):
        labels=re.findall(r'(?:^|[\s:：])([A-H])[.．、)）]\s*\S',question)
    labels=list(dict.fromkeys(labels))
    return labels if len(labels)>=2 else []

def choice_instruction(question):
    labels=classify_choices(question)
    if not labels:return ''
    if re.search(r'不定项|多项选择|多选',question):
        return '这是不定项或多选题，逐一判断所有给定选项；正确项可能有一个或多个，输出所有正确项字母，不要自行增加选项。'
    if re.search(r'单项选择|单选',question):
        return '这是单选题，逐一判断给定选项，选出仅一个最合适的选项字母。'
    return '逐一判断所有给定选项；按题目要求输出全部正确选项字母，不要自行增加选项。'

def clean_open_answer(question,answer):
    if classify_choices(question) or re.search(r'(?:以|用|写出|输出)\s*[A-H][.．、]',question,re.I):return answer
    # Preserve bare letters (e.g. the chemical symbol C) and restrict removal
    # to an unambiguous extra option prefix followed by substantive text.
    return re.sub(r'^\s*[A-H][.．、]\s*(?=[\u4e00-\u9fff《\d])','',answer,count=1)

def numeric_option_answer(question,value):
    labels=classify_choices(question)
    if not labels or not isinstance(value,(int,float)) or not math.isfinite(value):return None
    options=re.findall(r'(?m)^\s*([A-H])[.．、)）]\s*([-+]?(?:\d+(?:\.\d+)?|\.\d+))\s*$',question)
    if len(options)!=len(labels) or {name for name,_ in options}!=set(labels):return None
    matches=[name for name,number in options if math.isclose(float(number),value,rel_tol=1e-10,abs_tol=1e-10)]
    if not matches:return None
    if len(matches)>1 and re.search(r'单选|单项选择',question):return None
    return ','.join(matches)
