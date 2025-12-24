"""
Risk flags calculator.

Calculates boolean flags:
- ME022: Has recent changes to salary circumstances
- ME023: Has received crisis support payments
- ME024: Has superannuation credits
- ME025: Has cash advances
- ME026: Has redraws
- ME027: Has High-Cost Finance
- ME028: Missing non-discretionary expenses: groceries
- ME029: Missing non-discretionary expenses: telecommunication
- ME030: Missing non-discretionary expenses: utilities
- ME031: Has Unemployment Benefit
- ME032: Receives Child Support
- ME047: Has unshared mortgage account
"""
import pandas as pd
import yaml
from typing import Dict
from .base_calculator import BaseCalculator


class RiskFlagsCalculator(BaseCalculator):
    """Calculator for risk flag metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml',
                 classification_path: str = 'transformer/config/expense_classification.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        with open(classification_path, 'r') as f:
            self.classification = yaml.safe_load(f)
        
        self.high_cost_lenders = set(self.classification['high_cost_lenders'])
    
    def calculate_all(self, df: pd.DataFrame, account_data: Dict = None) -> Dict[str, bool]:
        """
        Calculate all risk flag metrics.
        
        Args:
            df: DataFrame with categorized transactions
            account_data: Optional dict with shared account info
        
        Returns:
            Dict of metric_id -> bool
        """
        # Filter to reporting period
        df = self.filter_by_date_range(df)
        
        # ME022: Recent salary changes
        me022 = self._has_recent_salary_changes(df)
        
        # ME023: Crisis support
        me023 = self._has_category(df, 'INC-021')
        
        # ME024: Superannuation credits
        me024 = self._has_category(df, 'INC-010')
        
        # ME025: Cash advances
        me025 = self._has_category(df, 'EXP-003')
        
        # ME026: Redraws
        me026 = self._has_category(df, 'EXP-029')
        
        # ME027: High-cost finance
        me027 = self._has_high_cost_finance(df)
        
        # ME028: Missing groceries
        me028 = not self._has_category(df, 'EXP-016')
        
        # ME029: Missing telecommunication
        me029 = not self._has_category(df, 'EXP-036')
        
        # ME030: Missing utilities
        me030 = not self._has_category(df, 'EXP-040')
        
        # ME031: Unemployment benefit
        me031 = self._has_category(df, 'INC-016')
        
        # ME032: Child support
        me032 = self._has_category(df, 'INC-002')
        
        # ME047: Unshared mortgage
        me047 = self._has_unshared_mortgage(df, account_data)
        
        return {
            'ME022': me022,
            'ME023': me023,
            'ME024': me024,
            'ME025': me025,
            'ME026': me026,
            'ME027': me027,
            'ME028': me028,
            'ME029': me029,
            'ME030': me030,
            'ME031': me031,
            'ME032': me032,
            'ME047': me047,
        }
    
    def _has_category(self, df: pd.DataFrame, category: str) -> bool:
        """Check if category exists in transactions."""
        return (df['basiq_category'] == category).any()
    
    def _has_recent_salary_changes(self, df: pd.DataFrame) -> bool:
        """
        Detect recent salary changes.
        
        Indicates new salary source in last 2 months OR salary source stopping.
        """
        salary_df = df[df['basiq_category'] == 'INC-009']
        
        if salary_df.empty:
            return False
        
        # Get recent transactions
        recent_df = self.filter_recent_transactions(salary_df, months=self.recent_months)
        
        # Get all historical transactions
        all_df = salary_df.copy()
        all_df['merchant_normalized'] = all_df['description'].str.lower().str.strip()
        recent_df_copy = recent_df.copy()
        recent_df_copy['merchant_normalized'] = recent_df_copy['description'].str.lower().str.strip()
        
        # Get unique merchants
        all_merchants = set(all_df['merchant_normalized'].unique())
        recent_merchants = set(recent_df_copy['merchant_normalized'].unique())
        
        # Check for new sources (in recent but not before)
        if len(recent_merchants - all_merchants) > 0:
            return True
        
        # Check for stopped sources (was before but not in recent)
        # Get older transactions
        end_date = df['date'].max()
        start_recent = end_date - pd.Timedelta(days=self.recent_months * 30)
        older_df = all_df[all_df['date'] < start_recent]
        
        if not older_df.empty:
            older_merchants = set(older_df['merchant_normalized'].unique())
            if len(older_merchants - recent_merchants) > 0:
                return True
        
        return False
    
    def _has_high_cost_finance(self, df: pd.DataFrame) -> bool:
        """Check if has payments to high-cost lenders."""
        expenses_df = df[df['amount'] < 0]
        return expenses_df['basiq_category'].isin(self.high_cost_lenders).any()
    
    def _has_unshared_mortgage(self, df: pd.DataFrame, account_data: Dict = None) -> bool:
        """
        Check if mortgage payments detected but no mortgage account shared.
        
        Args:
            df: Transaction DataFrame
            account_data: Optional dict with 'has_mortgage_account': bool
        
        Returns:
            True if mortgage payments exist but account not shared
        """
        has_mortgage_payments = self._has_category(df, 'EXP-056')
        
        if not has_mortgage_payments:
            return False
        
        if account_data is None:
            return True  # Assume unshared if no account data
        
        has_mortgage_account = account_data.get('has_mortgage_account', False)
        return not has_mortgage_account

