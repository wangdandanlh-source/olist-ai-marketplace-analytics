"""Statistical helpers; no data acquisition and no raw inputs."""
import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests

def wilson(success,n):
    if n==0:return np.nan,np.nan
    z=1.959963984540054; p=success/n; denom=1+z*z/n
    center=(p+z*z/(2*n))/denom; half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return center-half,center+half

class Tests:
    def __init__(self): self.rows=[]
    def add(self,id,family,test,n,stat,p,effect,effect_name,interpretation,**extra):
        self.rows.append(dict(test_id=id,family=family,test=test,N=int(n),statistic=float(stat),p_value=float(p),effect_size=float(effect),effect_name=effect_name,interpretation=interpretation,**extra))
    def categorical(self,id,family,group,outcome,permutations=9999):
        import pandas as pd
        codes,labels=pd.factorize(pd.Series(group).fillna('Missing').astype(str),sort=True)
        y=np.asarray(outcome,dtype=int); k=len(labels); size=np.bincount(codes,minlength=k)
        yes=np.bincount(codes,weights=y,minlength=k); table=np.column_stack([size-yes,yes])
        chi,p,dof,expected=stats.chi2_contingency(table,correction=False)
        method='Pearson chi-square'; seed=20260907
        if (expected<5).any():
            rng=np.random.default_rng(seed); exceed=0
            for _ in range(permutations):
                a=np.bincount(codes,weights=rng.permutation(y),minlength=k)
                sim=np.column_stack([size-a,a]); value=((sim-expected)**2/expected).sum()
                exceed+=value>=chi-1e-10
            p=(exceed+1)/(permutations+1); method=f'Pearson chi-square permutation ({permutations}, fixed margins)'
        v=np.sqrt(chi/len(y))
        self.add(id,family,method,len(y),chi,p,v,'Cramers V','分类变量与结果的关联；非因果。稀疏格使用固定种子置换p值。',df=dof,min_expected=float(expected.min()),groups=k,seed=seed)
        return table
    def mw(self,id,family,x,y):
        x=np.asarray(x); y=np.asarray(y); u,p=stats.mannwhitneyu(x,y,alternative='two-sided',method='asymptotic')
        delta=2*u/(len(x)*len(y))-1
        self.add(id,family,'Mann–Whitney U (two-sided, tie corrected)',len(x)+len(y),u,p,delta,'rank-biserial x minus y','检验分布差异；效应为x高于y的净概率。不是均值/中位数专属检验。',n_x=len(x),n_y=len(y))
    def kw(self,id,family,groups):
        groups=[np.asarray(x) for x in groups if len(x)>=10]
        if len(groups)<2:return
        h,p=stats.kruskal(*groups); n=sum(map(len,groups)); k=len(groups)
        self.add(id,family,'Kruskal–Wallis',n,h,p,max(0,(h-k+1)/(n-k)),'epsilon_squared','仅成熟且可观察子样本的分布比较，不排名全渠道质量。',groups=k)
    def spearman(self,id,x,y):
        rho,p=stats.spearmanr(x,y)
        self.add(id,'cx','Spearman correlation',len(x),rho,p,rho,'rho','等级相关；不能说明因果。')
    def frame(self):
        import pandas as pd
        f=pd.DataFrame(self.rows); f['q_value_bh']=np.nan
        for _,g in f.groupby('family'):
            f.loc[g.index,'q_value_bh']=multipletests(g.p_value,method='fdr_bh')[1]
        f['statistically_significant_fdr05']=f.q_value_bh.lt(.05)
        f['business_significance']='结合原始差值与分母判断；统计显著不自动等于业务重要'
        f['p_value_display']=f.p_value.map(lambda p:'<1e-300 (numerical underflow)' if p==0 else f'{p:.6g}')
        f['q_value_display']=f.q_value_bh.map(lambda p:'<1e-300 (numerical underflow)' if p==0 else f'{p:.6g}')
        f.loc[f.test.str.contains('permutation') & f.p_value.eq(.0001),'p_value_display']='0.0001 (Monte Carlo resolution floor)'
        return f
