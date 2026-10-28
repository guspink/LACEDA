"""Testes unitarios para a logica de matching e regras de decisao."""
import pandas as pd
import pytest
from src import config
from src.matcher import Consulta, IndiceCnefe, casar


@pytest.fixture
def base_cnefe_teste():
    data = [
        # Municipio 290130 - Rua Unica em 1 setor
        {
            "mun6": "290130",
            "setor": "290130405000006P",
            "cep": "46830000",
            "localidade_key": "CENTRO",
            "tipo": "RUA",
            "nome_valido": True,
            "street_nome_key": "RIO BAIANO",
            "street_full_key": "RUA RIO BAIANO",
            "numero": 10.0,
        },
        # Municipio 290070 - Rua Longa que cruza 2 setores
        {
            "mun6": "290070",
            "setor": "290070205000100P",
            "cep": "48030260",
            "localidade_key": "CENTRO",
            "tipo": "RODOVIA",
            "nome_valido": True,
            "street_nome_key": "BR 101",
            "street_full_key": "RODOVIA BR 101",
            "numero": 100.0,
        },
        {
            "mun6": "290070",
            "setor": "290070205000200P",
            "cep": "48030260",
            "localidade_key": "ZONA RURAL",
            "tipo": "RODOVIA",
            "nome_valido": True,
            "street_nome_key": "BR 101",
            "street_full_key": "RODOVIA BR 101",
            "numero": 500.0,
        },
        # Municipio 291840 - Rua de letra unica (RUA E)
        {
            "mun6": "291840",
            "setor": "291840705000209P",
            "cep": "48905000",
            "localidade_key": "CENTRO",
            "tipo": "RUA",
            "nome_valido": True,
            "street_nome_key": "E",
            "street_full_key": "RUA E",
            "numero": 20.0,
        },
        # Municipio 292925 - Setor com nome generico invalido
        {
            "mun6": "292925",
            "setor": "292925505000011P",
            "cep": "44915000",
            "localidade_key": "JACAREZINHO",
            "tipo": "RUA",
            "nome_valido": False,  # Marcado como invalido pelo filtro
            "street_nome_key": "SEM DENOINACAO",
            "street_full_key": "RUA SEM DENOINACAO",
            "numero": 26.0,
        },
    ]
    return pd.DataFrame(data)


def test_match_encontrado_setor_unico(base_cnefe_teste):
    indice = IndiceCnefe(base_cnefe_teste)
    q = Consulta(
        mun6="290130",
        cep="46830000",
        numero=None,
        tipo="RUA",
        full_key="RUA RIO BAIANO",
        nome_key="RIO BAIANO",
        bairro_key="CENTRO",
    )
    res = casar(q, indice)
    assert res["status_match"] == config.STATUS_OK
    assert res["codigo_setor_censitario"] == "290130405000006P"
    assert res["codigo_setor_15dig"] == "290130405000006"


def test_ambiguo_quando_setores_diferem(base_cnefe_teste):
    indice = IndiceCnefe(base_cnefe_teste)
    q = Consulta(
        mun6="290070",
        cep="48030260",
        numero=None,  # Sem numero para desempatar
        tipo="RODOVIA",
        full_key="RODOVIA BR 101",
        nome_key="BR 101",
        bairro_key="",
    )
    res = casar(q, indice)
    assert res["status_match"] == config.STATUS_AMBIGUO
    assert res["n_setores_candidatos"] == 2


def test_desempate_por_numero(base_cnefe_teste):
    indice = IndiceCnefe(base_cnefe_teste)
    q = Consulta(
        mun6="290070",
        cep="48030260",
        numero=100,  # Numero exato do primeiro setor
        tipo="RODOVIA",
        full_key="RODOVIA BR 101",
        nome_key="BR 101",
        bairro_key="",
    )
    res = casar(q, indice)
    assert res["status_match"] == config.STATUS_OK
    assert res["codigo_setor_censitario"] == "290070205000100P"


def test_rua_letra_unica_e(base_cnefe_teste):
    indice = IndiceCnefe(base_cnefe_teste)
    q = Consulta(
        mun6="291840",
        cep="48905000",
        numero=20,
        tipo="RUA",
        full_key="RUA E",
        nome_key="E",
        bairro_key="CENTRO",
    )
    res = casar(q, indice)
    # Deve encontrar com sucesso em vez de descartar como stopword
    assert res["status_match"] == config.STATUS_OK
    assert res["codigo_setor_censitario"] == "291840705000209P"


def test_rua_sem_denominacao_nao_casa_como_rua(base_cnefe_teste):
    indice = IndiceCnefe(base_cnefe_teste)
    q = Consulta(
        mun6="292925",
        cep="44915000",
        numero=26,
        tipo="RUA",
        full_key="RUA SEM DENOMINACAO",
        nome_key="SEM DENOMINACAO",
        bairro_key="",
    )
    res = casar(q, indice)
    # Nao deve casar como 'LOGRADOURO' de 100% em cima de nome invalido
    assert res["nivel_match"] != "LOGRADOURO"
