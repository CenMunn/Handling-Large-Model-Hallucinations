"""Conservative text-level evidence binding. This is not semantic verification.

Public interface: verify_binding(question, claim, source, entity_aliases=(),
verified_entity_aliases=(), attribute=''). `entity_aliases` must literally occur
in the question; `verified_entity_aliases` are only for identifiers/aliases
already confirmed by an external, independently auditable identity chain.
Never pass an LLM-generated guess as verified. Attribute must be supplied by a
trusted rule/caller; the caller remains responsible for question interpretation.
"""
import re
import unicodedata


RELATIONS={
    'birthplace': re.compile(r'出生(?:于|在|地)|诞生(?:于|在)|\bborn\s+(?:in|at)\b',re.I),
    'official_language': re.compile(r'官方语言|法定语言|\bofficial\s+languages?\b',re.I),
    'capital': re.compile(r'首都|\bcapital\s+of\b',re.I),
    'foundation_year': re.compile(r'成立(?:于|在)?|创立(?:于|在)?|建立(?:于|在)?|\bfounded\b|\bestablished\b',re.I),
}
SENTENCES=re.compile(r'[^。！？；，,\n.!?]+[。！？；，,\n.!?]*')
INJECTION=re.compile(r'忽略(?:此前|以上|题目|问题|指令)|只(?:回答|输出)|ignore\s+(?:the\s+)?(?:question|instructions)',re.I)
NEGATIVE=re.compile(r'不是|并非|非其|未曾|从未|不是.*?而是|\bnot\b|\bnever\b',re.I)
PREDECESSOR=re.compile(r'前身|前称|前稱|前任组织|predecessor|former(?:ly)?',re.I)
ANCESTRY=re.compile(r'籍贯|籍貫|祖籍|原籍|native\s+of|ancestr',re.I)
OTHER_PERSON=re.compile(r'其弟|其兄|其父|其母|姐姐|妹妹|兄弟|弟弟|哥哥|父亲|母亲|妻子|丈夫|儿子|女儿|\bhis\s+(?:wife|brother|father|mother)\b|\bher\s+(?:husband|sister|father|mother)\b',re.I)


def normalized(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC',value)).casefold()


def result(status, reason, **details):
    return {'status':status,'reason':reason,'method':'literal entity-relation-value proximity; lexical signal only',**details}


def verify_binding(question, claim, source, *, entity_aliases=(), verified_entity_aliases=(), attribute=''):
    if not all(isinstance(v,str) for v in (question,attribute)) or not isinstance(claim,dict) or not isinstance(source,dict):
        return result('rejected','invalid input type')
    quote,value,answer=claim.get('quote'),claim.get('source_value'),claim.get('answer')
    text=source.get('text')
    if not all(isinstance(v,str) and v.strip() for v in (quote,value,answer,text)):
        return result('rejected','missing source, quote, value or answer')
    if quote not in text or value not in quote:
        return result('rejected','quote or value not literal in source')
    if len(quote)>700:
        return result('rejected','quote exceeds size limit')
    # A claimed translation is not independently checked by this module.
    if normalized(answer) != normalized(value):
        return result('needs_verification','answer-value identity or translation unverified')
    if attribute not in RELATIONS:
        return result('needs_verification','unsupported attribute')
    aliases=[]
    for alias in entity_aliases:
        if isinstance(alias,str) and alias.strip() and normalized(alias) in normalized(question):aliases.append(alias)
    for alias in verified_entity_aliases:
        if isinstance(alias,str) and alias.strip():aliases.append(alias)
    if not aliases:
        return result('needs_verification','no entity literal in question or independently verified alias')
    if INJECTION.search(quote):
        return result('needs_verification','instruction-like text in evidence')
    segments=[m.group(0) for m in SENTENCES.finditer(quote)]
    same=[s for s in segments if normalized(value) in normalized(s) and any(normalized(a) in normalized(s) for a in aliases)]
    if not same:
        return result('rejected','entity and value are not in the same evidence sentence')
    for sentence in same:
        marker=RELATIONS[attribute].search(sentence)
        if not marker:continue
        if NEGATIVE.search(sentence):continue
        if OTHER_PERSON.search(sentence[:marker.start()]):continue
        if attribute=='foundation_year' and PREDECESSOR.search(sentence):continue
        value_position=normalized(sentence).find(normalized(value))
        if attribute=='birthplace':
            # Birth must precede its value. This intentionally declines some
            # valid reverse-order prose rather than confusing origin and birth.
            after=sentence[marker.end():]
            if normalized(value) not in normalized(after):continue
            before=sentence[:marker.start()]
            if ANCESTRY.search(before) and normalized(value) in normalized(before):continue
        # A marker far away is not sufficient to bind a particular value.
        if abs(value_position-len(normalized(sentence[:marker.start()])))>100:continue
        return result('supported_lexically','literal entity, relation and value appear in one sentence',attribute=attribute)
    return result('rejected','requested relation not established for entity and value')
