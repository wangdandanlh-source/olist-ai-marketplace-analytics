"""Frozen LLM decisions, based only on exported cluster profiles and 15 examples/cluster.

This is an auditable decision artifact, not a supervised classifier or human gold set.
"""
from session3_common import *
DECISIONS=[
 (0,'Product condition / mismatch','Quality, defect, appearance or wrong-item mixture','Seller / Product','缺陷、质量、外观与预期不符为主，也有缺货/错货混入；不可拆成准确的单一故障标签。',None,'medium',True,'中心及随机样本均出现defeito、材质、照片不符；另有缺件反例，保留宽类别。'),
 (1,'Generic / Unclear','Short or underspecified, including rating-text discordance','Unknown','短句好/不好、单标点和延迟/未收到等混杂，无法给每条确定经营原因。',None,'low',True,'最近样本包含bom、句点、推荐、未收到与慢递；必须保留Unknown。'),
 (2,'Delivery waiting / non-receipt','Not received at review time','Delivery','主要表达评论时尚未收到，不能声称最终永久未收到。',4,'medium',False,'10条中心例高度近似；随机样本有保温商品反例，标签仅簇级近似。'),
 (3,'Mixed resolution / service','Returns, refunds, contact and delivery problems','After-sales / Service','退换、退款、联系无回复与交付/商品问题交织。',5,'low',True,'中心与随机样本多次提到换货/取消/联系无回复，但同时覆盖不同上游问题。'),
 (4,'Delivery waiting / non-receipt','Promised date, long wait or overdue receipt','Delivery','承诺日期、等待过长、超时未收到；部分仅要求更快，并非都客观迟到。',2,'medium',False,'关键词prazo、entrega和例句支持等待主题；与簇2合并主类但保留子类。'),
 (5,'Mixed resolution / service','Retailer complaint, communication and unresolved purchase','After-sales / Service','对商店/平台不满、无法联系、取消退款以及未交付混杂；匿名品牌不能恢复真实公司。',3,'low',True,'中心样本强调未解决和无法联系；随机样本也有物流归因及暂时等待，不能称纯客服问题。'),
 (6,'Mixed / rating-text mismatch','Positive or ambivalent wording within score<=3','Unknown','中心是好商品/及时交付，随机样本有质量和交付抱怨；不把评分等同情感真值。',None,'low',True,'正向原文与1/3星同时出现；保留混合类，不改评分或强贴负向主题。'),
 (7,'Incomplete order / missing units','Partial receipt or fewer units than purchased','Fulfillment / Logistics','购买多件但只收到部分为主；文本陈述不能确认仓库或商家责任。',None,'medium',False,'中心例有明确2买1到、4买3到；部分随机样本仅问商品在哪，仍需人工复核。'),
 (100,'Positive delivery mentions','Early or on-time arrival, positive-rated corpus','Delivery','高评分语料中的提前/按时到达表达，亦可能同时提及商品。',None,'medium',False,'中心10例反复提到antes do prazo；随机例支持但也有商品小问题。'),
 (101,'Positive generic mentions','Brief approval or recommendation, no specific driver','Unknown','好、满意、推荐等低信息正向表达，不虚构具体运营驱动。',None,'medium',False,'中心多为单词/短句；部分有交付，但不足将整个簇命名为某一驱动。'),
 (102,'Positive product / overall mentions','Product approval plus delivery or seller appreciation','Seller / Product','商品好和整体购物体验/交付混合，作为次要正向语料概览。',None,'medium',False,'中心样本同时赞商品和交付，不能隔离价格/价值/客服独立效应。')
]
# AI short translations for centroid examples only; no full-corpus machine translation.
TRANSLATIONS={}  # Per-review translations excluded.

def main():
    cols=['cluster_id','proposed_issue_category','proposed_issue_subcategory','responsible_stage','cluster_summary','merge_with_cluster','confidence','is_mixed_or_unclear','reasoning_summary']
    decisions=pd.DataFrame(DECISIONS,columns=cols);decisions['issue_category']=decisions.proposed_issue_category;decisions['issue_subcategory']=decisions.proposed_issue_subcategory
    decisions['decision_source']='AI review of cluster profile + 10 nearest + 5 random examples; no human gold';decisions['model_name']='ChatGPT Work runtime — exact model identifier unavailable';decisions['naming_version']='s3-taxonomy-v1'
    save(decisions,'ai_taxonomy_decisions')
    reps=load('cluster_representatives');profiles=load('cluster_profiles');payload=[]
    for p in profiles.to_dict('records'):
        cid=p['cluster_id'];p['representative_input']=reps[reps.cluster_id.eq(cid)][['review_row_id','selection','review_text_raw','review_score']].to_dict('records');payload.append(p)
    jsave(payload,'ai_taxonomy_input')
    manual=[]
    for category,g in decisions.groupby('issue_category',sort=False):
        cids=g.cluster_id.tolist();nearest=reps[reps.cluster_id.isin(cids)&reps.selection.eq('centroid_nearest')]
        chosen=pd.concat([nearest[nearest.cluster_id.eq(cid)].head(10//len(cids)) for cid in cids])
        for row in chosen.itertuples():
            manual.append({'order_id':row.order_id,'review_row_id':row.review_row_id,'Portuguese Original':row.review_text_raw,'AI Issue':category,'Cluster':row.cluster_id,'Review Score':row.review_score,'Late Flag':row.is_late,'Late Eligible':row.late_eligible,'Short AI English/Chinese Translation':'','Review Notes':'AI生成短译与簇级建议；尚未人工标注。中心代表样本偏向典型表达，不用于准确率估计。','Human Issue':'','Human Agreement':'','Human Reviewer':'','human_gold_status':'UNLABELED','sampling_method':'centroid-nearest unique text; 10 per final category, balanced across merged clusters'})
    save(pd.DataFrame(manual),'manual_review_sample')
    print(decisions[['cluster_id','issue_category','is_mixed_or_unclear']].to_string(index=False));print('Manual review sample',len(manual))
if __name__=='__main__':main()
