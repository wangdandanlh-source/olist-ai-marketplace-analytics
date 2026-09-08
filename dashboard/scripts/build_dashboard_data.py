"""Validated aggregate outputs -> allowlisted static extracts. Python standard library only."""
from pathlib import Path
import csv,json,math,hashlib
APP=Path(__file__).resolve().parents[1];ROOT=APP.parent/'analysis';SOURCE=ROOT/'outputs';DATA=APP/'data';DATA.mkdir(exist_ok=True)
lineage=[];used={};recon=[]
def csvread(name):
 p=SOURCE/name;used[name]=hashlib.sha256(p.read_bytes()).hexdigest()
 return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def read(name):
 p=SOURCE/name;used[name]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text(encoding='utf-8'))
def f(v):return float(v) if v not in ['',None] else None
def extract(key,page,name,cols,rows=None,scope='Core delivered 2017-01..2018-07',den='See source definition'):
 rows=csvread(name) if rows is None else rows
 out=[{k:f(r[v]) if numeric else r[v] for k,(v,numeric) in cols.items()} for r in rows]
 for k,(v,_) in cols.items():lineage.append(dict(page=page,component=key,metric=k,dashboard_dataset='dashboard/data/dashboard.json#'+key,source_output=name,source_column=v,definition=scope,filter_scope='component only; frozen page KPIs unaffected',denominator=den,notes='Allowlisted aggregate fields only; no row-level reviews'))
 return out
def savecsv(name,rows):
 with (SOURCE/name).open('w',encoding='utf-8-sig',newline='') as file:
  w=csv.DictWriter(file,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def check(key,value,expected,tol,source):
 recon.append(dict(metric=key,dashboard_value=value,validated_source_value=expected,difference=value-expected,tolerance=tol,source_file=source,status='PASS' if abs(value-expected)<=tol else 'FAIL'))
def main():
 s=read('session2_summary.json');v=read('session3_summary.json');model=read('session3_model_manifest.json')
 k={};
 def scalar(key,value,source,col,definition,den):
  k[key]=value;lineage.append(dict(page='shared',component='KPI',metric=key,dashboard_dataset='dashboard/data/dashboard.json#kpi.'+key,source_output=source,source_column=col,definition=definition,filter_scope='fixed validated scope, outside component filters',denominator=den,notes='No browser recalculation'))
 for key,col in [('orders','core_orders'),('customers','core_customers'),('repeat','repeat_rate'),('repeatCount','repeat_customers'),('oneTime','one_time_share'),('mql','mql'),('deals','closed'),('conversion','conversion'),('matched','matched_sellers'),('late','late_rate'),('lateN','late_orders'),('lateDen','late_valid_n'),('lateScore','late_review_mean'),('ontimeScore','ontime_review_mean')]:scalar(key,s[col],'session2_summary.json',col,'Frozen Session2 scope','MQL=8000; core customers=86960; late valid=89852; score uses reviewed valid orders')
 scalar('gmv',s['core_gmv_cents']/100,'session2_summary.json','core_gmv_cents','Merchandise GMV, BRL','89860 delivered orders')
 scalar('match',s['matched_sellers']/s['closed'],'session2_summary.json','matched_sellers / closed','Observed seller join coverage','842 deals')
 scalar('p75',s['high_value_threshold_cents']/100,'session2_summary.json','high_value_threshold_cents','Sample-specific spend P75 BRL','Core purchasing customers')
 for key,col in [('voc','rows'),('primary','primary_n'),('positive','positive_n'),('mixed','mixed_primary_rate')]:scalar(key,v[col],'session3_summary.json',col,'All canonical written reviews; primary score<=3','40748 written; mixed denominator14375')
 scalar('embeddingDim',model['embedding_dimension'],'session3_model_manifest.json','embedding_dimension','Multilingual MiniLM','Not a business rate')
 rep=csvread('session2_customer_repurchase_summary.csv');rep=[r for r in rep if r['sample']=='common90'];r90=next(r for r in rep if r['days']=='90')
 for key,col in [('rep90','repurchase_rate'),('rep24','repurchase_atleast1day_rate'),('repDen','sample_size')]:scalar(key,f(r90[col]),'session2_customer_repurchase_summary.csv',col,'common90, days=90; >=1day sensitivity from validated layer','68617 common mature customers')
 seller=next(r for r in csvread('session2_seller_postdeal_summary.csv') if r['sample']=='common90' and r['days']=='90' and r['dimension']=='all' and r['metric']=='merchandise_cents')
 for key,col in [('sellerMedian','median'),('sellerMean','mean'),('sellerP25','p25'),('sellerP75','p75')]:scalar(key,f(seller[col])/100,'session2_seller_postdeal_summary.csv',col,'common90, days90, all, merchandise_cents /100','124 sellers')
 scalar('sellerN',f(seller['sample_size']),'session2_seller_postdeal_summary.csv','sample_size','common90 days90','124 mature sellers')
 scalar('inactive',1-f(seller['active_last30_rate']),'session2_seller_postdeal_summary.csv','1-active_last30_rate','No recorded order in final30days, not churn','124 sellers')
 scalar('inactiveN',round(k['inactive']*k['sellerN']),'session2_seller_postdeal_summary.csv','(1-active_last30_rate)*sample_size','No recorded order in final30days','124 sellers')
 orrow=next(r for r in csvread('session2_cx_logistic_coefficients.csv') if r['term']=='is_late' and r['model_sample']=='review_after_delivery')
 for key,col in [('or','odds_ratio'),('orLow','ci_lower'),('orHigh','ci_upper')]:scalar(key,f(orrow[col]),'session2_cx_logistic_coefficients.csv',col,'review_after_delivery model; is_late term; customer-cluster robust CI','84763 reviewed valid orders')
 monthly=extract('monthly','overview','session2_marketplace_monthly.csv',{'month':('month',False),'gmv':('merchandise_cents',True),'orders':('delivered_orders',True),'yoy':('gmv_yoy',True)},den='Delivered orders per purchase month')
 for row in monthly:row['gmv']/=100
 scalar('julyYoY',next(r['yoy'] for r in monthly if r['month']=='2018-07'),'session2_marketplace_monthly.csv','gmv_yoy','July2018 vs July2017','July2017 GMV')
 decom=extract('decomposition','overview','session2_gmv_decomposition.csv',{'factor':('factor',False),'share':('contribution_share',True),'amount':('shapley_contribution_brl',True)},rows=[r for r in csvread('session2_gmv_decomposition.csv') if r['comparison']=='july_yoy'],den='Total July YoY GMV change; mathematical Shapley contributions')
 origins=extract('origins','seller','session2_funnel_analysis.csv',{'origin':('value',False),'mql':('mql',True),'deals':('closed_deals',True),'rate':('observed_conversion',True)},rows=[r for r in csvread('session2_funnel_analysis.csv') if r['dimension']=='origin'],scope='Observed MQL contact cohorts 2017-06..2018-05; closed snapshot',den='MQL by origin; no cost/ROI')
 repdata=extract('repurchase','customer','session2_customer_repurchase_summary.csv',{'days':('days',True),'rate':('repurchase_rate',True),'sensitivity':('repurchase_atleast1day_rate',True),'n':('sample_size',True),'repeatN':('repurchasers',True)},rows=rep,den='Same 68617 common90 mature customers')
 customer=extract('customerSegments','customer','session2_customer_analysis.csv',{'segment':('value',False),'n':('sample_size',True),'share':('customer_share',True)},rows=[r for r in csvread('session2_customer_analysis.csv') if r['dimension']=='segment'],den='86960 core customers; spend P75=155BRL')
 lateMonthly=extract('lateMonthly','fulfillment','session2_fulfillment_cx.csv',{'month':('value',False),'rate':('late_rate',True),'lateN':('late_orders',True),'n':('sample_size',True)},rows=[r for r in csvread('session2_fulfillment_cx.csv') if r['dimension']=='month'],den='Valid delivered dates per purchase month')
 sensitivity=next(r for r in csvread('session2_cx_sensitivity.csv') if r['sample']=='review_after_delivery')
 scoreTiming=[dict(scope='全部代表评价',late=k['lateScore'],ontime=k['ontimeScore'],lateN=s['late_review_n'],ontimeN=s['ontime_review_n']),dict(scope='签收后作答评价',late=f(sensitivity['late_review']),ontime=f(sensitivity['ontime_review']),lateN=f(sensitivity['late_n']),ontimeN=f(sensitivity['ontime_n']))]
 lineage.append(dict(page='fulfillment',component='scoreTiming',metric='late / ontime / N',dashboard_dataset='dashboard/data/dashboard.json#scoreTiming',source_output='session2_summary.json; session2_cx_sensitivity.csv',source_column='late_review_mean/ontime_review_mean; late_review/ontime_review/late_n/ontime_n',definition='Canonical latest review; after delivery determined by review_answer_timestamp >= receipt (not creation date)',filter_scope='Timing selector only',denominator='All:5993/83237; after:1702/83061',notes='Exact Session2 timing rule retained'))
 categories=extract('categories','fulfillment','session2_category_analysis.csv',{'category':('category',False),'orders':('orders',True),'score':('review_mean',True),'reviewN':('review_n',True),'late':('late_rate',True),'lateN':('late_orders',True),'lateDen':('late_n',True)},den='Distinct order/category; not additive across categories')
 issues=extract('issues','ai','session3_issue_metrics.csv',{'issue':('issue_category',False),'role':('corpus_role',False),'n':('n',True),'late':('late_delivery_rate',True),'lateN':('late_count',True),'lateDen':('late_eligible_n',True)},den='N=all canonical written by role; late core valid only')
 timing=extract('issueTiming','ai','session3_issue_timing_comparison.csv',{'scope':('scope',False),'issue':('issue_category',False),'n':('n',True),'rate':('late_delivery_rate',True),'lateN':('late_count',True),'lateDen':('late_eligible_n',True)},den='Core valid written; after_delivery sub-scope explicit')
 base=next(r for r in csvread('session3_validation_baselines.csv') if r['scope']=='after_delivery_core_written')
 waiting='Delivery waiting / non-receipt';wa=next(r for r in timing if r['issue']==waiting and r['scope']=='all_core_written');wp=next(r for r in timing if r['issue']==waiting and r['scope']=='after_delivery_core_written')
 for key,val,source,col,den in [('waitAll',wa['rate'],'session3_issue_timing_comparison.csv','late_delivery_rate all_core_written',wa['lateDen']),('waitAfter',wp['rate'],'session3_issue_timing_comparison.csv','late_delivery_rate after_delivery_core_written',wp['lateDen']),('waitBaseline',f(base['late_delivery_rate']),'session3_validation_baselines.csv','late_delivery_rate after_delivery_core_written',f(base['late_eligible_n']))]:scalar(key,val,source,col,'Waiting/nonreceipt timing consistency',den)
 hero=[dict(label='全部核心正文 · 等待主题',rate=wa['rate'],num=wa['lateN'],den=wa['lateDen']),dict(label='签收后正文 · 等待主题',rate=wp['rate'],num=wp['lateN'],den=wp['lateDen']),dict(label='签收后正文基线',rate=f(base['late_delivery_rate']),num=f(base['late_count']),den=f(base['late_eligible_n']))]
 office=extract('office','ai/fulfillment','session3_category_month_diagnostics.csv',{'issue':('issue_category',False),'n':('issue_count',True),'den':('primary_written_denominator',True),'rate':('primary_conditional_rate',True)},rows=[r for r in csvread('session3_category_month_diagnostics.csv') if r['dimension']=='category' and r['value']=='office_furniture' and r['issue_category'] in ['Incomplete order / missing units','Product condition / mismatch']],den='Office primary written290; core primary11948')
 coretiming=[r for r in timing if r['scope']=='all_core_written'];primaryden=sum(r['n'] for r in coretiming if next(i['role'] for i in issues if i['issue']==r['issue'])=='primary')
 for r in office:r['baseline']=next(t['n'] for t in coretiming if t['issue']==r['issue'])/primaryden;r['baselineDen']=primaryden
 lineage.append(dict(page='ai/fulfillment',component='office',metric='baseline',dashboard_dataset='dashboard/data/dashboard.json#office',source_output='session3_issue_timing_comparison.csv',source_column='n(all_core_written, primary issues)',definition='Display ratio of accepted disjoint aggregates; no raw recomputation',filter_scope='fixed office diagnostic',denominator=primaryden,notes='Within score<=3 corpus; not population complaint probability'))
 for key,target,tol in [('gmv',12342450.49,.001),('orders',89860,0),('repeat',.030002,.0000005),('rep90',.0205,.00005),('rep24',.0127,.00005),('late',6138/89852,1e-12),('mql',8000,0),('deals',842,0),('conversion',.10525,1e-12),('match',380/842,1e-12),('sellerN',124,0),('sellerMedian',694.65,.01),('sellerMean',2376.19,.01),('inactiveN',41,0),('or',2.31,.005),('orLow',2.04,.005),('orHigh',2.62,.005),('voc',40748,0),('primary',14375,0),('waitAll',.5618,.00005),('waitAfter',.074,.00005),('waitBaseline',.0222,.00005),('mixed',.627,.00005),('julyYoY',.8022,.00005)]:check(key,k[key],target,tol,next(l['source_output'] for l in lineage if l['metric']==key))
 for row,target in zip(decom,[.8000,-.0149,.2149]):check('contribution_'+row['factor'],row['share'],target,.00005,'session2_gmv_decomposition.csv')
 savecsv('session5_kpi_reconciliation.csv',recon);assert all(r['status']=='PASS' for r in recon),'STOP: frozen KPI mismatch'
 payload=dict(kpi=k,monthly=monthly,decomposition=decom,origins=origins,repurchase=repdata,customerSegments=customer,lateMonthly=lateMonthly,scoreTiming=scoreTiming,categories=categories,issues=issues,issueTiming=timing,hero=hero,office=office)
 (DATA/'dashboard.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,separators=(',',':')),encoding='utf-8')
 (DATA/'sources.json').write_text(json.dumps(used,indent=2),encoding='utf-8')
 pagekeys={'overview':['gmv','orders','julyYoY','repeat','repeatCount','customers','late','lateN','lateDen','mql','deals','conversion','match','voc','mixed','rep90','rep24','oneTime'],'seller':['mql','deals','conversion','matched','match','sellerN','sellerMedian','sellerMean','sellerP25','sellerP75','inactive','inactiveN'],'customer':['repeat','repeatCount','customers','rep90','rep24','repDen','oneTime','p75'],'fulfillment':['late','lateN','lateDen','lateScore','ontimeScore','or','orLow','orHigh'],'ai':['voc','primary','positive','mixed','embeddingDim','waitAll']}
 shared=[r for r in lineage if r['page']=='shared'];lineage[:]=[r for r in lineage if r['page']!='shared']
 for page,keys in pagekeys.items():
  for row in shared:
   if row['metric'] in keys:lineage.append({**row,'page':page})
 for page in ['overview','ai']:
  lineage.append(dict(page=page,component='hero',metric='rate / num / den',dashboard_dataset='dashboard/data/dashboard.json#hero',source_output='session3_issue_timing_comparison.csv; session3_validation_baselines.csv',source_column='late_delivery_rate / late_count / late_eligible_n',definition='Waiting/nonreceipt all_core and after_delivery; after-delivery written baseline',filter_scope='fixed scope comparison, not improvement',denominator='2752 / 1298 / 33446',notes='No causal or final failed-delivery interpretation'))
 for row in lineage:
  if row['component']=='monthly' and row['metric']=='gmv':row['notes']='merchandise_cents /100 to BRL; chart /1e6 to million BRL; display conversion only'
 savecsv('session5_metric_lineage.csv',lineage)
 print('Frozen KPI PASS',len(recon),'lineage',len(lineage),'bytes',(DATA/'dashboard.json').stat().st_size)
if __name__=='__main__':main()
