from pathlib import Path
import sys,hashlib,json
import os
os.environ.setdefault('LOKY_MAX_CPU_COUNT','4')
ROOT=Path(__file__).resolve().parents[1]
import pandas as pd
import numpy as np
OUT=ROOT/'outputs';DOC=ROOT/'docs';STAGE=ROOT/'data/interim/session3';STAGE.mkdir(parents=True,exist_ok=True)
MODEL=ROOT/'data/models/minilm';MODEL.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(df,name):df.to_csv(OUT/('session3_'+name+'.csv'),index=False,encoding='utf-8-sig',date_format='%Y-%m-%d %H:%M:%S')
def jsave(obj,name):(OUT/('session3_'+name+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def load(name):return pd.read_csv(OUT/('session3_'+name+'.csv'))
def issue(stage,attempt,error):
    with (OUT/'session3_technical_events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(stage=stage,attempt=attempt,error=str(error),utc=pd.Timestamp.now(tz='UTC').isoformat()),ensure_ascii=False)+'\n')
