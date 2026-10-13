import json,tempfile,zipfile
from pathlib import Path,PurePosixPath
from flask import Flask,request,jsonify,render_template
from datasetguard import scan,review_manifest
app=Flask(__name__);app.config['MAX_CONTENT_LENGTH']=50*1024*1024

def safe_extract(file,target):
    with zipfile.ZipFile(file) as z:
        members=z.infolist()
        if len(members)>500:raise ValueError('Archive contains more than 500 entries.')
        total=0
        for item in members:
            name=PurePosixPath(item.filename)
            if name.is_absolute() or '..' in name.parts or item.is_dir():continue
            if not name.parts or name.parts[0] not in ('train','validation','test'):raise ValueError('Files must be under train/, validation/, or test/.')
            total+=item.file_size
            if total>100*1024*1024:raise ValueError('Uncompressed archive exceeds 100 MiB.')
            out=target.joinpath(*name.parts);out.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,out.open('wb') as dst:
                while chunk:=src.read(65536):dst.write(chunk)

@app.get('/')
def index():return render_template('index.html')
@app.post('/scan')
def run():
    try:
        threshold=int(request.form.get('threshold','12'));uploaded=request.files.get('dataset')
        if not uploaded:return jsonify(error='Choose a ZIP dataset.'),400
        with tempfile.TemporaryDirectory() as temp:
            safe_extract(uploaded,Path(temp));return jsonify(scan(temp,threshold))
    except (ValueError,zipfile.BadZipFile) as exc:return jsonify(error=str(exc)),400
@app.post('/review')
def review():
    try:
        data=request.get_json(force=True);return jsonify(review_manifest(data['report'],data['decisions']))
    except (ValueError,KeyError,TypeError) as exc:return jsonify(error=str(exc)),400
@app.errorhandler(413)
def large(_):return jsonify(error='ZIP exceeds 50 MiB.'),413
@app.after_request
def headers(r):r.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'";r.headers['X-Content-Type-Options']='nosniff';return r
if __name__=='__main__':app.run(host='127.0.0.1',port=8770)
