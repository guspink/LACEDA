# Geocodificação e Vinculação de Endereços ao CNEFE Bahia
### Desafio Prático - Engenharia de Dados Jr. (CIDACS / FIOCRUZ)

Solução computacional desenvolvida para localizar o setor censitário correspondente a cada endereço da base de busca utilizando como referência o **CNEFE Bahia** (Cadastro Nacional de Endereços para Fins Estatísticos - IBGE).

---

## 1. Visão Geral e Abordagem

O problema não consiste em um *join* relacional simples, mas sim em **Record Linkage probabilístico / fuzzy matching** entre textos livres não padronizados e uma base volumosa (~9 milhões de registros, ~1.46 GB).

### Pipeline em Cascata
1. **Ingestão e Blocking Estruturado**:
   - O CNEFE Bahia é lido em blocos (via Pandas ou Spark) e filtrado pelos municípios e CEPs presentes na base de busca.
   - O código do município IBGE (`COD_MUNICIPIO` com 7 dígitos) é compatibilizado com os 6 dígitos da busca (`consulta_municipio`).
   - Remove duplicatas por espécie e limpa valores nulos literais (`"NULL"`, `None`).
2. **Padronização Simétrica (Mesmo pipeline para busca e CNEFE)**:
   - Caixa alta, remoção de acentos e pontuação.
   - Separação de letras e números (ex.: `BR101` $\to$ `BR 101`).
   - Expansão de tipos (`R` $\to$ `RUA`, `AV` $\to$ `AVENIDA`, `TRAV` $\to$ `TRAVESSA`, `FAZ` $\to$ `FAZENDA`, etc.).
   - Expansão de títulos e modificadores (`DR` $\to$ `DOUTOR`, `STA` $\to$ `SANTA`, `RESI` $\to$ `RESIDENCIAL`, etc.).
   - Tratamento de contrações frequentes (`CAIXA D'AGUA` / `CAIXA D AGUA` $\to$ `CAIXA DAGUA`).
   - Extração do número estruturado (`SN`, `S/N`, vazio ou `0` são mapeados para ausência de número).
   - Remoção de stopwords sem apagar nomes de ruas curtas (ex.: `RUA E` preserva o token `E`).
   - Exclusão de nomes genéricos/inválidos no CNEFE (`SEM DENOMINACAO`, `PROJETADA`, etc.).
3. **Vinculação em Cascata Hierárquica**:
   - **Nível 1 - Logradouro (+ Número)**:
     - Similaridade textual de alta performance via RapidFuzz (ou difflib como fallback).
     - Comparação do nome da via isolado do tipo para evitar falsos positivos por compartilhamento de tipo (ex.: `FAZENDA BICO` vs `FAZENDA ANGICO`).
     - Compatibilidade de tipos equivalentes sem penalidade espúria (ex.: `CONDOMINIO` $\approx$ `CONJUNTO` $\approx$ `RESIDENCIAL`).
     - Bônus quando CEP ou Bairro conferem.
     - Seleção de setor censitário por número exato ou número aproximado de mesma paridade (mesmo lado da calçada).
   - **Nível 2 - Localidade / Povoado / Fazenda**:
     - Fallback quando não há logradouro compatível, buscando casar a localidade/distrito/bairro na base do CNEFE.
   - **Nível 3 - CEP**:
     - Fallback final baseado no polígono/setores atendidos pelo CEP no município.
4. **Régua de Decisão e Ambiguidade por Unicidade de Setor**:
   - **`MATCH_ENCONTRADO`**: Encontrado candidato confiável. **Crucial:** Se múltiplos endereços ou números empatam, mas todos pertencem ao **mesmo setor censitário**, o match é considerado válido e único.
   - **`AMBIGUO`**: Candidatos empatados pertencem a **setores censitários diferentes**, ou a similaridade da rua está na faixa limítrofe.
   - **`NAO_ENCONTRADO`**: Nenhuma similaridade satisfatória ou CEP abrangendo mais de `CEP_MAX_SETORES` setores (evitando palpites arbitrários).

---

## 2. Decisão Arquitetural: Spark + RapidFuzz vs. Elasticsearch

O edital concede liberdade técnica e sugere tecnologias como Docker, Spark e Elasticsearch. A arquitetura escolhida foi:
* **Spark (`--engine spark`)**: Utilizado para o processamento distribuído, filtragem e deduplicação da base volumosa do CNEFE (1.46 GB), gerando um cache Parquet compacto e veloz.
* **RapidFuzz em Memória (Python)**:
  - Após o blocking por município, o espaço de busca para as 100 consultas cabe perfeitamente em memória RAM.
  - A lógica de negócio para desempate (unicidade de setor entre múltiplos candidatos, paridade de número, bônus de CEP/bairro) torna-se muito mais **auditável, transparente e determinística** em código do que em DSLs de consultas do Elasticsearch.
  - Elimina a dependência de um cluster Elasticsearch externo, simplificando a reprodução e garantindo execução total em menos de 1 minuto.

---

## 3. Estrutura do Repositório

```text
.
├── docker-compose.yml          # Orquestração do container Docker
├── Dockerfile                  # Imagem base Python 3.11 com Java JRE (Spark)
├── requirements.txt            # Dependências básicas (pandas, rapidfuzz, pyarrow, pytest)
├── requirements-spark.txt      # Dependências adicionais para o engine Spark
├── src/
│   ├── config.py               # Mapeamento de colunas, limiares e flags de decisão
│   ├── normalize.py            # Pipeline simétrico de padronização de endereços
│   ├── similarity.py           # Cálculo de similaridade com penalidade de ordem
│   ├── ingest.py               # Leitura da busca e CNEFE filtrado
│   ├── spark_prep.py           # Preparação paralela com Spark e cache Parquet
│   ├── matcher.py              # Cascata de vinculação e regras de decisão
│   ├── main.py                 # Orquestrador do pipeline de ponta a ponta
│   └── evaluate.py             # Avaliação de acurácia contra gabarito
├── data/
│   ├── base_busca.csv          # 107 endereços da busca
│   ├── cnefe_bahia.csv         # Base CNEFE Bahia (ou Parquet correspondente)
│   └── cache/                  # Cache gerado para reexecuções instantâneas
├── output/
│   └── resultado_final.csv     # Saída final estruturada no padrão do edital
├── tests/
│   ├── test_normalize.py       # Testes unitários de padronização e stopwords
│   ├── test_similarity.py      # Testes unitários de métricas de similaridade
│   └── test_matcher.py         # Testes de cascata, unicidade de setor e ambiguidade
└── README.md                   # Documentação completa
```

---

## 4. Instruções de Execução

### Opção 1: Execução Local (Python / venv)
```bash
# Instalação das dependências
pip install -r requirements.txt

# Execução padrão (leitura em blocos com Pandas, sem dependência de Java)
python -m src.main --cnefe data/cnefe_bahia.csv --busca data/base_busca.csv --saida output/resultado_final.csv

# Execução com engine Spark (requer Java 11+ e `pip install -r requirements-spark.txt`)
python -m src.main --cnefe data/cnefe_bahia.csv --busca data/base_busca.csv --saida output/resultado_final.csv --engine spark
```

### Opção 2: Execução com Docker / Docker Compose
```bash
docker compose run --build app
```

### Execução dos Testes Automatizados
```bash
pytest -v
```
*(Todos os 30 testes unitários cobrem padronização, tratamento de stopwords, paridade de números e regras de unicidade de setor).*

---

## 5. Formato da Saída

O arquivo [`output/resultado_final.csv`](file:///e:/UFBA/LACEDA/output/resultado_final.csv) contém:
* **Todas as colunas originais** da base de busca;
* **`setor_censitario_encontrado`**: Código de 15 dígitos conforme especificado no edital (sem a letra final do CNEFE);
* **Colunas de auditoria**:
  - `status_match`: `MATCH_ENCONTRADO` / `AMBIGUO` / `NAO_ENCONTRADO`
  - `codigo_setor_censitario`: Código completo de 16 caracteres do CNEFE (com a letra final)
  - `nivel_match`: Nível que resolveu a consulta (`LOGRADOURO+NUMERO`, `LOGRADOURO+NUMERO_APROX`, `LOGRADOURO`, `LOCALIDADE`, `CEP`)
  - `score_confianca`: Score final de similaridade (0 a 100)
  - `n_setores_candidatos`: Quantidade de setores censitários possíveis
  - `setores_candidatos`: Lista dos setores candidatos
  - `logradouro_cnefe`: Denominação correspondente encontrada no CNEFE
  - `motivo`: Descrição clara em caso de ambiguidade ou não localização

*Nota:* Para obter uma saída estrita contendo apenas as colunas originais + `setor_censitario_encontrado` + `status_match`, utilize a flag `--minimo`.

---

## 6. Premissas e Limitações Conhecidas

1. **Paridade Numérica**: Quando a numeração exata do imóvel não consta no CNEFE, assume-se que o número mais próximo de mesma paridade (par/ímpar) tem maior probabilidade de pertencer ao mesmo setor censitário.
2. **Ambiguidade**: Endereços sem número em vias extensas que cortam múltiplos setores censitários são classificados honestamente como `AMBIGUO`, não forçando uma atribuição arbitrária.
3. **Ausência de Coordenadas Geográficas na Busca**: A base de busca não possui coordenadas prévias de latitude/longitude, de modo que o linkage baseia-se exclusivamente em semântica textual e hierarquia político-administrativa (Município $\to$ CEP $\to$ Logradouro $\to$ Número $\to$ Bairro).
