"""
Lightweight NLP - Semantic analysis without ML models
Pure Python - zero dependencies, extremely fast
"""

import re
import logging
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class NLPAnalysis:
    """Results from NLP analysis"""
    has_action_verb: bool = False
    has_tool_noun: bool = False
    has_execution_verb: bool = False
    verb_noun_pairs: List[Tuple[str, str]] = None
    is_imperative: bool = False
    is_past_tense: bool = False
    sentence_count: int = 0
    complexity_score: float = 0.0
    
    def __post_init__(self):
        if self.verb_noun_pairs is None:
            self.verb_noun_pairs = []


class LightweightNLP:
    """
    Semantic analysis without heavy NLP libraries
    Uses word lists and simple rules for fast, accurate analysis
    """
    
    def __init__(self):
        # Action verbs indicating tool creation
        self.action_verbs = {
            'create', 'build', 'make', 'write', 'develop',
            'generate', 'produce', 'construct', 'design',
            'implement', 'code', 'program', 'script',
            'compose', 'craft', 'author'
        }
        
        # Tool-related nouns
        self.tool_nouns = {
            'script', 'function', 'tool', 'program', 'code',
            'analyzer', 'parser', 'processor', 'handler',
            'utility', 'application', 'module', 'package',
            'library', 'framework', 'service', 'api'
        }
        
        # Execution-related verbs
        self.execution_verbs = {
            'run', 'execute', 'start', 'launch', 'invoke',
            'call', 'trigger', 'fire', 'initiate', 'kick off'
        }
        
        # Imperative indicators
        self.imperative_starts = {
            "i'll", "i will", "let me", "let's", "we'll",
            "we will", "i'm going to", "i am going to"
        }
        
        # Past tense indicators
        self.past_tense_verbs = {
            'created', 'built', 'made', 'wrote', 'developed',
            'generated', 'produced', 'constructed', 'designed',
            'implemented', 'coded', 'programmed', 'scripted'
        }
        
        logger.info("LightweightNLP initialized")
    
    def analyze(self, text: str) -> NLPAnalysis:
        """
        Analyze text for semantic signals
        Fast, deterministic, no ML required
        """
        analysis = NLPAnalysis()
        
        # Normalize text
        text_lower = text.lower()
        words = self._tokenize(text_lower)
        
        # Check for action verbs
        analysis.has_action_verb = any(verb in words for verb in self.action_verbs)
        
        # Check for tool nouns
        analysis.has_tool_noun = any(noun in words for noun in self.tool_nouns)
        
        # Check for execution verbs
        analysis.has_execution_verb = any(verb in words for verb in self.execution_verbs)
        
        # Find verb-noun pairs
        analysis.verb_noun_pairs = self._find_verb_noun_pairs(text_lower, words)
        
        # Check for imperative mood
        analysis.is_imperative = self._is_imperative(text_lower)
        
        # Check for past tense (tool already created)
        analysis.is_past_tense = any(verb in words for verb in self.past_tense_verbs)
        
        # Count sentences
        analysis.sentence_count = len(re.split(r'[.!?]+', text))
        
        # Calculate complexity (longer, more structured = higher complexity)
        analysis.complexity_score = self._calculate_complexity(text, words)
        
        logger.debug(f"NLP Analysis: action_verb={analysis.has_action_verb}, "
                    f"tool_noun={analysis.has_tool_noun}, "
                    f"pairs={len(analysis.verb_noun_pairs)}")
        
        return analysis
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple word tokenization"""
        # Remove punctuation except apostrophes
        text = re.sub(r'[^\w\s\']', ' ', text)
        # Split on whitespace
        words = text.split()
        # Remove empty strings
        return [w for w in words if w]
    
    def _find_verb_noun_pairs(self, text: str, words: List[str]) -> List[Tuple[str, str]]:
        """
        Find action verb + tool noun pairs
        Simple sliding window approach
        """
        pairs = []
        
        # Check action verb followed by tool noun within 3 words
        for i, word in enumerate(words):
            if word in self.action_verbs:
                # Look at next 3 words
                for j in range(i + 1, min(i + 4, len(words))):
                    if words[j] in self.tool_nouns:
                        pairs.append((word, words[j]))
                        break
        
        return pairs
    
    def _is_imperative(self, text: str) -> bool:
        """Check if text has imperative mood"""
        # Check if starts with imperative indicator
        text_start = text[:50].lower()
        
        for indicator in self.imperative_starts:
            if text_start.startswith(indicator):
                return True
        
        return False
    
    def _calculate_complexity(self, text: str, words: List[str]) -> float:
        """
        Calculate text complexity score (0.0 - 1.0)
        Higher = more detailed/technical
        """
        score = 0.0
        
        # Length contributes (longer = more complex)
        if len(words) > 50:
            score += 0.2
        elif len(words) > 20:
            score += 0.1
        
        # Code-related words
        code_words = {'function', 'class', 'variable', 'parameter', 'return', 'import'}
        if any(word in words for word in code_words):
            score += 0.2
        
        # Technical connectors
        technical_connectors = {'then', 'next', 'after', 'first', 'finally'}
        connector_count = sum(1 for word in words if word in technical_connectors)
        if connector_count >= 2:
            score += 0.2
        
        # Parentheses (often indicate code or technical explanation)
        if '(' in text and ')' in text:
            score += 0.1
        
        # Code blocks
        if '```' in text:
            score += 0.3
        
        return min(score, 1.0)
    
    def extract_description(self, text: str, max_length: int = 200) -> str:
        """
        Extract a concise description from text
        Takes first meaningful sentence
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        # Find first substantial sentence (>20 chars, not just "Here:", etc.)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20 and not sentence.endswith(':'):
                # Truncate if needed
                if len(sentence) > max_length:
                    sentence = sentence[:max_length] + '...'
                return sentence
        
        # Fallback: return first part of text
        return text[:max_length].strip() + ('...' if len(text) > max_length else '')
    
    def extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """
        Extract important keywords from text
        Simple frequency-based with stopword filtering
        """
        # Common stopwords to ignore
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
            'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that',
            'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'
        }
        
        # Tokenize and filter
        words = self._tokenize(text.lower())
        words = [w for w in words if w not in stopwords and len(w) > 3]
        
        # Count frequency
        from collections import Counter
        word_counts = Counter(words)
        
        # Return top N
        return [word for word, count in word_counts.most_common(top_n)]
