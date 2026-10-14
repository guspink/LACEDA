"""Configuracoes centrais: colunas, limiares e flags de decisao."""

# ---- CNEFE (layout confirmado pelo cabecalho real) ----
CNEFE = {
 "municipio": "COD_MUNICIPIO",# 7 digitos (IBGE) -> usamos os 6 primeiros
 "setor": "COD_SETOR",# 15 digitos + sufixo de letra (ex.: ...007P)
 "cep": "CEP",
 "localidade": "DSC_LOCALIDADE",
 "tipo": "NOM_TIPO_SEGLOGR",
 "titulo": "NOM_TITULO_SEGLOGR",
 "nome": "NOM_SEGLOGR",
 "numero": "NUM_ENDERECO",
}

# ---- Base de busca (layout confirmado) ----
BUSCA = {
 "logradouro": "consulta_logradouro",
 "numero": "consulta_numero",
 "bairro": "consulta_bairro",
 "cep": "consulta_cep",
 "complemento": "consulta_complemento",
 "municipio": "consulta_municipio",# 6 digitos
}

# ---- Limiares (escala 0-100) ----
SCORE_MIN_RUA = 80# abaixo disso a rua e considerada nao encontrada
TAM_NOME_CURTO = 8# nomes com ate N letras (sem espacos) exigem limiar mais alto
SCORE_MIN_RUA_CURTA = 90# evita casar FAZENDA BICO com FAZENDA ANGICO
SCORE_MATCH_RUA = 90# abaixo disso (mas >= MIN) o resultado vira AMBIGUO
MARGEM_EMPATE = 2.0# ruas a ate X pontos da melhor sao tratadas como empatadas
PENALIDADE_TIPO_DIFERENTE = 5
BONUS_CEP = 4
BONUS_BAIRRO = 4
SCORE_MIN_BAIRRO = 85# similaridade minima para considerar bairro == localidade
SCORE_MIN_LOCALIDADE = 90# fallback por localidade
SCORE_MIN_LOCALIDADE_CURTA = 95
CEP_MAX_SETORES = 10# fallback so por CEP com mais setores que isso vira NAO_ENCONTRADO
# (None = sempre da o palpite, mesmo com CEP cobrindo centenas de setores)
TOP_K_RUAS = 15

# Em casos AMBIGUO, preencher a coluna do setor com o melhor palpite?
# (o status continua AMBIGUO e os candidatos ficam em 'setores_candidatos')
PREENCHER_SETOR_EM_AMBIGUO = True

STATUS_OK = "MATCH_ENCONTRADO"
STATUS_AMBIGUO = "AMBIGUO"
STATUS_NAO = "NAO_ENCONTRADO"

# ---- Saida no formato do enunciado ----
COLUNA_SAIDA = "setor_censitario_encontrado"# setor com 15 digitos (sem a letra final do CNEFE)
MARCADOR_NAO_ENCONTRADO = ""# texto na coluna quando nao ha setor ("" = vazio);
# o status_match sempre identifica o caso