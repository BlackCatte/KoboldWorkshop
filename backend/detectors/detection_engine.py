"""
Detection Engine - Orchestrates all detection methods
Combines pattern matching, NLP, and confidence scoring
"""

import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import hashlib

from .pattern_detector import PatternDetector, DetectionSignals
from .lightweight_nlp import LightweightNLP, NLPAnalysis
from .confidence_scorer import ConfidenceScorer, ConfidenceScore

logger = logging.getLogger(__name__)


@dataclass
class DetectionResult:
    """Complete detection result"""
    detected: bool
    confidence: float
    tool_type: Optional[str] = None
    language: Optional[str] = None
    tool_name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    patterns_matched: list = None
    reasoning: list = None
    metadata: Dict[str, Any] = None
    response_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.patterns_matched is None:
            self.patterns_matched = []
        if self.reasoning is None:
            self.reasoning = []
        if self.metadata is None:
            self.metadata = {}


class DetectionEngine:
    """
    Comprehensive detection engine
    No ML models required - pure logic and patterns
    """
    
    def __init__(self, confidence_threshold: float = 0.7):
        self.pattern_detector = PatternDetector()
        self.nlp_analyzer = LightweightNLP()
        self.confidence_scorer = ConfidenceScorer(threshold=confidence_threshold)
        
        # Track processed responses
        self.processed_hashes = set()
        
        logger.info(f"DetectionEngine initialized with threshold {confidence_threshold}")
    
    async def analyze(self, text: str, context_id: str = "default") -> DetectionResult:
        """
        Analyze text for tool creation intent
        
        Process:
        1. Pattern detection (regex, code blocks)
        2. NLP analysis (semantic understanding)
        3. Confidence scoring (combine signals)
        4. Decision (threshold check)
        5. Metadata extraction
        
        Returns:
            DetectionResult with all findings
        """
        
        # Create hash to avoid duplicates
        response_hash = hashlib.md5(text.encode()).hexdigest()
        
        if response_hash in self.processed_hashes:
            logger.debug("Response already processed (duplicate)")
            return DetectionResult(
                detected=False,
                confidence=0.0,
                metadata={'reason': 'already_processed'}
            )
        
        logger.info(f"Analyzing text ({len(text)} chars) for tool detection...")
        
        # Step 1: Pattern Detection
        signals = self.pattern_detector.detect(text)
        
        # Step 2: NLP Analysis
        nlp = self.nlp_analyzer.analyze(text)
        signals.nlp_analysis = nlp
        
        # Step 3: Confidence Scoring
        confidence = self.confidence_scorer.score(signals, nlp)
        
        # Step 4: Decision
        detected = confidence.threshold_met
        
        if not detected:
            logger.info(f"Detection threshold not met: {confidence.value:.2f} < {self.confidence_scorer.threshold}")
            return DetectionResult(
                detected=False,
                confidence=confidence.value,
                reasoning=confidence.reasoning,
                metadata={
                    'signals': confidence.signals_used,
                    'breakdown': confidence.breakdown
                }
            )
        
        # Step 5: Extract Metadata
        result = self._extract_metadata(text, signals, nlp, confidence, response_hash)
        
        # Mark as processed
        self.processed_hashes.add(response_hash)
        
        logger.info(f"✅ Tool detected! Type: {result.tool_type}, Language: {result.language}, "
                   f"Confidence: {result.confidence:.2f}")
        
        return result
    
    def _extract_metadata(
        self,
        text: str,
        signals: DetectionSignals,
        nlp: NLPAnalysis,
        confidence: ConfidenceScore,
        response_hash: str
    ) -> DetectionResult:
        """Extract all metadata from successful detection"""
        
        # Extract code
        code = None
        if signals.code_blocks:
            # Use first code block
            code = signals.code_blocks[0].code
        elif len(text) > 100:  # Fallback: might be inline code
            code = text.strip()
        
        # Determine tool type
        tool_type = self._determine_tool_type(signals, code)
        
        # Extract tool name
        tool_name = self.pattern_detector.extract_tool_name(text, signals.code_blocks)
        if not tool_name:
            # Generate name based on timestamp
            tool_name = f"ai_tool_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Extract description
        description = self.nlp_analyzer.extract_description(text)
        
        # Get patterns matched
        patterns_matched = list(set([
            m.pattern.description 
            for m in signals.matches
        ]))
        
        # Build metadata
        metadata = {
            'code_blocks_count': len(signals.code_blocks),
            'patterns_found': len(signals.matches),
            'confidence_breakdown': confidence.breakdown,
            'keywords': self.nlp_analyzer.extract_keywords(text),
            'complexity': nlp.complexity_score,
            'has_function_signature': signals.has_function_signature(),
            'is_imperative': nlp.is_imperative,
            'is_past_tense': nlp.is_past_tense,
            'verb_noun_pairs': nlp.verb_noun_pairs
        }
        
        return DetectionResult(
            detected=True,
            confidence=confidence.value,
            tool_type=tool_type,
            language=signals.detected_language,
            tool_name=tool_name,
            code=code,
            description=description,
            patterns_matched=patterns_matched,
            reasoning=confidence.reasoning,
            metadata=metadata,
            response_hash=response_hash
        )
    
    def _determine_tool_type(self, signals: DetectionSignals, code: Optional[str]) -> str:
        """Determine the type of tool"""
        
        # Check for Docker
        from .pattern_detector import PatternCategory
        if signals.get_matches(PatternCategory.DOCKER_CONTAINER):
            return "docker_container"
        
        # Check for API endpoint
        if signals.get_matches(PatternCategory.API_ENDPOINT):
            return "api_endpoint"
        
        # Check code characteristics
        if code:
            if signals.has_function_signature():
                return "function"
            elif len(code.split('\n')) > 5:
                return "script"
            else:
                return "function"
        
        # Default
        return "script"
    
    def clear_processed(self):
        """Clear processed response hashes"""
        count = len(self.processed_hashes)
        self.processed_hashes.clear()
        logger.info(f"Cleared {count} processed response hashes")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get detection statistics"""
        return {
            'processed_count': len(self.processed_hashes),
            'threshold': self.confidence_scorer.threshold
        }
