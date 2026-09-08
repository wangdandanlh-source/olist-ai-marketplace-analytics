"""Processed-only canonical text audit and conservative Unicode/whitespace cleaning."""
from session3_common import *
import sqlite3,re,unicodedata,html
def clean(text):
    x=unicodedata.normalize('NFC',text)
    x=html.unescape(re.sub(r'<[^>]+>',' ',x))
    x=''.join(' ' if unicodedata.category(ch) in ['Cc','Cf'] else ch for ch in x)
    return re.sub(r'\s+',' ',x).strip()
def main():
    inputs={n:sha(ROOT/'data/processed'/n) for n in ['session1.sqlite','session2.sqlite']}
    s2=json.loads((OUT/'session2_summary.json').read_text())
    assert inputs['session1.sqlite']==s2['source_database_sha256'] and inputs['session2.sqlite']==s2['processed_database_sha256']
    c=sqlite3.connect(':memory:',uri=True);c.execute('ATTACH DATABASE ? AS s1',('file:'+(ROOT/'data/processed/session1.sqlite').as_posix()+'?mode=ro',))
    raw=pd.read_sql_query('SELECT review_row_id,order_id,review_comment_message FROM s1.fct_reviews',c)
    canonical=pd.read_sql_query((ROOT/'sql/session3_corpus.sql').read_text(),c);assert canonical.order_id.is_unique
    written_raw=raw.review_comment_message.fillna('').str.strip().ne('');written=canonical.review_text_raw.fillna('').str.strip().ne('')
    corpus=canonical[written].copy();corpus['review_text_clean']=corpus.review_text_raw.map(clean)
    corpus['clean_nonempty']=corpus.review_text_clean.str.len().gt(0)
    corpus['unique_text_id']=corpus.review_text_clean.map(lambda t:hashlib.sha256(t.encode('utf-8')).hexdigest())
    corpus['text_length']=corpus.review_text_clean.str.len();corpus['very_short']=corpus.text_length.le(5)
    corpus['replacement_character']=corpus.review_text_raw.str.contains('\ufffd',regex=False)
    corpus['control_character']=corpus.review_text_raw.map(lambda x:any(unicodedata.category(ch) in ['Cc','Cf'] and ch not in '\r\n\t' for ch in x))
    corpus['rating_group']=np.select([corpus.review_score.le(2),corpus.review_score.eq(3)],['Low Rating','Mixed / Neutral-like'],default='Positive Rating')
    corpus['corpus_role']=np.where(corpus.review_score.le(3),'Primary Issue Corpus','Secondary Positive Corpus')
    corpus['is_core_delivered']=corpus.order_status.eq('delivered')&corpus.purchase_month.between('2017-01','2018-07')
    answer=pd.to_datetime(corpus.review_answer_timestamp);delivery=pd.to_datetime(corpus.order_delivered_customer_date)
    corpus['review_after_delivery']=answer.ge(delivery).astype('Int64').where(delivery.notna()&answer.notna())
    corpus['late_eligible']=corpus.is_core_delivered&corpus.is_late.notna()
    counts=dict(raw_reviews=len(raw),raw_written_reviews=int(written_raw.sum()),canonical_orders=len(canonical),canonical_written_reviews=len(corpus),noncanonical_written_removed=int((written_raw&~raw.review_row_id.isin(canonical.review_row_id)).sum()),canonical_without_text=int((~written).sum()),empty_after_clean=int((~corpus.clean_nonempty).sum()),primary_issue_corpus=int(corpus.review_score.le(3).sum()),positive_corpus=int(corpus.review_score.ge(4).sum()),unique_clean_texts=corpus.unique_text_id.nunique(),duplicate_clean_text_rows=int(corpus.unique_text_id.duplicated().sum()),very_short_texts=int(corpus.very_short.sum()),replacement_char_rows=int(corpus.replacement_character.sum()),control_char_rows=int(corpus.control_character.sum()),core_delivered_written=int(corpus.is_core_delivered.sum()),core_late_eligible_written=int(corpus.late_eligible.sum()))
    audit=pd.DataFrame([dict(metric=k,count=v,denominator=len(raw) if k.startswith('raw_') else len(corpus),note='counts recomputed from Session1 processed; canonical selection before text filter') for k,v in counts.items()]);save(audit,'voc_corpus_audit')
    counts['raw_written_distinct_orders']=int(raw.loc[written_raw,'order_id'].nunique())
    counts['orders_with_old_text_but_latest_without_text']=int(raw.loc[written_raw&~raw.order_id.isin(corpus.order_id),'order_id'].nunique())
    denominators={'raw_written_reviews':len(raw),'canonical_written_reviews':len(canonical),'canonical_without_text':len(canonical),'noncanonical_written_removed':int(written_raw.sum()),'primary_issue_corpus':len(corpus),'positive_corpus':len(corpus),'unique_clean_texts':len(corpus),'duplicate_clean_text_rows':len(corpus),'empty_after_clean':len(corpus),'very_short_texts':len(corpus),'replacement_char_rows':len(corpus),'control_char_rows':len(corpus),'core_delivered_written':len(corpus),'core_late_eligible_written':int(corpus.is_core_delivered.sum())}
    save(pd.DataFrame([dict(metric=k,count=v,denominator=denominators.get(k,np.nan),note='counts recomputed; canonical first, text filter second; missing denominator means absolute count only') for k,v in counts.items()]),'voc_corpus_audit')
    save(corpus.groupby(['corpus_role','rating_group']).size().reset_index(name='n'),'corpus_rating_distribution')
    save(corpus.text_length.describe(percentiles=[.01,.25,.5,.75,.95,.99]).rename_axis('statistic').reset_index(name='characters'),'text_length_audit')
    db=sqlite3.connect(STAGE/'corpus.sqlite');corpus.to_sql('canonical_written',db,index=False,if_exists='replace');db.close();c.close()
    unique=corpus[corpus.clean_nonempty].drop_duplicates('unique_text_id')[['unique_text_id','review_text_clean']].sort_values('unique_text_id').reset_index(drop=True);unique.to_csv(STAGE/'unique_texts.csv',index=False,encoding='utf-8-sig')
    jsave(dict(counts=counts,input_sha256=inputs,cleaning='NFC; strip HTML; unescape entities; replace controls with spaces; whitespace collapse; preserve case/negation',canonical_rule='latest answer timestamp, creation timestamp, review_id, review_row_id as in Session1; select BEFORE checking text'),'corpus_manifest')
    print(json.dumps(counts,indent=2),flush=True)
if __name__=='__main__':main()
