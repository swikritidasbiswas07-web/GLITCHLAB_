from fastapi.testclient import TestClient
from unittest.mock import patch
from main import app

client = TestClient(app)

def test_ai_disabled_and_status():
    with patch.dict('os.environ', {}, clear=True):
        assert client.get('/ai/status').json()['enabled'] is False
        r = client.post('/ai/analyze',json={'content':'A draft to assess','channel':'social'})
        assert r.status_code == 503

def test_txt_source_upload_and_list():
    r=client.post('/sources/import',files={'file':('brand.txt',b'Never say guaranteed. Use the name NovaCell X.','text/plain')})
    assert r.status_code==201, r.text
    sid=r.json()['id']
    assert r.json()['status']=='imported_unapproved'
    assert client.get('/sources').status_code==200
    assert 'Never say guaranteed' in client.get('/sources/'+sid).json()['content']

def test_unsupported_or_empty_uploads():
    r=client.post('/sources/import',files={'file':('brand.png',b'not an image','image/png')})
    assert r.status_code==415
    r=client.post('/sources/import',files={'file':('empty.txt',b'  ','text/plain')})
    assert r.status_code==422

def test_ai_only_returns_existing_codes_and_real_spans():
    from intelligence import assess
    response={'summary':'Test','findings':[{'rule_code':'BR-103','quote':'Guaranteed','status':'NEEDS_REVIEW','category':'claim','explanation':'Check wording','suggested_edit':'Designed for','source_excerpt':'No guarantee'}, {'rule_code':'MADE-UP','quote':'Guaranteed','status':'FAIL'}, {'rule_code':'BR-103','quote':'not in draft','status':'FAIL'}]}
    with patch('intelligence._call_model',return_value=response):
        result=assess('Guaranteed performance','social',[{'code':'BR-103'}],[])
    assert len(result['findings'])==1
    assert result['findings'][0]['rule_code']=='BR-103'
