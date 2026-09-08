"""Order-grain descriptive validation; no inferred causal effects or gold labels."""
from session3_common import *
import sqlite3,shutil,joblib
from sklearn.metrics import adjusted_rand_score

def metrics(g):
    v=g[g.late_eligible.eq(1)]
    return dict(n=len(g),average_review_score=g.review_score.mean(),low_rating_rate=g.review_score.le(2).mean(),one_star_rate=g.review_score.eq(1).mean(),late_eligible_n=len(v),late_count=int(v.is_late.sum()),late_delivery_rate=v.is_late.mean(),median_delay_days=v.delay_days.median(),average_delay_days=v.delay_days.mean(),average_delivery_days=v.delivery_days.mean())

def main():
    with sqlite3.connect(STAGE/'corpus.sqlite') as c: corpus=pd.read_sql_query('SELECT * FROM canonical_written',c)
    a=pd.read_csv(STAGE/'cluster_assignments.csv');d=load('ai_taxonomy_decisions')
    z=corpus.merge(a,on='order_id',validate='one_to_one').merge(d[['cluster_id','issue_category','issue_subcategory','responsible_stage','confidence','is_mixed_or_unclear']],on='cluster_id',validate='many_to_one')
    save(z,'voc_labeled');core=z[z.is_core_delivered.eq(1)];primary=z[z.review_score.le(3)]
    rows=[]
    for category,g in z.groupby('issue_category'):
        cg=g[g.is_core_delivered.eq(1)];role='primary' if g.review_score.max()<=3 else 'positive'
        rows.append(dict(issue_category=category,corpus_role=role,share_all=len(g)/len(z),share_role=len(g)/(len(primary) if role=='primary' else len(z)-len(primary)),core_written_n=len(cg),top_categories_core=json.dumps(cg.category.value_counts().head(3).to_dict()),top_months_core=json.dumps(cg.purchase_month.value_counts().head(3).to_dict()),rating_scope='all canonical written in issue; conditioned on rating corpus',late_scope='core delivered written in issue with valid late dates',**metrics(g)))
    save(pd.DataFrame(rows),'issue_metrics')
    base=[];timing=[]
    scopes={'all_core_written':core,'after_delivery_core_written':core[core.review_after_delivery.eq(1)],'primary_core_written':core[core.review_score.le(3)],'positive_core_written':core[core.review_score.ge(4)]}
    for scope,g in scopes.items():base.append(dict(scope=scope,**metrics(g)))
    s2=json.loads((OUT/'session2_summary.json').read_text())
    base.append(dict(scope='session2_all_core_orders',n=s2['core_orders'],late_eligible_n=s2['late_valid_n'],late_count=s2['late_orders'],late_delivery_rate=s2['late_rate']))
    save(pd.DataFrame(base),'validation_baselines')
    for scope in ['all_core_written','after_delivery_core_written']:
        g=scopes[scope]
        for category,h in g.groupby('issue_category'):timing.append(dict(scope=scope,issue_category=category,scope_written_denominator=len(g),issue_rate=len(h)/len(g),**metrics(h)))
    save(pd.DataFrame(timing),'issue_timing_comparison')
    diagnostic=[]
    for dimension in ['category','purchase_month']:
        for value,g in core.groupby(dimension):
            for category in sorted(z.issue_category.unique()):
                h=g[g.issue_category.eq(category)];denprimary=int(g.review_score.le(3).sum())
                diagnostic.append(dict(dimension=dimension,value=value,issue_category=category,issue_count=len(h),written_denominator=len(g),issue_rate=len(h)/len(g),primary_written_denominator=denprimary,primary_conditional_rate=len(h)/denprimary if len(h) and h.review_score.max()<=3 and denprimary else np.nan,meets_minimum=len(g)>=100 and len(h)>=20,threshold='written>=100 and issue>=20; descriptive, no significance ranking'))
    save(pd.DataFrame(diagnostic),'category_month_diagnostics')
    qa=[]
    def check(name,ok,detail):qa.append(dict(check=name,status='PASS' if bool(ok) else 'FAIL',detail=detail))
    check('canonical order unique',z.order_id.is_unique,len(z))
    check('text nonempty',z.review_text_clean.fillna('').str.strip().ne('').all(),'All retained canonical text nonempty')
    check('order and category joins preserve corpus',len(z)==len(corpus) and set(z.order_id)==set(corpus.order_id),len(corpus))
    check('cluster map one per cluster',d.cluster_id.is_unique and d.issue_category.notna().all(),len(d))
    check('cluster assignments complete and legal',a.order_id.is_unique and set(z.cluster_id)==set(range(8))|{100,101,102} and z.cluster_id.notna().all(),sorted(z.cluster_id.unique().tolist()))
    check('rating corpus assignments respected',(z.loc[z.cluster_id.lt(100),'review_score']<=3).all() and (z.loc[z.cluster_id.ge(100),'review_score']>=4).all(),'No rating treated as sentiment truth')
    check('all issues mapped',z[['issue_category','issue_subcategory','responsible_stage']].notna().all().all(),z.issue_category.nunique())
    check('mixed retained',z.is_mixed_or_unclear.sum()>0,int(z.is_mixed_or_unclear.sum()))
    check('money not duplicated',int(z.merchandise_cents.sum())==int(corpus.merchandise_cents.sum()),int(z.merchandise_cents.sum()))
    check('late eligibility exact',(z.late_eligible.eq(1)==(z.is_core_delivered.eq(1)&z.is_late.notna())).all(),int(z.late_eligible.sum()))
    check('late counts reconcile',sum(r['late_eligible_n'] for r in rows)==int(z.late_eligible.sum()) and sum(r['late_count'] for r in rows)==int(core.is_late.sum()),'Disjoint categories')
    check('issue counts reconcile',sum(r['n'] for r in rows)==len(z),'Single main label')
    answer=pd.to_datetime(z.review_answer_timestamp);delivery=pd.to_datetime(z.order_delivered_customer_date);valid=answer.notna()&delivery.notna()
    check('timing independently reconciled',z.loc[valid,'review_after_delivery'].eq(answer[valid].ge(delivery[valid]).astype(int)).all() and z.loc[~valid,'review_after_delivery'].isna().all(),'Answer timestamp >= actual receipt; missing remains unknown')
    unique=pd.read_csv(STAGE/'unique_texts.csv');x=np.load(STAGE/'embeddings.npy');manifest=json.loads((OUT/'session3_model_manifest.json').read_text())
    check('embedding rows dimensions finite',x.shape==(len(unique),384) and np.isfinite(x).all(),x.shape)
    check('embedding index mapping',unique.unique_text_id.is_unique and z.unique_text_id.isin(unique.unique_text_id).all(),'Dedup text mapped back to orders')
    check('embedding hashes',sha(STAGE/'embeddings.npy')==manifest['embedding_sha256'] and sha(STAGE/'unique_texts.csv')==manifest['text_index_sha256'],'Matrix and ordered index pinned')
    reps=load('cluster_representatives');joined=reps.merge(z,on='order_id',suffixes=('_rep','_label'),validate='many_to_one')
    check('representatives correct cluster and raw text',len(joined)==len(reps) and joined.cluster_id_rep.eq(joined.cluster_id_label).all() and joined.review_text_raw_rep.eq(joined.review_text_raw_label).all(),'165 examples checked')
    check('ten centroid and five random per cluster',reps.groupby(['cluster_id','selection']).size().unstack().eq([10,5]).all().all(),'11 clusters')
    ix=dict(zip(unique.unique_text_id,range(len(unique))));nearest_ok=True
    models={False:joblib.load(STAGE/'kmeans_k8_seed42.joblib'),True:joblib.load(STAGE/'positive_kmeans.joblib')}
    for cid,g in z.groupby('cluster_id'):
        distances=np.linalg.norm(x[g.unique_text_id.map(ix)]-models[cid>=100].cluster_centers_[cid-100 if cid>=100 else cid],axis=1)
        expected=g.assign(distance=distances).sort_values(['distance','review_row_id']).drop_duplicates('unique_text_id').head(10).order_id.tolist()
        actual=reps[reps.cluster_id.eq(cid)&reps.selection.eq('centroid_nearest')].sort_values('rank').order_id.tolist();nearest_ok &= expected==actual
    check('centroid selection recomputed',nearest_ok,'Euclidean nearest distinct texts to fitted centroids')
    manual=load('manual_review_sample');mj=manual.merge(z,on='order_id',validate='one_to_one')
    check('manual sample coverage original and labels',manual.groupby('AI Issue').size().ge(10).all() and mj['Portuguese Original'].eq(mj.review_text_raw).all() and mj['AI Issue'].eq(mj.issue_category).all(),'90 rows; 10 per 9 final categories')
    check('manual not falsely gold',manual.human_gold_status.eq('UNLABELED').all() and manual[['Human Issue','Human Agreement','Human Reviewer']].isna().all().all() and manual['Short AI English/Chinese Translation'].notna().all(),'Translations AI generated; no accuracy metrics')
    selection=load('cluster_selection');ariok=True
    for k,g in selection.groupby('k'):
        labels=[np.load(STAGE/f'labels_k{k}_seed{s}.npy') for s in [42,7,2026]]
        aris=[adjusted_rand_score(labels[i],labels[j]) for i,j in [(0,1),(0,2),(1,2)]]
        ariok &= np.isclose(np.mean(aris),g.ari_mean.iloc[0])
    check('k and seed coverage stability recomputed',len(selection)==15 and selection.groupby('k').seed.nunique().eq(3).all() and ariok,'5 K values x 3 seeds')
    counts=json.loads((OUT/'session3_corpus_manifest.json').read_text())
    check('raw canonical text reconciliation',counts['counts']['raw_written_reviews']-counts['counts']['noncanonical_written_removed']==len(z),'40950 - 202 = 40748')
    check('source databases unchanged',all(sha(ROOT/'data/processed'/n)==h for n,h in counts['input_sha256'].items()),counts['input_sha256'])
    check('diagnostic rates denominators',all(0<=r['issue_rate']<=1 and r['issue_count']<=r['written_denominator'] for r in diagnostic),'Exclusive order category; written denominator per group')
    for name,detail in [('No human gold','No Accuracy/Precision/Recall/F1; translations not human validation'),('Weak cluster separation','K8 mean silhouette .0670; ARI .4003; labels approximate'),('High mixed rate','Broad product category included as mixed; not a pure defect classifier'),('Rating-conditioned sample','Score<=3 discovery cannot independently predict low rating'),('Review self-selection and Portuguese','Written reviews select themselves; idioms/typos/negations can confuse multilingual model'),('Timing and noncausal validation','External check not blinded; naming saw aggregate late statistics; not causal or accuracy'),('Single label and representative bias','Multiple complaints collapsed; nearest examples overstate purity; no random gold audit'),('Local raw text privacy','Full text and representatives may contain personal details; excluded from review archive and git')]:qa.append(dict(check=name,status='WARN',detail=detail))
    q=pd.DataFrame(qa);save(q,'qa_results')
    jsave(dict(rows=len(z),primary_n=len(primary),positive_n=len(z)-len(primary),mixed_primary_n=int(primary.is_mixed_or_unclear.sum()),mixed_primary_rate=float(primary.is_mixed_or_unclear.mean()),mixed_all_rate=float(z.is_mixed_or_unclear.mean()),qa=q.status.value_counts().to_dict(),decision='CONDITIONAL GO',source_sha256=counts['input_sha256']),'summary')
    assert not q.status.eq('FAIL').any(),q[q.status.eq('FAIL')].to_string()
    with sqlite3.connect(STAGE/'session3.sqlite') as c:z.to_sql('voc_labeled',c,index=False,if_exists='replace');c.execute('CREATE UNIQUE INDEX IF NOT EXISTS order_unique ON voc_labeled(order_id)')
    shutil.copy2(STAGE/'session3.sqlite',ROOT/'data/processed/session3.sqlite')
    manifest['clustering_library_versions']={'scikit-learn':'1.7.2','joblib':'1.5.2'};manifest['library_versions_note']='Embedding-time environment snapshot lists sklearn 1.9.0, which was not used for embedding or final clustering; final clustering uses isolated 1.7.2.';jsave(manifest,'model_manifest')
    print(pd.DataFrame(rows)[['issue_category','n','low_rating_rate','late_eligible_n','late_delivery_rate','median_delay_days']].to_string(index=False));print(pd.DataFrame(base).to_string(index=False));print(q.status.value_counts().to_dict())
if __name__=='__main__':main()
