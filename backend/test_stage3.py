"""Offline regression checks for source evidence and live aggregation."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import smart_patch

RULES = [
    {'code':'BR-101','pattern':r'72-hour','title':'Battery life','category':'fact',
     'explanation':'Use up to 48 hours','source':'Specification','replacement':'up to 48 hours'},
    {'code':'BR-102','pattern':r'best battery in India','title':'Superlative','category':'claim',
     'explanation':'Do not make ranking claims','source':'Claims policy','replacement':''},
]
SRC = [{'id':'source-1','filename':'fact.txt','content':'The approved battery duration is up to 48 hours of operation.'}]

class PatchTests(unittest.TestCase):
    def fake_model(self, **kwargs):
        return {'original_span':'Guaranteed 72-hour performance.',
                'replacement_span':'Designed for up to 48 hours of performance.',
                'rationale':'Replaced unsupported 72-hour claim.',
                'citations':[{'source_id':'source-1','quote':'up to 48 hours of operation'}]}

    def test_evidence_literal_match_and_violation_reduction(self):
        with patch.object(smart_patch,'_call_model', return_value=self.fake_model()):
            p=smart_patch.preview_smart_patch('Guaranteed 72-hour performance.','social',RULES,SRC)
        self.assertTrue(p['safe_to_offer'])
        self.assertEqual(p['before_count'],1)
        self.assertEqual(p['after_count'],0)
        self.assertEqual(p['evidence_status'],'reference_excerpt_matched')
        self.assertTrue(p['requires_human_fact_review'])

    def test_fake_citation_filtered(self):
        fake=self.fake_model(); fake['citations']=[{'source_id':'source-1','quote':'This sentence is invented and not in the document'}]
        with patch.object(smart_patch,'_call_model',return_value=fake):
            p=smart_patch.preview_smart_patch('Guaranteed 72-hour performance.','social',RULES,SRC)
        self.assertEqual(p['evidence'],[])
        self.assertEqual(p['evidence_status'],'no_valid_reference_citation')

    def test_change_must_target_failure(self):
        fake={'original_span':'A new product.','replacement_span':'Introducing the product.', 'citations':[]}
        with patch.object(smart_patch,'_call_model',return_value=fake):
            with self.assertRaises(smart_patch.AIUnavailable):
                smart_patch.preview_smart_patch('A new product. Guaranteed 72-hour performance.','social',RULES,SRC)

    def test_unverified_reference_not_accepted_as_approval(self):
        with patch.object(smart_patch,'_call_model',return_value=self.fake_model()):
            p=smart_patch.preview_smart_patch('Guaranteed 72-hour performance.','social',RULES,[])
        self.assertEqual(p['evidence_status'],'no_sources_supplied')

    def test_no_failures_skips_gemini(self):
        with patch.object(smart_patch,'_call_model') as ai:
            p=smart_patch.preview_smart_patch('A quiet product launch.','social',RULES,[])
            ai.assert_not_called()
        self.assertEqual(p['status'],'no_failures')

class EndpointTests(unittest.TestCase):
    def test_endpoints_with_scratch_database(self):
        from fastapi.testclient import TestClient
        import main
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(main,'DB',Path(temp)/'demo.db'):
                main.initialize()
                client=TestClient(main.app)
                source=client.post('/sources/import',files={'file':('facts.txt',SRC[0]['content'].encode('utf8'),'text/plain')})
                self.assertEqual(source.status_code,201,source.text)
                source_id=source.json()['id']
                with patch.object(smart_patch,'_call_model',return_value=self.fake_api_response(source_id)):
                    response=client.post('/ai/smart-patch',json={'content':'Guaranteed 72-hour performance.','channel':'social','source_ids':[source_id]})
                # API key guard is supposed to be independently validated.
                self.assertIn(response.status_code,(200,503))
                with patch.object(main,'enabled',return_value=True),patch.object(smart_patch,'_call_model',return_value=self.fake_api_response(source_id)):
                    response=client.post('/ai/smart-patch',json={'content':'Guaranteed 72-hour performance.','channel':'social','source_ids':[source_id]})
                self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(response.json()['evidence_status'],'reference_excerpt_matched')
                initial=client.get('/insights');self.assertEqual(initial.status_code,200)
                self.assertEqual(initial.json()['counts']['drafts'],0)
                d=client.post('/drafts',json={'title':'Demo','channel':'social','content':'72-hour performance.'})
                self.assertEqual(d.status_code,201)
                run=client.post(f"/drafts/{d.json()['id']}/run")
                self.assertEqual(run.status_code,200)
                insights=client.get('/insights').json()
                self.assertEqual(insights['counts']['drafts'],1)
                self.assertEqual(insights['counts']['runs'],1)
                self.assertEqual(insights['counts']['findings'],1)
    def fake_api_response(self,source_id):
        d=PatchTests().fake_model()
        d['citations']=[{'source_id':source_id,'quote':'up to 48 hours of operation'}]
        return d

if __name__=='__main__': unittest.main()
