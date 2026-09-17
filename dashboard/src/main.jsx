import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import * as echarts from 'echarts/core';
import {LineChart,BarChart} from 'echarts/charts';
import {GridComponent,TooltipComponent,LegendComponent,AriaComponent} from 'echarts/components';
import {SVGRenderer} from 'echarts/renderers';
import D from '../data/dashboard.json';
import './style.css';

echarts.use([LineChart,BarChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,SVGRenderer]);
const K=D.kpi, teal='#087E8B',blue='#315EE8',gray='#607486',amber='#B56A17',navy='#173246';
const num=(n,d=0)=>new Intl.NumberFormat('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}).format(n);
const pct=(n,d=2)=>num(n*100,d)+'%';
const issueNames={'Delivery waiting / non-receipt':'等待／尚未收到','Incomplete order / missing units':'少件／部分收到','Product condition / mismatch':'商品状态／不符','Mixed resolution / service':'混合解决／服务','Generic / Unclear':'泛化／不明确','Mixed / rating-text mismatch':'混合／评分文本不一致','Positive delivery mentions':'正向交付表达','Positive generic mentions':'泛化好评','Positive product / overall mentions':'正向商品／整体体验'};
const factorNames={unique_customers:'用户规模',purchase_frequency:'购买频次',aov:'AOV'};
const titles=['核心经营诊断','增长与留存','商家生命周期','履约与体验','AI 用户之声','策略与验证'];
const routes=['overview','growth','seller','fulfillment','ai-voc','strategy'];
const subtitles=['先给判断，再看证据：3 个问题 → 3 套行动','GMV 增长之后，用户有没有留下来？','商家签约之后，是否真正进入持续经营？','从迟到事实到用户体验，再找到可干预环节','结构化数据告诉我们发生了什么，VOC 帮助解释体验','把分析收口为行动，并明确下一步如何验证'];

function Chart({id,labels,series,kind='bar',horizontal=false,percent=false,max,height=230,decimals=1,legend=false}){
 const ref=useRef(); const unit=percent?'%':'';
 useEffect(()=>{
  if(!labels.length)return;
  const c=echarts.init(ref.current,null,{renderer:'svg'});
  const hasNeg=series.some(s=>s.values.some(v=>v<0));
  const valueAxis={type:'value',min:hasNeg?null:0,max:max??null,axisLabel:{color:gray,fontSize:10,formatter:v=>num(v,max&&max<=4?1:0)+unit},splitLine:{lineStyle:{color:'#E6EDF2'}}};
  const catAxis={type:'category',data:labels,axisTick:{show:false},axisLine:{show:false},axisLabel:{color:gray,fontSize:10,interval:kind==='line'?(i=>labels.length<7||i%6===0||i===labels.length-1):0,showMinLabel:true,showMaxLabel:true,hideOverlap:true}};
  c.setOption({animation:false,aria:{enabled:true},color:[teal,blue,gray,amber],grid:{left:horizontal?12:8,right:30,top:legend?34:18,bottom:10,containLabel:true},legend:{show:legend,top:0,textStyle:{color:gray,fontSize:10}},tooltip:{trigger:'axis',confine:true,backgroundColor:'#fff',borderColor:'#D7E1E7',textStyle:{color:navy,fontSize:12},formatter:params=>{const p=Array.isArray(params)?params:[params];return p[0].axisValueLabel+'<br/>'+p.map(t=>t.marker+t.seriesName+': '+num(t.value,decimals)+unit).join('<br/>');}},xAxis:horizontal?valueAxis:catAxis,yAxis:horizontal?{...catAxis,inverse:true}:valueAxis,series:series.map(s=>({name:s.name,type:kind,data:s.values,itemStyle:{color:s.color},lineStyle:{width:3,type:s.dashed?'dashed':'solid'},symbol:'circle',symbolSize:5,showSymbol:kind!=='line',barMaxWidth:18,label:{show:horizontal,position:'right',fontSize:10,color:gray,formatter:v=>num(v.value,decimals)+unit},emphasis:{focus:'series'}}))});
  const resize=new ResizeObserver(()=>c.resize());resize.observe(ref.current);return()=>{resize.disconnect();c.dispose();};
 },[id,labels.join('|'),JSON.stringify(series),kind,horizontal,percent,max,height,legend]);
 if(!labels.length)return <div className="no-data">当前筛选无数据</div>;
 return <div ref={ref} id={id} className="chart" style={{height}} role="img"/>;
}
function Card({title,sub,children,actions,className=''}){return <section className={'card '+className}><div className="card-head"><div><h2>{title}</h2>{sub&&<p>{sub}</p>}</div>{actions&&<div className="actions">{actions}</div>}</div>{children}</section>}
function Kpis({items}){return <div className="kpi-row" style={{'--count':items.length}}>{items.map(([label,value,note])=><div className="kpi" key={label}><div className="kpi-label">{label}</div><strong>{value}</strong><p>{note}</p></div>)}</div>}
function Select({label,value,onChange,options}){return <label className="filter">{label}<select value={value} onChange={e=>onChange(e.target.value)}>{options.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>}
function Tag({children,tone='finding'}){return <span className={'tag '+tone}>{children}</span>}
function ActionBox({title,children,metric,guardrail}){return <div className="action-box"><div><Tag tone="action">RECOMMENDATION</Tag><h3>{title}</h3><p>{children}</p></div>{metric&&<div className="action-meta"><span><b>验证指标</b>{metric}</span>{guardrail&&<span><b>Guardrail</b>{guardrail}</span>}</div>}</div>}
function Diagnosis({no,theme,title,evidence,judgment,action}){return <article className="diagnosis"><div className="diag-top"><span className="diag-no">0{no}</span><Tag>{theme}</Tag></div><h2>{title}</h2><p className="diag-evidence">{evidence}</p><div className="diag-judgment"><b>经营判断</b><span>{judgment}</span></div><div className="diag-action"><b>Action</b><span>{action}</span><i>→</i></div></article>}
function Insight({children}){return <div className="insight"><Tag>INSIGHT</Tag><p>{children}</p></div>}
function EvidencePath({steps}){return <div className="evidence-path">{steps.map((s,i)=><React.Fragment key={s}><div><span>{String(i+1).padStart(2,'0')}</span><b>{s}</b></div>{i<steps.length-1&&<i>→</i>}</React.Fragment>)}</div>}

function Overview(){
 const [metric,setMetric]=useState('gmv');
 return <>
  <div className="intro"><Tag tone="summary">EXECUTIVE SUMMARY</Tag><h2>增长、Seller 与 CX 三条线索指向同一个问题：<br/>平台需要从“规模扩张”走向“经营质量”。</h2><p>以下结论均来自公开 Olist 历史数据。策略为基于证据提出的下一步行动，不声称已上线或产生业务效果。</p></div>
  <div className="diagnosis-grid">
   <Diagnosis no="1" theme="GROWTH" title="增长很快，但主要靠拉新" evidence={<>July GMV YoY <b>+{pct(K.julyYoY)}</b> · 用户规模贡献约 <b>80%</b> · 全期复购 <b>{pct(K.repeat)}</b></>} judgment="规模增长强，但用户留存没有同步建立。" action="首购 → 二购激活"/>
   <Diagnosis no="2" theme="SELLER" title="签约之后，Seller 成长明显分化" evidence={<><b>{num(K.mql)} → {num(K.deals)}</b> MQL-to-Deal · 成熟 90D Seller 中 <b>{num(K.inactiveN)}/{num(K.sellerN)}</b> 最后 30D 无记录订单</>} judgment="商家运营不能止于签约，应延伸到成交后的持续经营。" action="Seller 30/60/90D 生命周期运营"/>
   <Diagnosis no="3" theme="CX" title="迟到之外，还有等待过程的信息问题" evidence={<>整体迟到率 <b>{pct(K.late)}</b> · 签收后调整 OR <b>{num(K.or,2)}</b> · AI VOC 识别等待/未收到主题</>} judgment="物流效率之外，等待过程中的信息不确定性也是可干预环节。" action="主动延迟沟通 + A/B 验证"/>
  </div>
  <Kpis items={[["商品 GMV",num(K.gmv/1e6,2)+'M BRL','核心期 2017-01 至 2018-07'],['已签收订单',num(K.orders),'核心分析样本'],['仅一单用户',pct(K.oneTime),'观测窗口内'],['整体迟到率',pct(K.late),num(K.lateN)+' / '+num(K.lateDen)]]}/>
  <div className="two-col wide-left"><Card title="证据 1｜平台月度经营趋势" sub="购买月 · 核心已签收订单" actions={<Select label="趋势指标" value={metric} onChange={setMetric} options={[["gmv","GMV · 百万 BRL"],["orders","已签收订单"]]}/> }><Insight>2018-07 GMV 同比 +{pct(K.julyYoY)}，但增长质量需要继续看“用户规模、频次、客单价”分别贡献了什么。</Insight><Chart id="overview-trend" kind="line" labels={D.monthly.map(r=>r.month)} series={[{name:metric==='gmv'?'GMV（百万BRL）':'订单',values:D.monthly.map(r=>metric==='gmv'?r.gmv/1e6:r.orders),color:teal}]} max={metric==='gmv'?1.2:undefined} decimals={metric==='gmv'?3:0} height={220}/></Card>
  <Card title="证据 2｜July YoY 增长分解" sub="数学分解，不代表因果贡献"><Insight>约 80% 的 GMV 增量来自用户规模，购买频次贡献为负，提示增长更多来自“更多人买”，而不是“同一用户买得更频繁”。</Insight><Chart id="overview-decomp" horizontal percent max={100} decimals={2} labels={D.decomposition.map(r=>factorNames[r.factor])} series={[{name:'贡献份额',values:D.decomposition.map(r=>r.share*100),color:blue}]} height={205}/></Card></div>
 </>
}

function Growth(){return <>
 <div className="question-banner"><span>BUSINESS QUESTION</span><h2>GMV 增长以后，用户有没有留下来？</h2><p>增长拆解回答“钱从哪里增长”，复购观察回答“用户是否形成持续购买”。</p></div>
 <Kpis items={[["July GMV YoY",'+'+pct(K.julyYoY),'2018-07 vs 2017-07'],['用户规模贡献',pct(D.decomposition.find(r=>r.factor==='unique_customers').share),'数学贡献份额'],['观测复购率',pct(K.repeat),num(K.repeatCount)+' / '+num(K.customers)],['仅一单用户',pct(K.oneTime),'核心窗口内']]}/>
 <div className="two-col"><Card title="增长来源：规模扩张主导" sub="GMV = Customers × Purchase Frequency × AOV"><Insight>用户规模贡献约 80%，AOV 提供正贡献，而购买频次为负贡献。平台当前的高速增长主要靠扩大购买用户规模。</Insight><Chart id="growth-decomp" horizontal percent max={100} decimals={2} labels={D.decomposition.map(r=>factorNames[r.factor])} series={[{name:'贡献份额',values:D.decomposition.map(r=>r.share*100),color:blue}]} height={220}/><p className="caption">Mathematical contribution, not causal attribution.</p></Card>
 <Card title="留存信号：复购仍然很低" sub={'共同成熟样本 n='+num(K.repDen)}><Insight>共同成熟用户的 90D 累计复购约 {pct(K.rep90)}；全期观测复购约 {pct(K.repeat)}。低复购是现象，当前数据不能单独证明原因。</Insight><Chart id="growth-repeat" kind="line" percent max={3} decimals={2} labels={D.repurchase.map(r=>r.days+'D')} series={[{name:'累计复购',values:D.repurchase.map(r=>r.rate*100),color:teal}]} height={220}/></Card></div>
 <div className="two-col"><Card title="优先人群：高价值一次性用户" sub={'样本支出 P75 = '+num(K.p75)+' BRL，仅用于本项目分层'}><Chart id="growth-segments" horizontal percent max={80} decimals={2} labels={D.customerSegments.map(r=>({'High-value One-time':'≥P75 · 仅一单','High-value Repeat':'≥P75 · 复购','One-time':'低于P75 · 仅一单','Repeat':'低于P75 · 复购'}[r.segment]))} series={[{name:'客户占比',values:D.customerSegments.map(r=>r.share*100),color:teal}]} height={225}/><p className="caption">不强行做 RFM：约 {pct(K.oneTime,0)} 用户只有一单，Frequency 缺乏区分度。</p></Card>
 <Card title="从分析到行动" sub="策略不是结果：下一步需要实验验证"><ActionBox title="首购 → 二购激活" metric="30/60/90D 二购率、增量 GMV" guardrail="优惠成本、毛利、退订率">优先针对高价值一次性用户，结合首购品类、客单价、履约体验与购买时间分层，在 30/60/90D 窗口测试差异化复购触达。</ActionBox><div className="why"><b>为什么先做这件事？</b><p>因为增长已经证明平台能获得新用户，而频次与复购没有同步建立。与继续堆拉新指标相比，二购激活更直接对应当前暴露的增长质量问题。</p></div></Card></div>
 </>}

function Seller(){
 const [origin,setOrigin]=useState('all'); const rows=(origin==='all'?D.origins:D.origins.filter(r=>r.origin===origin)).sort((a,b)=>b.mql-a.mql);
 return <>
 <div className="question-banner"><span>BUSINESS QUESTION</span><h2>Seller 签下来以后，是否真正进入持续经营？</h2><p>获客只是入口。更值得管理的是成交后的首单激活、成长与经营预警。</p></div>
 <Kpis items={[["MQL",num(K.mql),'2017-06 至 2018-05'],['成交 Deals',num(K.deals),'观测成交快照'],['观测转化率',pct(K.conversion),'非成熟队列转化'],['可匹配 Seller',num(K.matched)+' / '+num(K.deals),pct(K.match)+' 数据覆盖']]}/>
 <div className="lifecycle"><div><b>ACQUISITION</b><span>MQL</span></div><i>→</i><div><b>CONVERSION</b><span>成交 Deal</span></div><i>→</i><div><b>ACTIVATION</b><span>首单 / 早期经营</span></div><i>→</i><div><b>GROWTH</b><span>30/60/90D</span></div><i>→</i><div className="warn"><b>WATCH</b><span>Inactivity Signal</span></div></div>
 <div className="two-col"><Card title="入口：8,000 MQL → 842 Deals" sub="没有获客成本，不能比较渠道 ROI"><Insight>观测转化率 {pct(K.conversion)} 只能描述当前快照。842 个成交 Seller 中仅 {num(K.matched)} 个能与订单数据匹配，后续经营分析必须限定在可观察子样本。</Insight><Chart id="seller-funnel" horizontal labels={['MQL','成交 Deals']} series={[{name:'数量',values:[K.mql,K.deals],color:blue}]} max={K.mql} decimals={0} height={190}/></Card>
 <Card title="渠道差异：只作为诊断，不做 ROI 排名" sub="筛选仅影响当前表" actions={<Select label="Seller Origin" value={origin} onChange={setOrigin} options={[["all","全部来源"],...D.origins.map(r=>[r.origin,r.origin])]}/>}><div className="table-scroll"><table><thead><tr><th>Origin</th><th>MQL</th><th>Deals</th><th>观测转化</th></tr></thead><tbody>{rows.map(r=><tr key={r.origin}><td>{r.origin}</td><td>{num(r.mql)}</td><td>{num(r.deals)}</td><td>{pct(r.rate)}</td></tr>)}</tbody></table></div><p className="caption">缺少渠道成本与完整后续经营追踪，因此不判断“最佳渠道”。</p></Card></div>
 <div className="two-col"><Card title="成熟 Seller：经营表现明显分化" sub={'共同成熟 90D 样本 n='+num(K.sellerN)}><Insight>90D GMV 均值 {num(K.sellerMean,2)} BRL 明显高于中位数 {num(K.sellerMedian,2)} BRL，分布右偏；只看均值会高估典型 Seller 表现。</Insight><Chart id="seller-gmv" horizontal labels={['P25','中位数','P75','均值']} series={[{name:'90D GMV · BRL',values:[K.sellerP25,K.sellerMedian,K.sellerP75,K.sellerMean],color:teal}]} decimals={2} height={215}/></Card>
 <Card title="从签约管理转向成长管理" sub="41/124 是预警信号，不等同于流失率"><div className="signal-big"><span>最后 30D 无记录订单</span><strong>{num(K.inactiveN)} / {num(K.sellerN)}</strong><b>{pct(K.inactive)}</b><small>30D inactivity signal</small></div><ActionBox title="Seller 30/60/90D 生命周期运营" metric="首单激活率、30/60/90D 有单率、GMV" guardrail="商家触达负担、补贴成本">按“新成交 → 首单待激活 → 成长 → 稳定 → inactivity signal”组织运营动作，对不同阶段分别诊断商品、价格、流量与履约障碍。</ActionBox></Card></div>
 </>}

function Fulfillment(){
 const [timing,setTiming]=useState('after'); const score=timing==='all'?D.scoreTiming:D.scoreTiming.slice(1);
 return <>
 <div className="question-banner"><span>BUSINESS QUESTION</span><h2>用户为什么对履约不满意？可干预的环节在哪里？</h2><p>先确认迟到事实，再观察评分关联，最后用 VOC 理解用户在等待过程中表达了什么。</p></div>
 <EvidencePath steps={[`迟到率 ${pct(K.late)}`,`迟到订单评分更低`,`调整后 OR ${num(K.or,2)}`,`VOC 暴露等待问题`,`主动延迟沟通`]}/>
 <Kpis items={[["整体迟到率",pct(K.late),num(K.lateN)+' / '+num(K.lateDen)],['签收后迟到均分',num(D.scoreTiming[1].late,3),'n='+num(D.scoreTiming[1].lateN)],['签收后准时均分',num(D.scoreTiming[1].ontime,3),'n='+num(D.scoreTiming[1].ontimeN)],['调整后 OR',num(K.or,2),'95% CI '+num(K.orLow,2)+'–'+num(K.orHigh,2)]]}/>
 <div className="two-col"><Card title="迟到并非稳定不变" sub="购买月 · 已签收且日期有效"><Insight>整体迟到率为 {pct(K.late)}，但月度波动明显。2018-03 等月份值得回查；当前数据本身不能解释异常原因。</Insight><Chart id="late-month" kind="line" percent max={20} decimals={2} labels={D.lateMonthly.map(r=>r.month)} series={[{name:'迟到率',values:D.lateMonthly.map(r=>r.rate*100),color:amber}]} height={215}/></Card>
 <Card title="迟到与低评分存在明显关联" sub="Association only · 不解释为因果" actions={<Select label="评价时点" value={timing} onChange={setTiming} options={[["after","只看签收后"],["all","两种口径对照"]]}/> }><Insight>签收后作答样本中，迟到订单均分约 {num(D.scoreTiming[1].late,2)}，准时订单约 {num(D.scoreTiming[1].ontime,2)}；调整后 OR {num(K.or,2)} 说明关联仍然存在，但 OR 不是概率增幅。</Insight><Chart id="score-gap" labels={score.map(r=>r.scope)} series={[{name:'迟到',values:score.map(r=>r.late),color:amber},{name:'准时',values:score.map(r=>r.ontime),color:teal}]} legend max={5} decimals={2} height={190}/></Card></div>
 <div className="two-col"><Card title="VOC 把“迟到”翻译成用户体验" sub="等待/未收到主题需结合评价时点阅读"><div className="hero-bars"><div><span>全部核心正文 · 等待主题</span><b>{pct(K.waitAll)}</b><i><em style={{width:pct(K.waitAll)}}/></i></div><div><span>签收后作答 · 等待主题</span><b>{pct(K.waitAfter)}</b><i><em style={{width:pct(K.waitAfter)}}/></i></div><div><span>签收后正文基线</span><b>{pct(K.waitBaseline)}</b><i><em style={{width:pct(K.waitBaseline)}}/></i></div></div><p className="caption">这些比例是相应正文样本内的迟到率，不是最终未交付概率。等待主题会受到评价时点影响。</p></Card>
 <Card title="可干预机会：等待过程的信息不确定性" sub="不是泛泛地“优化物流”，而是定义可测试动作"><ActionBox title="主动延迟沟通" metric="14D 等待/未收到相关主动联系率" guardrail="取消、投诉、退订、通知成本、ETA 准确性">当订单首次超过原预计送达时间且仍未签收时，主动告知延迟、提供可靠的更新 ETA（若暂无则明确说明）和下一步处理入口。</ActionBox><div className="why"><b>证据边界</b><p>历史数据只能支持“迟到、低评分、等待表达之间存在关联”。策略是否有效，必须通过前瞻实验验证。</p></div></Card></div>
 </>}

function AI(){
 const [role,setRole]=useState('primary'); const rows=D.issues.filter(r=>r.role===role).sort((a,b)=>b.n-a.n);
 return <>
 <div className="question-banner"><span>BUSINESS QUESTION</span><h2>结构化订单数据看不到的体验问题，能否从评论中被系统地发现？</h2><p>AI 在这里不是结论生成器，而是非结构化信息的“发现助手”；业务判断仍回到订单与履约数据验证。</p></div>
 <div className="ai-role"><div><b>STRUCTURED DATA</b><span>订单 / 履约 / 评分</span><p>告诉我们 <strong>WHAT</strong> happened</p></div><i>+</i><div><b>AI-ASSISTED VOC</b><span>{num(K.voc)} 条葡语正文</span><p>帮助理解 <strong>WHY / HOW</strong> users described it</p></div><i>→</i><div className="result"><b>BUSINESS VALIDATION</b><span>回到结构化指标</span><p>形成可解释的经营判断</p></div></div>
 <Kpis items={[["Canonical 正文",num(K.voc),'全部日期语料'],['主问题语料',num(K.primary),'评分 ≤3'],['正向语料',num(K.positive),'评分 ≥4'],['Mixed / Other',pct(K.mixed),'主问题保守宽类别']]}/>
 <div className="two-col"><Card title="AI 发现：评论中的体验主题" sub="主题是探索性簇级映射，不是人工标注真值" actions={<Select label="语料组" value={role} onChange={setRole} options={[["primary","主问题语料"],["positive","正向语料"]]}/> }><Insight>{role==='primary'?'等待/未收到、少件/部分收到、商品状态/不符等主题提供了比星级评分更具体的问题线索。':'正向语料用于补充理解体验，不将正向评论简单视为“没有问题”。'}</Insight><Chart id="voc-topics" horizontal labels={rows.map(r=>issueNames[r.issue])} series={[{name:'评论 N',values:rows.map(r=>r.n),color:teal}]} decimals={0} height={250}/></Card>
 <Card title="从 AI 发现到业务验证" sub="以等待主题为例"><EvidencePath steps={[`${num(K.voc)} 条正文`,`语义聚类`,`AI 辅助主题命名`,`评价时点拆分`,`订单履约验证`]}/><div className="voc-case"><Tag>CASE</Tag><h3>“等待／未收到”不能直接解释为最终未交付</h3><p>全部核心正文中的等待主题迟到率很高，但限定到签收后作答后显著下降。说明评价时点会改变文本含义，因此必须把 AI 主题重新关联订单事实后再做判断。</p><div className="mini-stats"><span><b>{pct(K.waitAll)}</b>全部核心正文</span><span><b>{pct(K.waitAfter)}</b>签收后作答</span><span><b>{pct(K.waitBaseline)}</b>签收后基线</span></div></div></Card></div>
 <div className="method-strip"><div><Tag tone="method">METHOD</Tag><b>Multilingual MiniLM · {K.embeddingDim} dimensions → clustering → AI-assisted naming → structured validation</b></div><p>限制：No Human Gold Set · Review self-selection · Mixed / Other {pct(K.mixed)} · Correlation ≠ Causation。方法细节保留在 GitHub 文档，不让算法盖过业务结论。</p></div>
 </>}

function Strategy(){return <>
 <div className="intro strategy-intro"><Tag tone="summary">STRATEGY & EXPERIMENT</Tag><h2>分析不是终点。每个经营问题都需要对应一个动作，<br/>再用可观察指标判断是否值得继续。</h2><p>以下均为 Recommendation / Experiment Design，不是已实施结果。</p></div>
 <div className="strategy-grid">
  <article><Tag>GROWTH</Tag><h2>首购 → 二购激活</h2><div className="strategy-problem"><b>Problem</b><span>复购约 {pct(K.repeat)}，约 {pct(K.oneTime,0)} 用户仅一单；GMV 增长主要由用户规模驱动。</span></div><div className="strategy-do"><b>Do</b><span>对高价值一次性用户按品类、客单价、履约体验和购买时间分层，在 30/60/90D 窗口测试差异化触达。</span></div><div className="strategy-check"><b>Validate</b><span>二购率 / 90D 复购 / 增量 GMV；同时看优惠成本与毛利。</span></div></article>
  <article><Tag>SELLER</Tag><h2>30/60/90D Seller Lifecycle</h2><div className="strategy-problem"><b>Problem</b><span>成熟 Seller 表现右偏，{num(K.inactiveN)}/{num(K.sellerN)} 最后 30D 无记录订单。</span></div><div className="strategy-do"><b>Do</b><span>建立“新成交 → 首单待激活 → 成长 → 稳定 → inactivity signal”运营状态，分阶段诊断经营障碍。</span></div><div className="strategy-check"><b>Validate</b><span>首单激活率 / 30-60-90D 有单率 / GMV；不把 inactivity 直接当 churn。</span></div></article>
  <article><Tag>CX</Tag><h2>主动延迟沟通</h2><div className="strategy-problem"><b>Problem</b><span>迟到率 {pct(K.late)}，迟到与低评分关联明显，VOC 暴露等待过程的信息问题。</span></div><div className="strategy-do"><b>Do</b><span>首次超过原 ETA 且仍未签收时，发送延迟说明 + 可靠更新 ETA + 处理入口。</span></div><div className="strategy-check"><b>Validate</b><span>随机 A/B；14D 等待相关主动联系率为主指标，低评分为次指标。</span></div></article>
 </div>
 <Card title="A/B Test Design｜主动延迟沟通" sub="DESIGN ONLY · No experiment was run" className="experiment-card"><div className="experiment-grid"><div><span>01 · ELIGIBILITY</span><b>首次检查已超过原 ETA、仍未签收、未取消且有可用联系渠道</b></div><div><span>02 · RANDOMIZATION</span><b>客户级 1:1 随机；首次符合条件的订单作为 index order</b></div><div><span>03 · TREATMENT</span><b>延迟通知 + 可验证更新 ETA + 下一步处理/联系入口</b></div><div><span>04 · PRIMARY</span><b>14 天内等待/未收到相关客户主动联系率（ITT）</b></div><div><span>05 · SECONDARY</span><b>30 天内低评分 ≤2；同时报告评价响应率</b></div><div><span>06 · GUARDRAILS</span><b>取消、投诉、退订、重复触达、通知成本、ETA 准确性</b></div></div><p className="caption">当前 Olist 数据没有同定义的实验主指标历史基线，因此不虚构样本量或预期提升。样本量需在上线前由独立 logging pilot 的 p0 与业务 MDE 决定。</p></Card>
 <div className="closing"><b>PORTFOLIO TAKEAWAY</b><span>SQL / Python 负责把事实算清楚，AI 帮助组织非结构化信息，最终价值在于把证据转成可验证的经营动作。</span></div>
 </>}

function App(){
 const getPage=()=>{const i=routes.indexOf(location.hash.slice(2));return i<0?0:i};
 const [page,setPage]=useState(getPage);
 useEffect(()=>{const h=()=>{setPage(getPage());window.scrollTo(0,0)};window.addEventListener('hashchange',h);return()=>window.removeEventListener('hashchange',h)},[]);
 const pages=[Overview,Growth,Seller,Fulfillment,AI,Strategy]; const Component=pages[page];
 return <><a className="skip" href="#main-content">跳到内容</a><aside><div className="brand">MARKET / LAB<small>OLIST · BUSINESS CASE</small></div><nav>{titles.map((t,i)=><a key={t} href={'#/'+routes[i]} aria-current={page===i?'page':undefined}><span>{String(i+1).padStart(2,'0')}</span>{t}</a>)}</nav><div className="sidebar-foot">ANALYSIS WINDOW<br/><b>Jan 2017 — Jul 2018</b><br/><br/>FINDING → ACTION → VALIDATION</div></aside><main id="main-content"><header><div><div className="eyebrow">MARKETPLACE BUSINESS CASE / {String(page+1).padStart(2,'0')}</div><h1>{titles[page]}</h1><p>{subtitles[page]}</p></div><div className="scope"><b>{page===4?'VOC：全部日期 / 验证：核心窗口':page===2?'Seller Funnel：2017-06 至 2018-05':'核心窗口：2017-01 至 2018-07'}</b><small>Finding、Recommendation 与 Experiment Result 严格区分</small></div></header><Component key={page}/><footer><span>Olist public data · 聚合指标 · 经营分析作品</span><span>策略为建议；A/B 为设计，未声称实施效果</span></footer></main></>
}
createRoot(document.getElementById('root')).render(<App/>);
