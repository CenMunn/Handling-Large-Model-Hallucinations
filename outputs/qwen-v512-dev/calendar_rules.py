"""Narrow, deterministic handling of explicitly defined February baselines.

Returns None when no explicit baseline is found; otherwise a dictionary with
status 'solved' or 'unresolved'.  It deliberately declines unsupported syntax.
"""
import re

_NUMBER = r'(?:\d{1,3}|[零一二两三四五六七八九十]{1,3})'
_FEB = r'(?:2|二)月'
_YEAR = r'(?:闰年|特殊年份|特别年份)'
_BASE = re.compile(r'平年\s*(?:的\s*)?' + _FEB + r'\s*(?:有|是|为|改为|改成|变为|变成|调整为|规定为)\s*(' + _NUMBER + r')\s*天')
_REL = re.compile(r'(' + _YEAR + r')\s*(?:的\s*)?' + _FEB + r'\s*比\s*平年(?:\s*(?:的\s*)?' + _FEB + r')?\s*(多|少|增加|减少)\s*(' + _NUMBER + r')\s*天')
_ANY_CHANGE = re.compile(r'(?:多|少|增加|减少)\s*' + _NUMBER + r'\s*天')
_DIGITS = {'零': 0, '一': 1, '二': 2, '两': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def _number(text):
    if text.isascii() and text.isdigit():
        return int(text)
    if text in _DIGITS:
        return _DIGITS[text]
    if text == '十':
        return 10
    if text.count('十') == 1:
        left, right = text.split('十')
        if (not left or left in _DIGITS) and (not right or right in _DIGITS):
            return (10 if not left else _DIGITS[left] * 10) + (0 if not right else _DIGITS[right])
    raise ValueError('unsupported number')


def solve_explicit_calendar(question):
    bases = list(_BASE.finditer(question))
    if not bases:
        return None
    unresolved = {'status': 'unresolved', 'reason': '明确基准存在，但日历关系或所问对象无法唯一解析。'}
    relations = list(_REL.finditer(question))
    if (len(bases) != 1 or len(relations) != 1 or len(_ANY_CHANGE.findall(question)) != 1
            or re.search(r'不是|并非|不为|并不|未定|未知|或者|或|可能|不一定', question)):
        return unresolved
    base, rel = bases[0], relations[0]
    if base.start() > rel.start():
        return unresolved
    # The final question must ask for the same year and month, not the base.
    final = re.split(r'[。！？!?；;]', question.rstrip('。！？!?；;'))[-1]
    if not re.fullmatch(r'\s*(?:那么|则|因此|请问|问|现在)?\s*' + re.escape(rel.group(1))
                        + r'\s*(?:的\s*)?' + _FEB + r'\s*(?:有|是|为)?\s*(?:多少天|几天)\s*(?:呢)?\s*', final):
        return unresolved
    try:
        baseline = _number(base.group(1))
        change = _number(rel.group(3))
    except ValueError:
        return unresolved
    delta = change if rel.group(2) in ('多', '增加') else -change
    value = baseline + delta
    if not (1 <= baseline <= 100 and 0 <= change <= 100 and 1 <= value <= 100):
        return unresolved
    return {'status': 'solved', 'answer': str(value) + '天', 'value': value,
            'base': baseline, 'delta': delta, 'interpretation_verified': True,
            'source': 'explicit_calendar_rule'}
