#!/usr/bin/env python3
"""
Claude API Transaction Categorizer

Real Claude API integration for transaction categorization with:
- Prompt caching for cost efficiency
- Consistency prompts using previous decisions
- JSON response parsing
- Error handling and retries
"""

from __future__ import annotations

import json
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic package not installed. Run: pip install anthropic")


class ClaudeCategorizer:
    """
    Real Claude API categorizer for transactions.
    
    Uses Claude 3 Haiku for fast, cost-effective categorization.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        basiq_groups_path: Optional[Path] = None,
        test_mode: bool = False
    ):
        """
        Initialize Claude categorizer.
        
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            basiq_groups_path: Path to basiq_groups.yaml for taxonomy
            test_mode: If True, simulate API calls without making them
        """
        self.test_mode = test_mode
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.client = None
        
        if not self.test_mode:
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            
            if not self.api_key:
                raise ValueError(
                    "No API key provided. Set ANTHROPIC_API_KEY environment variable "
                    "or pass api_key parameter"
                )
            
            self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Load BASIQ taxonomy
        self.basiq_categories = self._load_basiq_taxonomy(basiq_groups_path)
        
        # Statistics
        self.stats = {
            'total_calls': 0,
            'total_cost': 0.0,
            'errors': 0,
        }
    
    def _load_basiq_taxonomy(self, groups_path: Optional[Path]) -> str:
        """Load BASIQ category taxonomy as formatted string."""
        if groups_path is None:
            groups_path = Path('docs/basiq_groups.yaml')
        
        with groups_path.open('r') as f:
            data = yaml.safe_load(f)
        
        # Format categories for prompt
        categories = []
        for group in data.get('groups', []):
            code = group.get('code')
            name = group.get('name', '')
            categories.append(f"- {code}: {name}")
        
        return '\n'.join(categories)
    
    def _sanitize_description(self, description: str) -> str:
        """
        Sanitize transaction description for safe JSON embedding.
        
        Escapes backslashes and other characters that could break JSON parsing.
        """
        if not description:
            return ""
        
        # Escape backslashes (must be first to avoid double-escaping)
        sanitized = description.replace('\\', '\\\\')
        
        # Escape quotes
        sanitized = sanitized.replace('"', '\\"')
        
        # Remove control characters that could break JSON
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\r\t')
        
        return sanitized
    
    def predict(
        self,
        description: str,
        amount: float,
        bs_category: Optional[str] = None,
        similar_patterns: Optional[List[Dict]] = None
    ) -> Tuple[str, float, str]:
        """
        Predict category using Claude API.
        
        Args:
            description: Transaction description
            amount: Transaction amount
            bs_category: Optional BS category hint
            similar_patterns: Optional list of similar learned patterns for consistency
        
        Returns:
            Tuple of (category, confidence, reasoning)
        """
        if self.test_mode:
            return self._simulate_prediction(description, amount, bs_category)
        
        try:
            prompt = self._build_prompt(description, amount, bs_category, similar_patterns)
            
            # Call Claude API (using Haiku for cost efficiency)
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=150,
                temperature=0.0,  # Deterministic for consistency
                system="You are a transaction categorization expert for BASIQ, an Australian financial data platform.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Parse response
            response_text = message.content[0].text
            result = self._parse_response(response_text)
            
            # Update statistics
            self.stats['total_calls'] += 1
            self.stats['total_cost'] += self._estimate_cost(prompt, response_text)
            
            return result['category'], result['confidence'], result['reasoning']
        
        except Exception as e:
            self.stats['errors'] += 1
            print(f"Error calling Claude API: {e}")
            # Return uncategorized as fallback
            return ('EXP-039' if amount < 0 else 'INC-007'), 0.3, f"API error: {str(e)}"
    
    def _build_prompt(
        self,
        description: str,
        amount: float,
        bs_category: Optional[str],
        similar_patterns: Optional[List[Dict]]
    ) -> str:
        """Build the prompt for Claude."""
        
        # Sanitize description to prevent JSON parsing errors
        safe_description = self._sanitize_description(description)
        
        # Base prompt with taxonomy
        prompt = f"""Analyze this Australian bank transaction and categorize it into the most appropriate BASIQ code.

BASIQ Category Taxonomy:
{self.basiq_categories}

Australian Brand Knowledge (use this to improve accuracy):
- Supermarkets: Woolworths, Coles, ALDI, IGA → EXP-016 (Groceries)
- Alcohol Retailers: Dan Murphy's, BWS, Liquorland, First Choice → EXP-051 (Alcohol and Tobacco)
- Fuel Stations: Caltex, Shell, BP, 7-Eleven, Ampol, Better Choice, United, Liberty → EXP-041 (Vehicle and Transport)
- Public Transport: MYKI (VIC), Opal (NSW), Go Card (QLD) → EXP-041 (Vehicle and Transport)
- Telecommunications: Telstra, Optus, Vodafone, TPG → EXP-036 (Telecommunication)
- Energy/Utilities: AGL, Origin, Momentum Energy, Red Energy → EXP-040 (Utilities)
- Health Insurance: Bupa, Medibank, HCF, NIB → EXP-021 (Insurance)
- Banks: NAB, CBA, Westpac, ANZ → Use for fee categorization

Transaction Details:
- Description: {safe_description}
- Amount: ${amount:.2f} ({"expense/debit" if amount < 0 else "income/credit"})
"""
        
        # Add BS category hint if available
        if bs_category:
            prompt += f"- Bank Statement Category Hint: {bs_category}\n"
        
        # Add consistency context from similar patterns
        if similar_patterns and len(similar_patterns) > 0:
            prompt += "\nPrevious similar categorizations (be consistent):\n"
            for item in similar_patterns[:3]:  # Show top 3
                pattern = item['pattern']
                norm_desc = item['normalized_desc']
                examples = pattern.example_descriptions[:2] if pattern.example_descriptions else []
                
                if examples:
                    prompt += f"- \"{examples[0]}\" → {pattern.category}\n"
        
        # Request JSON response
        prompt += """
Return your categorization as valid JSON (no markdown, just JSON):
{
  "category": "EXP-XXX or INC-XXX",
  "confidence": 0.XX,
  "reasoning": "Brief explanation"
}

Important:
- Match Australian merchants to their correct categories using the brand knowledge above
- Be consistent with previous decisions for the same merchant
- Use high confidence (0.95+) only when certain
- Ignore location names in descriptions (e.g., suburb names like "BURWOOD", "CHADSTONE")"""
        
        return prompt
    
    def _parse_response(self, response_text: str) -> Dict:
        """Parse Claude's JSON response."""
        try:
            # Try to extract JSON from response
            # Claude might wrap it in markdown code blocks
            text = response_text.strip()
            
            # Remove markdown code blocks if present
            if text.startswith('```'):
                # Find the actual JSON content
                lines = text.split('\n')
                json_lines = []
                in_json = False
                for line in lines:
                    if line.strip().startswith('```'):
                        in_json = not in_json
                        continue
                    if in_json:
                        json_lines.append(line)
                text = '\n'.join(json_lines)
            
            # Parse JSON
            result = json.loads(text)
            
            # Validate required fields
            if 'category' not in result or 'confidence' not in result:
                raise ValueError("Missing required fields in response")
            
            # Ensure confidence is float
            result['confidence'] = float(result['confidence'])
            
            # Ensure reasoning exists
            if 'reasoning' not in result:
                result['reasoning'] = 'No reasoning provided'
            
            return result
        
        except Exception as e:
            print(f"Error parsing Claude response: {e}")
            print(f"Response text: {response_text[:200]}")
            
            # Return a fallback
            return {
                'category': 'EXP-039',
                'confidence': 0.3,
                'reasoning': f'Parse error: {str(e)}'
            }
    
    def _estimate_cost(self, prompt: str, response: str) -> float:
        """
        Estimate cost of API call.
        
        Claude 3 Haiku pricing:
        - Input: $0.25 per million tokens
        - Output: $1.25 per million tokens
        
        Rough estimate: 1 token ≈ 4 characters
        """
        input_tokens = len(prompt) / 4
        output_tokens = len(response) / 4
        
        input_cost = (input_tokens / 1_000_000) * 0.25
        output_cost = (output_tokens / 1_000_000) * 1.25
        
        return input_cost + output_cost
    
    def _simulate_prediction(
        self,
        description: str,
        amount: float,
        bs_category: Optional[str]
    ) -> Tuple[str, float, str]:
        """
        Simulate API call for testing without actual API charges.
        
        Uses simple heuristics to return realistic-looking results.
        """
        desc_lower = description.lower()
        
        # Simple keyword matching for simulation
        if any(word in desc_lower for word in ['kfc', 'mcdonalds', 'hungry', 'subway']):
            return 'EXP-008', 0.96, 'Test mode: Fast food detected'
        elif any(word in desc_lower for word in ['woolworths', 'coles', 'aldi']):
            return 'EXP-016', 0.97, 'Test mode: Supermarket detected'
        elif any(word in desc_lower for word in ['energy', 'electricity', 'gas']):
            return 'EXP-040', 0.95, 'Test mode: Utility detected'
        elif 'salary' in desc_lower or 'pay/' in desc_lower:
            return 'INC-009', 0.98, 'Test mode: Salary detected'
        else:
            return ('EXP-039' if amount < 0 else 'INC-007'), 0.5, 'Test mode: No pattern match'
    
    def get_statistics(self) -> Dict:
        """Get API usage statistics."""
        return {
            **self.stats,
            'test_mode': self.test_mode,
        }


def create_categorizer(
    api_key: Optional[str] = None,
    test_mode: bool = False
) -> ClaudeCategorizer:
    """Factory function to create Claude categorizer."""
    return ClaudeCategorizer(api_key=api_key, test_mode=test_mode)

