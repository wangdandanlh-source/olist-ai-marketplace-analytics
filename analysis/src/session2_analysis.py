"""Session 2: processed-only business analysis; reproducible, QA-gated, no visual UI."""
from pathlib import Path
import sys,os,json,sqlite3,hashlib,itertools,shutil,subprocess,platform
ROOT=Path(__file__).resolve().parents[1]
import pandas as pd
import numpy as np
from scipy import stats
import statsmodels.api as sm
from session2_stats import Tests,wilson
OUT=ROOT/'outputs'; DOC=ROOT/'docs'; STAGE=ROOT/'data/interim/session2'
START=pd.Timestamp('2017-01-01'); END=pd.Timestamp('2018-08-01')
WINDOW='[2017-01-01,2018-08-01)'; SOURCE=ROOT/'data/processed/session1.sqlite'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def export(frame,name): frame.to_csv(OUT/('session2_'+name+'.csv'),index=False,encoding='utf-8-sig',date_format='%Y-%m-%d %H:%M:%S')
def context(frame,cohort,denominator,window=WINDOW):
    frame=frame.copy()
    for col,value in [('analysis_window',window),('cohort_definition',cohort),('denominator',denominator)]:
        if col not in frame:frame[col]=value
    if 'sample_size' not in frame:
        if 'N' in frame:frame['sample_size']=frame.N
        elif 'orders' in frame:frame['sample_size']=frame.orders
        elif 'items_2017' in frame:frame['sample_size']=frame.items_2017+frame.items_2018
        else:frame['sample_size']=1
    return frame
def jsonable(x):
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.floating,)):return float(x)
    if isinstance(x,(pd.Timestamp,Path)):return str(x)
    raise TypeError(type(x))
def main():
    STAGE.mkdir(parents=True,exist_ok=True); checks=[]; test=Tests(); results={}; tables={}
    def qa(name,ok,actual,expected,severity='ERROR'):
        checks.append(dict(test=name,status='PASS' if bool(ok) else ('WARN' if severity=='WARNING' else 'FAIL'),actual=str(actual),expected=str(expected)))
    def save(name,df,cohort,denominator,window=WINDOW):
        df=context(df,cohort,denominator,window); tables[name]=df; export(df,name); return df
    fingerprint=digest(SOURCE)
    s1=sqlite3.connect('file:'+SOURCE.as_posix()+'?mode=ro',uri=True)
    registry=pd.read_csv(OUT/'processed_table_registry.csv')
    for row in registry.itertuples():
        qa('session1_hash_'+row.table,digest(ROOT/'data/processed'/(row.table+'.csv'))==row.sha256,'verified SHA-256',row.sha256)
        qa('session1_sqlite_rows_'+row.table,s1.execute('SELECT COUNT(*) FROM '+row.table).fetchone()[0]==row.rows,s1.execute('SELECT COUNT(*) FROM '+row.table).fetchone()[0],row.rows)
    qa('session1_prior_no_fail',not pd.read_csv(OUT/'qa_results.csv').status.eq('FAIL').any(),'prior gate','no FAIL')
    if any(x['status']=='FAIL' for x in checks): export(pd.DataFrame(checks),'qa_results'); raise RuntimeError('Session1 input verification failed')
    p=STAGE/'session2.sqlite'
    if p.exists():p.unlink()
    conn=sqlite3.connect(p,uri=True); conn.execute('ATTACH DATABASE ? AS s1',('file:'+SOURCE.as_posix()+'?mode=ro',))
    conn.executescript((ROOT/'sql/session2_core.sql').read_text(encoding='utf-8')); conn.commit()
    def read(name):return pd.read_sql_query('SELECT * FROM '+name,conn)
    o=read('core_orders'); items=read('core_items'); bridge=read('order_category'); monthly=read('marketplace_monthly'); activation=read('seller_activation'); so=read('seller_orders_all'); hist=read('customer_delivered_history')
    for frame in [o,items,activation,so,hist]:
        for col in ['order_purchase_timestamp','won_date','first_order_on_or_after_won','first_delivered_order_on_or_after_won','review_answer_timestamp','order_delivered_customer_date']:
            if col in frame:frame[col]=pd.to_datetime(frame[col],format='%Y-%m-%d %H:%M:%S')
    # PREFLIGHT: actual delivered activation and calendar maturity.
    a=activation
    a['activation_anchor_changed']=a.first_order_on_or_after_won.ne(a.first_delivered_order_on_or_after_won)&a.first_order_on_or_after_won.notna()
    a['activation_in_core']=a.first_delivered_order_on_or_after_won.ge(START)&a.first_delivered_order_on_or_after_won.lt(END)
    a['time_to_first_delivered_days']=(a.first_delivered_order_on_or_after_won-a.won_date).dt.total_seconds()/86400
    for days in [30,60,90]:
        a[f'activation_{days}d_complete']=a.matched.eq(1)&a.activation_in_core&a.first_delivered_order_on_or_after_won.add(pd.Timedelta(days=days)).le(END)
        a[f'won_{days}d_complete']=a.matched.eq(1)&a.won_date.ge(START)&a.won_date.add(pd.Timedelta(days=days)).le(END)
    save('seller_activation_validation',a,'842 closed sellers; delivered activation timestamp','842 sellers; complete flags require matched and calendar maturity')
    all_del=pd.read_sql_query('SELECT * FROM fct_orders WHERE is_delivered=1',s1)
    rec=[]
    for scope,df in [('all_delivered',all_del),('core_delivered',o)]:
        both=df.has_items.eq(1)&df.has_payment.eq(1); payonly=df.has_items.eq(0)&df.has_payment.eq(1); itemonly=df.has_items.eq(1)&df.has_payment.eq(0)
        for group,mask in [('total',pd.Series(True,index=df.index)),('comparable',both),('payment_only',payonly),('items_only',itemonly),('neither',~(both|payonly|itemonly))]:
            z=df[mask]; m=int(z.merchandise_cents.sum()); f=int(z.freight_cents.sum()); pay=int(z.payment_cents.sum())
            dif=z.payment_cents-z.merchandise_cents-z.freight_cents
            rec.append(dict(scope=scope,group=group,sample_size=len(z),merchandise_cents=m,freight_cents=f,payment_cents=pay,difference_cents=pay-m-f,comparable_difference_gt_1cent=int(dif.abs().gt(1).sum()),amount_null_policy='missing legs count as 0 ONLY in accounting bridge; facts stay NULL'))
        total=rec[-5]; comp=rec[-4]; po=rec[-3]; io=rec[-2]
        qa('delivered_bridge_'+scope,total['difference_cents']==comp['difference_cents']+po['payment_cents']-io['merchandise_cents']-io['freight_cents'],total['difference_cents'],'comparable + payment-only - items-only')
    save('delivered_reconciliation',pd.DataFrame(rec),'delivered snapshot; scope specifies all/core','sample_size orders','all delivered + core delivered separately')
    # Marketplace and arithmetic decomposition (not causal).
    monthly['sample_size']=monthly.delivered_orders
    for field,num,den in [('aov_brl','merchandise_cents','delivered_orders'),('average_freight_brl','freight_cents','delivered_orders')]: monthly[field]=monthly[num]/monthly[den]/100
    monthly['items_per_order']=monthly['items']/monthly.delivered_orders; monthly['purchase_frequency']=monthly.delivered_orders/monthly.unique_customers; monthly['freight_ratio']=monthly.freight_cents/monthly.merchandise_cents
    monthly['gmv_mom']=monthly.merchandise_cents.pct_change(); monthly['orders_mom']=monthly.delivered_orders.pct_change(); monthly['gmv_yoy']=monthly.merchandise_cents.pct_change(12)
    monthly['returning_observed_customers']=monthly.unique_customers-monthly.new_observed_customers
    save('marketplace_monthly',monthly,'purchase month, delivered','delivered_orders; distinct customers/sellers within month')
    decomp=[]
    def shapley(before,after,label):
        x=np.array([before.unique_customers,before.purchase_frequency,before.aov_brl]); y=np.array([after.unique_customers,after.purchase_frequency,after.aov_brl]); contribution=np.zeros(3)
        for perm in itertools.permutations(range(3)):
            state=x.copy()
            for index in perm:
                old=np.prod(state); state[index]=y[index]; contribution[index]+=(np.prod(state)-old)/6
        delta=(after.merchandise_cents-before.merchandise_cents)/100
        for idx,factor in enumerate(['unique_customers','purchase_frequency','aov']):decomp.append(dict(comparison=label,start_month=before.month,end_month=after.month,factor=factor,start_value=x[idx],end_value=y[idx],gmv_change_brl=delta,shapley_contribution_brl=contribution[idx],contribution_share=contribution[idx]/delta if delta else np.nan,sample_size=int(before.delivered_orders+after.delivered_orders)))
        qa('shapley_reconciles_'+label,abs(contribution.sum()-delta)<1e-6,float(contribution.sum()),delta)
    shapley(monthly.iloc[0],monthly.iloc[-1],'first_to_last')
    shapley(monthly[monthly.month.eq('2017-07')].iloc[0],monthly.iloc[-1],'july_yoy')
    for k in range(1,len(monthly)):shapley(monthly.iloc[k-1],monthly.iloc[k],'mom_'+monthly.iloc[k].month)
    save('gmv_decomposition',pd.DataFrame(decomp),'specified month pair; symmetric 3-factor Shapley','customers × orders/customer × merchandise/order identity')
    qa('months_contiguous',monthly.month.tolist()==pd.period_range('2017-01','2018-07',freq='M').astype(str).tolist(),monthly.month.tolist(),'19 continuous months')
    source_month=pd.read_sql_query("SELECT * FROM monthly_marketplace_metrics WHERE month BETWEEN '2017-01' AND '2018-07' ORDER BY month",s1)
    for field in ['merchandise_cents','freight_cents','payment_cents','delivered_orders','unique_customers']:
        qa('s1_monthly_consistency_'+field,np.allclose(monthly[field],source_month[field],rtol=0,atol=0),int(monthly[field].sum()),int(source_month[field].sum()))
    # Category matrix: equal 6-month windows for growth, canonical score per order/category.
    oc=bridge.merge(o[['order_id','month','delivery_days','is_late','review_score']],on='order_id',validate='many_to_one')
    cat=oc.groupby('category').agg(merchandise_cents=('merchandise_cents','sum'),freight_cents=('freight_cents','sum'),orders=('order_id','size'),items=('items','sum'),review_n=('review_score','count'),review_mean=('review_score','mean'),delivery_n=('delivery_days','count'),delivery_mean_days=('delivery_days','mean'),late_n=('is_late','count'),late_orders=('is_late','sum')).reset_index()
    cat['sample_size']=cat.orders; cat['aov_proxy_brl']=cat.merchandise_cents/cat.orders/100; cat['freight_ratio']=cat.freight_cents/cat.merchandise_cents; cat['late_rate']=cat.late_orders/cat.late_n
    catmonths=oc.groupby(['month','category']).agg(merchandise_cents=('merchandise_cents','sum'),items=('items','sum'),orders=('order_id','size')).reset_index()
    for name,lo,hi in [('h1_2017','2017-01','2017-06'),('h1_2018','2018-01','2018-06')]:
        z=catmonths[catmonths.month.between(lo,hi)].groupby('category').agg(**{name+'_cents':('merchandise_cents','sum'),name+'_orders':('orders','sum')})
        cat=cat.merge(z,on='category',how='left',validate='one_to_one')
    for col in ['h1_2017_cents','h1_2018_cents','h1_2017_orders','h1_2018_orders']:cat[col]=cat[col].fillna(0).astype('int64')
    cat['h1_growth']=cat.h1_2018_cents.div(cat.h1_2017_cents.replace(0,np.nan))-1
    cat['growth_eligible']=cat.h1_2017_orders.ge(30)&cat.h1_2018_orders.ge(30)&cat.orders.ge(100)
    gmvp75=float(cat.loc[cat.orders.ge(100),'merchandise_cents'].quantile(.75)); growth_med=float(cat.loc[cat.growth_eligible,'h1_growth'].median())
    latebase=float(o.is_late.mean()); freightbase=float(o.freight_cents.sum()/o.merchandise_cents.sum()); reviewbase=float(o.review_score.mean())
    cat['high_gmv']=cat.merchandise_cents.ge(gmvp75)&cat.orders.ge(100); cat['high_growth']=cat.growth_eligible&cat.h1_growth.gt(max(0,growth_med))
    cat['poor_cx_screen']=cat.review_n.ge(100)&cat.review_mean.lt(reviewbase-.3)
    cat['high_late_screen']=cat.late_n.ge(100)&cat.late_rate.gt(latebase+.02)
    cat['high_freight_screen']=cat.orders.ge(100)&cat.freight_ratio.gt(freightbase+.05)
    cat['gmv_share']=cat.merchandise_cents/cat.merchandise_cents.sum()
    cat['matrix_tags']=cat.apply(lambda x:'; '.join(label for flag,label in [(x.high_gmv and x.high_growth,'High GMV + High Growth'),(x.high_gmv and x.poor_cx_screen,'High GMV + Poor CX'),(not x.high_gmv and x.high_growth,'Lower GMV + High Growth'),(x.high_freight_screen,'High Freight Burden'),(x.high_late_screen,'High Late Delivery')] if flag) or 'No threshold flag',axis=1)
    save('category_analysis',cat.sort_values('merchandise_cents',ascending=False),'core delivered; H1 growth compares Jan-Jun 2017 vs Jan-Jun 2018','distinct order/category; category orders and CX not additive')
    save('category_monthly',catmonths,'purchase month and category','order/category counts; item money')
    qa('category_money_no_duplication',cat.merchandise_cents.sum()==o.merchandise_cents.sum(),int(cat.merchandise_cents.sum()),int(o.merchandise_cents.sum()))
    # Mix arithmetic on item-weighted unit prices, avoids double-counted category AOV.
    mix=[]
    for year in ['2017','2018']:
        z=items[items.month.between(year+'-01',year+'-06')].groupby('category').agg(cents=('price_cents','sum'),items=('order_item_id','size')); z.columns=[c+'_'+year for c in z.columns]; mix.append(z)
    mx=mix[0].join(mix[1],how='outer').fillna(0)
    for year in ['2017','2018']: mx['weight_'+year]=mx['items_'+year]/mx['items_'+year].sum(); mx['unit_cents_'+year]=mx['cents_'+year]/mx['items_'+year].replace(0,np.nan)
    # New/disappearing categories: carry available unit price to missing period, allocate emergence to mix.
    mx['unit_cents_2017']=mx.unit_cents_2017.fillna(mx.unit_cents_2018); mx['unit_cents_2018']=mx.unit_cents_2018.fillna(mx.unit_cents_2017)
    mx['mix_unit_price_change_cents']=(mx.weight_2018-mx.weight_2017)*(mx.unit_cents_2018+mx.unit_cents_2017)/2
    mx['within_category_unit_price_change_cents']=(mx.unit_cents_2018-mx.unit_cents_2017)*(mx.weight_2018+mx.weight_2017)/2
    save('category_mix_decomposition',mx.reset_index(),'H1 2017 vs H1 2018; items weighted','arithmetic unit-price change, not product price inflation')
    region=o.groupby('state',dropna=False).agg(orders=('order_id','size'),merchandise_cents=('merchandise_cents','sum'),freight_cents=('freight_cents','sum'),review_n=('review_score','count'),review_mean=('review_score','mean'),late_n=('is_late','count'),late_orders=('is_late','sum')).reset_index()
    region['sample_size']=region.orders;region['gmv_share']=region.merchandise_cents/region.merchandise_cents.sum();region['late_rate']=region.late_orders/region.late_n;region['freight_ratio']=region.freight_cents/region.merchandise_cents
    save('regional_analysis',region.sort_values('merchandise_cents',ascending=False),'customer state on each order','core delivered orders; no geolocation join')
    print('Marketplace and category complete',flush=True)
    # FULL FUNNEL. Type/segment only exist for closed deals: their conversion is undefined.
    leads=pd.read_sql_query('SELECT * FROM fct_marketing_leads',s1)
    for col in ['first_contact_date','won_date']:leads[col]=pd.to_datetime(leads[col],format='%Y-%m-%d %H:%M:%S')
    leads['contact_month']=leads.first_contact_date.dt.strftime('%Y-%m');leads['valid_timing']=~(leads.is_closed.eq(1)&leads.won_date.lt(leads.first_contact_date))
    ttc=(leads.won_date-leads.first_contact_date).dt.total_seconds()/86400
    funnelrows=[]
    for dim in ['origin','contact_month','lead_type','business_segment','business_type']:
        frame=leads if dim in ['origin','contact_month'] else leads[leads.is_closed.eq(1)]
        for value,z in frame.groupby(dim,dropna=False):
            full=dim in ['origin','contact_month']; n=len(z); closed=int(z.is_closed.sum()); timing=z.time_to_close_days.dropna(); low,high=wilson(closed,n) if full else (np.nan,np.nan)
            row=dict(dimension=dim,value='Missing' if pd.isna(value) else str(value),sample_size=n,mql=n if full else np.nan,closed_deals=closed,observed_conversion=closed/n if full else np.nan,conversion_ci_low=low,conversion_ci_high=high,time_to_close_n=len(timing),time_to_close_mean_days=timing.mean(),time_to_close_median_days=timing.median(),low_sample=n<100 if full else n<30,conversion_identifiable=full)
            for days in [30,60,90]:
                eligible=z.first_contact_date.add(pd.Timedelta(days=days)).le(END)&z.valid_timing if full else pd.Series(False,index=z.index)
                successes=z.won_date.ge(z.first_contact_date)&z.won_date.lt(z.first_contact_date+pd.Timedelta(days=days))&eligible
                row[f'mature_{days}d_n']=int(eligible.sum()) if full else np.nan;row[f'closed_{days}d']=int(successes.sum()) if full else np.nan;row[f'observed_{days}d_conversion']=successes.sum()/eligible.sum() if eligible.sum() else np.nan
            funnelrows.append(row)
    save('funnel_analysis',pd.DataFrame(funnelrows),'all 8000 MQL; type/segment rows are closed-only','mql for origin/contact month; closed sellers for type/segment','contact cohorts 2017-06..2018-05; calendar maturity reference 2018-08-01; snapshot observed close separately')
    test.categorical('origin_observed_conversion','funnel',leads.origin,leads.is_closed)
    # Bias gate across full 842 deals, permutation when sparse cells.
    a['won_month']=a.won_date.dt.strftime('%Y-%m');bias=[]
    for dim in ['origin','lead_type','business_segment','won_month']:
        for value,z in a.groupby(dim,dropna=False):
            n=len(z); matched=int(z.matched.sum()); lo,hi=wilson(matched,n)
            bias.append(dict(dimension=dim,value='Missing' if pd.isna(value) else str(value),closed_deals=n,matched_sellers=matched,match_rate=matched/n,ci_low=lo,ci_high=hi,sample_size=n,low_sample=n<30))
        test.categorical('match_bias_'+dim,'match_bias',a[dim],a.matched)
    save('seller_match_bias',pd.DataFrame(bias),'842 closed deals; all won months','closed_deals within each group','full closed-deal snapshot')
    qa('type_conversion_not_fabricated',pd.DataFrame(funnelrows).query("dimension in ['lead_type','business_segment']").observed_conversion.isna().all(),'NULL','no full-population type denominator')
    # Seller post-activation outcomes. All horizons also re-evaluated on common90 sellers.
    so=so[so.order_status.eq('delivered')]; perf=[]
    for days in [30,60,90]:
        eligible=a[a[f'activation_{days}d_complete']]
        for row in eligible.itertuples():
            z=so[so.seller_id.eq(row.seller_id)&so.order_purchase_timestamp.ge(row.first_delivered_order_on_or_after_won)&so.order_purchase_timestamp.lt(row.first_delivered_order_on_or_after_won+pd.Timedelta(days=days))]
            trailing=z[z.order_purchase_timestamp.ge(row.first_delivered_order_on_or_after_won+pd.Timedelta(days=days-30))]
            perf.append(dict(seller_id=row.seller_id,origin=row.origin,lead_type=row.lead_type,business_segment=row.business_segment,days=days,activation_date=row.first_delivered_order_on_or_after_won,window_end=row.first_delivered_order_on_or_after_won+pd.Timedelta(days=days),orders=z.order_id.nunique(),merchandise_cents=int(z.merchandise_cents.sum()),items=int(z['items'].sum()),active_any=int(len(z)>0),active_last30=int(len(trailing)>0),time_to_first_delivered_days=row.time_to_first_delivered_days,common90=bool(row.activation_90d_complete),sample_size=1))
    perf=pd.DataFrame(perf);save('seller_postdeal',perf,'first delivered purchase >= won_date; complete activation+N window','matched, activated and mature sellers only')
    ps=[]
    for sample,z in [('each_horizon_mature',perf),('common90',perf[perf.common90])]:
        for dim in ['all','origin','lead_type','business_segment']:
            zz=z.assign(all='All') if dim=='all' else z
            for (days,value),group in zz.groupby(['days',dim],dropna=False):
                n=len(group)
                for metric in ['merchandise_cents','orders','items','time_to_first_delivered_days']:
                    x=group[metric];ps.append(dict(sample=sample,days=days,dimension=dim,value='Missing' if pd.isna(value) else str(value),metric=metric,sample_size=n,mean=x.mean(),median=x.median(),p25=x.quantile(.25),p75=x.quantile(.75),active_any_rate=group.active_any.mean(),active_last30_rate=group.active_last30.mean(),low_sample=n<10))
    save('seller_postdeal_summary',pd.DataFrame(ps),'mature by horizon OR same common90 sample, explicitly separated','seller count; group n<10 not interpreted')
    for dim in ['origin','lead_type','business_segment']:
        groups=[g.merchandise_cents.to_numpy() for _,g in perf[perf.days.eq(90)].groupby(dim,dropna=False) if len(g)>=10]
        test.kw('seller_90d_'+dim,'seller_performance',groups)
    # Activation selection audit: not activated as of cutoff stays separate, not zero business quality.
    matched_a=a[a.matched.eq(1)].copy();matched_a['activated_before_cutoff']=matched_a.first_delivered_order_on_or_after_won.lt(END)
    save('seller_activation_funnel',matched_a.groupby('activated_before_cutoff').size().reset_index(name='sample_size'),'380 matched sellers as of core cutoff','matched sellers; not an unbiased all-deals activation rate')
    print('Funnel, bias gate and seller horizons complete',flush=True)
    # Customers: core-window frequency; first-ever-observed delivered cohort uses prior history.
    customers=o.groupby('customer_unique_id').agg(orders=('order_id','size'),merchandise_cents=('merchandise_cents','sum'),first_core_purchase=('order_purchase_timestamp','min'),last_core_purchase=('order_purchase_timestamp','max')).reset_index()
    high=float(customers.merchandise_cents.quantile(.75)); customers['segment']=np.where(customers.orders.ge(2),'Repeat','One-time');customers.loc[customers.merchandise_cents.ge(high),'segment']='High-value '+customers.loc[customers.merchandise_cents.ge(high),'segment']
    customers['frequency_bucket']=np.where(customers.orders.ge(3),'3+',customers.orders.astype(str))
    ca=[]
    for dim in ['frequency_bucket','segment']:
        for value,z in customers.groupby(dim): ca.append(dict(dimension=dim,value=value,sample_size=len(z),orders=int(z.orders.sum()),merchandise_cents=int(z.merchandise_cents.sum()),customer_share=len(z)/len(customers),purchase_frequency=z.orders.mean(),repeat_rate=z.orders.ge(2).mean()))
    ca.append(dict(dimension='all',value='All',sample_size=len(customers),orders=len(o),merchandise_cents=int(o.merchandise_cents.sum()),customer_share=1,purchase_frequency=len(o)/len(customers),repeat_rate=customers.orders.ge(2).mean()))
    save('customer_analysis',pd.DataFrame(ca),'core-window delivered purchases per customer_unique_id','unique anonymous purchasing users in core')
    customers.to_sql('customer_level',conn,index=False,if_exists='replace')
    hist=hist.sort_values(['customer_unique_id','order_purchase_timestamp','order_id'],kind='stable')
    first=hist.drop_duplicates('customer_unique_id',keep='first').rename(columns={'order_purchase_timestamp':'first_purchase','order_id':'first_order_id'})[['customer_unique_id','first_purchase','first_order_id']]
    new=first[first.first_purchase.ge(START)].copy(); new['cohort']=new.first_purchase.dt.strftime('%Y-%m');new['cohort_end']=new.first_purchase.dt.to_period('M').add(1).dt.to_timestamp()
    later=hist.merge(new[['customer_unique_id','first_purchase']],on='customer_unique_id',validate='many_to_one')
    later['elapsed_days']=(later.order_purchase_timestamp-later.first_purchase).dt.total_seconds()/86400
    second=later[later.elapsed_days.gt(0)].groupby('customer_unique_id').elapsed_days.min()
    second1=later[later.elapsed_days.ge(1)].groupby('customer_unique_id').elapsed_days.min()
    new['next_purchase_days']=new.customer_unique_id.map(second);new['next_purchase_at_least1day']=new.customer_unique_id.map(second1)
    catfirst=bridge.groupby('order_id').category.agg(lambda x:x.iloc[0] if x.nunique()==1 else 'Multi-category')
    new['first_category']=new.first_order_id.map(catfirst).fillna('Unknown')
    cohortrows=[]
    for days in [30,60,90]:
        new[f'mature_{days}d']=new.cohort_end.add(pd.Timedelta(days=days)).le(END)
        new[f'repurchase_{days}d']=new.next_purchase_days.lt(days)&new.next_purchase_days.gt(0)
        for cohort,z in new.groupby('cohort'):
            mature=bool(z[f'mature_{days}d'].all()); n=len(z) if mature else 0; successes=int(z[f'repurchase_{days}d'].sum()) if mature else np.nan;lo,hi=wilson(successes,n) if mature else (np.nan,np.nan)
            cohortrows.append(dict(cohort=cohort,days=days,cohort_customers=len(z),sample_size=n,fully_mature_cohort=mature,repurchasers=successes,repurchase_rate=successes/n if n else np.nan,ci_low=lo,ci_high=hi,latest_possible_window_end=z.cohort_end.iloc[0]+pd.Timedelta(days=days)))
    save('customer_cohort',pd.DataFrame(cohortrows),'first observed delivered purchase month; entire month mature','all first-purchase users in a fully mature cohort; immature outcomes NULL')
    cr=[]
    for sample in ['each_horizon_mature','common90']:
        for days in [30,60,90]:
            z=new[new[f'mature_{days}d'] if sample=='each_horizon_mature' else new.mature_90d]; n=len(z);count=int(z[f'repurchase_{days}d'].sum());lo,hi=wilson(count,n)
            cr.append(dict(sample=sample,days=days,sample_size=n,repurchasers=count,repurchase_rate=count/n,ci_low=lo,ci_high=hi,repurchase_atleast1day=int(z.next_purchase_at_least1day.lt(days).sum()),repurchase_atleast1day_rate=float(z.next_purchase_at_least1day.lt(days).mean())))
    save('customer_repurchase_summary',pd.DataFrame(cr),'entire month maturity; strict later timestamp; >=1day sensitivity','new observed users; common90 for comparing 30 vs60 vs90')
    crep=[]
    for catname,z in new[new.mature_90d].groupby('first_category'):
        n=len(z);count=int(z.repurchase_90d.sum());lo,hi=wilson(count,n)
        crep.append(dict(first_category=catname,sample_size=n,repurchasers_90d=count,repurchase_90d=count/n,ci_low=lo,ci_high=hi,low_sample=n<200,eligible_for_screen=n>=200 and count>=10))
    save('customer_category_repurchase',pd.DataFrame(crep).sort_values('sample_size',ascending=False),'same fully mature 90D first-purchase cohorts','exclusive first-order category; Multi-category bucket; subsequent purchase any category')
    # A single global category association, no uncorrected category-by-category significance hunt.
    zn=new[new.mature_90d].copy();counts=zn.first_category.value_counts();zn['category_test']=zn.first_category.where(zn.first_category.isin(counts[counts.ge(200)].index),'Other small categories')
    test.categorical('first_category_repurchase90','customer',zn.category_test,zn.repurchase_90d.astype(int))
    new.to_sql('customer_cohort_members',conn,index=False,if_exists='replace')
    print('Customer frequency, segmentation and matured cohorts complete',flush=True)
    # Fulfillment/CX with one canonical review per order.
    valid=o[o.is_late.notna()].copy();cx=valid[valid.review_score.notna()].copy();cx['low_rating']=cx.review_score.le(2).astype(int)
    cx['one_star']=cx.review_score.eq(1).astype(int);cx['freight_ratio']=cx.freight_cents/cx.merchandise_cents
    qdelay=valid.loc[valid.is_late.eq(1),'estimated_gap_days'].quantile([.25,.5,.75,.9,.95]).to_dict()
    valid['delay_group']=pd.cut(valid.estimated_gap_days,[-np.inf,0,3,7,np.inf],labels=['On time / early','1-3 days late','4-7 days late','8+ days late'])
    cx['delay_group']=valid.loc[cx.index,'delay_group'];groups=[]
    for dim in ['is_late','delay_group','month']:
        for value,z in valid.groupby(dim,observed=True):
            reviewed=z[z.review_score.notna()]; n=len(reviewed);low=int(reviewed.review_score.le(2).sum());ci=wilson(low,n)
            groups.append(dict(dimension=dim,value=str(value),sample_size=len(z),review_n=n,review_coverage=n/len(z),delivery_mean_days=z.delivery_days.mean(),delivery_median_days=z.delivery_days.median(),late_orders=int(z.is_late.sum()),late_rate=z.is_late.mean(),estimated_gap_mean_days=z.estimated_gap_days.mean(),review_mean=reviewed.review_score.mean(),review_median=reviewed.review_score.median(),low_rating_n=low,low_rating_rate=low/n if n else np.nan,low_ci_lower=ci[0],low_ci_upper=ci[1],one_star_rate=reviewed.review_score.eq(1).mean()))
    save('fulfillment_cx',pd.DataFrame(groups),'core purchase dates; valid fulfillment; canonical latest order review','sample_size valid delivered orders; review_n for score/low-rating')
    late=cx[cx.is_late.eq(1)];ontime=cx[cx.is_late.eq(0)]
    test.mw('late_review_score','cx',late.review_score,ontime.review_score)
    test.categorical('late_low_rating','cx',cx.is_late,cx.low_rating)
    test.spearman('delay_days_review',cx.estimated_gap_days,cx.review_score);test.spearman('delivery_time_review',cx.delivery_days,cx.review_score)
    # Independent-user and review-after-delivery sensitivities.
    sensitivities=[]
    for label,z in [('one_order_per_customer',cx.sort_values(['order_purchase_timestamp','order_id']).drop_duplicates('customer_unique_id')),('review_after_delivery',cx[cx.review_answer_timestamp.ge(cx.order_delivered_customer_date)])]:
        x=z[z.is_late.eq(1)];y=z[z.is_late.eq(0)];test.mw(label,'cx_sensitivity',x.review_score,y.review_score)
        sensitivities.append(dict(sample=label,sample_size=len(z),late_n=len(x),ontime_n=len(y),late_review=x.review_score.mean(),ontime_review=y.review_score.mean(),late_low_rating_rate=x.low_rating.mean(),ontime_low_rating_rate=y.low_rating.mean(),low_rating_difference=x.low_rating.mean()-y.low_rating.mean()))
    save('cx_sensitivity',pd.DataFrame(sensitivities),'review timing / repeat-user sensitivity','canonical reviewed valid delivered orders retained by rule')
    ordercat=bridge.groupby('order_id').category.agg(lambda x:x.iloc[0] if x.nunique()==1 else 'Multi-category')
    cx['category']=cx.order_id.map(ordercat);cx['log_order_value']=np.log1p(cx.merchandise_cents/100);cx['log_freight_ratio']=np.log1p(cx.freight_ratio)
    # Confounder distributions with explicit denominators; no raw-row money join.
    conf=[]
    cx['value_band']=pd.qcut(cx.merchandise_cents,q=4,duplicates='drop').astype(str);cx['freight_band']=pd.qcut(cx.freight_ratio,q=4,duplicates='drop').astype(str)
    for dim in ['category','state','value_band','freight_band']:
        for value,z in cx.groupby(dim,dropna=False):conf.append(dict(dimension=dim,value=str(value),sample_size=len(z),late_rate=z.is_late.mean(),low_rating_rate=z.low_rating.mean(),review_mean=z.review_score.mean(),low_sample=len(z)<100))
    save('cx_confounder_profiles',pd.DataFrame(conf),'core reviewed valid orders','order counts; value/freight empirical quartile bands')
    # Binomial GLM = logistic association model, customer-cluster robust covariance.
    model=cx.dropna(subset=['log_order_value','log_freight_ratio','category','state','month']).copy()
    for dim in ['category','state']:
        vc=model[dim].value_counts();model[dim+'_model']=model[dim].where(model[dim].isin(vc[vc.ge(500)].index),'Other (<500)')
    design=pd.get_dummies(model[['is_late','log_order_value','log_freight_ratio','category_model','state_model','month']],columns=['category_model','state_model','month'],drop_first=True,dtype=float)
    design=sm.add_constant(design.astype(float));fit=sm.GLM(model.low_rating.astype(float),design,family=sm.families.Binomial()).fit(maxiter=100,cov_type='cluster',cov_kwds={'groups':model.customer_unique_id})
    confidence=fit.conf_int(); coef=pd.DataFrame(dict(term=fit.params.index,coefficient=fit.params.values,odds_ratio=np.exp(fit.params.values),ci_lower=np.exp(confidence.iloc[:,0].values),ci_upper=np.exp(confidence.iloc[:,1].values),z=fit.tvalues.values,p_value=fit.pvalues.values,sample_size=len(model)))
    coef['model_sample']='all_canonical_reviews'
    latecoef=coef[coef.term.eq('is_late')].iloc[0]
    test.add('adjusted_late_low_rating','cx','Binomial GLM logistic; customer-cluster robust z',len(model),latecoef.z,latecoef.p_value,latecoef.odds_ratio,'adjusted odds ratio','调整品类、州、月份、订单金额及运费负担后的关联；非因果。',ci_lower=latecoef.ci_lower,ci_upper=latecoef.ci_upper,customer_clusters=model.customer_unique_id.nunique())
    after=model[model.review_answer_timestamp.ge(model.order_delivered_customer_date)]
    design_after=design.loc[after.index]
    fit_after=sm.GLM(after.low_rating.astype(float),design_after,family=sm.families.Binomial()).fit(maxiter=100,cov_type='cluster',cov_kwds={'groups':after.customer_unique_id})
    ac=fit_after.conf_int();coef_after=pd.DataFrame(dict(term=fit_after.params.index,coefficient=fit_after.params.values,odds_ratio=np.exp(fit_after.params.values),ci_lower=np.exp(ac.iloc[:,0].values),ci_upper=np.exp(ac.iloc[:,1].values),z=fit_after.tvalues.values,p_value=fit_after.pvalues.values,sample_size=len(after),model_sample='review_after_delivery'))
    save('cx_logistic_coefficients',pd.concat([coef,coef_after],ignore_index=True),'all canonical reviews vs review-after-delivery; same covariates; category/state count>=500 else Other','reviewed valid orders with covariates; customer-cluster robust covariance')
    alc=coef_after[coef_after.term.eq('is_late')].iloc[0]
    test.add('adjusted_late_after_delivery','cx_sensitivity','Binomial GLM logistic; customer-cluster robust z',len(after),alc.z,alc.p_value,alc.odds_ratio,'adjusted odds ratio','仅保留签收之后的评价，调整相同协变量；非因果。',ci_lower=alc.ci_lower,ci_upper=alc.ci_upper,customer_clusters=after.customer_unique_id.nunique())
    qa('logistic_after_delivery_converged',fit_after.converged,fit_after.converged,True)
    qa('logistic_converged',fit.converged,fit.converged,True)
    qa('logistic_sample',int(fit.nobs)==len(model),fit.nobs,len(model))
    # Single-seller shipping proxy only, not actual item dispatch.
    single_orders=o[o.seller_count.eq(1)]
    single_map=items.loc[items.order_id.isin(single_orders.order_id),['order_id','seller_id']].drop_duplicates()
    singles=single_orders.merge(single_map,on='order_id',validate='one_to_one')
    proxy=singles.groupby('seller_id').agg(sample_size=('order_id','size'),handoff_n=('carrier_handoff_days','count'),handoff_mean_days=('carrier_handoff_days','mean'),late_n=('is_late','count'),late_rate=('is_late','mean')).reset_index();proxy['low_sample']=proxy.sample_size.lt(30)
    save('seller_shipping_proxy',proxy,'single-seller orders only','order-level approval-to-carrier proxy; not item dispatch events')
    cx.to_sql('cx_order_sample',conn,index=False,if_exists='replace')
    statframe=test.frame()
    statframe['analysis_window']=np.where(statframe.family.isin(['funnel','match_bias']),'full marketing snapshot; contact 2017-06..2018-05, won through 2018-11',WINDOW)
    statframe['cohort_definition']=statframe.test_id.map(lambda x:'842 closed sellers, matched vs unmatched' if x.startswith('match_bias') else 'all 8000 MQL' if x=='origin_observed_conversion' else 'matched delivered-activated sellers, complete 90D, groups n>=10' if x.startswith('seller_90d') else 'fully mature 90D first-purchase monthly cohorts' if x=='first_category_repurchase90' else 'core reviewed valid orders; sensitivity named in test_id')
    save('statistical_tests',statframe,'test-specific sample and FDR family','N from exact tested sample; exploratory observational inference')
    print('Fulfillment, statistical tests and adjusted association model complete',flush=True)
    # Core QA plus independent SQL assertions before publication.
    qa('core_window',o.order_purchase_timestamp.ge(START).all()&o.order_purchase_timestamp.lt(END).all(),str(o.order_purchase_timestamp.agg(['min','max']).tolist()),WINDOW)
    qa('core_delivered_only',o.is_delivered.eq(1).all(),o.is_delivered.unique(),'1')
    qa('core_pk',o.order_id.is_unique,len(o),o.order_id.nunique())
    qa('customer_unique_id_denominator',len(customers)==o.customer_unique_id.nunique(),len(customers),o.customer_unique_id.nunique())
    qa('seller_unmatched_excluded',perf.seller_id.isin(a.loc[a.matched.eq(1),'seller_id']).all(),perf.seller_id.nunique(),'subset of 380 matched')
    qa('seller_all_windows_complete',perf.window_end.le(END).all()&perf.activation_date.ge(START).all(),'all start/end checked',WINDOW)
    qa('seller_activation_delivered',a.first_delivered_order_on_or_after_won.dropna().ge(a.loc[a.first_delivered_order_on_or_after_won.notna(),'won_date']).all(),'activation after won','all')
    qa('seller_common90_same_users',len({tuple(sorted(perf[perf.common90&perf.days.eq(d)].seller_id)) for d in [30,60,90]})==1,'same IDs','same IDs at all horizons')
    qa('customer_cohort_maturity',pd.DataFrame(cohortrows).query('fully_mature_cohort').latest_possible_window_end.le(END).all(),'all complete monthly cohorts',str(END))
    qa('immature_customer_rates_null',pd.DataFrame(cohortrows).query('not fully_mature_cohort').repurchase_rate.isna().all(),'NULL','NULL')
    qa('cx_one_review_per_order',cx.order_id.is_unique,len(cx),cx.order_id.nunique())
    qa('late_denominator',int(pd.DataFrame(groups).query("dimension == 'is_late'").sample_size.sum())==o.is_late.notna().sum(),len(valid),int(o.is_late.notna().sum()))
    qa('cx_test_n',int(statframe.set_index('test_id').loc['late_review_score','N'])==len(cx),int(statframe.set_index('test_id').loc['late_review_score','N']),len(cx))
    qa('cx_no_missing_scores_in_tests',cx.review_score.notna().all(),len(cx),'all non-null')
    qa('statistical_p_valid',statframe.p_value.between(0,1).all()&statframe.q_value_bh.between(0,1).all(),'p,q in [0,1]','all')
    qa('source_database_unchanged',digest(SOURCE)==fingerprint,digest(SOURCE),fingerprint)
    qa('match_bias_gate_clear',not statframe.query("family == 'match_bias'").statistically_significant_fdr05.any(),'see match_bias tests','no statistically detected match bias','WARNING')
    qa('funnel_followup_fully_known',False,'no individual loss-to-followup / administrative censor date','calendar maturity only; fixed-window rates are observed proportions','WARNING')
    qa('closed_attributes_full_mql',False,'lead_type/segment observed in closed deals only','conversion unavailable by type/segment','WARNING')
    qa('observational_cx_causal',False,'observational sample; residual confounding and review selection','association only','WARNING')
    for name,frame in tables.items(): frame.to_sql('s2_'+name,conn,index=False,if_exists='replace')
    conn.commit();conn.close();s1.close()
    export(pd.DataFrame(checks),'qa_results')
    if any(x['status']=='FAIL' for x in checks):raise RuntimeError('Session2 blocking QA failed. No publication.')
    env=os.environ.copy();env['OLIST_S2_QA_DB']=str(p);env['PYTHONIOENCODING']='utf-8'
    run=subprocess.run([sys.executable,'-X','utf8',str(ROOT/'tests/test_session2.py')],capture_output=True,text=True,encoding='utf-8',env=env)
    (OUT/'session2_independent_tests.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    if run.returncode:raise RuntimeError('Independent Session2 QA failed. Publication blocked.')
    shutil.copy2(p,ROOT/'data/processed/session2.sqlite')
    outreg=[]
    for name,frame in tables.items():outreg.append(dict(table='s2_'+name,rows=len(frame),source='data/processed/session1.sqlite',source_sha256=fingerprint,transformation='sql/session2_core.sql + src/session2_analysis.py + src/session2_stats.py',qa_status='PASS_WITH_CONDITIONS',csv='outputs/session2_'+name+'.csv',sha256=digest(OUT/('session2_'+name+'.csv'))))
    export(pd.DataFrame(outreg),'table_registry')
    results.update(dict(core_orders=len(o),core_customers=len(customers),core_gmv_cents=int(o.merchandise_cents.sum()),core_freight_cents=int(o.freight_cents.sum()),core_sellers=int(items.seller_id.nunique()),repeat_customers=int(customers.orders.ge(2).sum()),repeat_rate=float(customers.orders.ge(2).mean()),one_time_share=float(customers.orders.eq(1).mean()),high_value_threshold_cents=high,activation_changed=int(a.activation_anchor_changed.sum()),activated_core_matched=int((a.matched.eq(1)&a.activation_in_core).sum()),matched_sellers=int(a.matched.sum()),seller_complete={str(d):int(a[f'activation_{d}d_complete'].sum()) for d in [30,60,90]},mql=len(leads),closed=int(leads.is_closed.sum()),conversion=float(leads.is_closed.mean()),funnel_invalid_timing=int((~leads.valid_timing).sum()),late_valid_n=len(valid),late_orders=int(valid.is_late.sum()),late_rate=float(valid.is_late.mean()),cx_n=len(cx),late_review_n=len(late),ontime_review_n=len(ontime),late_review_mean=float(late.review_score.mean()),ontime_review_mean=float(ontime.review_score.mean()),late_low_rate=float(late.low_rating.mean()),ontime_low_rate=float(ontime.low_rating.mean()),late_review_effect=float(statframe.set_index('test_id').loc['late_review_score','effect_size']),adjusted_late_or=float(latecoef.odds_ratio),adjusted_or_ci=[float(latecoef.ci_lower),float(latecoef.ci_upper)],delay_quantiles=qdelay,category_matrix_thresholds=dict(gmv_p75_cents=gmvp75,growth_median=growth_med,late_platform=latebase,freight_platform=freightbase,review_platform=reviewbase),qa_pass=sum(x['status']=='PASS' for x in checks),qa_warn=sum(x['status']=='WARN' for x in checks),qa_fail=sum(x['status']=='FAIL' for x in checks),source_database_sha256=fingerprint,processed_database_sha256=digest(ROOT/'data/processed/session2.sqlite'),generated_utc=pd.Timestamp.now(tz='UTC').isoformat()))
    (OUT/'session2_summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=jsonable),encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2,default=jsonable),flush=True)
if __name__=='__main__':main()
