"""
Risk metrics calculator.

Calculates:
- ME017: # of SACC loans
- ME018: % of income withdrawn via ATM
- ME019: # of financial dishonours
- ME020: % of income spent on High Risk Activities
- ME021: Total spend on High Risk Activities
"""
import pandas as pd
from typing import Dict
from .base_calculator import BaseCalculator


class RiskMetricsCalculator(BaseCalculator):
    """Calculator for risk metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        self.high_risk_categories = set(self.config['high_risk_categories'])
    
    def calculate_all(self, df: pd.DataFrame) -> Dict:
        """
        Calculate all risk metrics.
        
        Args:
            df: DataFrame with categorized transactions
        
        Returns:
            Dict of metric_id -> value
        """
        # Filter to reporting period
        df = self.filter_by_date_range(df)
        
        # Separate income and expenses
        income_df = df[df['amount'] > 0].copy()
        expenses_df = df[df['amount'] < 0].copy()
        expenses_df['amount'] = expenses_df['amount'].abs()
        
        # Calculate total income
        total_income = income_df['amount'].sum()
        
        # ME017: Count SACC lenders (unique merchants in EXP-033)
        sacc_df = expenses_df[expenses_df['basiq_category'] == 'EXP-033']
        me017 = self.count_unique_merchants(sacc_df)
        
        # ME019: Count dishonours
        dishonour_df = df[df['basiq_category'] == 'EXP-009']
        me019 = len(dishonour_df)
        
        # ME018: % of income withdrawn via ATM
        atm_df = expenses_df[expenses_df['basiq_category'] == 'EXP-001']
        atm_total = atm_df['amount'].sum()
        
        if total_income > 0:
            me018 = (atm_total / total_income) * 100
        else:
            me018 = 0.0
        
        # ME020, ME021: High risk activities
        high_risk_df = expenses_df[expenses_df['basiq_category'].isin(self.high_risk_categories)]
        high_risk_total = high_risk_df['amount'].sum()
        
        me021 = high_risk_total
        
        if total_income > 0:
            me020 = (high_risk_total / total_income) * 100
        else:
            me020 = 0.0
        
        return {
            'ME017': me017,
            'ME018': round(me018, 2),
            'ME019': me019,
            'ME020': round(me020, 2),
            'ME021': round(me021, 2),
        }

