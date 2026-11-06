"""
OmniScout-TG: Pipeline Module
Exports graph discovery engine, pipeline orchestrator, and result containers.
"""

from src.pipeline.graph_discovery import RecommendationGraphDiscovery
from src.pipeline.orchestrator import OmniScoutPipeline, PipelineResult

__all__ = [
    "OmniScoutPipeline",
    "PipelineResult",
    "RecommendationGraphDiscovery",
]
