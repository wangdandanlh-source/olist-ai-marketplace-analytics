"""Download only the specified public model, never Olist data; two-attempt stop loss."""
from session3_common import *
import urllib.request
REPO='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REVISION='e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
def main():
    for attempt in [1,2]:
        try:
            api='https://huggingface.co/api/models/'+REPO+'/revision/'+REVISION
            meta=json.loads(urllib.request.urlopen(api,timeout=45).read());rev=meta['sha']
            (MODEL/'hub_metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            files=['onnx/model_quint8_avx2.onnx','tokenizer.json','tokenizer_config.json','special_tokens_map.json','config.json','sentence_bert_config.json','1_Pooling/config.json']
            records=[]
            for name in files:
                dst=MODEL/name;dst.parent.mkdir(parents=True,exist_ok=True)
                url=f'https://huggingface.co/{REPO}/resolve/{rev}/{name}'
                if not dst.exists():
                    with urllib.request.urlopen(url,timeout=120) as r:body=r.read()
                    dst.write_bytes(body)
                records.append(dict(file=name,bytes=dst.stat().st_size,sha256=sha(dst),url=url))
                print(name,dst.stat().st_size,flush=True)
            jsave(dict(model_name=REPO,revision=rev,files=records,download_success=True,attempts=attempt),'model_download')
            return
        except Exception as e:issue('primary_model_download',attempt,e);print(type(e).__name__,str(e),flush=True)
    jsave(dict(model_name=REPO,download_success=False,attempts=2,fallback_required=True),'model_download')
if __name__=='__main__':main()
