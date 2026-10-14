# API SAIS — demonstração acadêmica

A API utiliza exclusivamente a RL persistida. Retorna uma probabilidade do desfecho simulado, sem categorias, diagnósticos, recomendações ou limiares clínicos. Não acessa o dataset, não treina modelos e não usa o ensemble antigo nas requisições.

## Ambiente

O carregador exige Python **3.14.8** e as versões exatas das bibliotecas de ML registradas nos metadados. Não desabilite essa verificação. Confira primeiro `python --version`. Os comandos abaixo são PowerShell, executados na raiz do projeto.

```powershell
python -m venv .venv-api
& .\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

Para executar **todos** os testes históricos, são necessárias também as dependências dos experimentos (incluindo XGBoost e matplotlib), que não são exigidas pela API:

```powershell
& .\.venv-api\Scripts\python.exe -m pip install xgboost==3.4.1 matplotlib==3.11.2
& .\.venv-api\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
```

Somente os testes da API:

```powershell
& .\.venv-api\Scripts\python.exe -B -m unittest discover -s tests -p test_api.py -v
```

## Inicialização

Configure explicitamente a pasta de artefato. Não há seleção automática do modelo mais recente. A pasta é uma configuração local do operador, não um parâmetro recebido dos clientes.

```powershell
$env:TCC_MODEL_DIR = (Resolve-Path 'artifacts\rl_20261014T100407101829_b83773b9').Path
& .\.venv-api\Scripts\python.exe -B -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

No ambiente temporário já utilizado no projeto, substitua `.\.venv-api\Scripts\python.exe` por `"$env:TEMP\tcc_dataset_audit_20261013\Scripts\python.exe"`.

O lifespan carrega uma vez por processo, com as verificações existentes de origem, integridade, ambiente, pipeline e variáveis. O modelo é mantido em memória até o encerramento. Falha de carregamento interrompe a inicialização. Arquivos joblib devem vir somente da origem confiável do próprio projeto; hashes não autenticam terceiros.

Documentação interativa: http://127.0.0.1:8000/docs

Esquema OpenAPI: http://127.0.0.1:8000/openapi.json

## Requisição real de exemplo

```powershell
$dados = @{
    pas = 127.6
    fc = 108.1
    temperatura = 36.08
    leucocitos = 10.4
    neutrofilos = 9.82
    rnl = 5.34
    bastonetes = 5.35
    pao2_fio2 = 223
    creatinina = 1.3
    lactato = 3.15
    plaquetas = 193
} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/predict' -Method Post -ContentType 'application/json' -Body $dados
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health'
```

Resposta para esses valores e esse artefato:

```json
{
  "probabilidade": 0.16466697211865272,
  "versao_modelo": "87130c15c8eb66d1242c6fa731cc5b2da081eb79e3547eeead4a7d936cdd8ccc",
  "finalidade": "Demonstração acadêmica com dados sintéticos; sem validação clínica."
}
```

O valor é calculado por `predict_proba` a cada chamada; não é uma resposta fixa. Alterar as entradas pode alterar a probabilidade. A versão é o hash SHA-256 do arquivo carregado.

Os onze campos são obrigatórios. Aceitam números JSON inteiros e decimais finitos, sem coerção de strings ou booleanos. Ausências, nulos, NaN, infinitos e campos extras são rejeitados. A ordenação interna reutiliza VARIABLES_T0 e a função de predição existente. Não se introduzem limites clínicos adicionais.

## Erros e saúde

- `200`: predição ou saúde bem-sucedida.
- `422`: corpo inválido; resposta com localização, mensagem e tipo do erro, sem ecoar valores não finitos.
- `503`: modelo indisponível; `/health` também retorna esse código.
- `500`: falha inesperada de inferência; mensagem pública genérica, detalhes no log.
- Configuração ausente, hash incorreto ou ambiente incompatível: inicialização interrompida; não há fallback nem treinamento.

`GET /health` retorna `status` e `versao_modelo`. A API não mantém cadastro de pacientes.

## Interface integrada

Com a API iniciada pelo comando acima, abra http://127.0.0.1:8000/frontend/ . Frontend e endpoints são servidos pela mesma origem; não é necessário CORS. Não abra o HTML diretamente por file://.

`GET /demo/patients` lê exclusivamente `data/dataset_interface.csv` e retorna os 30 pacientes sintéticos, identificador, data e onze parâmetros. Não retorna alvo ou probabilidade e não usa a base principal. Somente a pasta frontend é exposta como conteúdo estático.

Pesquise ou pagine a listagem e clique em **Ver avaliação**. Em `avaliacao.html?id=DEMO001`, os parâmetros aparecem com unidades, somente leitura. Clique em **Calcular probabilidade** para enviar exatamente onze números a `POST /predict`. A tela exibe percentual com duas casas decimais e versão do modelo. Nenhuma classificação clínica é atribuída. A data do registro e o momento do cálculo são apresentados separadamente.

Falhas de conexão, resposta inválida e indisponibilidade são exibidas na página; use **Tentar novamente**. A listagem não calcula probabilidades automaticamente. O sistema não grava avaliações ou pacientes.

### Verificação no navegador

Os testes `test_frontend_browser.py` usam Edge instalado no caminho padrão do Windows, em modo headless, e um servidor local temporário. Não modificam dados ou artefatos. Para habilitá-los no ambiente de testes:

```powershell
& .\.venv-api\Scripts\python.exe -m pip install playwright==1.64.0
& .\.venv-api\Scripts\python.exe -B -m unittest discover -s tests -p 'test_*.py' -v
```

Sem Playwright ou Edge, os dois testes de navegador são explicitamente ignorados; os testes HTTP de integração continuam disponíveis. Nesta implementação, os vinte testes foram executados e aprovados, incluindo o navegador em desktop e em viewport de 390 × 844 pixels.
