"""Testes unitarios para o modulo de normalizacao de enderecos."""
import pytest
from src.normalize import (
    chave_comparacao,
    normalizar_cep,
    normalizar_municipio,
    normalizar_texto,
    parse_numero,
    separar_tipo,
    tipos_compativeis,
)


class TestNormalizarTexto:
    def test_remocao_acentos_e_maiusculas(self):
        assert normalizar_texto("Praça São João") == "PRACA SAO JOAO"
        assert normalizar_texto("Largo da Sé") == "LARGO DA SE"
        assert chave_comparacao(normalizar_texto("Largo da Sé")) == "LARGO SE"

    def test_expansao_abreviacoes_tipo(self):
        assert normalizar_texto("R. Rio Baiano") == "RUA RIO BAIANO"
        assert normalizar_texto("Av. Principal") == "AVENIDA PRINCIPAL"
        assert normalizar_texto("Trav. das Flores") == "TRAVESSA DAS FLORES"
        assert normalizar_texto("Faz. Esperança") == "FAZENDA ESPERANCA"

    def test_expansao_titulos_e_modificadores(self):
        assert normalizar_texto("RUA DR. ANTONIO CARLOS") == "RUA DOUTOR ANTONIO CARLOS"
        assert normalizar_texto("AV PROF. MILTON SANTOS") == "AVENIDA PROFESSOR MILTON SANTOS"
        assert normalizar_texto("CONDOMINIO RESI FLORES") == "CONDOMINIO RESIDENCIAL FLORES"

    def test_separacao_letras_e_digitos(self):
        assert normalizar_texto("RODOVIA BR101") == "RODOVIA BR 101"
        assert normalizar_texto("RUA A1") == "RUA A 1"

    def test_limpeza_nulos_e_literais_none(self):
        assert normalizar_texto(None) == ""
        assert normalizar_texto("NULL") == ""
        assert normalizar_texto("None EVILASIO FIRMATO") == "EVILASIO FIRMATO"

    def test_contracoes_especiais(self):
        assert normalizar_texto("CAIXA D'AGUA") == "CAIXA DAGUA"
        assert normalizar_texto("CAIXA D AGUA") == "CAIXA DAGUA"
        assert normalizar_texto("OLHO D'AGUA") == "OLHO DAGUA"


class TestChaveComparacao:
    def test_remocao_stopwords(self):
        assert chave_comparacao("RUA DOS ANDRADAS") == "RUA ANDRADAS"
        assert chave_comparacao("ESTRADA DO COCO") == "ESTRADA COCO"

    def test_preservacao_ruas_de_letra_unica(self):
        # Regressao: a letra 'E' nao deve ser apagada quando for o unico token
        assert chave_comparacao("E") == "E"
        assert chave_comparacao("A") == "A"
        assert chave_comparacao("D") == "D"


class TestSepararTipo:
    def test_tipo_identificado(self):
        tipo, resto = separar_tipo("RUA RIO BAIANO")
        assert tipo == "RUA"
        assert resto == "RIO BAIANO"

    def test_tipo_ausente(self):
        tipo, resto = separar_tipo("RIO BAIANO")
        assert tipo == ""
        assert resto == "RIO BAIANO"


class TestParseNumero:
    def test_numeros_validos(self):
        assert parse_numero("123") == 123
        assert parse_numero(456) == 456
        assert parse_numero("102E") == 102
        assert parse_numero("KM 12") == 12

    def test_sem_numero_e_nulos(self):
        assert parse_numero("SN") is None
        assert parse_numero("S/N") is None
        assert parse_numero("SEM NUMERO") is None
        assert parse_numero(0) is None
        assert parse_numero("") is None
        assert parse_numero(None) is None


class TestNormalizarMunicipio:
    def test_municipio_6_digitos(self):
        assert normalizar_municipio("290070") == "290070"
        assert normalizar_municipio(290070) == "290070"

    def test_municipio_7_digitos_ibge(self):
        assert normalizar_municipio("2900702") == "290070"

    def test_municipio_invalido(self):
        assert normalizar_municipio(None) is None
        assert normalizar_municipio("123") is None


class TestNormalizarCep:
    def test_cep_valido(self):
        assert normalizar_cep("48030260") == "48030260"
        assert normalizar_cep("48030-260") == "48030260"
        assert normalizar_cep(48030260) == "48030260"

    def test_cep_com_zeros_a_esquerda(self):
        assert normalizar_cep("1234567") == "01234567"

    def test_cep_invalido(self):
        assert normalizar_cep("00000000") is None
        assert normalizar_cep(None) is None


class TestTiposCompativeis:
    def test_tipos_mesmo_grupo(self):
        assert tipos_compativeis("CONDOMINIO", "CONJUNTO") is True
        assert tipos_compativeis("RUA", "TRAVESSA") is True
        assert tipos_compativeis("FAZENDA", "ESTRADA") is True

    def test_tipos_diferentes(self):
        assert tipos_compativeis("RUA", "FAZENDA") is False
        assert tipos_compativeis("AVENIDA", "CONDOMINIO") is False
