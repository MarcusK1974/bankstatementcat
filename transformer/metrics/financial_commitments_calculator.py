"""
Financial commitments metrics calculator.

Calculates:
- ME008: Average monthly amount to lenders
- ME009: # of identified lending companies
- ME010: Total credit card limit (requires account data)
- ME011: Total credit card balance (requires account data)
- ME046: Average monthly ongoing amount to lenders
- ME048: Ongoing Monthly Mortgage Repayment
"""
import pandas as pd
import yaml
from typing import Dict
from .base_calculator import BaseCalculator


class FinancialCommitmentsCalculator(BaseCalculator):
    """Calculator for financial commitments metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml',
                 classification_path: str = 'transformer/config/expense_classification.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        with open(classification_path, 'r') as f:
            self.classification = yaml.safe_load(f)
        
        self.lender_categories = set(self.classification['lender_categories'])
    
    def calculate_all(self, df: pd.DataFrame, account_data: Dict = None) -> Dict:
        """
        Calculate all financial commitments metrics.
        
        Args:
            df: DataFrame with categorized transactions
            account_data: Optional dict with credit card account data
                {'credit_card_limits': [float], 'credit_card_balances': [float]}
        
        Returns:
            Dict of metric_id -> value
        """
        # Filter to reporting period and expenses
        df = self.filter_by_date_range(df)
        expenses_df = df[df['amount'] < 0].copy()
        expenses_df['amount'] = expenses_df['amount'].abs()
        
        # Filter to lender payments
        lender_df = expenses_df[expenses_df['basiq_category'].isin(self.lender_categories)]
        
        # Filter to mortgage payments
        mortgage_df = expenses_df[expenses_df['basiq_category'] == 'EXP-056']
        
        # Calculate monthly totals
        lender_monthly = self.calculate_monthly_totals(lender_df)
        mortgage_monthly = self.calculate_monthly_totals(mortgage_df)
        
        # ME008: Average monthly lender payments
        me008 = self.calculate_mean_monthly(lender_monthly)
        
        # ME009: Count of lending companies
        me009 = self.count_unique_merchants(lender_df)
        
        # ME010, ME011: Credit card account data (requires shared accounts)
        me010 = None
        me011 = None
        if account_data:
            me010 = sum(account_data.get('credit_card_limits', []))
            me011 = sum(account_data.get('credit_card_balances', []))
        
        # ME046: Ongoing monthly lender payments
        # This is average of lenders with detected frequency
        me046 = self._calculate_ongoing_lender_payments(lender_df)
        
        # ME048: Ongoing monthly mortgage payment
        # This is average of mortgage payments with detected frequency
        me048 = self._calculate_ongoing_mortgage_payment(mortgage_df)
        
        return {
            'ME008': round(me008, 2),
            'ME009': me009,
            'ME010': round(me010, 2) if me010 is not None else None,
            'ME011': round(me011, 2) if me011 is not None else None,
            'ME046': round(me046, 2),
            'ME048': round(me048, 2),
        }
    
    def _calculate_ongoing_lender_payments(self, df: pd.DataFrame) -> float:
        """
        Calculate ongoing monthly lender payments.
        
        Only includes lenders with detected frequency pattern.
        """
        if df.empty:
            return 0.0
        
        df = df.copy()
        df['merchant_normalized'] = df['description'].str.lower().str.strip()
        
        ongoing_totals = {}
        
        for (category, merchant), group in df.groupby(['basiq_category', 'merchant_normalized']):
            dates = group['date'].tolist()
            frequency = self.detect_frequency(dates)
            
            if frequency is not None:
                # Calculate monthly average for this lender
                monthly_totals = self.calculate_monthly_totals(group)
                avg = self.calculate_mean_monthly(monthly_totals)
                
                for month in monthly_totals:
                    if month not in ongoing_totals:
                        ongoing_totals[month] = 0
                    ongoing_totals[month] += monthly_totals[month]
        
        return self.calculate_mean_monthly(ongoing_totals)
    
    def _calculate_ongoing_mortgage_payment(self, df: pd.DataFrame) -> float:
        """
        Calculate ongoing monthly mortgage payment.
        
        Projects forward based on detected frequency.
        """
        if df.empty:
            return 0.0
        
        # Check if mortgage has regular frequency
        dates = df['date'].tolist()
        frequency = self.detect_frequency(dates)
        
        if frequency is None:
            return 0.0
        
        # Calculate mean monthly
        monthly_totals = self.calculate_monthly_totals(df)
        return self.calculate_mean_monthly(monthly_totals)

