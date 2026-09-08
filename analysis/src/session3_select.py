"""Freeze reviewed K and build nearest and random evidence (no LLM labeling here)."""
from session3_common import *
import sqlite3,joblib,argparse
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits
from session3_cluster import STOP
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--k',type=int,required=True);args=parser.parse_args();k=args.k
    c=sqlite3.connect(STAGE/'corpus.sqlite');corpus=pd.read_sql_query('SELECT * FROM canonical_written',c);c.close()
    unique=pd.read_csv(STAGE/'unique_texts.csv');ix=dict(zip(unique.unique_text_id,range(len(unique))));x=np.load(STAGE/'embeddings.npy');profiles=[];reps=[];assigned=[]
    for role,mask in [('primary',corpus.review_score.le(3)),('positive',corpus.review_score.ge(4))]:
        z=corpus[mask&corpus.clean_nonempty.eq(1)].reset_index(drop=True);xz=x[z.unique_text_id.map(ix)]
        if role=='primary':model=joblib.load(STAGE/f'kmeans_k{k}_seed42.joblib');lab=np.load(STAGE/f'labels_k{k}_seed42.npy');count=k
        else:
            count=3
            with threadpool_limits(limits=4):model=MiniBatchKMeans(n_clusters=3,random_state=42,n_init=10,batch_size=1024,max_iter=200).fit(xz)
            lab=model.predict(xz);joblib.dump(model,STAGE/'positive_kmeans.joblib')
        z['cluster_id']=lab+(100 if role=='positive' else 0);assigned.append(z[['order_id','cluster_id']])
        vec=TfidfVectorizer(min_df=2,max_df=.95,ngram_range=(1,2),stop_words=STOP,max_features=30000,sublinear_tf=True)
        tf=vec.fit_transform(z.review_text_clean);terms=np.array(vec.get_feature_names_out())
        for cluster in range(count):
            idx=np.flatnonzero(lab==cluster);g=z.iloc[idx].copy();cid=cluster+(100 if role=='positive' else 0)
            dist=np.linalg.norm(xz[idx]-model.cluster_centers_[cluster],axis=1);g['centroid_distance']=dist
            valid=g[g.late_eligible.eq(1)];weights=np.asarray(tf[idx].mean(axis=0)).ravel()
            keywords='; '.join(terms[np.argsort(weights)[-15:][::-1]])
            nearest=g.sort_values(['centroid_distance','review_row_id']).drop_duplicates('unique_text_id').head(10)
            remaining=g[~g.unique_text_id.isin(nearest.unique_text_id)].drop_duplicates('unique_text_id')
            random=remaining.sample(n=min(5,len(remaining)),random_state=20260907+cid)
            for method,rows in [('centroid_nearest',nearest),('random_diagnostic',random)]:
                for rank,row in enumerate(rows.itertuples(),1):reps.append(dict(cluster_id=cid,corpus_role=role,rank=rank,selection=method,order_id=row.order_id,review_row_id=row.review_row_id,unique_text_id=row.unique_text_id,review_text_raw=row.review_text_raw,review_score=row.review_score,is_late=row.is_late,late_eligible=row.late_eligible,review_after_delivery=row.review_after_delivery,centroid_distance=row.centroid_distance))
            profiles.append(dict(cluster_id=cid,corpus_role=role,sample_size=len(g),share=len(g)/len(z),average_review_score=g.review_score.mean(),low_rating_rate=g.review_score.le(2).mean(),late_eligible_n=len(valid),late_delivery_rate=valid.is_late.mean(),average_delay_days=valid.delay_days.mean(),median_delay_days=valid.delay_days.median(),top_keywords=keywords,representative_comments=json.dumps(nearest.review_text_raw.tolist(),ensure_ascii=False),rating_distribution=json.dumps(g.review_score.value_counts().sort_index().to_dict()),structured_scope='core delivered with valid dates only',issue_scope='all canonical written score<=3' if role=='primary' else 'all canonical written score>=4'))
    save(pd.DataFrame(profiles),'cluster_profiles');save(pd.DataFrame(reps),'cluster_representatives')
    pd.concat(assigned).to_csv(STAGE/'cluster_assignments.csv',index=False,encoding='utf-8-sig')
    jsave(dict(selected_k=k,selected_seed=42,positive_k=3,selection_status='LLM evidence review, see docs/session3_cluster_selection.md'),'selected_configuration')
    print(pd.DataFrame(profiles).drop(columns=['representative_comments']).to_string(index=False))
if __name__=='__main__':main()
