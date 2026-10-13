# Avaliação OOF — 13/10/2026

Avaliação experimental em dados sintéticos. Nenhum modelo foi escolhido definitivamente para a API.

## Protocolo

- Dataset SHA-256: `0ffe90627e19a05c4d25ad747fe19d5766e7a1080dff512e98679d5330d196ca`.
- Divisão existente preservada: 80/20, estratificada, random_state=42.
- Avaliação somente nos 4.684 registros de treinamento: 505 positivos e 4.179 negativos.
- Cinco folds compartilhados, estratificados e embaralhados, random_state=42.
- Folds 1–4: 937 observações de validação; fold 5: 936. Todos com 101 positivos.
- Cada observação tem uma previsão OOF por candidato. Nenhum índice reservado ao teste aparece nas OOF.
- SVM: StandardScaler → SVC dentro do CalibratedClassifierCV; cv=5, ensemble=False e demais hiperparâmetros preservados.
- Ensemble fixo: 90% RL + 10% RF. Sem pesquisa de pesos, stacking ou seleção de limiar.
- Brier principal; AUC secundária; desvio-padrão entre folds com ddof=0.
- Python 3.14.8; NumPy 2.5.4; pandas 3.0.6; scikit-learn 1.9.1; XGBoost 3.4.1; matplotlib 3.11.2.

## Resultados globais

| Modelo | Brier média ± DP | Brier OOF | AUC média ± DP | AUC OOF |
|---|---:|---:|---:|---:|
| RL | 0,093936 ± 0,001363 | 0,093935 | 0,647353 ± 0,021345 | 0,646608 |
| RF | 0,097430 ± 0,001211 | 0,097430 | 0,602461 ± 0,016097 | 0,602523 |
| XGB | 0,106234 ± 0,003052 | 0,106233 | 0,592746 ± 0,026697 | 0,592469 |
| SVM | 0,096271 ± 0,000144 | 0,096271 | 0,510893 ± 0,030483 | 0,505013 |
| RL + RF 90/10 | 0,093934 ± 0,001276 | 0,093933 | 0,648739 ± 0,019784 | 0,647895 |
| Prevalência do treino do fold | 0,096190 ± 0,000036 | 0,096190 | 0,500000 ± 0 | 0,499904 |

A AUC global do baseline pode diferir ligeiramente de 0,5 porque a prevalência de treinamento varia entre folds. Sua AUC em cada fold é exatamente 0,5.

## Métricas por fold

Ordem: folds 1, 2, 3, 4 e 5. Valores completos em metricas_folds.csv.

| Modelo | AUC por fold | Brier por fold |
|---|---|---|
| RL | 0,649403; 0,638069; 0,682766; 0,649640; 0,616885 | 0,093582; 0,094026; 0,092177; 0,093528; 0,096365 |
| RF | 0,581997; 0,617930; 0,611463; 0,617018; 0,583898 | 0,099087; 0,096397; 0,097040; 0,096021; 0,098604 |
| XGB | 0,569591; 0,591655; 0,641587; 0,593455; 0,567439 | 0,110189; 0,107706; 0,102746; 0,102551; 0,107977 |
| SVM | 0,456215; 0,499147; 0,538550; 0,529206; 0,531345 | 0,096539; 0,096273; 0,096132; 0,096159; 0,096251 |
| RL + RF | 0,647449; 0,644204; 0,679734; 0,654283; 0,618023 | 0,093754; 0,093918; 0,092329; 0,093434; 0,096233 |

## Classificação OOF com limiar 0,5

Matrizes: [[verdadeiros negativos, falsos positivos], [falsos negativos, verdadeiros positivos]]. Precisão e F1 são definidos como zero quando não há positivos preditos.

| Modelo | Sensibilidade | Especificidade | Precisão | F1 | Matriz |
|---|---:|---:|---:|---:|---|
| RL | 0% | 99,9761% | 0% | 0 | [[4178,1],[505,0]] |
| RF | 0% | 99,8564% | 0% | 0 | [[4173,6],[505,0]] |
| XGB | 1,9802% | 98,4925% | 13,6986% | 0,034602 | [[4116,63],[495,10]] |
| SVM | 0% | 100% | 0% | 0 | [[4179,0],[505,0]] |
| RL + RF | 0% | 99,9761% | 0% | 0 | [[4178,1],[505,0]] |

## Distribuição das probabilidades

| Modelo | Mínimo | Mediana | Média | P95 | Máximo |
|---|---:|---:|---:|---:|---:|
| RL | 0,012534 | 0,097541 | 0,107677 | 0,214947 | 0,701578 |
| RF | 0 | 0,100000 | 0,121798 | 0,280000 | 0,550000 |
| XGB | 0,000026 | 0,021145 | 0,061949 | 0,276681 | 0,910239 |
| SVM | 0,082700 | 0,107680 | 0,107903 | 0,114597 | 0,233077 |
| RL + RF | 0,013280 | 0,098280 | 0,109089 | 0,216440 | 0,684420 |

A baixa sensibilidade no limiar 0,5 é compatível com probabilidades predominantemente inferiores a esse valor e forte sobreposição entre classes. Na RL, as médias são 0,104539 para negativos e 0,133641 para positivos; na SVM são praticamente iguais.

## Calibração e baseline

Curvas e tamanhos dos grupos estão em calibracao.csv e calibracao.png. São análises descritivas por quantis, com limites repetidos colapsados.

RL e ensemble têm Brier melhor que o baseline. RF e XGB têm Brier pior; SVM se aproxima do baseline, com discriminação próxima de 0,5. RL e ensemble apresentam desvios de calibração: no grupo de probabilidades mais altas, a RL prevê 0,232717 e observa 0,196162; o ensemble prevê 0,233576 e observa 0,202559. Não se afirma calibração perfeita ou validade clínica.

## Comparação pareada RL versus ensemble

| Fold | ΔAUC (ensemble − RL) | ΔBrier (ensemble − RL) |
|---|---:|---:|
| 1 | −0,001954 | +0,000172 |
| 2 | +0,006135 | −0,000107 |
| 3 | −0,003032 | +0,000152 |
| 4 | +0,004643 | −0,000094 |
| 5 | +0,001138 | −0,000132 |

O ensemble melhora ambas as métricas em três folds e piora em dois. A diferença média de Brier é −0,000001946; a diferença global OOF é −0,000001918. A diferença média de AUC é +0,001386 e a global +0,001287.

O ganho de Brier é mínimo e não consistente em todos os folds. Esta execução não fornece evidência suficiente para justificar a complexidade adicional do ensemble. Isso não constitui teste de equivalência, significância ou prova de ausência de benefício. Cinco folds têm treinamentos sobrepostos; o DP entre folds não é intervalo de confiança.

## Limiares alternativos — somente descrição

| Modelo | Limiar | Sensibilidade | Especificidade | Precisão | F1 |
|---|---:|---:|---:|---:|---:|
| RL | 0,05 | 96,63% | 12,42% | 11,76% | 0,209757 |
| RL | 0,10 | 65,54% | 54,68% | 14,88% | 0,242491 |
| RL | 0,15 | 31,49% | 83,39% | 18,64% | 0,234168 |
| RL | 0,20 | 12,08% | 94,02% | 19,61% | 0,149510 |
| Ensemble | 0,05 | 96,63% | 11,56% | 11,66% | 0,208147 |
| Ensemble | 0,10 | 67,92% | 53,84% | 15,10% | 0,247029 |
| Ensemble | 0,15 | 30,69% | 82,94% | 17,86% | 0,225783 |
| Ensemble | 0,20 | 12,48% | 93,78% | 19,50% | 0,152174 |

Resultados para todos os candidatos e os 14 limiares estão em limiares.csv. Não foi escolhido limiar operacional. Se houver seleção futura, escolher em validação interna e avaliar em folds externos, somente no treinamento.

## Verificação e limitações

- Três testes automatizados aprovados: cobertura/separação/scaler/ensemble, isolamento interno da SVM e rejeição de índices desalinhados.
- Nenhum aviso dos estimadores durante a avaliação.
- Matplotlib emitiu aviso de permissão no cache padrão e utilizou automaticamente cache temporário; todos os gráficos foram gerados.
- Dataset, divisão, variáveis, modelo_final.py e notebooks preservados, com verificação de hashes.
- Nenhum treinamento final, seleção de pesos, stacking, API ou avaliação do teste nesta execução.
- Resultados não substituem os experimentos anteriores, nem comprovam generalização temporal ou clínica.
- A correção da SVM precisa ser mencionada ao comparar resultados históricos.

## Reprodução

No ambiente com as versões registradas em requirements-execucao.txt:

```powershell
python -B -m unittest discover -s tests -p test_avaliacao_oof.py -v
python -B scripts/avaliar_modelos_oof.py
```

O executor cria uma pasta nova por execução e registra dados, configurações, parâmetros, versões e hashes. Nenhum modelo definitivo da API foi escolhido.
