"""
Detection package - Pattern intelligence without ML
Advanced detection using pure Python logic
"""

from .pattern_detector import PatternDetector, DetectionSignals, PatternCategory
from .lightweight_nlp import LightweightNLP, NLPAnalysis
from .confidence_scorer import ConfidenceScorer, ConfidenceScore
from .detection_engine import DetectionEngine, DetectionResult

__all__ = [
    'PatternDetector',
    'DetectionSignals',
    'PatternCategory',
    'LightweightNLP',
    'NLPAnalysis',
    'ConfidenceScorer',
    'ConfidenceScore',
    'DetectionEngine',
    'DetectionResult'
]
