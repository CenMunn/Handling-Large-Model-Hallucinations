import unittest
import evidence


class SpanTests(unittest.TestCase):
    def functions(self):
        self.assertTrue(hasattr(evidence,'source_spans'),'Numbered verbatim spans are missing')
        self.assertTrue(hasattr(evidence,'materialize_claim'),'Span claims must bind to source text')

    def test_quotation_is_reconstructed_from_source(self):
        self.functions()
        doc={'id':'s1','url':'https://example.org/a','text':'记录：设备位于星湖。其型号为Q73。'}
        doc['spans']=evidence.source_spans(doc['text'])
        claim={'source_id':'s1','status':'supports','span_id':doc['spans'][0]['id'],'answer':'星湖','source_value':'星湖','quote':'伪造的引文会被忽略'}
        actual=evidence.materialize_claim(claim,doc)
        self.assertEqual(actual['quote'],doc['spans'][0]['text'])
        self.assertIn(actual['quote'],doc['text'])

    def test_unknown_span_and_value_outside_span_fail(self):
        self.functions()
        doc={'id':'s1','url':'https://example.org/a','text':'位置为星湖。'};doc['spans']=evidence.source_spans(doc['text'])
        claim={'source_id':'s1','status':'supports','span_id':'invented','answer':'星湖','source_value':'星湖'}
        with self.assertRaises(ValueError):evidence.materialize_claim(claim,doc)
        with self.assertRaises(ValueError):evidence.materialize_claim({**claim,'span_id':'p0','source_value':'未知值'},doc)

    def test_spans_preserve_decimal_and_unicode(self):
        self.functions();text='实际净质量为2.75千克。型号是Å-3。'
        spans=evidence.source_spans(text)
        self.assertTrue(any('2.75' in s['text'] for s in spans))
        self.assertTrue(all(s['text'] in text for s in spans))

    def test_long_source_spans_bounded(self):
        self.functions();text='a'*2000+'出生于星湖。'
        spans=evidence.source_spans(text)
        self.assertLessEqual(len(spans),12)
        self.assertTrue(all(len(s['text'])<=240 for s in spans))
        self.assertTrue(all(s['text'] in text for s in spans))

    def test_one_invalid_item_does_not_erase_valid_items_for_repair(self):
        self.functions()
        docs=[{'id':'s1','url':'https://one.example/','text':'设备位于星湖。'}, {'id':'s2','url':'https://two.example/','text':'设备位于星湖。'}]
        for doc in docs:doc['spans']=evidence.source_spans(doc['text'])
        claims=[{'source_id':'s1','status':'supports','span_id':'p0','answer':'星湖','source_value':'星湖'}, {'source_id':'s2','status':'supports','span_id':'wrong','answer':'星湖','source_value':'星湖'}]
        self.assertTrue(hasattr(evidence,'inspect_span_claims'))
        valid,errors=evidence.inspect_span_claims(claims,docs,'设备位于哪里？')
        self.assertEqual(list(valid),['s1'])
        self.assertEqual([e['source_id'] for e in errors],['s2'])

    def test_award_and_designer_cues_keep_relevant_source_text(self):
        text='页首导航。'*100+' The Nobel Prize in Physiology or Medicine 1945 was awarded to this scientist.'
        self.assertIn('Physiology',evidence.evidence_window({'text':text},'科学家获得的是哪类诺贝尔奖？'))


if __name__=='__main__':unittest.main()
