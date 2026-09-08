"""Compare five K values x three seeds; export data-driven interpretation evidence."""
from session3_common import *
import sqlite3,itertools,joblib
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score,adjusted_rand_score
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits
STOP='a o as os de da do das dos e em no na nos nas um uma uns umas que eu para com por foi ao aos esta este esse essa isso se me meu minha mais muito bem mas como pelo pela quando estou está são ser ter um só já até pois também'.split()
def main():
    c=sqlite3.connect(STAGE/'corpus.sqlite');corpus=pd.read_sql_query('SELECT * FROM canonical_written',c);c.close()
    unique=pd.read_csv(STAGE/'unique_texts.csv');x=np.load(STAGE/'embeddings.npy');idx=dict(zip(unique.unique_text_id,range(len(unique))))
    primary=corpus[corpus.review_score.le(3)&corpus.clean_nonempty.eq(1)].copy().reset_index(drop=True);ix=primary.unique_text_id.map(idx).to_numpy();xp=x[ix]
    vec=TfidfVectorizer(min_df=2,max_df=.95,ngram_range=(1,2),stop_words=STOP,sublinear_tf=True,max_features=30000)
    tf=vec.fit_transform(primary.review_text_clean);terms=np.array(vec.get_feature_names_out())
    rows=[];previews=[];seeds=[42,7,2026];rng=np.random.default_rng(20260907);sample=np.sort(rng.choice(len(primary),size=min(3000,len(primary)),replace=False))
    with threadpool_limits(limits=4):
        for k in [8,10,12,15,18]:
            labels=[]
            for seed in seeds:
                model=MiniBatchKMeans(n_clusters=k,random_state=seed,batch_size=1024,n_init=10,max_iter=200,reassignment_ratio=.01)
                lab=model.fit_predict(xp);labels.append(lab);counts=np.bincount(lab,minlength=k)
                sil=silhouette_score(xp[sample],lab[sample],metric='cosine')
                joblib.dump(model,STAGE/f'kmeans_k{k}_seed{seed}.joblib');np.save(STAGE/f'labels_k{k}_seed{seed}.npy',lab)
                row=dict(k=k,seed=seed,silhouette=float(sil),silhouette_metric='cosine',silhouette_sample_n=len(sample),smallest_cluster=int(counts.min()),largest_cluster_share=float(counts.max()/len(primary)),cluster_size_distribution=json.dumps(counts.tolist()),primary_n=len(primary))
                rows.append(row);print('K',k,'seed',seed,'silhouette',round(sil,4),'sizes',counts.tolist(),flush=True)
                if seed==42:
                    for cluster in range(k):
                        inds=np.flatnonzero(lab==cluster);z=primary.iloc[inds];dist=np.linalg.norm(xp[inds]-model.cluster_centers_[cluster],axis=1)
                        order=np.argsort(dist,kind='stable');zrep=z.iloc[order].drop_duplicates('unique_text_id').head(3)
                        weights=np.asarray(tf[inds].mean(axis=0)).ravel();keywords='; '.join(terms[np.argsort(weights)[-12:][::-1]])
                        previews.append(dict(k=k,cluster_id=cluster,sample_size=len(z),keywords=keywords,nearest_three=' || '.join(zrep.review_text_raw.tolist())))
            ari=[adjusted_rand_score(labels[a],labels[b]) for a,b in itertools.combinations(range(3),2)]
            for row in rows[-3:]:row.update(ari_mean=float(np.mean(ari)),ari_min=float(np.min(ari)),ari_pairs=json.dumps(ari))
    save(pd.DataFrame(rows),'cluster_selection');save(pd.DataFrame(previews),'candidate_cluster_previews')
    primary[['order_id','review_row_id','unique_text_id']].to_csv(STAGE/'primary_index.csv',index=False,encoding='utf-8-sig')
    print(pd.DataFrame(rows).groupby('k')[['silhouette','ari_mean','smallest_cluster','largest_cluster_share']].mean().to_string(),flush=True)
if __name__=='__main__':main()
