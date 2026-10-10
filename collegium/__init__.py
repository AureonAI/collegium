"""COLLEGIUM — núcleo LEX (primitivo) + ANAIS (ledger) + autonomia conquistada."""
from .ledger import Ledger
from .lex import Acao, Decisao, Lex, carregar_regimento, RegimentoInvalido
from .autonomia import Historico, nivel, wilson_inferior

__version__ = "0.1.2"
__all__ = ["Ledger", "Acao", "Decisao", "Lex", "carregar_regimento", "RegimentoInvalido",
           "Historico", "nivel", "wilson_inferior"]
