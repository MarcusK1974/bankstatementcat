"""
Expense metrics calculator.

Calculates:
- ME012: Monthly spend on non-discretionary expenses
- ME013: % of spend on non-discretionary expenses
- ME014: Monthly spend on discretionary expenses
- ME015: % of spend on discretionary expenses
- ME016: Monthly spend on other expenses
- ME034: Average Outgoings monthly
- ME039: Average outgoings excluding liabilities
"""
import pandas as pd
import yaml
from typing import Dict
from .base_calculator import BaseCalculator


class ExpenseCalculator(BaseCalculator):
    """Calculator for expense-related metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml',
                 classification_path: str = 'transformer/config/expense_classification.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        with open(classification_path, 'r') as f:
            self.classification = yaml.safe_load(f)
        
        self.non_discretionary = set(self.classification['non_discretionary'])
        self.discretionary = set(self.classification['discretionary'])
        self.other_expenses = set(self.classification['other_expenses'])
        self.liabilities = set(self.classification['liabilities'])
    
    def calculate_all(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate all expense metrics.
        
        Args:
            df: DataFrame with categorized transactions
        
        Returns:
            Dict of metric_id -> value
        """
        # Filter to reporting period and expenses only (negative amounts)
        df = self.filter_by_date_range(df)
        expenses_df = df[df['amount'] < 0].copy()
        expenses_df['amount'] = expenses_df['amount'].abs()  # Work with positive amounts
        
        # Calculate monthly totals by category type
        non_disc_monthly = self._calculate_category_monthly(expenses_df, self.non_discretionary)
        disc_monthly = self._calculate_category_monthly(expenses_df, self.discretionary)
        other_monthly = self._calculate_category_monthly(expenses_df, self.other_expenses)
        all_monthly = self._calculate_all_expenses_monthly(expenses_df)
        non_liability_monthly = self._calculate_non_liability_monthly(expenses_df)
        
        # Calculate means
        me012 = self.calculate_mean_monthly(non_disc_monthly)
        me014 = self.calculate_mean_monthly(disc_monthly)
        me016 = self.calculate_mean_monthly(other_monthly)
        me034 = self.calculate_mean_monthly(all_monthly)
        me039 = self.calculate_mean_monthly(non_liability_monthly)
        
        # Calculate percentages (ME013, ME015)
        total_discretionary_non_discretionary = me012 + me014
        
        if total_discretionary_non_discretionary > 0:
            me013 = (me012 / total_discretionary_non_discretionary) * 100
            me015 = (me014 / total_discretionary_non_discretionary) * 100
        else:
            me013 = 0.0
            me015 = 0.0
        
        return {
            'ME012': round(me012, 2),
            'ME013': round(me013, 2),
            'ME014': round(me014, 2),
            'ME015': round(me015, 2),
            'ME016': round(me016, 2),
            'ME034': round(me034, 2),
            'ME039': round(me039, 2),
        }
    
    def _calculate_category_monthly(self, df: pd.DataFrame, categories: set) -> Dict[str, float]:
        """Calculate monthly totals for specific categories."""
        category_df = df[df['basiq_category'].isin(categories)]
        return self.calculate_monthly_totals(category_df)
    
    def _calculate_all_expenses_monthly(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate monthly totals for all expenses."""
        return self.calculate_monthly_totals(df)
    
    def _calculate_non_liability_monthly(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate monthly totals excluding liability payments."""
        non_liability_df = df[~df['basiq_category'].isin(self.liabilities)]
        return self.calculate_monthly_totals(non_liability_df)

