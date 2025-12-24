"""
Base calculator class with common utilities for all metric calculators.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import yaml
from pathlib import Path


class BaseCalculator:
    """Base class for all metric calculators with common utilities."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml'):
        """Initialize with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.reporting_period_days = self.config['reporting_period_days']
        self.stability_threshold = self.config['stability_threshold_pct']
        self.recent_months = self.config['recent_months']
    
    def filter_by_date_range(self, df: pd.DataFrame, end_date: Optional[datetime] = None) -> pd.DataFrame:
        """
        Filter transactions to reporting period.
        
        Args:
            df: DataFrame with 'date' column
            end_date: End date (defaults to most recent transaction)
        
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df['date']):
            df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y', errors='coerce')
        
        if end_date is None:
            end_date = df['date'].max()
        
        start_date = end_date - timedelta(days=self.reporting_period_days)
        
        return df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    def get_calendar_months(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of calendar months in format 'YYYY-MM'.
        
        Args:
            df: DataFrame with 'date' column
        
        Returns:
            Sorted list of month strings
        """
        if df.empty:
            return []
        
        return sorted(df['date'].dt.to_period('M').unique().astype(str).tolist())
    
    def calculate_monthly_totals(self, df: pd.DataFrame, amount_col: str = 'amount') -> Dict[str, float]:
        """
        Calculate totals by calendar month.
        
        Args:
            df: DataFrame with 'date' and amount column
            amount_col: Name of amount column
        
        Returns:
            Dict mapping 'YYYY-MM' to total amount
        """
        if df.empty:
            return {}
        
        df = df.copy()
        df['month'] = df['date'].dt.to_period('M').astype(str)
        monthly = df.groupby('month')[amount_col].sum().to_dict()
        
        return monthly
    
    def calculate_mean_monthly(self, monthly_totals: Dict[str, float]) -> float:
        """
        Calculate mean of monthly totals.
        
        Args:
            monthly_totals: Dict of month -> amount
        
        Returns:
            Mean monthly amount
        """
        if not monthly_totals:
            return 0.0
        
        return float(np.mean(list(monthly_totals.values())))
    
    def calculate_median_monthly(self, monthly_totals: Dict[str, float]) -> float:
        """
        Calculate median of monthly totals.
        
        Args:
            monthly_totals: Dict of month -> amount
        
        Returns:
            Median monthly amount
        """
        if not monthly_totals:
            return 0.0
        
        return float(np.median(list(monthly_totals.values())))
    
    def calculate_stability_months(self, monthly_totals: Dict[str, float]) -> int:
        """
        Calculate number of consecutive stable months from most recent.
        
        Stable = within stability_threshold % of previous month.
        
        Args:
            monthly_totals: Dict of month -> amount (must be chronological)
        
        Returns:
            Number of stable months (minimum 1 if any data)
        """
        if not monthly_totals:
            return 0
        
        months = sorted(monthly_totals.keys())
        if len(months) == 1:
            return 1
        
        # Start from most recent and go backwards
        stable_count = 1  # Current month is always counted
        
        for i in range(len(months) - 1, 0, -1):
            current_month = months[i]
            prev_month = months[i - 1]
            
            current_amount = monthly_totals[current_month]
            prev_amount = monthly_totals[prev_month]
            
            # Handle zero amounts
            if prev_amount == 0 and current_amount == 0:
                stable_count += 1
                continue
            
            if prev_amount == 0:
                break  # Not stable if previous was zero but current isn't
            
            # Calculate percentage difference
            pct_change = abs(current_amount - prev_amount) / abs(prev_amount)
            
            if pct_change <= self.stability_threshold:
                stable_count += 1
            else:
                break  # Stop at first unstable month
        
        return stable_count
    
    def calculate_security_months(self, monthly_totals: Dict[str, float]) -> int:
        """
        Calculate number of consecutive secure months (stable or improving).
        
        Secure = amount is stable or increasing compared to previous month.
        
        Args:
            monthly_totals: Dict of month -> amount
        
        Returns:
            Number of secure months
        """
        if not monthly_totals:
            return 0
        
        months = sorted(monthly_totals.keys())
        if len(months) == 1:
            return 1
        
        secure_count = 1  # Current month
        
        for i in range(len(months) - 1, 0, -1):
            current_amount = monthly_totals[months[i]]
            prev_amount = monthly_totals[months[i - 1]]
            
            # Secure if increasing or stable
            if prev_amount == 0:
                if current_amount >= 0:
                    secure_count += 1
                else:
                    break
            else:
                pct_change = (current_amount - prev_amount) / abs(prev_amount)
                
                if pct_change >= -self.stability_threshold:  # Stable or improving
                    secure_count += 1
                else:
                    break
        
        return secure_count
    
    def detect_frequency(self, dates: List[datetime]) -> Optional[str]:
        """
        Detect transaction frequency pattern.
        
        Args:
            dates: List of transaction dates
        
        Returns:
            'weekly', 'fortnightly', 'monthly', or None
        """
        if len(dates) < self.config['minimum_frequency_count']:
            return None
        
        dates = sorted(dates)
        gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
        
        if not gaps:
            return None
        
        avg_gap = np.mean(gaps)
        
        patterns = self.config['frequency_patterns']
        
        if patterns['weekly']['min_days'] <= avg_gap <= patterns['weekly']['max_days']:
            return 'weekly'
        elif patterns['fortnightly']['min_days'] <= avg_gap <= patterns['fortnightly']['max_days']:
            return 'fortnightly'
        elif patterns['monthly']['min_days'] <= avg_gap <= patterns['monthly']['max_days']:
            return 'monthly'
        
        return None
    
    def count_unique_merchants(self, df: pd.DataFrame) -> int:
        """
        Count unique merchants (normalized descriptions).
        
        Args:
            df: DataFrame with 'description' column
        
        Returns:
            Count of unique merchants
        """
        if df.empty:
            return 0
        
        # Normalize descriptions for counting
        merchants = df['description'].str.lower().str.strip().unique()
        return len(merchants)
    
    def filter_recent_transactions(self, df: pd.DataFrame, months: int = None) -> pd.DataFrame:
        """
        Filter to recent transactions.
        
        Args:
            df: DataFrame with 'date' column
            months: Number of recent months (defaults to config)
        
        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df
        
        if months is None:
            months = self.recent_months
        
        end_date = df['date'].max()
        start_date = end_date - timedelta(days=months * 30)
        
        return df[df['date'] >= start_date]

