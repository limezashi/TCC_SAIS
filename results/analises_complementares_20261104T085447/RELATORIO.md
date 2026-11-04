# Análises complementares exploratórias

**Aviso:** exploratório, base sintética, teste não independente, sem validação clínica.

Não é validação clínica e não envolve SOFA. A divisão foi reproduzida com `test_size=0,20`, `random_state=42` e estratificação por `sepsis`: 4.684 registros de treino e 1.171 de teste, com 126 positivos no teste. O modelo persistido foi carregado pelo carregador do projeto com `origem_confiavel=True`, a partir do caminho explícito em `TCC_MODEL_DIR`; não houve retreinamento.

## Testes do projeto

- 18 aprovados; 57 subtestes aprovados; um aviso de depreciação de `starlette.testclient`.
- Excluído `tests/test_frontend_browser.py`, conforme solicitado.
- Python 3.14.8; NumPy 2.5.4; pandas 3.0.6; SciPy 1.18.1; scikit-learn 1.9.1; joblib 1.6.0; matplotlib 3.11.2.

## Coeficientes e colinearidade

Nove dos onze coeficientes coincidiram com o sinal esperado fixado no pedido. Leucócitos e temperatura tiveram coeficientes negativos. O maior par de correlação de Spearman foi leucócitos–neutrófilos (ρ=0,9462; |ρ|>0,7). VIF acima de 5: leucócitos (10,89) e neutrófilos (11,85). RNL apresentou VIF 1,87. A tabela integral está em `coeficientes.csv`; matrizes e VIF em seus CSVs correspondentes.

## Comparação no teste

Intervalos de confiança percentílicos com 1.000 reamostragens estratificadas por classe e semente 42. A diferença foi calculada como AUC do modelo menos AUC do preditor indicado.

| Preditor | AUC | IC95% | Diferença para modelo | IC95% da diferença |
|---|---:|---:|---:|---:|
| Modelo | 0,6892 | 0,6390–0,7370 | 0 | — |
| SIRS parcial (sem frequência respiratória e PaCO2) | 0,5871 | 0,5406–0,6353 | 0,1021 | 0,0459–0,1544 |
| Lactato contínuo | 0,6027 | 0,5520–0,6501 | 0,0865 | 0,0313–0,1460 |
| Lactato > 2 (binária) | 0,5513 | 0,5076–0,5948 | 0,1379 | 0,0816–0,1918 |
| PaO2/FiO2 contínuo (invertido) | 0,6172 | 0,5610–0,6713 | 0,0720 | 0,0259–0,1162 |

Brier do modelo: **0,09137** (IC95% 0,08900–0,09367). Brier da referência com prevalência do treino (0,10781): **0,09602** (IC95% 0,09602–0,09602); o intervalo é constante porque a reamostragem estratificada fixa as contagens das classes. AUC e Brier do modelo reproduzem 0,689 e 0,0914 dentro da tolerância de 0,001.

## Sensibilidade e auditoria da base

Na análise univariada dos três pacientes selecionados, temperatura e leucócitos não variaram monotonicamente no sentido fixado para os três pacientes; as demais variáveis variadas tiveram monotonicidade no sentido esperado. Neutrófilos e RNL não foram variados isoladamente, por serem derivadas conforme pedido. Foram registrados lactato=50, PAS=−10 e PaO2/FiO2=0 como casos extremos demonstrativos.

Na auditoria de 5.855 registros, 1.167 (19,93%) tiveram neutrófilos + linfócitos acima dos leucócitos. A razão (neutrófilos + linfócitos)/leucócitos teve média 0,9142, desvio-padrão 0,1101, mediana 0,9157, mínimo 0,4953 e máximo 1,4415. Nenhum registro teve neutrófilos acima de leucócitos. Não foram encontrados valores fora dos limites informados para as nove variáveis auditadas.

## Divergências e problemas encontrados

- O primeiro carregamento Python gerou bytecode novo sob `src/__pycache__`; os arquivos `.cpython-314.pyc` gerados nessa execução foram removidos e as execuções seguintes desativaram gravação de bytecode.
- O `git status --short` emitiu `warning: could not open directory '.pytest_cache/': Permission denied`. O snapshot inicial não mostrou alterações rastreadas; o aviso de acesso está preservado em `git_status_antes.txt` e também ocorreu na consulta final.
- O backend gráfico padrão do matplotlib tentou iniciar Tk e falhou porque Tcl não está disponível. As figuras foram produzidas com o backend `Agg`; nenhum pacote foi instalado.
- As verificações de AUC e Brier passaram dentro da tolerância especificada. Não houve ajuste de parâmetros ou retreinamento.

**Aviso:** exploratório, base sintética, teste não independente, sem validação clínica.
