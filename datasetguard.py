"""Non-destructive exact and perceptual image split auditor."""
import argparse, hashlib, io, json, time
from itertools import combinations
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

EXTENSIONS={'.png','.jpg','.jpeg','.webp','.bmp'}
Image.MAX_IMAGE_PIXELS=20_000_000

def hamming(a,b): return (a^b).bit_count()

def dhash(image,size=16):
    """256-bit difference hash; orientation-sensitive by design."""
    gray=ImageOps.exif_transpose(image).convert('L').resize((size+1,size),Image.Resampling.LANCZOS)
    arr=np.asarray(gray,dtype=np.int16)
    bits=(arr[:,1:]>arr[:,:-1]).ravel()
    value=0
    for bit in bits:value=(value<<1)|int(bit)
    return value

def load_image(path):
    try:
        with path.open('rb') as f: raw=f.read()
        with Image.open(io.BytesIO(raw)) as source:
            if source.width*source.height>20_000_000: raise ValueError('pixel limit exceeded')
            image=ImageOps.exif_transpose(source).convert('RGB')
        pixel=hashlib.sha256(f'{image.width}x{image.height}:RGB'.encode()+image.tobytes()).hexdigest()
        return {'file_sha256':hashlib.sha256(raw).hexdigest(),'pixel_sha256':pixel,'dhash':dhash(image),'width':image.width,'height':image.height}
    except (OSError,UnidentifiedImageError,Image.DecompressionBombError,ValueError) as exc:
        raise ValueError(f'cannot decode {path.name}: {exc}') from exc

def scan(root,threshold=12):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Dataset root must be a directory.')
    if not isinstance(threshold,int) or not 0<=threshold<=64:raise ValueError('Threshold must be an integer from 0 to 64.')
    split_dirs=[root/s for s in ('train','validation','test') if (root/s).is_dir()]
    if len(split_dirs)<2:raise ValueError('Provide at least two split folders: train, validation, test.')
    started=time.perf_counter();images=[];errors=[]
    for folder in split_dirs:
        for path in sorted(p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS):
            rel=path.relative_to(root).as_posix()
            try: images.append({'path':rel,'split':folder.name,**load_image(path)})
            except ValueError as exc:errors.append({'path':rel,'error':str(exc)})
    pairs=[]
    for left,right in combinations(images,2):
        if left['split']==right['split']:continue
        exact_file=left['file_sha256']==right['file_sha256']
        exact_pixels=left['pixel_sha256']==right['pixel_sha256']
        distance=hamming(left['dhash'],right['dhash'])
        if exact_file or exact_pixels or distance<=threshold:
            kind='exact_file' if exact_file else ('exact_pixels' if exact_pixels else 'near')
            pairs.append({'left':left['path'],'right':right['path'],'left_split':left['split'],'right_split':right['split'],'kind':kind,'distance':distance,'decision':'pending','note':''})
    pairs.sort(key=lambda p:({'exact_file':0,'exact_pixels':1,'near':2}[p['kind']],p['distance'],p['left'],p['right']))
    return {'schema_version':1,'root_name':root.name,'threshold':threshold,'hash':'dHash-256','image_count':len(images),'error_count':len(errors),'candidate_count':len(pairs),'elapsed_seconds':time.perf_counter()-started,'images':[{**x,'dhash':f'{x["dhash"]:064x}'} for x in images],'errors':errors,'candidates':pairs,'destructive_actions':0}

def review_manifest(report,decisions):
    allowed={'pending','confirmed_duplicate','false_positive'}
    lookup={(p['left'],p['right']):p for p in report['candidates']}
    for item in decisions:
        key=(item.get('left'),item.get('right'))
        if key not in lookup:raise ValueError(f'Unknown candidate: {key}')
        if item.get('decision') not in allowed:raise ValueError('Invalid review decision.')
        lookup[key]['decision']=item['decision'];lookup[key]['note']=str(item.get('note',''))[:500]
    report['review_summary']={x:sum(p['decision']==x for p in report['candidates']) for x in allowed}
    return report

def sample(root):
    root=Path(root)
    for split in ('train','validation','test'):(root/split).mkdir(parents=True,exist_ok=True)
    def scene(seed):
        rng=np.random.default_rng(seed)
        # Smooth seeded texture plus a unique object: visually plausible
        # lookalikes with enough structure for meaningful hash negatives.
        texture=rng.integers(0,256,(16,16,3),dtype=np.uint8)
        im=Image.fromarray(texture).resize((128,128),Image.Resampling.BICUBIC)
        from PIL import ImageDraw
        draw=ImageDraw.Draw(im);x,y=rng.integers(25,80,2);w=int(rng.integers(25,55))
        draw.rounded_rectangle((x,y,min(125,x+w),min(125,y+w)),radius=8,outline=tuple(map(int,rng.integers(180,256,3))),width=5)
        return im
    originals=[scene(i) for i in range(8)]
    for i,im in enumerate(originals):im.save(root/'train'/f'base_{i}.png')
    originals[0].save(root/'validation'/'exact.png')
    originals[1].resize((112,112)).save(root/'validation'/'resized.jpg',quality=82)
    originals[2].save(root/'test'/'reencoded.jpg',quality=70)
    for i in range(3,8):scene(100+i).save(root/'test'/f'unrelated_{i}.png')
    truth=[('train/base_0.png','validation/exact.png'),('train/base_1.png','validation/resized.jpg'),('train/base_2.png','test/reencoded.jpg')]
    (root/'ground_truth.json').write_text(json.dumps({'positive_pairs':[list(x) for x in truth],'note':'Synthetic known transforms; all other cross-split pairs are negatives.'},indent=2)+'\n')
    return truth

def evaluate(report,truth):
    expected={tuple(sorted(x)) for x in truth};pred={tuple(sorted((p['left'],p['right']))) for p in report['candidates']}
    tp=len(expected&pred);fp=len(pred-expected);fn=len(expected-pred)
    return {'true_positives':tp,'false_positives':fp,'false_negatives':fn,'precision':tp/(tp+fp) if tp+fp else None,'recall':tp/(tp+fn) if tp+fn else None}

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('scan');s.add_argument('root',type=Path);s.add_argument('--threshold',type=int,default=12);s.add_argument('--output',type=Path,default=Path('outputs/report.json'))
    d=sub.add_parser('demo');d.add_argument('--root',type=Path,default=Path('outputs/sample'));d.add_argument('--threshold',type=int,default=12);d.add_argument('--output',type=Path,default=Path('outputs/demo-report.json'))
    a=p.parse_args()
    try:
        truth=sample(a.root) if a.command=='demo' else None;report=scan(a.root,a.threshold)
        if truth:report['evaluation']=evaluate(report,truth);report['synthetic_sample']=True
        a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('images','candidates','errors')},indent=2))
    except (ValueError,OSError) as exc:p.exit(2,f'Error: {exc}\n')
if __name__=='__main__':main()
