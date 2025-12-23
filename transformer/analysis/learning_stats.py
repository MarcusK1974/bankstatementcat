#!/usr/bin/env python3
"""
Learning Statistics and Cost Tracking

Tracks performance metrics, learning progress, and API costs for the hybrid system.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class LearningStats:
    """Tracks statistics for the hybrid learning system."""
    
    def __init__(self, storage_path: Path):
        """
        Initialize statistics tracker.
        
        Args:
            storage_path: Path to JSON file for persistent storage
        """
        self.storage_path = storage_path
        self.current_session = {
            'session_start': datetime.now().isoformat(),
            'transactions_processed': 0,
            'predictions_by_source': defaultdict(int),
            'claude_api_calls': 0,
            'claude_api_cost': 0.0,
            'patterns_learned': 0,
            'learned_dict_hits': 0,
        }
        self.history = []
        
        # Load existing history
        self._load()
    
    def _load(self) -> None:
        """Load historical statistics."""
        if not self.storage_path.exists():
            return
        
        try:
            with self.storage_path.open('r') as f:
                data = json.load(f)
            
            self.history = data.get('history', [])
            print(f"Loaded {len(self.history)} previous sessions")
        
        except Exception as e:
            print(f"Error loading statistics: {e}")
    
    def save(self) -> None:
        """Save statistics to disk."""
        # Finalize current session
        self.current_session['session_end'] = datetime.now().isoformat()
        self.current_session['predictions_by_source'] = dict(self.current_session['predictions_by_source'])
        
        # Add to history
        self.history.append(self.current_session.copy())
        
        # Save to disk
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open('w') as f:
            json.dump({
                'history': self.history,
                'last_updated': datetime.now().isoformat()
            }, f, indent=2)
    
    def record_prediction(self, source: str) -> None:
        """Record a prediction by its source."""
        self.current_session['transactions_processed'] += 1
        self.current_session['predictions_by_source'][source] += 1
        
        if source == 'claude':
            self.current_session['claude_api_calls'] += 1
        elif source == 'learned':
            self.current_session['learned_dict_hits'] += 1
    
    def record_claude_call(self, cost: float) -> None:
        """Record a Claude API call and its cost."""
        self.current_session['claude_api_cost'] += cost
    
    def record_pattern_learned(self) -> None:
        """Record that a new pattern was learned."""
        self.current_session['patterns_learned'] += 1
    
    def get_session_summary(self) -> Dict:
        """Get summary of current session."""
        total_txs = self.current_session['transactions_processed']
        claude_calls = self.current_session['claude_api_calls']
        
        return {
            'session_start': self.current_session['session_start'],
            'transactions_processed': total_txs,
            'predictions_by_source': dict(self.current_session['predictions_by_source']),
            'claude_api_calls': claude_calls,
            'claude_api_cost': round(self.current_session['claude_api_cost'], 4),
            'claude_percentage': round(claude_calls / total_txs * 100, 2) if total_txs > 0 else 0,
            'patterns_learned': self.current_session['patterns_learned'],
            'learned_dict_hits': self.current_session['learned_dict_hits'],
            'cost_per_transaction': round(self.current_session['claude_api_cost'] / total_txs, 6) if total_txs > 0 else 0,
        }
    
    def get_historical_summary(self) -> Dict:
        """Get summary across all sessions."""
        if not self.history:
            return {'message': 'No historical data available'}
        
        total_txs = sum(s.get('transactions_processed', 0) for s in self.history)
        total_claude_calls = sum(s.get('claude_api_calls', 0) for s in self.history)
        total_cost = sum(s.get('claude_api_cost', 0.0) for s in self.history)
        total_learned = sum(s.get('patterns_learned', 0) for s in self.history)
        
        return {
            'total_sessions': len(self.history),
            'total_transactions': total_txs,
            'total_claude_calls': total_claude_calls,
            'total_cost': round(total_cost, 2),
            'total_patterns_learned': total_learned,
            'average_cost_per_transaction': round(total_cost / total_txs, 6) if total_txs > 0 else 0,
            'claude_usage_rate': round(total_claude_calls / total_txs * 100, 2) if total_txs > 0 else 0,
        }
    
    def get_learning_curve(self) -> List[Dict]:
        """Get learning curve data showing improvement over time."""
        if not self.history:
            return []
        
        curve = []
        for i, session in enumerate(self.history):
            total_txs = session.get('transactions_processed', 0)
            claude_calls = session.get('claude_api_calls', 0)
            claude_pct = (claude_calls / total_txs * 100) if total_txs > 0 else 0
            
            curve.append({
                'session': i + 1,
                'date': session.get('session_start', '')[:10],
                'transactions': total_txs,
                'claude_calls': claude_calls,
                'claude_percentage': round(claude_pct, 2),
                'cost': round(session.get('claude_api_cost', 0), 4),
                'patterns_learned': session.get('patterns_learned', 0),
            })
        
        return curve
    
    def print_report(self) -> None:
        """Print a formatted report."""
        print("\n" + "=" * 80)
        print("HYBRID LEARNING SYSTEM - STATISTICS REPORT")
        print("=" * 80)
        
        # Current session
        print("\nCurrent Session:")
        print("-" * 80)
        session = self.get_session_summary()
        for key, value in session.items():
            if key != 'predictions_by_source':
                print(f"  {key:30s}: {value}")
        
        print("\n  Predictions by Source:")
        for source, count in session.get('predictions_by_source', {}).items():
            pct = count / session['transactions_processed'] * 100 if session['transactions_processed'] > 0 else 0
            print(f"    {source:25s}: {count:6d} ({pct:5.1f}%)")
        
        # Historical summary
        if self.history:
            print("\nHistorical Summary:")
            print("-" * 80)
            historical = self.get_historical_summary()
            for key, value in historical.items():
                print(f"  {key:30s}: {value}")
            
            # Learning curve
            print("\nLearning Curve (Last 10 Sessions):")
            print("-" * 80)
            curve = self.get_learning_curve()[-10:]
            print(f"  {'Session':<10} {'Date':<12} {'Txs':<8} {'Claude':<8} {'%':<8} {'Cost':<8}")
            print("  " + "-" * 70)
            for point in curve:
                print(f"  {point['session']:<10} {point['date']:<12} {point['transactions']:<8} "
                      f"{point['claude_calls']:<8} {point['claude_percentage']:<8.1f} "
                      f"${point['cost']:<7.4f}")
        
        print("\n" + "=" * 80)


def create_stats_tracker(storage_path: Path) -> LearningStats:
    """Factory function to create statistics tracker."""
    return LearningStats(storage_path)

