import json,zipfile
from pathlib import Path
import pytest
from PIL import Image
from datasetguard import scan,sample,evaluate,review_manifest,hamming
from app import app,safe_extract

def test_sample_metrics(tmp_path):
    truth=sample(tmp_path);report=scan(tmp_path,12);metrics=evaluate(report,truth)
    assert metrics=={'true_positives':3,'false_positives':0,'false_negatives':0,'precision':1.0,'recall':1.0}
    kinds={x['kind'] for x in report['candidates']};assert 'exact_file' in kinds and 'near' in kinds
    assert report['destructive_actions']==0

def test_threshold_changes_candidates(tmp_path):
    sample(tmp_path);assert scan(tmp_path,64)['candidate_count']>scan(tmp_path,0)['candidate_count']

@pytest.mark.parametrize('threshold',[-1,65,1.2])
def test_threshold_validation(tmp_path,threshold):
    sample(tmp_path)
    with pytest.raises(ValueError):scan(tmp_path,threshold)

def test_requires_splits(tmp_path):
    (tmp_path/'train').mkdir()
    with pytest.raises(ValueError):scan(tmp_path)

def test_corrupt_recorded_not_crash(tmp_path):
    for x in ('train','test'):(tmp_path/x).mkdir()
    (tmp_path/'train'/'bad.png').write_bytes(b'bad')
    Image.new('RGB',(40,40)).save(tmp_path/'test'/'ok.png')
    result=scan(tmp_path);assert result['error_count']==1 and result['image_count']==1

def test_pixel_exact_different_encoding(tmp_path):
    for x in ('train','test'):(tmp_path/x).mkdir()
    im=Image.new('RGB',(50,50),'red');im.save(tmp_path/'train'/'a.png');im.save(tmp_path/'test'/'b.bmp')
    assert scan(tmp_path,0)['candidates'][0]['kind']=='exact_pixels'

def test_reviews():
    report={'candidates':[{'left':'a','right':'b','decision':'pending','note':''}]}
    reviewed=review_manifest(report,[{'left':'a','right':'b','decision':'confirmed_duplicate','note':'checked'}])
    assert reviewed['review_summary']['confirmed_duplicate']==1
    with pytest.raises(ValueError):review_manifest(report,[{'left':'x','right':'b','decision':'pending'}])
    with pytest.raises(ValueError):review_manifest(report,[{'left':'a','right':'b','decision':'delete'}])

def make_zip(path,members):
    with zipfile.ZipFile(path,'w') as z:
        for name,data in members:z.writestr(name,data)

def test_safe_zip(tmp_path):
    archive=tmp_path/'a.zip';make_zip(archive,[('train/a.txt',b'a'),('../escape',b'x')])
    out=tmp_path/'out';out.mkdir();safe_extract(archive,out)
    assert (out/'train/a.txt').read_bytes()==b'a' and not (tmp_path/'escape').exists()

def test_bad_zip_layout(tmp_path):
    archive=tmp_path/'a.zip';make_zip(archive,[('other/a.png',b'x')])
    with pytest.raises(ValueError):safe_extract(archive,tmp_path/'out')

def test_web_failures_and_headers():
    c=app.test_client();assert c.get('/').status_code==200
    r=c.post('/scan');assert r.status_code==400
    r=c.post('/review',json={'report':{'candidates':[]},'decisions':[]});assert r.status_code==200
    assert 'frame-ancestors' in r.headers['Content-Security-Policy']

def test_hamming():assert hamming(0b1010,0b0011)==2
