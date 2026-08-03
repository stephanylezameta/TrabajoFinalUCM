"""Módulo Recomendador (Bloque 4)."""
from src.recommender.affinity.cosine_model import CosineAffinityModel
from src.recommender.tdrs_calculator import TDRSCalculator
from src.recommender.reranking_engine import ReRankingEngine
from src.recommender.explainability import ExplainabilityBuilder
from src.recommender.opportunity_detector import MarketOpportunityDetector
from src.recommender.territorial_simulator import TerritorialImpactSimulator

__all__ = [
    "CosineAffinityModel",
    "TDRSCalculator",
    "ReRankingEngine",
    "ExplainabilityBuilder",
    "MarketOpportunityDetector",
    "TerritorialImpactSimulator",
]
