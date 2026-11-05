# API SAIS — demonstração acadêmica

A API utiliza exclusivamente o modelo de Regressão Logística (RL) persistido. Retorna uma probabilidade do desfecho simulado, sem categorias, diagnósticos, recomendações ou limiares clínicos. Nas requisições, não acessa o dataset de treinamento, não realiza treinamento e não utiliza o ensemble antigo. Os dados dos pacientes demonstrativos e o histórico das avaliações são consultados e armazenados no PostgreSQL.

## Ambiente

O carregador exige Python **3.14.8** e as versões exatas das bibliotecas de ML registradas nos metadados. Não desabilite essa verificação. Confira primeiro `python --version`. Os comandos abaixo são PowerShell, executados na raiz do projeto.

```powershell
python -m venv .venv-api
& .\.venv-api\Scripts\python.exe -m pip install -r requirements-api.txt
```

## Preparacao do banco PostgreSQL

A API utiliza PostgreSQL para armazenar os pacientes demonstrativos e o historico de avaliacoes. A preparacao do banco e separada da inicializacao da API.

### Pre-requisitos

- PostgreSQL instalado e em execucao.
- Permissão para criar o banco `sais_db` em uma instalação nova ou acesso ao banco já existente.
- DBeaver ou outra ferramenta de administracao PostgreSQL.
- Arquivo `data/dataset_interface.csv`.

### Configuracao da conexao

Na raiz do projeto, crie `.env` a partir de `.env.example` e preencha os valores locais:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=sais_db
DB_USER=postgres
DB_PASSWORD=sua_senha_local
```

Use as credenciais da instalacao local do PostgreSQL. `.env` contem credenciais e nao deve ser versionado.

### Estrutura do banco

Para uma instalacao nova, o DDL abaixo cria as tabelas, restricoes e indices usados pela API. Os campos clinicos sao `NOT NULL` para que cada paciente possua as onze entradas necessarias para a avaliacao.

Em uma instalacao nova, conecte-se primeiro ao banco administrativo `postgres` no DBeaver e execute o comando abaixo para criar `sais_db`. Depois, abra uma conexao com `sais_db` e execute o DDL das tabelas apresentado a seguir. Nao execute este comando no banco ja utilizado pelo projeto.

```sql
CREATE DATABASE sais_db;
```

```sql
CREATE TABLE pacientes (
    patient_id VARCHAR(30) PRIMARY KEY,
    data_avaliacao DATE NOT NULL,
    pas DOUBLE PRECISION NOT NULL,
    fc DOUBLE PRECISION NOT NULL,
    temperatura DOUBLE PRECISION NOT NULL,
    leucocitos DOUBLE PRECISION NOT NULL,
    neutrofilos DOUBLE PRECISION NOT NULL,
    rnl DOUBLE PRECISION NOT NULL,
    bastonetes DOUBLE PRECISION NOT NULL,
    pao2_fio2 DOUBLE PRECISION NOT NULL,
    creatinina DOUBLE PRECISION NOT NULL,
    lactato DOUBLE PRECISION NOT NULL,
    plaquetas DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE avaliacoes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id VARCHAR(30) NOT NULL REFERENCES pacientes(patient_id),
    probabilidade DOUBLE PRECISION NOT NULL
        CHECK (probabilidade >= 0 AND probabilidade <= 1),
    modelo_hash VARCHAR(64) NOT NULL,
    calculado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    entradas_utilizadas JSONB NOT NULL,
    CONSTRAINT ck_entradas_completas CHECK (
        jsonb_typeof(entradas_utilizadas) = 'object'
        AND entradas_utilizadas ?& ARRAY[
            'pas', 'fc', 'temperatura', 'leucocitos', 'neutrofilos', 'rnl',
            'bastonetes', 'pao2_fio2', 'creatinina', 'lactato', 'plaquetas'
        ]
        AND jsonb_typeof(entradas_utilizadas -> 'pas') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'fc') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'temperatura') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'leucocitos') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'neutrofilos') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'rnl') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'bastonetes') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'pao2_fio2') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'creatinina') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'lactato') = 'number'
        AND jsonb_typeof(entradas_utilizadas -> 'plaquetas') = 'number'
    )
);

CREATE INDEX idx_avaliacoes_patient_id ON avaliacoes(patient_id);
CREATE INDEX idx_avaliacoes_calculado_em ON avaliacoes(calculado_em);
```

O DDL apresentado destina-se à criação de uma instalação nova e não deve ser executado sobre tabelas existentes. Na auditoria inicial, as onze colunas clínicas da tabela `pacientes` aceitavam valores `NULL`. Essa condição foi posteriormente corrigida no banco utilizado pelo projeto, e a verificação confirmou que os 30 pacientes demonstrativos possuem as onze variáveis preenchidas. A restrição JSONB do banco atual verifica os tipos das entradas, mas não exige explicitamente a presença de todas as chaves. Já o DDL apresentado para novas instalações utiliza a condição `?&` para exigir a presença das onze chaves, além de verificar seus tipos numéricos.
### Importacao dos pacientes demonstrativos

`data/dataset_interface.csv` contem trinta pacientes sinteticos, identificados pelo prefixo `DEMO`, a data de avaliacao e as onze variaveis clinicas. Para carregar os registros em uma instalacao nova:

1. Se ainda nao existir, crie `sais_db` conectado ao banco administrativo `postgres`, conforme a instrucao da secao Estrutura do banco.
2. Abra uma conexao com `sais_db` no DBeaver e execute o DDL das tabelas uma unica vez.
3. Use a importacao de dados da tabela `pacientes` e selecione `data/dataset_interface.csv`.
4. Configure a origem como CSV, separador virgula e primeira linha com nomes de colunas.
5. Mapeie as treze colunas do arquivo para os campos de destino com o mesmo nome. Deixe `created_at` sem mapeamento para usar o valor padrao do PostgreSQL.
6. Execute a importacao e confira a quantidade e a completude dos registros.

A tabela `avaliacoes` deve iniciar vazia em uma instalacao nova. O historico e criado pela aplicacao quando novas avaliacoes sao realizadas. Faca esta importacao apenas uma vez; repetir a carga em uma tabela ja preenchida pode causar conflito na chave primaria.

Verifique a carga com:

```sql
SELECT
    COUNT(*) AS total_pacientes,
    COUNT(*) FILTER (
        WHERE pas IS NULL
           OR fc IS NULL
           OR temperatura IS NULL
           OR leucocitos IS NULL
           OR neutrofilos IS NULL
           OR rnl IS NULL
           OR bastonetes IS NULL
           OR pao2_fio2 IS NULL
           OR creatinina IS NULL
           OR lactato IS NULL
           OR plaquetas IS NULL
    ) AS pacientes_incompletos
FROM pacientes;
```

O resultado esperado para a carga demonstrativa e `30` pacientes e `0` registros incompletos. A API le os dados do PostgreSQL durante o uso; o CSV serve somente para a preparacao inicial.

## Inicialização

Na raiz do projeto, inicie com um comando:

```powershell
.\run-api.bat
```

O script configura explicitamente a pasta do artefato e inicia o servidor usando o ambiente `.venv-api`, aceitando conexões da rede local. Mantenha o terminal aberto; pare com `Ctrl+C`. Se o ambiente ainda não existir, crie-o e instale as dependências seguindo a seção Ambiente acima. O artefato usado é fixo no script, não há seleção automática do modelo mais recente.

Para testar em outro dispositivo na mesma rede Wi-Fi:

1. Inicie `.\run-api.bat` no computador que hospeda a API.
2. No PowerShell desse computador, execute `ipconfig` e anote o endereço IPv4 da conexão Wi-Fi.
3. No outro dispositivo, abra http://<IPv4-do-computador>:8000/ (por exemplo, http://192.168.1.25:8000/).

Se o Firewall do Windows perguntar, permita o acesso em redes privadas. Não compartilhe o endereço `127.0.0.1`: nele, cada dispositivo aponta para si mesmo. Este servidor de demonstração não tem autenticação; use apenas numa rede confiável e não exponha a porta diretamente à internet.

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

Os principais códigos HTTP utilizados pela API são:

- `200`: requisição concluída com sucesso, incluindo predição, consulta de dados e verificação de saúde.
- `201`: nova avaliação calculada e persistida com sucesso.
- `404`: paciente não encontrado nas operações que exigem um paciente existente.
- `422`: corpo da requisição ou parâmetros inválidos. A resposta apresenta a localização, a mensagem e o tipo do erro, sem ecoar valores não finitos.
- `500`: falha inesperada durante a inferência. A resposta apresenta uma mensagem pública genérica, enquanto os detalhes são registrados no log.
- `503`: modelo indisponível ou banco de dados indisponível nas operações que dependem do PostgreSQL.

`GET /health` retorna `status` e `versao_modelo` e verifica a disponibilidade do modelo carregado. Essa verificação não testa a conexão com o PostgreSQL; portanto, uma resposta bem-sucedida nesse endpoint não garante que as operações de consulta ou persistência estejam disponíveis.

A API consulta os pacientes previamente cadastrados na tabela `pacientes`, mas não oferece endpoints para criação ou edição desses registros. O cadastro demonstrativo é preparado diretamente no banco de dados.

## Endpoints de avaliacao persistida

`POST /patients/{patient_id}/evaluations` recebe o mesmo JSON estrito de onze campos usado por `/predict`, verifica o paciente, calcula com o artefato carregado e insere uma nova linha em `avaliacoes`. Cada chamada cria um novo ID; o historico anterior nao e atualizado. Resposta `201`:

```json
{
  "id": 1,
  "patient_id": "DEMO001",
  "probabilidade": 0.1646,
  "versao_modelo": "<sha256>",
  "calculado_em": "2026-11-05T12:00:00+00:00",
  "finalidade": "Demonstracao academica com dados sinteticos; sem validacao clinica."
}
```

`GET /patients/{patient_id}/evaluations` retorna o historico daquele paciente em ordem decrescente de horario e ID, incluindo `id`, `probabilidade`, `modelo_hash`, `calculado_em` e `entradas_utilizadas`. Para paciente valido sem historico, retorna `[]`. `GET /patients/{patient_id}/evaluations/latest` retorna o registro mais recente. Paciente inexistente retorna `404`; banco indisponivel retorna `503`.

`GET /evaluations/latest` continua disponivel e retorna uma avaliacao recente por paciente com historico. A listagem principal usa o endpoint paginado `/demo/patients`, que associa a ultima avaliacao diretamente aos pacientes da pagina atual. O endpoint consolidado e mantido para compatibilidade; a tela individual continua usando sua rota propria.

`POST /predict` permanece disponivel e nao grava no banco. A interface usa a rota persistida e consulta o PostgreSQL para mostrar o ultimo resultado na listagem e na tela do paciente. O historico oficial fica no banco, sem uso de `localStorage`.

## Listagem paginada de pacientes

`GET /demo/patients` consulta os pacientes e as ultimas avaliacoes diretamente no PostgreSQL. A resposta e paginada no servidor; o navegador recebe somente os itens da pagina atual.

Parametros opcionais:

- `page`: pagina a partir de 1 (padrao `1`).
- `page_size`: itens por pagina, de 1 a 100 (padrao `10`).
- `search`: trecho literal, sem diferenciar maiusculas de minusculas, do `patient_id`; maximo 100 caracteres.
- `data_avaliacao`: data exata no formato `YYYY-MM-DD`.

Exemplo: `GET /demo/patients?page=1&page_size=10&search=demo0&data_avaliacao=2026-10-20`.

Exemplo de resposta:

```json
{
  "items": [
    {
      "patient_id": "DEMO001",
      "data_avaliacao": "2026-10-20",
      "pas": 127.6,
      "fc": 108.1,
      "temperatura": 36.08,
      "leucocitos": 10.4,
      "neutrofilos": 9.82,
      "rnl": 5.34,
      "bastonetes": 5.35,
      "pao2_fio2": 223.0,
      "creatinina": 1.3,
      "lactato": 3.15,
      "plaquetas": 193.0,
      "ultima_avaliacao": {
        "id": 12,
        "probabilidade": 0.1646,
        "modelo_hash": "<sha256>",
        "calculado_em": "2026-10-21T12:00:00+00:00"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "total_pages": 1
}
```

A resposta inclui `items`, `total`, `page`, `page_size` e `total_pages`. Cada item tem `patient_id`, `data_avaliacao`, as onze variaveis clinicas do modelo e `ultima_avaliacao`, que e `null` quando nao ha historico ou contem `id`, `probabilidade`, `modelo_hash` e `calculado_em`. Pagina sem resultados retorna `items: []`; `total_pages` e zero quando nao ha correspondencias. Parametros invalidos retornam `422`.

A consulta conta os registros com os mesmos filtros e busca uma pagina ordenada por `patient_id`. Um `LEFT JOIN LATERAL` busca somente para os pacientes dessa pagina a avaliacao ordenada por `calculado_em DESC, id DESC`, com limite de uma linha. O filtro de identificador usa `strpos(lower(...))`; os valores de busca, data, limite e deslocamento sao vinculados como parametros SQL. A consulta geral nao exige prefixo `DEMO`; os 30 registros sinteticos permanecem na tabela e a listagem nao importa dados externos.

Os indices observados no banco sao a chave primaria de `pacientes(patient_id)`, a chave primaria de `avaliacoes(id)`, e indices separados em `avaliacoes(patient_id)` e `avaliacoes(calculado_em)`. Nao foram criados indices nesta alteracao. Se o volume justificar, avalie um indice composto `avaliacoes(patient_id, calculado_em DESC, id DESC)` para o LATERAL; como ele compartilha o prefixo `patient_id`, reavalie o indice isolado atual antes de manter ambos. O filtro de data pode se beneficiar de um indice em `pacientes(data_avaliacao)`. Busca parcial com `strpos` nao usa um B-tree; para tabelas grandes, meca antes e considere `pg_trgm` com indice GIN. A chave primaria em `patient_id` ja auxilia a ordenacao deterministica.

## Interface integrada

Com a API iniciada pelo comando acima, abra http://127.0.0.1:8000/. A listagem consulta os pacientes por pagina no PostgreSQL; os 30 pacientes sinteticos continuam disponiveis; a avaliacao exibe os onze valores, registra cada calculo no historico e mostra confirmacao somente apos persistencia confirmada. O frontend e a API sao servidos pela mesma origem; nao abra o HTML diretamente por `file://`.

A demonstracao usa dados sinteticos e tem finalidade exclusivamente academica. As probabilidades nao tem validacao clinica, nao constituem diagnostico ou recomendacao e nao devem orientar atendimento hospitalar.
