"""COLLEGIUM — núcleo LEX (primitivo) + ANAIS (ledger) + autonomia conquistada."""
from .ledger import Ledger
from .lex import Acao, Decisao, Lex, carregar_regimento, RegimentoInvalido
from .autonomia import Historico, nivel, wilson_inferior

__version__ = "0.3.0"  # fonte ÚNICA (pyproject, portão MCP e --versao leem daqui)
__all__ = ["__version__", "Ledger", "Acao", "Decisao", "Lex", "carregar_regimento", "RegimentoInvalido",
           "Historico", "nivel", "wilson_inferior"]
