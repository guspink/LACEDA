"""Testes unitarios para calculo de similaridade de texto."""
import pytest
from src.similarity import pontuar, similaridade


class TestSimilarity:
    def test_strings_identicas(self):
        assert similaridade("RUA RIO BAIANO", "RUA RIO BAIANO") == 100.0

    def test_strings_com_pequeno_erro_grafico(self):
        # BONFIM vs BOMFIM
        score = similaridade("SERGIO BOMFIM", "SERGIO BONFIM")
        assert score >= 90.0

    def test_penalidade_ordem_das_palavras(self):
        # 'BOA VISTA' vs 'VISTA BOA' nao deve ser 100.0
        score = similaridade("BOA VISTA", "VISTA BOA")
        assert score < 100.0
        assert score >= 70.0

    def test_strings_vazias(self):
        assert similaridade("", "RUA A") == 0.0
        assert similaridade("RUA A", "") == 0.0
        assert similaridade("", "") == 0.0

    def test_pontuar_multiplas_opcoes(self):
        consulta = "RIO BAIANO"
        opcoes = ["RIO BAIANO", "RIO PARDO", "BAIANO RIO"]
        scores = pontuar(consulta, opcoes)
        assert len(scores) == 3
        assert scores[0] == 100.0
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]
