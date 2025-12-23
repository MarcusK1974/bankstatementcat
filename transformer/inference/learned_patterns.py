#!/usr/bin/env python3
"""
Learned Patterns Manager

Manages the growing dictionary of learned transaction patterns from Claude API.
Provides lookup, storage, and statistics tracking for the self-improving system.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from .normalizer import normalize_description, get_normalization_variants


@dataclass
class LearnedPattern:
    """Represents a learned transaction pattern."""
    category: str
    confidence: float
    source: str  # 'claude', 'manual', etc.
    learned_at: str  # ISO timestamp
    usage_count: int = 0
    last_used: Optional[str] = None  # ISO timestamp
    example_descriptions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'category': self.category,
            'confidence': self.confidence,
            'source': self.source,
            'learned_at': self.learned_at,
            'usage_count': self.usage_count,
            'last_used': self.last_used,
            'example_descriptions': self.example_descriptions[:5],  # Keep only 5 examples
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> LearnedPattern:
        """Create from dictionary."""
        return cls(
            category=data['category'],
            confidence=data['confidence'],
            source=data['source'],
            learned_at=data['learned_at'],
            usage_count=data.get('usage_count', 0),
            last_used=data.get('last_used'),
            example_descriptions=data.get('example_descriptions', []),
        )


class LearnedPatternsManager:
    """
    Manages learned transaction patterns for the hybrid categorization system.
    
    Features:
    - Persistent storage in JSON
    - Fast lookup by normalized description
    - Usage tracking and statistics
    - Automatic pruning of low-confidence patterns
    """
    
    def __init__(self, storage_path: Path):
        """
        Initialize the learned patterns manager.
        
        Args:
            storage_path: Path to JSON file for persistent storage
        """
        self.storage_path = storage_path
        self.patterns: Dict[str, LearnedPattern] = {}
        self.metadata = {
            'total_patterns': 0,
            'last_updated': None,
            'claude_calls_saved': 0,
            'total_lookups': 0,
            'total_hits': 0,
        }
        
        # Load existing patterns if available
        self._load()
    
    def _load(self) -> None:
        """Load patterns from disk."""
        if not self.storage_path.exists():
            print(f"No existing learned patterns found at {self.storage_path}")
            return
        
        try:
            with self.storage_path.open('r') as f:
                data = json.load(f)
            
            # Load patterns
            for norm_desc, pattern_data in data.get('patterns', {}).items():
                self.patterns[norm_desc] = LearnedPattern.from_dict(pattern_data)
            
            # Load metadata
            self.metadata = data.get('metadata', self.metadata)
            
            print(f"Loaded {len(self.patterns)} learned patterns from {self.storage_path}")
        
        except Exception as e:
            print(f"Error loading learned patterns: {e}")
            self.patterns = {}
    
    def save(self) -> None:
        """Save patterns to disk."""
        # Update metadata
        self.metadata['total_patterns'] = len(self.patterns)
        self.metadata['last_updated'] = datetime.now().isoformat()
        
        # Prepare data for JSON
        data = {
            'patterns': {
                norm_desc: pattern.to_dict()
                for norm_desc, pattern in self.patterns.items()
            },
            'metadata': self.metadata
        }
        
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save to disk
        with self.storage_path.open('w') as f:
            json.dump(data, f, indent=2)
    
    def lookup(self, description: str) -> Optional[LearnedPattern]:
        """
        Lookup a pattern by transaction description.
        
        Args:
            description: Raw transaction description
        
        Returns:
            LearnedPattern if found, None otherwise
        """
        self.metadata['total_lookups'] += 1
        
        # Try exact normalized match
        normalized = normalize_description(description)
        
        if normalized in self.patterns:
            pattern = self.patterns[normalized]
            pattern.usage_count += 1
            pattern.last_used = datetime.now().isoformat()
            self.metadata['total_hits'] += 1
            self.metadata['claude_calls_saved'] += 1
            return pattern
        
        # Try variants for fuzzy matching
        variants = get_normalization_variants(description)
        for variant in variants:
            if variant in self.patterns:
                pattern = self.patterns[variant]
                pattern.usage_count += 1
                pattern.last_used = datetime.now().isoformat()
                self.metadata['total_hits'] += 1
                self.metadata['claude_calls_saved'] += 1
                return pattern
        
        return None
    
    def add_pattern(
        self,
        description: str,
        category: str,
        confidence: float,
        source: str = 'claude'
    ) -> bool:
        """
        Add a new learned pattern.
        
        Args:
            description: Raw transaction description
            category: BASIQ category code
            confidence: Confidence score (0-1)
            source: Source of the pattern (default: 'claude')
        
        Returns:
            True if pattern was added, False if skipped
        """
        # Only learn high-confidence patterns
        if not self.should_learn(confidence, category):
            return False
        
        normalized = normalize_description(description)
        
        if not normalized:
            return False
        
        # Check if pattern already exists
        if normalized in self.patterns:
            # Update existing pattern
            existing = self.patterns[normalized]
            
            # Add example if not already present
            if description not in existing.example_descriptions:
                existing.example_descriptions.append(description)
            
            # Update confidence if new confidence is higher
            if confidence > existing.confidence:
                existing.confidence = confidence
            
            return False  # Didn't add new, just updated
        
        # Add new pattern
        self.patterns[normalized] = LearnedPattern(
            category=category,
            confidence=confidence,
            source=source,
            learned_at=datetime.now().isoformat(),
            usage_count=0,
            example_descriptions=[description],
        )
        
        return True
    
    def should_learn(self, confidence: float, category: str) -> bool:
        """
        Determine if a pattern should be learned.
        
        Args:
            confidence: Confidence score
            category: BASIQ category code
        
        Returns:
            True if pattern should be learned
        """
        # Learn if confidence is high enough
        if confidence >= 0.90:
            return True
        
        # Don't learn uncategorized patterns
        if category in ['EXP-039', 'INC-007']:
            return False
        
        return False
    
    def get_similar_patterns(self, description: str, limit: int = 5) -> List[LearnedPattern]:
        """
        Get similar patterns for consistency prompting.
        
        Args:
            description: Raw transaction description
            limit: Maximum number of patterns to return
        
        Returns:
            List of similar learned patterns
        """
        normalized = normalize_description(description)
        
        if not normalized:
            return []
        
        # Extract key words
        key_words = set(normalized.split())
        
        # Find patterns with overlapping words
        similar = []
        for norm_desc, pattern in self.patterns.items():
            pattern_words = set(norm_desc.split())
            overlap = key_words & pattern_words
            
            if overlap:
                similarity = len(overlap) / max(len(key_words), len(pattern_words))
                similar.append((similarity, pattern, norm_desc))
        
        # Sort by similarity and return top N
        similar.sort(reverse=True, key=lambda x: x[0])
        
        return [
            {
                'pattern': pattern,
                'normalized_desc': norm_desc,
                'similarity': sim
            }
            for sim, pattern, norm_desc in similar[:limit]
        ]
    
    def prune_low_confidence(self, min_confidence: float = 0.85) -> int:
        """
        Remove low-confidence patterns that haven't been used.
        
        Args:
            min_confidence: Minimum confidence to keep
        
        Returns:
            Number of patterns removed
        """
        to_remove = []
        
        for norm_desc, pattern in self.patterns.items():
            # Remove if low confidence and never used
            if pattern.confidence < min_confidence and pattern.usage_count == 0:
                to_remove.append(norm_desc)
        
        for norm_desc in to_remove:
            del self.patterns[norm_desc]
        
        return len(to_remove)
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about learned patterns.
        
        Returns:
            Dictionary with statistics
        """
        if not self.patterns:
            return {
                'total_patterns': 0,
                'hit_rate': 0.0,
                'claude_calls_saved': 0,
            }
        
        # Category distribution
        category_counts = defaultdict(int)
        for pattern in self.patterns.values():
            category_counts[pattern.category] += 1
        
        # Source distribution
        source_counts = defaultdict(int)
        for pattern in self.patterns.values():
            source_counts[pattern.source] += 1
        
        # Usage statistics
        total_usage = sum(p.usage_count for p in self.patterns.values())
        
        # Hit rate
        total_lookups = self.metadata.get('total_lookups', 0)
        total_hits = self.metadata.get('total_hits', 0)
        hit_rate = (total_hits / total_lookups * 100) if total_lookups > 0 else 0.0
        
        return {
            'total_patterns': len(self.patterns),
            'total_lookups': total_lookups,
            'total_hits': total_hits,
            'hit_rate': round(hit_rate, 2),
            'claude_calls_saved': self.metadata.get('claude_calls_saved', 0),
            'total_usage': total_usage,
            'category_distribution': dict(category_counts),
            'source_distribution': dict(source_counts),
            'top_patterns': self._get_top_patterns(10),
        }
    
    def _get_top_patterns(self, limit: int = 10) -> List[Dict]:
        """Get most frequently used patterns."""
        sorted_patterns = sorted(
            self.patterns.items(),
            key=lambda x: x[1].usage_count,
            reverse=True
        )
        
        return [
            {
                'pattern': norm_desc,
                'category': pattern.category,
                'usage_count': pattern.usage_count,
                'confidence': pattern.confidence,
            }
            for norm_desc, pattern in sorted_patterns[:limit]
        ]
    
    def export_for_review(self, output_path: Path) -> None:
        """
        Export patterns in a human-readable format for review.
        
        Args:
            output_path: Path to output CSV file
        """
        import csv
        
        with output_path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Normalized Pattern', 'Category', 'Confidence', 
                'Usage Count', 'Source', 'Learned At', 'Example'
            ])
            
            for norm_desc, pattern in sorted(self.patterns.items()):
                example = pattern.example_descriptions[0] if pattern.example_descriptions else ''
                writer.writerow([
                    norm_desc,
                    pattern.category,
                    f"{pattern.confidence:.2f}",
                    pattern.usage_count,
                    pattern.source,
                    pattern.learned_at,
                    example
                ])
        
        print(f"Exported {len(self.patterns)} patterns to {output_path}")


def create_manager(storage_path: Path) -> LearnedPatternsManager:
    """Factory function to create a learned patterns manager."""
    return LearnedPatternsManager(storage_path)

