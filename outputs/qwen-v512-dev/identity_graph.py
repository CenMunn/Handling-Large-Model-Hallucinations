"""Extract narrowly stated identity/attribute edges; never invent an identity.

This parser is intentionally incomplete.  It verifies literal relation wording,
not whether a source is trustworthy or whether a person with that name is unique.
"""
import re

_NAME = r'(?:(?!的)[\u4e00-\u9fff·]){2,4}'
_WORK = r'《[^《》\n]{1,30}》'
_ORG = r'[\u4e00-\u9fffA-Za-z0-9]{2,30}?(?:研究院|大学|学院|研究所|实验室|公司|中心|博物馆|图书馆|实验站|测站|资料馆|档案馆)'
_OCCUPATION = r'(?:演员|作家|画家|诗人|导演|科学家|工程师|学者|教授|音乐家|发明家|研究员|医生|馆员)'
_WORK_ROLE = r'(?:作者|导演|作家|表演者|编剧|创作者|创作人|主演|表演人|摄影师)'
_WORK_PREFIX = r'[\u4e00-\u9fff]{0,8}'
_SUBJECT = (r'(?:' + _OCCUPATION + _NAME + r'|创作' + _WORK + r'的' + _NAME
            + r'|任职于' + _ORG + r'的' + _NAME
            + r'|' + _WORK_PREFIX + _WORK + r'的' + _WORK_ROLE + _NAME
            + r'|研究[\u4e00-\u9fff]{2,10}的' + _NAME
            + r'|在' + _ORG + r'(?:工作|任职)的' + _OCCUPATION + _NAME + r')')
_QUERY = re.compile(r'^\s*(?:依据检索资料[，,]\s*)?(' + _SUBJECT
                    + r')(?:(?:的)?(出生地|籍贯|祖籍)(?:是|为|在)?(?:什么|哪里|哪(?:座|个)(?:城市|地方|县))'
                    + r'|(出生(?:于|在))(?:哪里|哪(?:座|个)(?:城市|地方)))\s*[？?。]?\s*$')
_BAD = re.compile(r'不是|并非|从未|未曾|没有|不曾|否认|否定|不实|错误|虚假|假的|传闻|据说|可能|疑似|也许|尚未|未经证实|不确定|何时|如果|假如|指令|忽略')
_LOCATION = r'[\u4e00-\u9fff·]{1,18}(?:省|市|县|区|国|州|镇|乡|村|城)'
_LOCATION_BAD = re.compile(r'出生|祖籍|籍贯|亲属|父亲|母亲|哥哥|姐姐|弟弟|妹妹|儿子|女儿|其|他|她|的')
_PRONOUN_CLAIM = re.compile(r'(?:他|她|其)(?:的)?(?:出生|祖籍|籍贯)')
_CLAUSE = re.compile(r'[^。！？；，,;!?\n]+')
_ORG_QUERY = re.compile(r'^\s*(?:依据检索资料[，,]\s*)?(' + _ORG + r')的前身(?:叫(?:什么|啥)|是(?:什么|哪(?:个|家))(?:机构|组织)?)\s*[？?。]?\s*$')
_ORG_VALUE = r'(?:(?!前身|下属|所属|其|的)[\u4e00-\u9fffA-Za-z0-9]){2,30}(?:研究院|大学|学院|研究所|实验室|公司|中心|博物馆|图书馆|实验站|测站|资料馆|档案馆)'


def bind_identity(question, sources):
    """Return unsupported, unresolved, conflict, or supported with literal quote.

    Sources are dicts with ``text`` and ``url``; no network calls are made.  A
    recognized qualifier and value must occur in one simple source clause.  A
    caller must assess source quality and must not treat a supported edge as a
    guarantee of factual truth or unique identity.
    """
    if not isinstance(question, str) or not isinstance(sources, (list, tuple)):
        return {'status': 'unsupported', 'reason': 'invalid input'}
    parsed = _QUERY.fullmatch(question)
    organization = _ORG_QUERY.fullmatch(question)
    if not parsed and not organization:
        return {'status': 'unsupported', 'reason': 'question identity or attribute is not explicitly supported'}
    if organization:
        subject=organization.group(1)
        if re.search(r'下属|所属|附属|旗下|前身|的',subject):
            return {'status':'unsupported','reason':'organization identity includes an ambiguous relationship'}
        person=subject
        attribute='predecessor'
        candidate=re.compile(r'^\s*' + re.escape(subject) + r'的前身(?:是|为)(' + _ORG_VALUE + r')\s*$')
    else:
        subject, query_attribute, birth_verb = parsed.groups()
        occupation_match = re.fullmatch(_OCCUPATION + r'(' + _NAME + r')', subject)
        if occupation_match:
            person = occupation_match.group(1)
        elif '的' in subject:
            identity_match = re.fullmatch(_WORK_PREFIX + _WORK + r'的' + _WORK_ROLE + r'(' + _NAME + r')', subject)
            affiliation_match = re.fullmatch(r'在' + _ORG + r'(?:工作|任职)的' + _OCCUPATION + r'(' + _NAME + r')', subject)
            if identity_match:
                person = identity_match.group(1)
            elif affiliation_match:
                person = affiliation_match.group(1)
            else:
                person = subject.rsplit('的', 1)[1]
        else:
            return {'status': 'unsupported', 'reason': 'could not extract the explicitly named person'}
        attribute = 'birthplace' if query_attribute == '出生地' or birth_verb else 'ancestry'
        if attribute == 'birthplace':
            relation = r'(?:出生于|出生在|的出生地(?:是|为))'
        else:
            # 祖籍 and 籍贯 are separate relations; no inference of equivalence.
            relation = r'(?:的)?' + re.escape(query_attribute) + r'(?:是|为|在)'
        candidate = re.compile(r'^\s*' + re.escape(subject) + relation + r'(' + _LOCATION + r')\s*$')
    edges = []
    uncertain = False
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('text'), str):
            uncertain = True
            continue
        # Do not let a positive fragment mask a nearby negation or disclaimer;
        # cross-sentence reference resolution would itself need verification.
        if person in source['text'] and (_BAD.search(source['text']) or _PRONOUN_CLAIM.search(source['text'])):
            uncertain = True
            continue
        source_edges = []
        for match in _CLAUSE.finditer(source['text']):
            quote = match.group(0).strip()
            if _BAD.search(quote):
                continue
            edge = candidate.fullmatch(quote)
            if not edge or (attribute != 'predecessor' and _LOCATION_BAD.search(edge.group(1))) or edge.group(1)==subject:
                continue
            source_edges.append({'entity_qualifier': subject, 'attribute': attribute,
                                 'value': edge.group(1), 'quote': quote,
                                 'source_url': source.get('url', '')})
        # Each literal mention must belong to a parsed edge. A separate
        # unqualified mention could describe a conflicting same-name person.
        # False positives from names embedded in longer words are deliberate.
        if source['text'].count(person) != len(source_edges):
            uncertain = True
        edges.extend(source_edges)
    if uncertain:
        return {'status': 'unresolved', 'reason': 'qualified identity appears in a source containing negation or uncertainty'}
    if not edges:
        return {'status': 'unresolved', 'reason': 'no explicit same-clause qualified identity and attribute'}
    values = {edge['value'] for edge in edges}
    if len(values) != 1:
        return {'status': 'conflict', 'reason': 'same qualified identity and attribute have distinct literal values',
                'evidence': edges}
    return {'status': 'supported', 'value': next(iter(values)), 'attribute': attribute,
            'identity': subject, 'evidence': edges}
