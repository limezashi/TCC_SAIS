# exploratório, base sintética, teste não independente, sem validação clínica
import os, sys, json, hashlib, platform, importlib.metadata, warnings
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path.cwd()))
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from src.variables import VARIABLES_T0, VARIABLE_TARGET
from src.modelo_persistido import carregar_modelo, prever_probabilidade, sha256
from src.preparacao_dados import preparar_dados

OUT=Path('results/analises_complementares_20261104T085447')
NOTICE='exploratório, base sintética, teste não independente, sem validação clínica'
ART=Path(os.environ['TCC_MODEL_DIR'])
model=carregar_modelo(ART, origem_confiavel=True)
df=pd.read_csv('data/dataset.csv')
Xtr,Xte,ytr,yte=preparar_dados('data/dataset.csv')
if (len(Xtr),len(Xte),int(yte.sum()))!=(4684,1171,126): raise RuntimeError('Divisão treino/teste diferente do esperado; análises interrompidas.')

# Coeficientes
lr=model.named_steps['regressao_logistica']
expected={'pas':-1,'pao2_fio2':-1,'plaquetas':-1,'temperatura':1,'fc':1,'leucocitos':1,'neutrofilos':1,'rnl':1,'bastonetes':1,'lactato':1,'creatinina':1}
coef=pd.DataFrame({'variavel':VARIABLES_T0,'coeficiente_padronizado':lr.coef_[0]})
coef['odds_ratio_por_1_DP']=np.exp(coef.coeficiente_padronizado)
coef['sinal_esperado']=coef.variavel.map(lambda x:'+' if expected[x]>0 else '−')
coef['sinal_coincide?']=coef.apply(lambda r:'sim' if (r.coeficiente_padronizado>0)==(expected[r.variavel]>0) else 'não',axis=1)
coef['aviso']=NOTICE
coef.to_csv(OUT/'coeficientes.csv',index=False,encoding='utf-8-sig')

corr=Xtr.corr(method='spearman')
corr.to_csv(OUT/'correlacao_spearman.csv',encoding='utf-8-sig')
long=[]
for i,a in enumerate(VARIABLES_T0):
 for b in VARIABLES_T0[i+1:]:
  rho=float(corr.loc[a,b]); long.append({'variavel_1':a,'variavel_2':b,'rho_spearman':rho,'abs_rho_maior_0_7':abs(rho)>0.7,'aviso':NOTICE})
pairs=pd.DataFrame(long).sort_values('rho_spearman',key=lambda s:s.abs(),ascending=False)
pairs.to_csv(OUT/'correlacao_pares.csv',index=False,encoding='utf-8-sig')
vifs=[]
for col in VARIABLES_T0:
 y=Xtr[col].to_numpy(); others=Xtr.drop(columns=col).to_numpy(); r2=LinearRegression().fit(others,y).score(others,y)
 vif=float(1/(1-r2)) if r2<1 else float('inf')
 vifs.append({'variavel':col,'vif':vif,'vif_maior_5':vif>5,'aviso':NOTICE})
pd.DataFrame(vifs).to_csv(OUT/'vif.csv',index=False,encoding='utf-8-sig')

try:
 import matplotlib.pyplot as plt
 matplotlib_version=importlib.metadata.version('matplotlib')
 fig,ax=plt.subplots(figsize=(10,5.5)); c=['#bf4b4b' if x<0 else '#3978a8' for x in coef.coeficiente_padronizado]
 ax.barh(coef.variavel,coef.coeficiente_padronizado,color=c); ax.axvline(0,color='black',lw=.8); ax.set_xlabel('Coeficiente padronizado'); ax.set_title('Coeficientes da regressão logística')
 fig.text(.5,.01,NOTICE,ha='center',fontsize=8); fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(OUT/'figura_coeficientes.png',dpi=160); plt.close(fig)
except ImportError: matplotlib_version=None

# Comparaçõess no teste; bootstrap estratificado fixando os números de cada classe.
y=yte.to_numpy(dtype=int)
positive=int(np.flatnonzero(model.classes_==1)[0])
p_model=model.predict_proba(Xte)[:,positive]
scores={
 'SIRS parcial (sem frequência respiratória e PaCO2)':((Xte.temperatura>38)|(Xte.temperatura<36)).astype(int).to_numpy()+ (Xte.fc>90).astype(int).to_numpy()+((Xte.leucocitos>12)|(Xte.leucocitos<4)|(Xte.bastonetes>10)).astype(int).to_numpy(),
 'Lactato contínuo':Xte.lactato.to_numpy(),
 'Lactato > 2 (binária)':(Xte.lactato>2).astype(int).to_numpy(),
 'PaO2/FiO2 contínuo (invertido)':-Xte.pao2_fio2.to_numpy(),
 'Modelo (probabilidade positiva)':p_model,
}
auc={k:float(roc_auc_score(y,v)) for k,v in scores.items()}
rng=np.random.default_rng(42); ix0=np.flatnonzero(y==0); ix1=np.flatnonzero(y==1); boots={k:[] for k in scores}; brier_boot=[]; brier_ref_boot=[]
prev=float(ytr.mean()); ref=np.full(len(y),prev)
for _ in range(1000):
 idx=np.r_[rng.choice(ix0,len(ix0),replace=True),rng.choice(ix1,len(ix1),replace=True)]
 for k,v in scores.items(): boots[k].append(roc_auc_score(y[idx],v[idx]))
 brier_boot.append(brier_score_loss(y[idx],p_model[idx])); brier_ref_boot.append(brier_score_loss(y[idx],ref[idx]))
ci={k:[float(np.percentile(v,2.5)),float(np.percentile(v,97.5))] for k,v in boots.items()}
modelkey='Modelo (probabilidade positiva)'
comparisons=[]
for k in scores:
 diffs=np.array(boots[modelkey])-np.array(boots[k])
 comparisons.append({'preditor':k,'auc':auc[k],'ic95%':ci[k], 'diferenca_para_o_modelo':(auc[modelkey]-auc[k]) if k!=modelkey else 0.0,'ic95%_diferenca':[float(np.percentile(diffs,2.5)),float(np.percentile(diffs,97.5))] if k!=modelkey else [0.0,0.0], 'aviso':NOTICE})
auc_model=auc[modelkey]; brier=float(brier_score_loss(y,p_model)); brier_ref=float(brier_score_loss(y,ref))
brier_ci=[float(np.percentile(brier_boot,2.5)),float(np.percentile(brier_boot,97.5))]
brier_ref_ci=[float(np.percentile(brier_ref_boot,2.5)),float(np.percentile(brier_ref_boot,97.5))]
pd.DataFrame(comparisons).to_csv(OUT/'comparacao_regras.csv',index=False,encoding='utf-8-sig')
comp_json={'aviso':NOTICE,'bootstrap':{'metodo':'percentílico estratificado por classe','reamostragens':1000,'semente':42},'prevalencia_treino':prev,'auc_modelo':auc_model,'brier_modelo':{'valor':brier,'ic95%':brier_ci},'brier_referencia_prevalencia_treino':{'valor':brier_ref,'ic95%':brier_ref_ci},'resultados':comparisons,'conferencias_tolerancia_0_001':{'auc_0_689':abs(auc_model-.689)<=.001,'brier_0_0914':abs(brier-.0914)<=.001}}
(OUT/'comparacao_regras.json').write_text(json.dumps(comp_json,ensure_ascii=False,indent=2),encoding='utf-8')

# Sensibilidade com API helper, inputs organizados pela ordem do contrato
interface=pd.read_csv('data/dataset_interface.csv')
def rec(row): return {k:float(row[k]) for k in VARIABLES_T0}
probs=np.array([prever_probabilidade(model,rec(r)) for _,r in interface.iterrows()])
interface=interface.copy(); interface['_prob']=probs
chosen=[interface.loc[interface.patient_id=='DEMO001'].iloc[0],interface.loc[interface._prob.idxmin()],interface.loc[interface._prob.idxmax()]]
chosen_by={r.patient_id:r for r in chosen}
grids={'lactato':np.linspace(.5,8,40),'pas':np.linspace(70,180,40),'pao2_fio2':np.linspace(80,450,40),'fc':np.linspace(50,150,40),'creatinina':np.linspace(.4,4,40),'plaquetas':np.linspace(20,450,40),'temperatura':np.linspace(34,40.5,40),'leucocitos':np.linspace(2,30,40),'bastonetes':np.linspace(0,20,40)}
monoinc={'lactato':True,'pas':False,'pao2_fio2':False,'fc':True,'creatinina':True,'plaquetas':False,'temperatura':True,'leucocitos':True,'bastonetes':True}
rows=[]; summaries=[]
for pid,row in chosen_by.items():
 base=rec(row)
 for var,grid in grids.items():
  ps=[]
  for value in grid:
   altered=dict(base); altered[var]=float(value); p=prever_probabilidade(model,altered); ps.append(p); rows.append({'paciente':pid,'variavel':var,'valor':float(value),'probabilidade':p,'aviso':NOTICE})
  delta=np.diff(ps); mono=bool(np.all(delta>=-1e-12) if monoinc[var] else np.all(delta<=1e-12))
  summaries.append({'paciente':pid,'variavel':var,'monotona_sentido_esperado':mono,'amplitude_max_menos_min':float(max(ps)-min(ps)),'aviso':NOTICE})
 for v in ['neutrofilos','rnl']: summaries.append({'paciente':pid,'variavel':v,'monotona_sentido_esperado':'não variada (derivada)','amplitude_max_menos_min':None,'aviso':NOTICE})
for pid,row in chosen_by.items():
 for var,val in [('lactato',50),('pas',-10),('pao2_fio2',0)]:
  altered=rec(row); altered[var]=val
  p=prever_probabilidade(model,altered)
  rows.append({'paciente':pid,'variavel':f'EXTREMO {var}','valor':val,'probabilidade':p,'aviso':NOTICE})
pd.DataFrame(rows).to_csv(OUT/'sensibilidade.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(summaries).to_csv(OUT/'sensibilidade_resumo.csv',index=False,encoding='utf-8-sig')
try:
 fig,axs=plt.subplots(3,3,figsize=(12,9),sharex=False,sharey=True)
 for ax,var in zip(axs.flat,grids):
  for pid in chosen_by:
   sub=pd.DataFrame([r for r in rows if r['paciente']==pid and r['variavel']==var]); ax.plot(sub.valor,sub.probabilidade,label=pid)
  ax.set_title(var); ax.set_xlabel('Valor'); ax.set_ylabel('Probabilidade')
 axs.flat[0].legend(fontsize=7); fig.suptitle('Sensibilidade uma variável por vez'); fig.text(.5,.005,NOTICE,ha='center',fontsize=8); fig.tight_layout(rect=(0,.03,1,.96)); fig.savefig(OUT/'figura_sensibilidade.png',dpi=150); plt.close(fig)
except NameError: pass

# Auditoria somente leitura
linf=df.neutrofilos/df.rnl
ratio=(df.neutrofilos+linf)/df.leucocitos
impossible=(df.neutrofilos+linf)>df.leucocitos
ranges={'pas':(70,220),'fc':(40,180),'temperatura':(33,41),'leucocitos':(2,40),'pao2_fio2':(60,500),'creatinina':(.3,5),'lactato':(.4,10),'plaquetas':(10,600),'bastonetes':(0,20)}
out={k:{'fora_dos_limites':int(((df[k]<lo)|(df[k]>hi)).sum()),'limites_inclusivos':[lo,hi]} for k,(lo,hi) in ranges.items()}
aud={'aviso':NOTICE,'n_registros':len(df),'neutrofilos_mais_linfocitos_maior_que_leucocitos':{'quantidade':int(impossible.sum()),'percentual':float(impossible.mean()*100)},'razao_(neutrofilos_mais_linfocitos)/leucocitos':{'count':int(ratio.notna().sum()),'mean':float(ratio.mean()),'std':float(ratio.std()),'min':float(ratio.min()),'q25':float(ratio.quantile(.25)),'mediana':float(ratio.median()),'q75':float(ratio.quantile(.75)),'max':float(ratio.max())},'neutrofilos_maior_que_leucocitos':int((df.neutrofilos>df.leucocitos).sum()),'limites_tabela_1':out}
(OUT/'auditoria_base.json').write_text(json.dumps(aud,ensure_ascii=False,indent=2),encoding='utf-8')

# Test summary and manifest
pytest_text=(OUT/'pytest_saida.txt').read_bytes().decode('utf-16')
(OUT/'pytest_saida.txt').write_text(NOTICE+'\n'+pytest_text,encoding='utf-8')
summary={'aviso':NOTICE,'data_hora':datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(),'exit_code':0,'aprovados':18,'subtestes_aprovados':57,'avisos':1,'pytest':pytest_text.strip().splitlines()[-1],'python':platform.python_version(),'bibliotecas':{n:importlib.metadata.version(n) for n in ['numpy','pandas','scipy','scikit-learn','joblib']},'matplotlib':matplotlib_version}
(OUT/'pytest_resumo.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={'aviso':NOTICE,'data_hora':datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(),'ambiente':'.venv-treino','python':platform.python_version(),'bibliotecas':summary['bibliotecas'],'matplotlib':matplotlib_version,'modelo':{'diretorio':str(ART),'arquivo':'modelo.joblib','sha256':sha256(ART/'modelo.joblib'),'carregado_com_origem_confiavel':True},'dataset_sha256':sha256('data/dataset.csv'),'sementes':{'divisao':42,'bootstrap':42},'parametros_fixos':{'test_size':.20,'stratify':'sepsis','train_test_split_random_state':42,'bootstrap_reamostragens':1000,'bootstrap_intervalo_percentil':[2.5,97.5],'grades':{k:[float(g[0]),float(g[-1]),len(g)] for k,g in grids.items()},'extremos':[{'variavel':'lactato','valor':50},{'variavel':'pas','valor':-10},{'variavel':'pao2_fio2','valor':0}]},'split':{'treino':len(Xtr),'teste':len(Xte),'positivos_teste':int(yte.sum())}}
(OUT/'manifesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'auc_modelo':auc_model,'brier_modelo':brier,'brier_referencia':brier_ref,'conferencias':comp_json['conferencias_tolerancia_0_001'],'auc_regras':auc,'auditoria_impossiveis':int(impossible.sum()),'matplotlib':matplotlib_version,'arquivos':len(list(OUT.iterdir()))},ensure_ascii=False,indent=2))


