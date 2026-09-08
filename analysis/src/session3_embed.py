"""Local multilingual MiniLM ONNX inference; after two failures use explicit TF-IDF/SVD."""
from session3_common import *
import time,importlib.metadata as metadata
def fallback(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    v=TfidfVectorizer(ngram_range=(1,2),min_df=2,max_df=.98,max_features=60000,sublinear_tf=True)
    matrix=v.fit_transform(texts);svd=TruncatedSVD(n_components=256,random_state=42)
    x=normalize(svd.fit_transform(matrix)).astype('float32')
    import joblib
    joblib.dump((v,svd),STAGE/'fallback_tfidf_svd.joblib')
    return x
def main():
    unique=pd.read_csv(STAGE/'unique_texts.csv');fingerprint=sha(STAGE/'unique_texts.csv')
    if (STAGE/'embeddings.npy').exists() and (OUT/'session3_model_manifest.json').exists():
        prev=json.loads((OUT/'session3_model_manifest.json').read_text())
        if prev['text_index_sha256']==fingerprint and prev['embedding_sha256']==sha(STAGE/'embeddings.npy'):
            print('Verified cached embeddings; no inference repeated.');return
    download=json.loads((OUT/'session3_model_download.json').read_text());successful=False;truncated=0;began=time.time();attempts=0
    if download['download_success']:
        for attempt in [1,2]:
            attempts=attempt
            try:
                import onnxruntime as ort
                from tokenizers import Tokenizer
                tok=Tokenizer.from_file(str(MODEL/'tokenizer.json'))
                special=json.loads((MODEL/'special_tokens_map.json').read_text());pad=special['pad_token'];pad=pad['content'] if isinstance(pad,dict) else pad
                opts=ort.SessionOptions();opts.intra_op_num_threads=4;opts.inter_op_num_threads=1
                sess=ort.InferenceSession(str(MODEL/'onnx/model_quint8_avx2.onnx'),sess_options=opts,providers=['CPUExecutionProvider'])
                needed={x.name for x in sess.get_inputs()};print('ONNX inputs',needed,'outputs',[(x.name,x.shape) for x in sess.get_outputs()],flush=True)
                # Audit truncation before enabling 128-token model limit.
                tok.no_truncation();tok.no_padding()
                lengths=[len(z.ids) for z in tok.encode_batch(unique.review_text_clean.tolist())];truncated=sum(n>128 for n in lengths)
                tok.enable_truncation(max_length=128);tok.enable_padding(pad_id=tok.token_to_id(pad),pad_token=pad)
                allx=[]
                # Sort by character length to reduce padding, then restore stable unique_text_id order.
                order=np.argsort(unique.review_text_clean.str.len().to_numpy(),kind='stable');batchsize=64
                for b in range(0,len(order),batchsize):
                    encoded=tok.encode_batch(unique.review_text_clean.iloc[order[b:b+batchsize]].tolist())
                    inputs={'input_ids':np.array([e.ids for e in encoded],dtype=np.int64),'attention_mask':np.array([e.attention_mask for e in encoded],dtype=np.int64),'token_type_ids':np.array([e.type_ids for e in encoded],dtype=np.int64)}
                    output=sess.run(None,{k:v for k,v in inputs.items() if k in needed})[0]
                    if output.ndim==3:
                        mask=inputs['attention_mask'][...,None];embedding=(output*mask).sum(axis=1)/mask.sum(axis=1).clip(1)
                    else:embedding=output
                    embedding=embedding/np.linalg.norm(embedding,axis=1,keepdims=True).clip(1e-12)
                    allx.append(embedding.astype('float32'))
                    if b%2048==0:print(f'Embedded {min(b+batchsize,len(order))}/{len(order)} elapsed={time.time()-began:.1f}s',flush=True)
                x=np.empty((len(unique),384),dtype='float32');x[order]=np.vstack(allx)
                assert x.shape==(len(unique),384) and np.isfinite(x).all()
                successful=True;break
            except Exception as e:issue('primary_model_load_or_inference',attempt,e);print(type(e).__name__,str(e),flush=True)
    if not successful:x=fallback(unique.review_text_clean.tolist())
    np.save(STAGE/'embeddings.npy',x)
    versions={name:metadata.version(name) for name in ['numpy','pandas','scikit-learn','onnxruntime','tokenizers']}
    manifest=dict(model_name=download['model_name'] if successful else 'TF-IDF + TruncatedSVD',primary_model_name=download['model_name'],primary_success=successful,fallback_used=not successful,backend='ONNX Runtime CPU; official uint8 AVX2 export' if successful else 'scikit-learn TF-IDF/SVD',model_revision=download.get('revision'),library_versions=versions,embedding_dimension=x.shape[1],embedding_rows=x.shape[0],text_index_sha256=fingerprint,embedding_sha256=sha(STAGE/'embeddings.npy'),run_timestamp=pd.Timestamp.now(tz='UTC').isoformat(),elapsed_seconds=time.time()-began,primary_load_inference_attempts=attempts,download_attempts=download['attempts'],max_sequence_length=128 if successful else None,truncated_unique_texts=truncated if successful else None,pooling='attention-mask mean pooling then L2 normalization' if successful else 'TF-IDF word1-2 + SVD256 + L2 normalization',translation_before_embedding=False,weights_in_git=False,paid_api=False,model_license='Apache-2.0',llm_naming_runtime='ChatGPT Work runtime — exact model identifier unavailable')
    jsave(manifest,'model_manifest');print(json.dumps(manifest,indent=2),flush=True)
if __name__=='__main__':main()
