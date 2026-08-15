"""csoai-city — the governed arena. Signed simulations that emit usable data."""
from .law import ALLOWED, BLOCKED, UNMEASURED, Action, Verdict, gate, check_article5, ART5
from .chain import Chain, ChainResult, content_id
from .arena import BLUE, RED, Citizen, CityRun, build_citizens, ollama_models, wilson

__version__ = "0.1.0"
__all__ = ["ALLOWED","BLOCKED","UNMEASURED","Action","Verdict","gate","check_article5","ART5",
           "Chain","ChainResult","content_id","BLUE","RED","Citizen","CityRun","build_citizens",
           "ollama_models","wilson"]
