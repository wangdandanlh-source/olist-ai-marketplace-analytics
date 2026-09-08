"""Session 1 deterministic audit, modeling and QA-gated publication (no analysis UI)."""
from pathlib import Path
import hashlib,json,sqlite3,shutil,sys,datetime,subprocess,os
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs'; DOC=ROOT/'docs'; STAGE=ROOT/'data/interim'
NAMES={'customers':'olist_customers_dataset.csv','geolocation':'olist_geolocation_dataset.csv','orders':'olist_orders_dataset.csv','items':'olist_order_items_dataset.csv','payments':'olist_order_payments_dataset.csv','reviews':'olist_order_reviews_dataset.csv','products':'olist_products_dataset.csv','sellers':'olist_sellers_dataset.csv','translation':'product_category_name_translation.csv','deals':'olist_closed_deals_dataset.csv','leads':'olist_marketing_qualified_leads_dataset.csv'}
KEYS={'customers':['customer_id'],'orders':['order_id'],'items':['order_id','order_item_id'],'payments':['order_id','payment_sequential'],'reviews':['review_id','order_id'],'products':['product_id'],'sellers':['seller_id'],'translation':['product_category_name'],'deals':['mql_id'],'leads':['mql_id']}
DATES={'orders':['order_purchase_timestamp','order_approved_at','order_delivered_carrier_date','order_delivered_customer_date','order_estimated_delivery_date'],'items':['shipping_limit_date'],'reviews':['review_creation_date','review_answer_timestamp'],'deals':['won_date'],'leads':['first_contact_date']}
EXPECTED={'customers':99441,'geolocation':1000163,'orders':99441,'items':112650,'payments':103886,'reviews':99224,'products':32951,'sellers':3095,'translation':71,'deals':842,'leads':8000}
def csv(df,name): df.to_csv(OUT/name,index=False,encoding='utf-8-sig',date_format='%Y-%m-%d %H:%M:%S')
def md(df):
    def clean(x): return str(x).replace('|','/').replace('\n',' ') if pd.notna(x) else 'NULL'
    return '| '+' | '.join(map(str,df.columns))+' |\n| '+' | '.join(['---']*len(df.columns))+' |\n'+'\n'.join('| '+' | '.join(clean(x) for x in row)+' |' for row in df.itertuples(index=False,name=None))
def write(name,text): (DOC/name).write_text(text,encoding='utf-8')
def main():
    raw={}; fields=[]; manifest=[]; quality=[]; ranges=[]; checks=[]
    def qa(name,ok,actual,expected,severity='ERROR'):
        checks.append(dict(test=name,status='PASS' if bool(ok) else ('WARN' if severity=='WARNING' else 'FAIL'),actual=str(actual),expected=str(expected)))
    def warn(issue,count,impact,action,table='cross_table'):
        if int(count)==0: return
        quality.append(dict(table=table,issue=issue,count=int(count),severity='WARNING',impact=impact,action=action))
    acquisition={x['dataset']:x for x in json.loads((OUT/'acquisition.json').read_text(encoding='utf-8'))}
    for name,filename in NAMES.items():
        p=next((ROOT/'data/raw').rglob(filename)); dataset=p.parent.name
        header=pd.read_csv(p,nrows=0).columns
        types={c:'string' for c in header if c.endswith('_id') or 'zip_code_prefix' in c}
        if name=='items': types.pop('order_item_id',None)
        d=pd.read_csv(p,dtype=types); raw[name]=d
        manifest.append(dict(dataset=dataset,filename=filename,rows=len(d),columns=len(d.columns),file_size=p.stat().st_size,source=acquisition[dataset]['source'],sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        official=json.loads((OUT/(dataset+'_metadata.json')).read_text())['datasetFiles']
        advertised=next(x['totalBytes'] for x in official if x['name']==filename)
        qa('official_file_size_'+name,p.stat().st_size==advertised,p.stat().st_size,advertised)
        qa('snapshot_rows_'+name,len(d)==EXPECTED[name],len(d),EXPECTED[name])
        if name in KEYS:
            key=KEYS[name]; n=int(d.duplicated(key).sum()+d[key].isna().any(axis=1).sum())
            qa('raw_pk_'+name,n==0,n,0)
        duplicates=int(d.duplicated().sum())
        if duplicates: warn('exact_duplicate_rows',duplicates,'地理点重复影响坐标权重','保留原始数据；地理聚合先去全行重复',name)
        for c in d:
            s=d[c]; num=pd.api.types.is_numeric_dtype(s)
            fields.append(dict(table=name,filename=filename,field=c,dtype=str(s.dtype),missing=int(s.isna().sum()),missing_rate=float(s.isna().mean()),distinct=int(s.nunique()),min=s.min() if num else '',max=s.max() if num else '',negative=int((s<0).sum()) if num else '',zero=int((s==0).sum()) if num else ''))
        for c in DATES.get(name,[]):
            before=d[c]; fmt='%Y-%m-%d' if c=='first_contact_date' else '%Y-%m-%d %H:%M:%S'
            parsed=pd.to_datetime(before,format=fmt,errors='coerce')
            failures=int((before.notna()&parsed.isna()).sum()); qa('date_parse_'+name+'.'+c,failures==0,failures,0)
            qa('date_range_'+name+'.'+c,parsed.min()<parsed.max(),f'{parsed.min()} .. {parsed.max()}','min < max')
            qa('multi_month_'+name+'.'+c,parsed.dt.to_period('M').nunique()>1,parsed.dt.to_period('M').nunique(),'>1')
            d[c]=parsed
            ranges.append(dict(table=name,field=c,min_date=str(parsed.min()),max_date=str(parsed.max()),nulls=int(parsed.isna().sum()),parse_errors=failures))
        print('Audited',name,len(d),flush=True)
    csv(pd.DataFrame(manifest),'data_manifest.csv'); csv(pd.DataFrame(fields),'field_audit.csv'); csv(pd.DataFrame(ranges),'date_ranges.csv')
    o=raw['orders']; i=raw['items']; p=raw['payments']; r=raw['reviews']; c=raw['customers']; s=raw['sellers']; d=raw['deals']; l=raw['leads']; g=raw['geolocation']
    fks=[]
    relations=[('orders','customer_id','customers','customer_id'),('items','order_id','orders','order_id'),('items','product_id','products','product_id'),('items','seller_id','sellers','seller_id'),('payments','order_id','orders','order_id'),('reviews','order_id','orders','order_id'),('deals','mql_id','leads','mql_id'),('deals','seller_id','sellers','seller_id'),('products','product_category_name','translation','product_category_name'),('customers','customer_zip_code_prefix','geolocation','geolocation_zip_code_prefix'),('sellers','seller_zip_code_prefix','geolocation','geolocation_zip_code_prefix')]
    for child,col,parent,key in relations:
        x=raw[child][col]; non=x.notna(); missing=int((non&~x.isin(raw[parent][key])).sum()); rate=float(x[non].isin(raw[parent][key]).mean())
        fks.append(dict(child=child,field=col,parent=parent,parent_field=key,non_null_rows=int(non.sum()),unmatched_rows=missing,match_rate=rate,parent_key_unique=raw[parent][key].is_unique))
        optional=child in ['deals','products','customers','sellers'] and parent in ['sellers','translation','geolocation']
        qa('fk_'+child+'_'+col,missing==0,missing,0,'WARNING' if optional else 'ERROR')
        if missing: warn('unmatched_'+col,missing,'不可假定全量覆盖','LEFT JOIN 保留；附匹配标记',child)
    csv(pd.DataFrame(fks),'foreign_key_audit.csv')
    customer_order=o.merge(c[['customer_id','customer_unique_id']],on='customer_id',validate='many_to_one')
    all_freq=customer_order.groupby('customer_unique_id').size(); delivered=customer_order[customer_order.order_status.eq('delivered')]; freq=delivered.groupby('customer_unique_id').size()
    qa('customer_id_one_order',o.customer_id.is_unique,o.customer_id.nunique(),len(o))
    qa('reasonable_orders',90000<len(o)<110000,len(o),'90000..110000')
    qa('reasonable_users',90000<c.customer_unique_id.nunique()<=len(c),c.customer_unique_id.nunique(),'90000..orders')
    counts=i.groupby('order_id').size(); paycounts=p.groupby('order_id').size(); reviewcounts=r.groupby('order_id').size()
    dist=counts.reindex(o.order_id,fill_value=0).value_counts().sort_index().rename_axis('items_per_order').reset_index(name='orders'); csv(dist,'items_per_order_distribution.csv')
    months=o.groupby(o.order_purchase_timestamp.dt.to_period('M')).size().reindex(pd.period_range(o.order_purchase_timestamp.min(),o.order_purchase_timestamp.max(),freq='M'),fill_value=0).rename_axis('month').reset_index(name='orders')
    months['coverage_flag']=np.where(months.month.astype(str).between('2017-01','2018-07'),'core_candidate',np.where(months.month.astype(str)<'2017-01','startup_or_sparse','right_boundary_censored'))
    months['month']=months.month.astype(str)
    date_months=[]
    for col in DATES['orders']:
        series=o[col].dropna().dt.strftime('%Y-%m').value_counts().sort_index()
        date_months.extend(dict(date_field=col,month=month,orders=int(n)) for month,n in series.items())
    csv(pd.DataFrame(date_months),'monthly_counts_all_order_dates.csv')
    csv(months,'monthly_order_counts.csv'); csv(o.order_status.value_counts().rename_axis('order_status').reset_index(name='orders'),'order_status_counts.csv')
    for name,col in [('items','price'),('items','freight_value'),('payments','payment_value'),('deals','declared_monthly_revenue'),('deals','declared_product_catalog_size')]:
        x=raw[name][col]; qa('nonnegative_'+name+'_'+col,not (x.dropna()<0).any(),int((x<0).sum()),0)
    qa('review_score_range',r.review_score.between(1,5).all(),f'{r.review_score.min()}..{r.review_score.max()}','1..5')
    for col in ['price','freight_value']:
        qa('money_precision_'+col,np.allclose(i[col]*100,np.round(i[col]*100)),float((i[col]*100-np.round(i[col]*100)).abs().max()),'<0.000001 cents')
    qa('money_precision_payment',np.allclose(p.payment_value*100,np.round(p.payment_value*100)),float((p.payment_value*100-np.round(p.payment_value*100)).abs().max()),'<0.000001 cents')
    i=i.copy(); p=p.copy(); i['price_cents']=(i.price*100).round().astype('int64'); i['freight_cents']=(i.freight_value*100).round().astype('int64'); p['payment_cents']=(p.payment_value*100).round().astype('int64')
    ia=i.groupby('order_id').agg(merchandise_cents=('price_cents','sum'),freight_cents=('freight_cents','sum'),item_count=('order_item_id','size'),seller_count=('seller_id','nunique'))
    pa=p.groupby('order_id').agg(payment_cents=('payment_cents','sum'),payment_count=('payment_sequential','size'))
    r=r.copy(); r['review_row_id']=np.arange(1,len(r)+1); r['has_text']=r.review_comment_message.fillna('').str.strip().ne('')
    latest=r.sort_values(['order_id','review_answer_timestamp','review_creation_date','review_id','review_row_id'],kind='stable').drop_duplicates('order_id',keep='last')
    fo=customer_order.merge(ia,on='order_id',how='left',validate='one_to_one').merge(pa,on='order_id',how='left',validate='one_to_one')
    for col in ['merchandise_cents','freight_cents','item_count','seller_count','payment_cents','payment_count']: fo[col]=fo[col].astype('Int64')
    fo['has_items']=fo.item_count.notna(); fo['has_payment']=fo.payment_count.notna(); fo['is_delivered']=fo.order_status.eq('delivered')
    for target,end,start in [('approval_days','order_approved_at','order_purchase_timestamp'),('carrier_handoff_days','order_delivered_carrier_date','order_approved_at'),('delivery_days','order_delivered_customer_date','order_purchase_timestamp'),('carrier_transit_days','order_delivered_customer_date','order_delivered_carrier_date')]:
        delta=(fo[end]-fo[start]).dt.total_seconds()/86400
        fo[target+'_invalid']=delta.lt(0); fo[target]=delta.where(delta.ge(0))
        warn('negative_'+target,int(delta.lt(0).sum()),'时间顺序异常','原时间保留；对应耗时设为空并排除该指标分母','orders')
    valid=fo.is_delivered&fo.delivery_days.notna()&fo.order_estimated_delivery_date.notna()
    fo['estimated_gap_days']=(fo.order_delivered_customer_date.dt.normalize()-fo.order_estimated_delivery_date.dt.normalize()).dt.days.where(valid)
    fo['is_late']=fo.estimated_gap_days.gt(0).astype('Int64').where(valid)
    reconciliation=fo[['order_id','order_status','merchandise_cents','freight_cents','payment_cents','has_items','has_payment']].copy()
    reconciliation['difference_cents']=reconciliation.payment_cents-reconciliation.merchandise_cents-reconciliation.freight_cents
    reconciliation['comparable']=reconciliation.has_items&reconciliation.has_payment
    reconciliation['within_one_cent']=reconciliation.difference_cents.abs().le(1)
    csv(reconciliation,'payment_reconciliation.csv')
    mismatches=reconciliation[reconciliation.comparable&reconciliation.difference_cents.abs().gt(1)]
    warn('payment_vs_items_plus_freight_difference_gt_1cent',len(mismatches),'支付不等于商品加运费；无退款/折扣流水不能归因','保留差异明细；严禁修补金额')
    # A real, fully materialized bad join, for evidence only.
    naive=o[['order_id']].merge(i[['order_id','price_cents','freight_cents']],on='order_id',how='left').merge(p[['order_id','payment_cents']],on='order_id',how='left').merge(r[['order_id','review_row_id']],on='order_id',how='left')
    predicted=int((counts.reindex(o.order_id,fill_value=0).clip(lower=1).to_numpy()*paycounts.reindex(o.order_id,fill_value=0).clip(lower=1).to_numpy()*reviewcounts.reindex(o.order_id,fill_value=0).clip(lower=1).to_numpy()).sum())
    qa('naive_join_cardinality_formula',len(naive)==predicted,len(naive),predicted)
    qa('safe_order_join_cardinality',len(fo)==len(o) and fo.order_id.is_unique,len(fo),len(o))
    candidates=counts.index[(counts>1)&(paycounts.reindex(counts.index,fill_value=0)>1)]
    example_id=sorted(candidates)[0]; ex=naive[naive.order_id.eq(example_id)]; good=fo[fo.order_id.eq(example_id)].iloc[0]
    join_evidence=dict(order_id=example_id,items=int(counts[example_id]),payments=int(paycounts[example_id]),reviews=int(reviewcounts.get(example_id,0)),naive_rows=len(ex),correct_merchandise_cents=int(good.merchandise_cents),naive_merchandise_cents=int(ex.price_cents.sum()),correct_payment_cents=int(good.payment_cents),naive_payment_cents=int(ex.payment_cents.sum()),all_naive_rows=len(naive),all_correct_merchandise_cents=int(i.price_cents.sum()),all_naive_merchandise_cents=int(naive.price_cents.sum()),all_correct_payment_cents=int(p.payment_cents.sum()),all_naive_payment_cents=int(naive.payment_cents.sum()),multi_items_multi_pay_orders=len(candidates))
    qa('naive_join_inflation_detected',join_evidence['naive_merchandise_cents']>join_evidence['correct_merchandise_cents'] and join_evidence['naive_payment_cents']>join_evidence['correct_payment_cents'],join_evidence,'inflation in both money measures')
    (OUT/'join_evidence.json').write_text(json.dumps(join_evidence,indent=2),encoding='utf-8')
    del naive
    # Keep funnel-only sellers in the conformed dimension, without invented attributes.
    seller_dim=s.merge(d[['seller_id']].drop_duplicates(),on='seller_id',how='outer',indicator=True,validate='one_to_one')
    seller_dim['in_ecommerce']=seller_dim['_merge'].ne('right_only'); seller_dim['in_closed_deals']=seller_dim['_merge'].ne('left_only'); seller_dim=seller_dim.drop(columns='_merge')
    funnel=l.merge(d,on='mql_id',how='left',validate='one_to_one'); funnel['is_closed']=funnel.seller_id.notna()
    ttc=(funnel.won_date-funnel.first_contact_date).dt.total_seconds()/86400; funnel['time_to_close_days']=ttc.where(ttc.ge(0))
    warn('won_before_contact',int(ttc.lt(0).sum()),'漏斗时间顺序异常','排除 Time to Close 分母','deals')
    links=d[['mql_id','seller_id','won_date']].copy(); links['matched_seller_dimension']=links.seller_id.isin(s.seller_id); links['matched_order_items']=links.seller_id.isin(i.seller_id)
    csv(links,'seller_funnel_link_test.csv'); matched=int(links.matched_order_items.sum()); unique_deal_sellers=d.seller_id.nunique()
    qa('deal_seller_unique',unique_deal_sellers==len(d),unique_deal_sellers,len(d))
    qa('seller_funnel_match_baseline',matched==380,matched,380)
    # Reliability only: eligibility windows, no 30/60/90 outcome/growth estimates.
    so=i[['seller_id','order_id']].drop_duplicates().merge(o[['order_id','order_purchase_timestamp','order_status']],on='order_id',validate='many_to_one')
    sd=so[so.order_status.eq('delivered')]; first_all=so.groupby('seller_id').order_purchase_timestamp.min(); first_delivered=sd.groupby('seller_id').order_purchase_timestamp.min()
    windows=links.copy(); windows['first_observed_order']=windows.seller_id.map(first_all); windows['first_observed_delivered_order']=windows.seller_id.map(first_delivered)
    post=so.merge(d[['seller_id','won_date']],on='seller_id',validate='many_to_one'); post=post[post.order_purchase_timestamp.ge(post.won_date)]
    first_post=post.groupby('seller_id').order_purchase_timestamp.min(); windows['first_order_on_or_after_won']=windows.seller_id.map(first_post)
    windows['pre_won_order']=windows.first_observed_order.lt(windows.won_date)
    cutoff=pd.Timestamp('2018-08-01'); windows['conservative_observation_end_exclusive']=cutoff
    for days in [30,60,90]:
        windows[f'won_{days}d_calendar_complete']=windows.won_date.add(pd.Timedelta(days=days)).le(cutoff)&windows.won_date.ge(pd.Timestamp('2017-01-01'))
        windows[f'won_{days}d_computable']=windows[f'won_{days}d_calendar_complete']&windows.matched_order_items&~windows.pre_won_order
        windows[f'first_order_{days}d_computable']=windows.first_order_on_or_after_won.add(pd.Timedelta(days=days)).le(cutoff)&windows.first_order_on_or_after_won.ge(pd.Timestamp('2017-01-01'))&~windows.pre_won_order
    csv(windows,'seller_window_eligibility.csv')
    warn('funnel_sellers_unmatched',len(d)-matched,'不可把未匹配解释为零订单','商家增长仅限匹配且观察窗完整子样本')
    warn('seller_orders_before_won',int(windows.pre_won_order.sum()),'won_date 不等于真实入驻时点','异常商家不用于获客后增长比较')
    warn('review_id_non_unique',int(r.review_id.duplicated().sum()),'review_id 不能独立作主键','用来源行号作为稳定快照主键；保留所有评论','reviews')
    warn('multiple_reviews_per_order',int(reviewcounts.gt(1).sum()),'评论平均数存在加权偏差','订单体验指标只用确定性最新一条','reviews')
    warn('review_message_missing',int((~r.has_text).sum()),'文本样本有选择偏差','保留评分；后续 VOC 只读有文本子集','reviews')
    warn('geolocation_prefix_not_unique',int(g.geolocation_zip_code_prefix.duplicated().sum()),'直接连接会膨胀','先去全行重复、再按邮编取有效坐标中位数','geolocation')
    valid_coord=g.geolocation_lat.between(-90,90)&g.geolocation_lng.between(-180,180)
    brazil_box=g.geolocation_lat.between(-34,6)&g.geolocation_lng.between(-74,-28)
    warn('coordinates_outside_brazil_screen',int((~brazil_box).sum()),'粗略边界筛查，非国界判定','保留原值；聚合坐标只取粗框内有效点','geolocation')
    gg=g.drop_duplicates().copy(); gg['valid_coord']=gg.geolocation_lat.between(-34,6)&gg.geolocation_lng.between(-74,-28)
    gg.loc[~gg.valid_coord,['geolocation_lat','geolocation_lng']]=np.nan
    geo=gg.groupby('geolocation_zip_code_prefix',as_index=False).agg(latitude=('geolocation_lat','median'),longitude=('geolocation_lng','median'),distinct_source_points=('geolocation_city','size'),city_variants=('geolocation_city','nunique'),state_variants=('geolocation_state','nunique'))
    warn('geo_prefix_multiple_states',int(geo.state_variants.gt(1).sum()),'邮编前缀不是精确地址','地区名称以客户/商家维表为准','geolocation')
    warn('zero_payment_installments',int(p.payment_installments.eq(0).sum()),'分期字段异常或特殊记录','保留且不用于标准分期分布','payments')
    warn('shipping_limit_beyond_order_estimate_horizon',int(i.shipping_limit_date.gt(o.order_estimated_delivery_date.max()).sum()),'商品发货截止出现超出订单整体时间范围的日期（最大到2020年）','原值保留；不能用该字段延长经营观察窗','items')
    warn('boundary_months',int((months.coverage_flag!='core_candidate').sum()),'边界/稀疏月份不可解释为业务下降','默认趋势候选窗 2017-01 至 2018-07；不声称全覆盖','orders')
    sample=r.loc[r.has_text,['review_row_id','review_comment_message']].sample(n=min(40,int(r.has_text.sum())),random_state=42)
    csv(sample,'review_language_sample.csv')
    product=raw['products'].merge(raw['translation'],on='product_category_name',how='left',validate='many_to_one')
    # Cover every observed date role, including won_date beyond order coverage.
    minimum=min(raw[t][col].min() for t,cols in DATES.items() for col in cols)
    maximum=max(raw[t][col].max() for t,cols in DATES.items() for col in cols)
    date=pd.DataFrame({'date':pd.date_range(minimum.normalize(),maximum.normalize(),freq='D')}); date['month']=date.date.dt.strftime('%Y-%m'); date['year']=date.date.dt.year; date['month_number']=date.date.dt.month; date['month_sort']=date.date.dt.year*100+date.date.dt.month
    tables={'fct_orders':fo,'fct_order_items':i,'fct_payments':p,'fct_reviews':r,'fct_marketing_leads':funnel,'fct_closed_deals':d,'dim_customers':c,'dim_products':product,'dim_sellers':seller_dim,'dim_date':date,'dim_geolocation_prefix':geo,'order_review_summary':latest}
    db=STAGE/'session1.sqlite'
    if db.exists(): db.unlink()
    conn=sqlite3.connect(db)
    for name,frame in tables.items(): frame.to_sql(name,conn,index=False,if_exists='replace')
    conn.executescript((ROOT/'sql/metric_layer.sql').read_text(encoding='utf-8')); conn.commit()
    for name in ['monthly_marketplace_metrics','customer_metrics','seller_metrics','category_metrics','review_metrics','fulfillment_metrics','seller_funnel_metrics']: tables[name]=pd.read_sql_query('SELECT * FROM '+name,conn)
    processed_keys={'fct_orders':['order_id'],'fct_order_items':['order_id','order_item_id'],'fct_payments':['order_id','payment_sequential'],'fct_reviews':['review_row_id'],'fct_marketing_leads':['mql_id'],'fct_closed_deals':['mql_id'],'dim_customers':['customer_id'],'dim_products':['product_id'],'dim_sellers':['seller_id'],'dim_date':['date'],'dim_geolocation_prefix':['geolocation_zip_code_prefix'],'order_review_summary':['order_id'],'monthly_marketplace_metrics':['month'],'customer_metrics':['customer_unique_id'],'seller_metrics':['seller_id'],'category_metrics':['month','category'],'review_metrics':['month'],'fulfillment_metrics':['month'],'seller_funnel_metrics':['contact_month','origin']}
    for name,frame in tables.items():
        key=processed_keys[name]; qa('processed_pk_'+name,not frame.duplicated(key).any() and not frame[key].isna().any().any(),int(frame.duplicated(key).sum()),0)
    for name,source in [('fct_orders','orders'),('fct_order_items','items'),('fct_payments','payments'),('fct_reviews','reviews'),('fct_marketing_leads','leads'),('fct_closed_deals','deals'),('dim_customers','customers'),('dim_products','products')]: qa('processed_rows_'+name,len(tables[name])==len(raw[source]),len(tables[name]),len(raw[source]))
    qa('safe_gmv_reconciliation',fo.merchandise_cents.sum()==i.price_cents.sum(),int(fo.merchandise_cents.sum()),int(i.price_cents.sum()))
    qa('safe_freight_reconciliation',fo.freight_cents.sum()==i.freight_cents.sum(),int(fo.freight_cents.sum()),int(i.freight_cents.sum()))
    qa('safe_payment_reconciliation',fo.payment_cents.sum()==p.payment_cents.sum(),int(fo.payment_cents.sum()),int(p.payment_cents.sum()))
    target=int(fo.loc[fo.is_delivered,'merchandise_cents'].sum())
    for layer in ['monthly_marketplace_metrics','customer_metrics','seller_metrics','category_metrics']: qa('metric_gmv_'+layer,int(tables[layer].merchandise_cents.sum())==target,int(tables[layer].merchandise_cents.sum()),target)
    qa('metric_payment_monthly',tables['monthly_marketplace_metrics'].payment_cents.sum()==fo.loc[fo.is_delivered,'payment_cents'].sum(),int(tables['monthly_marketplace_metrics'].payment_cents.sum()),int(fo.loc[fo.is_delivered,'payment_cents'].sum()))
    qa('metric_orders_monthly',tables['monthly_marketplace_metrics'].delivered_orders.sum()==len(delivered),int(tables['monthly_marketplace_metrics'].delivered_orders.sum()),len(delivered))
    qa('metric_funnel_mql',tables['seller_funnel_metrics'].mql.sum()==len(l),int(tables['seller_funnel_metrics'].mql.sum()),len(l))
    qa('metric_funnel_deals',tables['seller_funnel_metrics'].closed_deals.sum()==len(d),int(tables['seller_funnel_metrics'].closed_deals.sum()),len(d))
    qa('month_sort',tables['monthly_marketplace_metrics'].month.is_monotonic_increasing,tables['monthly_marketplace_metrics'].month.tolist(),'ascending YYYY-MM')
    qa('month_format',tables['monthly_marketplace_metrics'].month.str.fullmatch(r'\d{4}-\d{2}').all(),'YYYY-MM','YYYY-MM')
    # Accounting identity includes non-comparable records, never forces payment=GMV+freight.
    both=reconciliation.comparable; residual=int(reconciliation.loc[both,'difference_cents'].sum())
    pay_only=int(reconciliation.loc[~reconciliation.has_items,'payment_cents'].sum()); items_only=int((reconciliation.loc[~reconciliation.has_payment,'merchandise_cents']+reconciliation.loc[~reconciliation.has_payment,'freight_cents']).sum())
    observed=int(p.payment_cents.sum()-i.price_cents.sum()-i.freight_cents.sum())
    qa('payment_difference_bridge',observed==residual+pay_only-items_only,observed,residual+pay_only-items_only)
    qa('delivered_item_coverage',fo.loc[fo.is_delivered,'has_items'].all(),int((~fo.loc[fo.is_delivered,'has_items']).sum()),0)
    qa('date_dimension_contiguous',len(date)==(maximum.normalize()-minimum.normalize()).days+1,len(date),(maximum.normalize()-minimum.normalize()).days+1)
    registry=[]
    lineage={'fct_orders':'orders + customers + items(order aggregate) + payments(order aggregate)','fct_order_items':'items','fct_payments':'payments','fct_reviews':'reviews','fct_marketing_leads':'leads LEFT JOIN deals','fct_closed_deals':'deals','dim_customers':'customers','dim_products':'products LEFT JOIN translation','dim_sellers':'sellers UNION deals.seller_id','dim_date':'all parsed date fields','dim_geolocation_prefix':'geolocation','order_review_summary':'reviews','monthly_marketplace_metrics':'fct_orders','customer_metrics':'fct_orders','seller_metrics':'fct_order_items + fct_orders','category_metrics':'fct_order_items + fct_orders + dim_products','review_metrics':'order_review_summary + fct_orders','fulfillment_metrics':'fct_orders','seller_funnel_metrics':'fct_marketing_leads'}
    for name,frame in tables.items():
        path=STAGE/(name+'.csv'); frame.to_csv(path,index=False,encoding='utf-8-sig',date_format='%Y-%m-%d %H:%M:%S')
        check=pd.read_csv(path,dtype={col:'string' for col in processed_keys[name]})
        qa('export_rows_'+name,len(check)==len(frame),len(check),len(frame))
        registry.append(dict(table=name,grain=' + '.join(processed_keys[name]),source=lineage[name],transformation='sql/metric_layer.sql' if name.endswith('_metrics') else 'src/build.py; details: docs/data_model.md',rows=len(frame),qa_status='PENDING',sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    conn.close()
    csv(pd.DataFrame(quality),'data_quality_log.csv'); csv(pd.DataFrame(checks),'qa_results.csv')
    failed=sum(x['status']=='FAIL' for x in checks)
    if failed: raise RuntimeError(f'{failed} blocking QA failures. Nothing published; see outputs/qa_results.csv')
    env=os.environ.copy(); env['OLIST_QA_DB']=str(db); env['PYTHONIOENCODING']='utf-8'
    independent=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tests/test_session1.py')],env=env,capture_output=True,text=True,encoding='utf-8')
    (OUT/'independent_tests.log').write_text(independent.stdout+independent.stderr,encoding='utf-8')
    if independent.returncode: raise RuntimeError('Independent QA failed; publication blocked. See independent_tests.log')
    for rec in registry:
        rec['qa_status']='PASS_WITH_DOCUMENTED_WARNINGS'; shutil.copy2(STAGE/(rec['table']+'.csv'),ROOT/'data/processed'/(rec['table']+'.csv'))
    shutil.copy2(db,ROOT/'data/processed/session1.sqlite'); csv(pd.DataFrame(registry),'processed_table_registry.csv')
    summary=dict(files=len(manifest),raw_rows=sum(x['rows'] for x in manifest),raw_bytes=sum(x['file_size'] for x in manifest),orders=len(o),delivered_orders=len(delivered),unique_customers_all=int(all_freq.size),repeat_customers_all=int(all_freq.gt(1).sum()),repeat_rate_all=float(all_freq.gt(1).mean()),unique_customers_delivered=int(freq.size),repeat_customers_delivered=int(freq.gt(1).sum()),repeat_rate_delivered=float(freq.gt(1).mean()),multiple_item_orders=int(counts.gt(1).sum()),orders_without_items=int((~fo.has_items).sum()),multiple_payment_orders=int(paycounts.gt(1).sum()),multiple_payment_types=int(p.groupby('order_id').payment_type.nunique().gt(1).sum()),installment_rows=int(p.payment_installments.gt(1).sum()),orders_without_payment=int((~fo.has_payment).sum()),reviews=len(r),reviewed_orders=r.order_id.nunique(),review_id_distinct=r.review_id.nunique(),multi_review_orders=int(reviewcounts.gt(1).sum()),text_reviews=int(r.has_text.sum()),text_unique_orders=int(r.loc[r.has_text,'order_id'].nunique()),title_or_message_reviews=int((r.has_text|r.review_comment_title.fillna('').str.strip().ne('')).sum()),mql=len(l),closed_deals=len(d),matched_sellers=matched,unmatched_sellers=len(d)-matched,seller_match_rate=matched/unique_deal_sellers,pre_won_sellers=int(windows.pre_won_order.sum()),window_eligibility={k:int(windows[k].sum()) for k in windows if k.endswith('computable')},geo_rows=len(g),geo_prefixes=g.geolocation_zip_code_prefix.nunique(),geo_exact_duplicates=int(g.duplicated().sum()),merchandise_cents=int(i.price_cents.sum()),freight_cents=int(i.freight_cents.sum()),payment_cents=int(p.payment_cents.sum()),payment_diff_gt_onecent=len(mismatches),payment_difference_bridge=dict(total_difference_cents=observed,comparable_difference_cents=residual,payment_only_cents=pay_only,items_only_cents=items_only),delivery_eligible=int(fo.loc[fo.is_delivered,'delivery_days'].notna().sum()),late_eligible=int(fo.is_late.notna().sum()),multi_seller_orders=int(fo.seller_count.gt(1).sum()),qa_pass=sum(x['status']=='PASS' for x in checks),qa_fail=failed,qa_warn=sum(x['status']=='WARN' for x in checks),quality_warning_types=len(quality),processed_tables=len(registry),snapshot_date=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    sections=['# 原始数据审计报告\n\n原始 CSV 未更改。数值金额使用 BRL，建模层使用整数分。所有统计来自本次官方快照。字段 dtype 为读取时类型，日期解析后为 datetime64；ID/邮编保留字符串。',md(pd.DataFrame(manifest)[['filename','rows','columns','file_size']])]
    for name,frame in raw.items():
        key=KEYS.get(name,['无自然唯一主键；来源文件行号'])
        sections += [f'## {name}\n\n文件：{NAMES[name]}；候选键：{", ".join(key)}；全行重复：{int(frame.duplicated().sum())}。',md(pd.DataFrame(fields).query('table == @name').drop(columns=['table','filename']))]
    sections+=['## 外键与 JOIN\n\nmatch_rate 分母为非空子表记录；跨数据集 seller 匹配另见专项文档。',md(pd.DataFrame(fks)),'## 日期范围',md(pd.DataFrame(ranges)),'## 订单月份（含零订单月份）\n\n2016 是启动/稀疏期；2018-08 以后标记右边界截断风险。2017-01 至 2018-07 是保守分析候选窗，不等于证明月度全量采集。2018-08 虽有订单仍存在尾部骤减与交付成熟度风险。',md(months),'## 每订单商品行数\n\norder_item_id 是订单内序号，每行按一个商品单位处理；不是独立 SKU 数。',md(dist),'## 专项验证摘要\n\n'+json.dumps(summary,ensure_ascii=False,indent=2),'## 数值异常及处置\n\n负坐标不是异常；地理粗框筛查不作为精确国界。缺失产品尺寸/属性、声明收入零值及极端值均保留，不因分布极端删除。未提供汇率、成本、退款/优惠明细。',md(pd.DataFrame(quality))]
    write('data_audit_report.md','\n\n'.join(sections))
    write('join_cardinality_risk.md','# JOIN 基数专项实证\n\n以下使用真实订单及实际 LEFT JOIN，代码见 src/build.py。金额单位为分，除以100即 BRL。\n\n'+md(pd.DataFrame([join_evidence]).T.reset_index().rename(columns={'index':'字段',0:'实际结果'}))+'\n\norders × items × payments × reviews 的订单行数为 max(1,I)×max(1,P)×max(1,R)。商品金额被支付数×评论数重复，支付金额被商品数×评论数重复。全量实证与基数公式一致。\n\n安全方案：items/payment 各自聚合至 order_id，再以 validate=one_to_one 接订单；reviews 保留独立事实表，订单评分单独选择最新一条。绝不对原始多子表大宽表求金额。地理原表邮编不唯一，只有 dim_geolocation_prefix 可按 many_to_one 使用。跨商家/品类的订单数不可相加当平台订单数；订单总支付额不可直接分摊到商品或商家。')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__': main()
