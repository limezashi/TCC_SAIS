# Seleção experimental do modelo para a API

## Conclusão

Recomenda-se **Regressão Logística**, na configuração existente, para a futura API que retorna probabilidade. Não houve implementação da API, alteração de modelo_final.py, ajuste de pesos, hiperparâmetros ou limiares.

O ensemble foi o melhor candidato numérico na OOF original de semente 42. Após cinco partições estratificadas de cinco folds, a RL obteve o menor Brier médio e a maior AUC média. Venceu o ensemble em ambas as métricas em quatro das cinco repetições. O ganho inicial do ensemble não se manteve.

Não foi demonstrada diferença estatisticamente significativa nem equivalência entre os dois. A diferença absoluta continua pequena. A recomendação combina desempenho repetido favorável à RL com o critério previamente registrado de menor complexidade quando a diferença permanece incerta.

## Protocolo previamente registrado

Ver protocolo.json: Brier principal, AUC secundária, calibração e estabilidade como apoio. Bootstrap pareado estratificado por classe: 5.000 amostras, semente 20261013. Partições: sementes 42, 43, 44, 45 e 46. Mesmos folds para todos os candidatos em cada repetição. Pesos 90/10 e hiperparâmetros existentes preservados.

Somente os 4.684 registros de treinamento foram utilizados, incluindo 505 positivos. A divisão treino/teste não mudou. O teste foi descartado após sua separação e seus índices foram usados apenas para verificar exclusão das OOF. As sementes alteram as partições CV; as sementes internas dos estimadores permanecem 42.

Semente 42 reutilizada após conferir todos os hashes de artefatos, dataset, fontes utilizadas e versões centrais das bibliotecas. Recalculados Brier/AUC, verificados identificadores, alvo, ordem, ausência de índices de teste e fórmula do ensemble. As outras quatro repetições foram treinadas novamente.

## Bootstrap sobre a OOF original

Diferenças: ensemble menos RL. Brier negativo favorece ensemble; AUC positiva favorece ensemble.

| Métrica | Diferença observada | Intervalo percentil 95% |
|---|---:|---:|
| Brier | −0,000001918 | [−0,000120918; +0,000116043] |
| AUC | +0,001287437 | [−0,002067421; +0,004683495] |

O ensemble teve menor Brier em 51,92% das reamostragens e maior AUC em 78,18%. Essas frações não são probabilidades posteriores de superioridade nem p-valores. Ambos os intervalos incluem zero.

Limitações: bootstrap condicional a previsões fixas, sem reajuste dos modelos. Estratificação preserva a prevalência empírica. Não incorpora toda a incerteza do treinamento, do desenho sintético ou da seleção. Folds compartilham dados de treinamento. Não extrapolar esses intervalos para validade clínica ou equivalência formal.

## Ranking pelo Brier médio global OOF das cinco repetições

DP populacional entre repetições (ddof=0), não erro-padrão nem intervalo de confiança.

| Posição | Modelo | Brier médio | DP Brier | AUC média | DP AUC |
|---|---|---:|---:|---:|---:|
| 1 | RL | 0,093801751 | 0,000070531 | 0,650289069 | 0,002157760 |
| 2 | RL + RF 90/10 | 0,093847102 | 0,000053597 | 0,649991021 | 0,001562012 |
| 3 | SVM | 0,096281802 | 0,000045666 | 0,507184484 | 0,010125036 |
| 4 | RF | 0,097662869 | 0,000194511 | 0,598739904 | 0,004311154 |
| 5 | XGB | 0,105510060 | 0,000952317 | 0,583318099 | 0,005566198 |

Baseline: Brier 0,096190013. RL e ensemble superaram o baseline nas cinco repetições. SVM, RF e XGB tiveram Brier pior em todas. O terceiro lugar da SVM é estritamente pelo critério principal; sua discriminação próxima do acaso e a ausência de melhora sobre o baseline não justificam sua escolha. RF discrimina melhor que SVM, mas tem pior Brier.

## RL versus ensemble por repetição

| Semente | Brier RL | Brier ensemble | AUC RL | AUC ensemble |
|---|---:|---:|---:|---:|
| 42 | 0,093935178 | 0,093933260 | 0,646607863 | 0,647895299 |
| 43 | 0,093728235 | 0,093766765 | 0,652603896 | 0,652295897 |
| 44 | 0,093769202 | 0,093828164 | 0,651402699 | 0,650413785 |
| 45 | 0,093777307 | 0,093849108 | 0,651659997 | 0,650703778 |
| 46 | 0,093798835 | 0,093858215 | 0,649170890 | 0,648646343 |

Ensemble menos RL, na média: ΔBrier = +0,000045351 e ΔAUC = −0,000298048. Portanto, na média repetida, ambas as métricas favorecem RL. Nos 25 folds, o ensemble venceu em Brier em 10 e em AUC em 12. Esses folds e repetições não são independentes; não foi feito teste t/binomial tratando-os como amostras independentes.

O ensemble tem DP entre repetições ligeiramente menor, mas essa estabilidade não é evidência de maior precisão estatística nem compensa automaticamente pior desempenho médio. Não foi definida margem clínica de equivalência ou importância prática; a pequena diferença não deve ser denominada clinicamente relevante ou irrelevante.

## Calibração

Curvas por candidato e repetição em calibracao_repetida.png; valores e tamanhos de grupos em calibracao.csv. Cada curva usa grupos por quantis, com limites repetidos colapsados, sem ajustar calibrador novo.

Na análise descritiva, a média entre repetições do desvio absoluto ponderado por tamanho dos grupos foi: RL 0,012341; ensemble 0,012844; SVM 0,012882; RF 0,034561; XGB 0,081229. Esse indicador depende da discretização e não substitui o Brier nem prova calibração adequada. RL e ensemble continuam com desvios. SVM pode ficar perto da prevalência, com aparente calibração média, sem discriminar positivos e negativos.

## Distinções necessárias

- **Melhor resultado numérico original:** ensemble.
- **Melhor desempenho médio repetido:** RL em Brier e AUC.
- **Consistência entre partições:** RL vence ensemble em quatro de cinco repetições; vantagem inicial do ensemble não se sustenta.
- **Evidência de melhoria significativa:** não demonstrada pelo bootstrap condicional; não foi inventado p-valor.
- **Decisão de engenharia:** RL, pois o desempenho repetido favorece essa configuração e ela requer um único estimador/pipeline, contra duas bases no ensemble.

## Integridade e reprodução

Arquivos originais de resultados, dataset, módulos existentes e notebooks permaneceram iguais, verificados por SHA-256. Não houve avisos dos modelos. Cinco testes automatizados passaram (três OOF e dois bootstrap). Novos arquivos de código: src/selecao_modelo.py, scripts/selecionar_modelo_oof.py e tests/test_selecao_modelo.py.

Ambiente: Python 3.14.8; NumPy 2.5.4; pandas 3.0.6; scikit-learn 1.9.1; XGBoost 3.4.1. Demais versões em metadados.json. Fontes identificadas por hashes.

```powershell
python -B -m unittest discover -s tests -p 'test_*.py' -v
python -B scripts/selecionar_modelo_oof.py
```

O executor cria uma pasta nova, não sobrescreve a execução anterior. Esta recomendação se restringe à simulação acadêmica; não representa validação clínica, temporal ou externa. A seleção pelo treinamento também tem incerteza e otimismo, e as cinco partições não constituem cinco populações independentes.
