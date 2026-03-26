"""
Pattern Detector - Comprehensive pattern matching for tool detection
Works with ANY model - no ML required, pure regex and logic
"""

import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PatternCategory(str, Enum):
    """Categories of patterns"""
    TOOL_CREATION_STRONG = "tool_creation_strong"
    TOOL_CREATION_MODERATE = "tool_creation_moderate"
    TOOL_CREATION_WEAK = "tool_creation_weak"
    EXECUTION_INTENT = "execution_intent"
    CODE_BLOCK = "code_block"
    FUNCTION_SIGNATURE = "function_signature"
    DOCKER_CONTAINER = "docker_container"
    API_ENDPOINT = "api_endpoint"


@dataclass
class Pattern:
    """A detection pattern"""
    regex: str
    weight: float
    description: str
    extract_group: int = 0
    case_sensitive: bool = False


@dataclass
class PatternMatch:
    """A matched pattern"""
    category: PatternCategory
    pattern: Pattern
    match_text: str
    extracted: Optional[str] = None
    start_pos: int = 0
    end_pos: int = 0


@dataclass
class CodeBlock:
    """An extracted code block"""
    language: Optional[str]
    code: str
    confidence: float = 0.9


@dataclass
class DetectionSignals:
    """All signals from pattern detection"""
    matches: List[PatternMatch] = field(default_factory=list)
    code_blocks: List[CodeBlock] = field(default_factory=list)
    detected_language: Optional[str] = None
    nlp_analysis: Optional[Dict] = None
    
    def add_match(self, category: PatternCategory, pattern: Pattern, match_text: str, extracted: Optional[str] = None):
        """Add a pattern match"""
        self.matches.append(PatternMatch(
            category=category,
            pattern=pattern,
            match_text=match_text,
            extracted=extracted
        ))
    
    def get_matches(self, category: PatternCategory) -> List[PatternMatch]:
        """Get all matches for a category"""
        return [m for m in self.matches if m.category == category]
    
    def has_function_signature(self) -> bool:
        """Check if function signature was detected"""
        return len(self.get_matches(PatternCategory.FUNCTION_SIGNATURE)) > 0


class PatternDetector:
    """
    Advanced pattern matching without ML
    Detects tool creation and execution intent from text
    """
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.language_signatures = self._load_language_signatures()
        logger.info("PatternDetector initialized with comprehensive patterns")
    
    def _load_patterns(self) -> Dict[PatternCategory, List[Pattern]]:
        """Load all detection patterns"""
        return {
            # Strong tool creation signals
            PatternCategory.TOOL_CREATION_STRONG: [
                Pattern(
                    regex=r"(?:I will|I'll|let me)\s+(?:create|write|build|make|develop|generate)\s+(?:a|an|the)?\s*(?:script|function|tool|program|code)",
                    weight=0.3,
                    description="Strong creation intent with action verb"
                ),
                Pattern(
                    regex=r"here'?s\s+(?:a|the|an)\s+(?:script|function|tool|code|program)",
                    weight=0.3,
                    description="Presenting created tool"
                ),
                Pattern(
                    regex=r"(?:I've|I have|I just)\s+(?:created|written|built|made|developed)\s+(?:a|an|the)?\s*(?:script|function|tool)",
                    weight=0.25,
                    description="Past tense creation"
                ),
                Pattern(
                    regex=r"(?:created|wrote|built|made)\s+(?:this|a)\s+(?:script|function|tool|program)",
                    weight=0.25,
                    description="Tool creation statement"
                ),
            ],
            
            # Moderate tool creation signals
            PatternCategory.TOOL_CREATION_MODERATE: [
                Pattern(
                    regex=r"(?:can|could|should|would)\s+(?:create|write|build|make)\s+(?:a|an|the)?\s*(?:script|tool|function)",
                    weight=0.15,
                    description="Conditional creation"
                ),
                Pattern(
                    regex=r"(?:to|we'll|we will)\s+(?:analyze|process|handle|parse|check|monitor|manage)",
                    weight=0.10,
                    description="Purpose statement"
                ),
                Pattern(
                    regex=r"(?:script|tool|function|program)\s+(?:that|which|to)\s+(?:will|can|should)",
                    weight=0.10,
                    description="Tool purpose description"
                ),
            ],
            
            # Weak signals (need other evidence)
            PatternCategory.TOOL_CREATION_WEAK: [
                Pattern(
                    regex=r"\b(?:script|function|tool|program|code)\b",
                    weight=0.05,
                    description="Tool-related noun"
                ),
            ],
            
            # Execution intent
            PatternCategory.EXECUTION_INTENT: [
                Pattern(
                    regex=r"(?:let me|I'll|I will)\s+(?:run|execute|start|launch|test)",
                    weight=0.25,
                    description="Immediate execution intent"
                ),
                Pattern(
                    regex=r"(?:running|executing|starting|launching)\s+(?:this|the|it|now)",
                    weight=0.20,
                    description="Currently executing"
                ),
                Pattern(
                    regex=r"(?:should|can|we)\s+(?:run|execute|test)\s+(?:this|it)",
                    weight=0.15,
                    description="Execution suggestion"
                ),
            ],
            
            # Code blocks (strongest signal)
            PatternCategory.CODE_BLOCK: [
                Pattern(
                    regex=r'```(?P<lang>python|javascript|js|bash|sh|sql|docker|dockerfile|yaml|json)?\n(?P<code>.*?)```',
                    weight=0.4,
                    description="Markdown code block",
                    extract_group=2
                ),
                Pattern(
                    regex=r'`([^`]+)`',
                    weight=0.1,
                    description="Inline code"
                ),
            ],
            
            # Function signatures (strong signal)
            PatternCategory.FUNCTION_SIGNATURE: [
                Pattern(
                    regex=r'def\s+([a-zA-Z_]\w*)\s*\(',
                    weight=0.2,
                    description="Python function",
                    extract_group=1
                ),
                Pattern(
                    regex=r'function\s+([a-zA-Z_]\w*)\s*\(',
                    weight=0.2,
                    description="JavaScript function",
                    extract_group=1
                ),
                Pattern(
                    regex=r'(?:const|let|var)\s+([a-zA-Z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>',
                    weight=0.2,
                    description="Arrow function",
                    extract_group=1
                ),
                Pattern(
                    regex=r'([a-zA-Z_]\w*)\s*\(\s*\)\s*{',
                    weight=0.15,
                    description="Shell/Bash function",
                    extract_group=1
                ),
            ],
            
            # Docker patterns
            PatternCategory.DOCKER_CONTAINER: [
                Pattern(
                    regex=r'(?:create|start|run|spin up)\s+(?:a\s+)?(?:docker\s+)?container',
                    weight=0.25,
                    description="Docker container creation"
                ),
                Pattern(
                    regex=r'docker\s+(?:run|start|create|compose)',
                    weight=0.25,
                    description="Docker command"
                ),
                Pattern(
                    regex=r'FROM\s+\w+',
                    weight=0.3,
                    description="Dockerfile FROM statement"
                ),
            ],
            
            # API endpoints
            PatternCategory.API_ENDPOINT: [
                Pattern(
                    regex=r'@(?:app|router)\.(?:get|post|put|delete|patch)\(',
                    weight=0.25,
                    description="FastAPI/Flask route decorator"
                ),
                Pattern(
                    regex=r'app\.(?:get|post|put|delete)\s*\(',
                    weight=0.2,
                    description="Express.js route"
                ),
            ],
        }
    
    def _load_language_signatures(self) -> Dict[str, List[str]]:
        """Language-specific signatures for detection"""
        return {
            'python': [
                r'\bdef\s+\w+\s*\(',
                r'\bimport\s+\w+',
                r'\bfrom\s+\w+\s+import',
                r'\bclass\s+\w+',
                r'\bif\s+__name__\s*==\s*["\']__main__["\']',
                r'print\s*\(',
            ],
            'javascript': [
                r'\bfunction\s+\w+\s*\(',
                r'\bconst\s+\w+\s*=',
                r'\blet\s+\w+\s*=',
                r'=>',
                r'console\.log\s*\(',
                r'require\s*\(',
                r'import\s+.*\s+from',
            ],
            'bash': [
                r'#!/bin/(?:bash|sh)',
                r'\becho\s+',
                r'\$\{?\w+\}?',
                r'\|\s*grep',
                r'\bif\s*\[',
                r'\bfor\s+\w+\s+in',
            ],
            'sql': [
                r'\bSELECT\s+.*\s+FROM\b',
                r'\bINSERT\s+INTO\b',
                r'\bUPDATE\s+.*\s+SET\b',
                r'\bDELETE\s+FROM\b',
                r'\bCREATE\s+TABLE\b',
            ],
            'docker': [
                r'\bFROM\s+\w+',
                r'\bRUN\s+',
                r'\bCOPY\s+',
                r'\bWORKDIR\s+',
                r'\bEXPOSE\s+',
            ],
        }
    
    def detect(self, text: str) -> DetectionSignals:
        """
        Detect all patterns in text
        Returns comprehensive signals for confidence scoring
        """
        signals = DetectionSignals()
        
        # Check all pattern categories
        for category, patterns in self.patterns.items():
            for pattern in patterns:
                flags = 0 if pattern.case_sensitive else re.IGNORECASE
                if category == PatternCategory.CODE_BLOCK:
                    flags |= re.DOTALL
                
                matches = re.finditer(pattern.regex, text, flags)
                for match in matches:
                    extracted = None
                    if pattern.extract_group > 0:
                        try:
                            extracted = match.group(pattern.extract_group)
                        except:
                            extracted = match.group('code') if 'code' in match.groupdict() else None
                    
                    signals.add_match(
                        category=category,
                        pattern=pattern,
                        match_text=match.group(0),
                        extracted=extracted
                    )
        
        # Extract code blocks
        signals.code_blocks = self._extract_code_blocks(text)
        
        # Detect language
        signals.detected_language = self._detect_language(text, signals.code_blocks)
        
        logger.debug(f"Detected {len(signals.matches)} pattern matches, {len(signals.code_blocks)} code blocks")
        
        return signals
    
    def _extract_code_blocks(self, text: str) -> List[CodeBlock]:
        """Extract all code blocks from text"""
        code_blocks = []
        
        # Markdown code blocks with language
        pattern = r'```(?P<lang>\w+)?\n(?P<code>.*?)```'
        for match in re.finditer(pattern, text, re.DOTALL):
            lang = match.group('lang')
            code = match.group('code').strip()
            
            # If no language specified, try to detect
            if not lang:
                lang = self._detect_language_from_code(code)
            
            if code:
                code_blocks.append(CodeBlock(
                    language=lang,
                    code=code,
                    confidence=0.9 if lang else 0.7
                ))
        
        # Inline code (lower confidence)
        if not code_blocks:
            inline_pattern = r'`([^`\n]{10,})`'
            for match in re.finditer(inline_pattern, text):
                code = match.group(1).strip()
                if code:
                    code_blocks.append(CodeBlock(
                        language=None,
                        code=code,
                        confidence=0.3
                    ))
        
        return code_blocks
    
    def _detect_language(self, text: str, code_blocks: List[CodeBlock]) -> Optional[str]:
        """Detect programming language from signatures"""
        
        # First check code blocks
        for block in code_blocks:
            if block.language:
                return block.language.lower()
        
        # Then check for language signatures in full text
        language_scores = {}
        
        for lang, signatures in self.language_signatures.items():
            score = 0
            for sig_pattern in signatures:
                matches = re.findall(sig_pattern, text, re.IGNORECASE)
                score += len(matches)
            
            if score > 0:
                language_scores[lang] = score
        
        if language_scores:
            detected = max(language_scores, key=language_scores.get)
            logger.debug(f"Detected language: {detected} (scores: {language_scores})")
            return detected
        
        return None
    
    def _detect_language_from_code(self, code: str) -> Optional[str]:
        """Detect language from code snippet"""
        for lang, signatures in self.language_signatures.items():
            for sig in signatures:
                if re.search(sig, code, re.IGNORECASE):
                    return lang
        return None
    
    def extract_tool_name(self, text: str, code_blocks: List[CodeBlock]) -> Optional[str]:
        """Extract tool name from text or code"""
        
        # Try to find explicit naming
        name_patterns = [
            r'(?:called|named)\s+["\']?([a-zA-Z_][a-zA-Z0-9_]*)["\']?',
            r'(?:tool|script|function)\s+["\']([a-zA-Z_][a-zA-Z0-9_]*)["\']',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Try to extract from function names in code
        for block in code_blocks:
            if block.language == 'python':
                match = re.search(r'def\s+([a-zA-Z_]\w*)', block.code)
                if match:
                    return match.group(1)
            elif block.language in ['javascript', 'js']:
                match = re.search(r'function\s+([a-zA-Z_]\w*)', block.code)
                if match:
                    return match.group(1)
        
        return None
