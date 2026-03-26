"""
Confidence Scorer - Heuristic scoring without ML
Combines multiple signals to calculate detection confidence
"""

import logging
from typing import Dict, List
from dataclasses import dataclass, field

from .pattern_detector import DetectionSignals, PatternCategory
from .lightweight_nlp import NLPAnalysis

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceScore:
    """Confidence score with reasoning"""
    value: float  # 0.0 - 1.0
    reasoning: List[str] = field(default_factory=list)
    threshold_met: bool = False
    signals_used: Dict[str, any] = field(default_factory=dict)
    breakdown: Dict[str, float] = field(default_factory=dict)


class ConfidenceScorer:
    """
    Calculate detection confidence from multiple signals
    Pure heuristic scoring - no ML required
    """
    
    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        logger.info(f"ConfidenceScorer initialized with threshold {threshold}")
    
    def score(self, signals: DetectionSignals, nlp: NLPAnalysis = None) -> ConfidenceScore:
        """
        Calculate overall confidence (0.0 - 1.0)
        
        Scoring logic:
        - Code block: +0.4 (strongest signal)
        - Strong creation patterns: up to +0.3
        - Function signature: +0.2
        - Language detected: +0.1
        - Execution intent: +0.15
        - Action verb + tool noun: +0.2
        - Imperative mood: +0.1
        - Moderate patterns: up to +0.15
        - Past tense (already created): +0.1
        """
        score = 0.0
        reasoning = []
        breakdown = {}
        
        # === CODE BLOCK (Strongest Signal) ===
        if signals.code_blocks:
            code_score = 0.4
            code_count = len(signals.code_blocks)
            score += code_score
            reasoning.append(f"Code block found ({code_count}) [+{code_score:.2f}]")
            breakdown['code_block'] = code_score
        
        # === STRONG CREATION PATTERNS ===
        strong_matches = signals.get_matches(PatternCategory.TOOL_CREATION_STRONG)
        if strong_matches:
            # Sum weights, cap at 0.3
            pattern_score = min(sum(m.pattern.weight for m in strong_matches), 0.3)
            score += pattern_score
            pattern_descriptions = [m.pattern.description for m in strong_matches]
            reasoning.append(f"Strong patterns: {', '.join(pattern_descriptions[:2])} [+{pattern_score:.2f}]")
            breakdown['strong_patterns'] = pattern_score
        
        # === FUNCTION SIGNATURES ===
        if signals.has_function_signature():
            func_score = 0.2
            func_matches = signals.get_matches(PatternCategory.FUNCTION_SIGNATURE)
            func_names = [m.extracted for m in func_matches if m.extracted]
            score += func_score
            if func_names:
                reasoning.append(f"Function: {func_names[0]} [+{func_score:.2f}]")
            else:
                reasoning.append(f"Function signature [+{func_score:.2f}]")
            breakdown['function_signature'] = func_score
        
        # === LANGUAGE DETECTION ===
        if signals.detected_language:
            lang_score = 0.1
            score += lang_score
            reasoning.append(f"Language: {signals.detected_language} [+{lang_score:.2f}]")
            breakdown['language'] = lang_score
        
        # === EXECUTION INTENT ===
        exec_matches = signals.get_matches(PatternCategory.EXECUTION_INTENT)
        if exec_matches:
            exec_score = 0.15
            score += exec_score
            reasoning.append(f"Execution intent detected [+{exec_score:.2f}]")
            breakdown['execution_intent'] = exec_score
        
        # === NLP ANALYSIS (if provided) ===
        if nlp:
            nlp_score = 0.0
            
            # Action verb + tool noun pair (strong signal)
            if nlp.verb_noun_pairs:
                pair_score = 0.2
                nlp_score += pair_score
                pair_str = f"{nlp.verb_noun_pairs[0][0]} {nlp.verb_noun_pairs[0][1]}"
                reasoning.append(f"Verb-noun pair: '{pair_str}' [+{pair_score:.2f}]")
            
            # Imperative mood
            if nlp.is_imperative:
                imp_score = 0.1
                nlp_score += imp_score
                reasoning.append(f"Imperative mood [+{imp_score:.2f}]")
            
            # Past tense (tool already created)
            if nlp.is_past_tense:
                past_score = 0.1
                nlp_score += past_score
                reasoning.append(f"Past tense creation [+{past_score:.2f}]")
            
            # High complexity (detailed/technical)
            if nlp.complexity_score >= 0.6:
                comp_score = 0.05
                nlp_score += comp_score
                reasoning.append(f"High complexity ({nlp.complexity_score:.1f}) [+{comp_score:.2f}]")
            
            score += nlp_score
            if nlp_score > 0:
                breakdown['nlp_analysis'] = nlp_score
        
        # === MODERATE PATTERNS ===
        moderate_matches = signals.get_matches(PatternCategory.TOOL_CREATION_MODERATE)
        if moderate_matches:
            # Sum weights, cap at 0.15
            mod_score = min(sum(m.pattern.weight for m in moderate_matches), 0.15)
            score += mod_score
            reasoning.append(f"Moderate patterns ({len(moderate_matches)}) [+{mod_score:.2f}]")
            breakdown['moderate_patterns'] = mod_score
        
        # === DOCKER CONTAINER ===
        docker_matches = signals.get_matches(PatternCategory.DOCKER_CONTAINER)
        if docker_matches:
            docker_score = 0.2
            score += docker_score
            reasoning.append(f"Docker container intent [+{docker_score:.2f}]")
            breakdown['docker'] = docker_score
        
        # === API ENDPOINT ===
        api_matches = signals.get_matches(PatternCategory.API_ENDPOINT)
        if api_matches:
            api_score = 0.2
            score += api_score
            reasoning.append(f"API endpoint definition [+{api_score:.2f}]")
            breakdown['api_endpoint'] = api_score
        
        # Cap total score at 1.0
        final_score = min(score, 1.0)
        
        # Add summary
        reasoning.insert(0, f"Total confidence: {final_score:.2f}")
        
        # Determine if threshold met
        threshold_met = final_score >= self.threshold
        
        logger.debug(f"Confidence score: {final_score:.2f} (threshold: {self.threshold}, met: {threshold_met})")
        logger.debug(f"Breakdown: {breakdown}")
        
        return ConfidenceScore(
            value=final_score,
            reasoning=reasoning,
            threshold_met=threshold_met,
            signals_used={
                'code_blocks': len(signals.code_blocks),
                'strong_patterns': len(strong_matches),
                'moderate_patterns': len(moderate_matches),
                'has_function': signals.has_function_signature(),
                'language': signals.detected_language,
                'nlp_available': nlp is not None
            },
            breakdown=breakdown
        )
    
    def get_recommendation(self, confidence: ConfidenceScore) -> str:
        """Get a recommendation based on confidence score"""
        if confidence.value >= 0.9:
            return "Very high confidence - definitely a tool creation"
        elif confidence.value >= 0.7:
            return "High confidence - likely tool creation"
        elif confidence.value >= 0.5:
            return "Moderate confidence - possible tool creation"
        elif confidence.value >= 0.3:
            return "Low confidence - unclear intent"
        else:
            return "Very low confidence - probably not tool creation"
