"""
Income metrics calculator.

Calculates:
- ME001: # of identified salary sources
- ME002: Average monthly amount from salary
- ME003: Salary has been stable for (months)
- ME004: Other possible income monthly
- ME033: Average Income monthly (SALARY ONLY)
- ME035: Total Income has been stable for (months) (SALARY STABILITY)
- ME036: Median monthly amount from Salary
- ME037: Median Income monthly (SALARY ONLY)
- ME040: Average Monthly Credits (ALL INCOME)
- ME041: Average Monthly Debits
- ME042: # of recent income sources
- ME043: # of ongoing regular income sources
- ME045: Total Income has been secure for (months) (ALL INCOME)
"""
import pandas as pd
from typing import Dict, List
from .base_calculator import BaseCalculator


class IncomeCalculator(BaseCalculator):
    """Calculator for income-related metrics."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml'):
        """Initialize with configuration."""
        super().__init__(config_path)
        
        self.salary_groups = set(self.config['salary_income_groups'])
        self.all_income_groups = set(self.config['all_income_groups'])
    
    def calculate_all(self, df: pd.DataFrame) -> Dict:
        """
        Calculate all income metrics.
        
        Args:
            df: DataFrame with categorized transactions
        
        Returns:
            Dict of metric_id -> value
        """
        # Filter to reporting period
        df = self.filter_by_date_range(df)
        
        # Separate income (positive) and expenses (negative)
        income_df = df[df['amount'] > 0].copy()
        expense_df = df[df['amount'] < 0].copy()
        expense_df['amount'] = expense_df['amount'].abs()
        
        # Filter by salary only
        salary_df = income_df[income_df['basiq_category'].isin(self.salary_groups)]
        
        # Filter all income
        all_income_df = income_df[income_df['basiq_category'].isin(self.all_income_groups)]
        
        # Filter other income (not salary)
        other_income_groups = self.all_income_groups - self.salary_groups
        other_income_df = income_df[income_df['basiq_category'].isin(other_income_groups)]
        
        # Calculate monthly totals
        salary_monthly = self.calculate_monthly_totals(salary_df)
        all_income_monthly = self.calculate_monthly_totals(all_income_df)
        other_income_monthly = self.calculate_monthly_totals(other_income_df)
        expense_monthly = self.calculate_monthly_totals(expense_df)
        
        # ME001: Count salary sources
        me001 = self._count_income_sources(salary_df)
        
        # ME002: Average monthly salary
        me002 = self.calculate_mean_monthly(salary_monthly)
        
        # ME003: Salary stability months
        me003 = self.calculate_stability_months(salary_monthly)
        
        # ME004: Other income monthly
        me004 = self.calculate_mean_monthly(other_income_monthly)
        
        # ME033: Average Income monthly (SALARY ONLY - same as ME002)
        me033 = me002
        
        # ME035: Total Income stable months (SALARY STABILITY - same as ME003)
        me035 = me003
        
        # ME036: Median monthly salary
        me036 = self.calculate_median_monthly(salary_monthly)
        
        # ME037: Median Income monthly (SALARY ONLY - same as ME036)
        me037 = me036
        
        # ME040: Average Monthly Credits (ALL INCOME)
        me040 = self.calculate_mean_monthly(all_income_monthly)
        
        # ME041: Average Monthly Debits
        me041 = self.calculate_mean_monthly(expense_monthly)
        
        # ME042: # of recent income sources
        recent_income_df = self.filter_recent_transactions(income_df)
        me042 = self._count_income_sources(recent_income_df)
        
        # ME043: # of ongoing regular income sources
        me043 = self._count_ongoing_income_sources(income_df)
        
        # ME045: Total Income secure months (ALL INCOME)
        me045 = self.calculate_security_months(all_income_monthly)
        
        return {
            'ME001': me001,
            'ME002': round(me002, 2),
            'ME003': me003,
            'ME004': round(me004, 2),
            'ME033': round(me033, 2),
            'ME035': me035,
            'ME036': round(me036, 2),
            'ME037': round(me037, 2),
            'ME040': round(me040, 2),
            'ME041': round(me041, 2),
            'ME042': me042,
            'ME043': me043,
            'ME045': me045,
        }
    
    def _count_income_sources(self, df: pd.DataFrame) -> int:
        """
        Count unique income sources.
        
        Groups by basiq_category and normalized description to count unique sources.
        """
        if df.empty:
            return 0
        
        # Count unique combinations of category + merchant
        df = df.copy()
        df['merchant_normalized'] = df['description'].str.lower().str.strip()
        
        unique_sources = df.groupby(['basiq_category', 'merchant_normalized']).size()
        return len(unique_sources)
    
    def _count_ongoing_income_sources(self, df: pd.DataFrame) -> int:
        """
        Count ongoing income sources with detected frequency.
        
        An income source is "ongoing" if it has a detectable frequency pattern.
        """
        if df.empty:
            return 0
        
        df = df.copy()
        df['merchant_normalized'] = df['description'].str.lower().str.strip()
        
        # Group by category + merchant
        ongoing_count = 0
        
        for (category, merchant), group in df.groupby(['basiq_category', 'merchant_normalized']):
            dates = group['date'].tolist()
            frequency = self.detect_frequency(dates)
            
            if frequency is not None:
                ongoing_count += 1
        
        return ongoing_count

