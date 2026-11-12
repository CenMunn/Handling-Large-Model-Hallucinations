import importlib.util,unittest

QUESTION='负责产生ATP且具有自身DNA的细胞结构，其人体细胞数量通常达到什么范围？'
BODY='''### Description
Energosomes are structures within cells that convert the energy from food into a form that cells can use.
Each cell contains tens to hundreds of energosomes, which are located in the cytoplasm.
Although most DNA is in the nucleus, energosomes also have a small amount of their own DNA.
In humans, the genome encodes proteins involved in reactions that create adenosine triphosphate (ATP).
### Health Conditions
'''


class CellSourceTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('cell_source'),'source-bound functional cell count adapter is missing')
        import cell_source
        return cell_source

    def test_new_entity_and_quantity_come_from_source_not_demo_answer(self):
        r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov/genetics/example/','text':BODY})
        self.assertEqual(r['status'],'supported');self.assertEqual(r['subject'],'energosomes');self.assertIn('数十至数百',r['answer'])

    def test_body_proofs_of_own_dna_energy_and_human_scope_are_required(self):
        for missing in ['their own DNA','(ATP)','In humans']:
            with self.subTest(missing=missing):
                r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov/genetics/example/','text':BODY.replace(missing,'unavailable')})
                self.assertNotEqual(r['status'],'supported')

    def test_dna_copies_are_not_organelle_count(self):
        r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov/genetics/example/','text':BODY.replace('of energosomes,','of DNA copies,')})
        self.assertNotEqual(r['status'],'supported')

    def test_wrong_named_structure_or_extra_constraint_is_not_ignored(self):
        m=self.module()
        for q in ['人体叶绿体负责产生ATP且具有自身DNA，其数量通常达到什么范围？',
                  QUESTION.replace('自身DNA','不具有自身DNA'),
                  QUESTION.replace('细胞结构','没有细胞膜的细胞结构'),
                  '仅根据材料：'+QUESTION,
                  QUESTION.replace('人体','小鼠')]:
            with self.subTest(q=q):self.assertFalse(m.functional_question(q))

    def test_lookalike_host_or_unverified_provider_body_cannot_be_trusted(self):
        r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov.evil.example/genetics/example/','text':BODY})
        self.assertNotEqual(r['status'],'supported')
        r=self.module().inspect(QUESTION,{'url':'https://news.cnr.cn/native/gd/fixture','text':BODY})
        self.assertNotEqual(r['status'],'supported')

    def test_count_and_own_dna_must_describe_same_subject(self):
        body=BODY.replace('energosomes also have','othergosomes also have')
        r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov/genetics/example/','text':body})
        self.assertNotEqual(r['status'],'supported')

    def test_reversed_source_range_cannot_be_silently_fixed(self):
        r=self.module().inspect(QUESTION,{'url':'https://medlineplus.gov/genetics/example/','text':BODY.replace('tens to hundreds','thousands to hundreds')})
        self.assertNotEqual(r['status'],'supported')

if __name__=='__main__':unittest.main()
