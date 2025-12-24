"""
Government services metrics calculator.

Calculates:
- ME005: Youth Allowance monthly
- ME006: Rental Assistance monthly
- ME007: Misc Government services monthly
"""
import pandas as pd
from typing import Dict
from .base_calculator import BaseCalculator


class GovernmentServicesCalculator(BaseCalculator):
    """Calculator for government services metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        gov_config = self.config['government_services']
        self.youth_allowance = gov_config['youth_allowance']
        self.rental_assistance = gov_config['rental_assistance']
        self.other_benefits = set(gov_config['other_benefits'])
    
    def calculate_all(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate all government services metrics.
        
        Args:
            df: DataFrame with categorized transactions
        
        Returns:
            Dict of metric_id -> value
        """
        # Filter to reporting period and income
        df = self.filter_by_date_range(df)
        income_df = df[df['amount'] > 0].copy()
        
        # Filter by benefit type
        youth_allowance_df = income_df[income_df['basiq_category'] == self.youth_allowance]
        rental_assistance_df = income_df[income_df['basiq_category'] == self.rental_assistance]
        other_benefits_df = income_df[income_df['basiq_category'].isin(self.other_benefits)]
        
        # Calculate monthly averages
        youth_monthly = self.calculate_monthly_totals(youth_allowance_df)
        rental_monthly = self.calculate_monthly_totals(rental_assistance_df)
        other_monthly = self.calculate_monthly_totals(other_benefits_df)
        
        me005 = self.calculate_mean_monthly(youth_monthly)
        me006 = self.calculate_mean_monthly(rental_monthly)
        me007 = self.calculate_mean_monthly(other_monthly)
        
        return {
            'ME005': round(me005, 2),
            'ME006': round(me006, 2),
            'ME007': round(me007, 2),
        }

