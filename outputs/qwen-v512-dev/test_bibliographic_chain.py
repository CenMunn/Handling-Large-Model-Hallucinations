import importlib.util,unittest
import time
from unittest.mock import patch

AUTHOR_Q='如果英国文学数据库规定，那部围绕雪原湖泊与强烈情感纠葛的小说应直接以真实作者命名条目，那么条目应使用谁的名字？'
HISTORY_Q='1926年首次出版并由政治组织推动发行的理论著作，其相关政治组织成立年份是多少？'


def source(text,url='https://www.zzhvc.cn/tsg/fixture'):
    return {'url':url,'text':text,'transport':'independent_https','raw_sha256':'fixture'}


class BibliographicTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('bibliographic_chain'),'source-bound bibliographic chains are missing')
        import bibliographic_chain
        return bibliographic_chain

    def books(self):
        return [source('《柳岸》\n(英) 阿柳著;阿竹译\n《柳岸》是阿柳的传世经典。小说写雪原和湖泊，情感炽热，描写爱恨纠葛。'),
                source('《柳岸》是英国作家阿柳的唯一长篇代表作。故事围绕湖泊展开。','https://se.zhangyue.com/book/detail?bookId=123')]

    def test_descriptive_work_and_author_are_linked_without_demo_names(self):
        r=self.module().analyze(AUTHOR_Q,self.books())
        self.assertEqual(r['status'],'supported');self.assertEqual(r['work'],'柳岸');self.assertEqual(r['author'],'阿柳')
        self.assertNotIn('阿竹',r['answer']);self.assertEqual(len({c['source_url'] for c in r['credit_sources']}),2)

    def test_missing_or_wrong_clue_is_not_discarded(self):
        for q in [AUTHOR_Q.replace('雪原','沙漠'),AUTHOR_Q.replace('强烈','平静'),AUTHOR_Q.replace('雪原','没有雪原')]:
            with self.subTest(q=q):self.assertNotEqual(self.module().analyze(q,self.books())['status'],'supported')

    def test_country_hint_and_translator_role_cannot_be_substituted(self):
        self.assertNotEqual(self.module().analyze(AUTHOR_Q.replace('英国','法国'),self.books())['status'],'supported')
        docs=[source('《柳岸》\n(英) 阿竹译\n小说写雪原和湖泊，情感炽热，描写爱恨纠葛。'),source('《柳岸》由阿竹翻译。','https://se.zhangyue.com/book/detail?bookId=123')]
        self.assertNotEqual(self.module().analyze(AUTHOR_Q,docs)['status'],'supported')

    def test_book_namesake_or_author_conflict_cannot_choose_first(self):
        docs=self.books()+[source('《柳岸》是英国作家阿松的唯一长篇代表作。','https://news.cnr.cn/native/gd/fixture')]
        self.assertEqual(self.module().analyze(AUTHOR_Q,docs)['status'],'conflict')
        docs=self.books()+[source('《竹岸》\n(英) 阿松著;阿木译\n小说写雪原和湖泊，情感炽热，描写爱恨纠葛。','https://www.zzhvc.cn/tsg/fixture2')]
        self.assertEqual(self.module().analyze(AUTHOR_Q,docs)['status'],'ambiguous')

    def test_pen_name_only_and_one_credit_page_are_insufficient(self):
        self.assertNotEqual(self.module().analyze(AUTHOR_Q,self.books()[:1])['status'],'supported')
        docs=[source('《柳岸》署名溪风，笔名身份未公开。小说写雪原湖泊，情感强烈，爱恨纠葛。')]
        self.assertNotEqual(self.module().analyze(AUTHOR_Q,docs)['status'],'supported')

    def test_created_by_credit_and_relatives_have_distinct_subjects(self):
        docs=self.books();docs[1]['text']='《柳岸》是英国小说家阿柳创作的长篇小说。'
        r=self.module().analyze(AUTHOR_Q,docs)
        self.assertEqual(r['status'],'supported');self.assertEqual(r['author'],'阿柳')
        docs[1]['text']='《柳岸》是英国作家阿柳的妻子阿松创作的小说。'
        self.assertNotEqual(self.module().analyze(AUTHOR_Q,docs)['status'],'supported')

    def historical(self,year=1926,foundation=1924):
        return source(f'{year}年2月的一天，一个重要日子。这一天，《岸边纲领》在当地问世。\n\n{foundation}年6月，“旧岸会”这一秘密组织改组为“新岸会”，成为当地第一个政治组织。《岸边纲领》，正是阿柳受同盟委托起草的党纲。','https://news.cnr.cn/native/gd/fixture')

    def test_publication_commission_and_reconstitution_are_separate_dates(self):
        # The shorthand must match the current organization's own suffix.
        doc=self.historical();doc['text']=doc['text'].replace('新岸会','新岸同盟').replace('旧岸会','旧岸同盟')
        r=self.module().analyze(HISTORY_Q,[doc])
        self.assertEqual(r['status'],'supported');self.assertEqual(r['year'],1924);self.assertEqual(r['organization'],'新岸同盟')
        self.assertNotEqual(r['year'],1926);self.assertIn('改组',r['answer'])

    def test_wrong_publication_year_and_translation_date_cannot_match(self):
        doc=self.historical();doc['text']=doc['text'].replace('新岸会','新岸同盟')
        self.assertNotEqual(self.module().analyze(HISTORY_Q.replace('1926','1927'),[doc])['status'],'supported')
        doc['text']=doc['text'].replace('在当地问世','的译本在当地问世')
        self.assertNotEqual(self.module().analyze(HISTORY_Q,[doc])['status'],'supported')

    def test_inconsistent_first_publication_year_or_future_foundation_is_not_hidden(self):
        doc=self.historical();doc['text']=doc['text'].replace('新岸会','新岸同盟')
        later=source('《岸边纲领》于1928年首次出版。','https://news.cnr.cn/native/gd/fixture2')
        self.assertEqual(self.module().analyze(HISTORY_Q,[doc,later])['status'],'conflict')
        doc=self.historical(foundation=1930);doc['text']=doc['text'].replace('新岸会','新岸同盟')
        self.assertNotEqual(self.module().analyze(HISTORY_Q,[doc])['status'],'supported')

    def test_rename_is_not_founding_and_predecessor_date_is_not_substituted(self):
        doc=source('1926年，《岸边纲领》首次出版。旧岸同盟成立于1900年，是政治组织。1924年，旧岸同盟改名为新岸同盟。《岸边纲领》是新岸同盟委托起草的纲领。','https://news.cnr.cn/native/gd/fixture')
        self.assertNotEqual(self.module().analyze(HISTORY_Q,[doc])['status'],'supported')

    def test_named_commission_and_direct_foundation_generalize(self):
        doc=source('《远山纲领》于1936年首次出版。《远山纲领》是山岭会委托起草的纲领。山岭会于1933年成立，是政治组织。','https://news.cnr.cn/native/gd/fixture')
        q=HISTORY_Q.replace('1926','1936')
        r=self.module().analyze(q,[doc]);self.assertEqual(r['status'],'supported');self.assertEqual(r['year'],1933)

    def test_conflicting_same_organization_foundation_year_is_retained(self):
        doc=self.historical();doc['text']=doc['text'].replace('新岸会','新岸同盟')
        other=source('新岸同盟于1922年成立，是政治组织。','https://news.cnr.cn/native/gd/fixture2')
        self.assertEqual(self.module().analyze(HISTORY_Q,[doc,other])['status'],'conflict')

    def test_unfetched_retrieval_conflict_requires_followup_instead_of_being_ignored(self):
        m=self.module();verified=self.books();docs=[{'url':s['url'],'full_text':s['text']} for s in verified]
        docs.append({'url':'https://other.example/book','full_text':'《柳岸》是英国作家阿松的唯一长篇代表作。'})
        with patch.object(m,'bounded_fetch',side_effect=[{'status':'ok','source':s} for s in verified]):
            r=m.lookup(AUTHOR_Q,docs,time.monotonic()+5)
        self.assertEqual(r['status'],'needs_verification');self.assertNotIn('answer',r)

if __name__=='__main__':unittest.main()
