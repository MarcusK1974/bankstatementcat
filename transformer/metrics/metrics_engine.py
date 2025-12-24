"""
Main metrics engine that orchestrates all metric calculators.
"""
import pandas as pd
import json
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

from .expense_calculator import ExpenseCalculator
from .income_calculator import IncomeCalculator
from .financial_commitments_calculator import FinancialCommitmentsCalculator
from .government_services_calculator import GovernmentServicesCalculator
from .risk_flags_calculator import RiskFlagsCalculator
from .risk_metrics_calculator import RiskMetricsCalculator


class MetricsEngine:
    """Orchestrates all metric calculators."""
    
    def __init__(self, config_path: str = 'transformer/config/metrics_config.yaml'):
        """Initialize all calculators."""
        self.expense_calc = ExpenseCalculator(config_path)
        self.income_calc = IncomeCalculator(config_path)
        self.financial_calc = FinancialCommitmentsCalculator(config_path)
        self.gov_services_calc = GovernmentServicesCalculator(config_path)
        self.risk_flags_calc = RiskFlagsCalculator(config_path)
        self.risk_metrics_calc = RiskMetricsCalculator(config_path)
        
        self.reporting_period_days = self.expense_calc.reporting_period_days
    
    def calculate_all_metrics(self, 
                              transactions_df: pd.DataFrame, 
                              customer_id: str,
                              account_data: Optional[Dict] = None) -> Dict:
        """
        Calculate all 46 metrics for a customer.
        
        Args:
            transactions_df: DataFrame with categorized transactions
                Required columns: date, description, amount, basiq_category
            customer_id: Customer identifier
            account_data: Optional dict with account information:
                - credit_card_limits: List[float]
                - credit_card_balances: List[float]
                - has_mortgage_account: bool
        
        Returns:
            Dict with all metrics
        """
        # Ensure date column is datetime
        if not pd.api.types.is_datetime64_any_dtype(transactions_df['date']):
            transactions_df['date'] = pd.to_datetime(
                transactions_df['date'], 
                format='%d/%m/%Y', 
                errors='coerce'
            )
        
        # Normalize column names
        if 'basiq_category_code' in transactions_df.columns and 'basiq_category' not in transactions_df.columns:
            transactions_df['basiq_category'] = transactions_df['basiq_category_code']
        
        # Validate required columns
        required_columns = ['date', 'description', 'amount', 'basiq_category']
        missing_columns = [col for col in required_columns if col not in transactions_df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Initialize result
        metrics = {
            'customer_id': customer_id,
            'reporting_period_days': self.reporting_period_days,
            'calculation_date': datetime.now().isoformat(),
        }
        
        # Calculate each section
        print(f"  Calculating metrics for {customer_id}...")
        
        metrics.update(self.expense_calc.calculate_all(transactions_df))
        metrics.update(self.income_calc.calculate_all(transactions_df))
        metrics.update(self.financial_calc.calculate_all(transactions_df, account_data))
        metrics.update(self.gov_services_calc.calculate_all(transactions_df))
        metrics.update(self.risk_flags_calc.calculate_all(transactions_df, account_data))
        metrics.update(self.risk_metrics_calc.calculate_all(transactions_df))
        
        # Convert numpy types to native Python types for JSON serialization
        metrics = self._convert_to_native_types(metrics)
        
        return metrics
    
    def _convert_to_native_types(self, metrics: Dict) -> Dict:
        """Convert numpy/pandas types to native Python types."""
        import numpy as np
        
        converted = {}
        for key, value in metrics.items():
            if isinstance(value, (np.integer, np.int64, np.int32)):
                converted[key] = int(value)
            elif isinstance(value, (np.floating, np.float64, np.float32)):
                converted[key] = float(value)
            elif isinstance(value, (np.bool_, bool)):
                converted[key] = bool(value)
            elif pd.isna(value):
                converted[key] = None
            else:
                converted[key] = value
        
        return converted
    
    def process_single_file(self, 
                           input_csv: str, 
                           customer_id: Optional[str] = None,
                           account_data: Optional[Dict] = None) -> Dict:
        """
        Process a single customer's transactions from CSV.
        
        Args:
            input_csv: Path to categorized transactions CSV
            customer_id: Optional customer ID (defaults to filename)
            account_data: Optional account information
        
        Returns:
            Dict with all metrics
        """
        # Load transactions
        df = pd.read_csv(input_csv)
        
        if customer_id is None:
            customer_id = Path(input_csv).stem
        
        return self.calculate_all_metrics(df, customer_id, account_data)
    
    def process_batch(self, 
                     input_files: list, 
                     output_csv: Optional[str] = None,
                     output_json: Optional[str] = None) -> pd.DataFrame:
        """
        Process multiple customers and export results.
        
        Args:
            input_files: List of paths to categorized transaction CSVs
            output_csv: Optional path to export CSV
            output_json: Optional path to export JSON
        
        Returns:
            DataFrame with all metrics
        """
        results = []
        
        print(f"Processing {len(input_files)} customers...")
        
        for input_file in input_files:
            try:
                metrics = self.process_single_file(input_file)
                results.append(metrics)
            except Exception as e:
                print(f"  ERROR processing {input_file}: {e}")
                continue
        
        # Create DataFrame
        results_df = pd.DataFrame(results)
        
        # Reorder columns logically
        column_order = ['customer_id', 'reporting_period_days', 'calculation_date']
        
        # Add all ME metrics in order
        me_columns = sorted([col for col in results_df.columns if col.startswith('ME')],
                          key=lambda x: int(x.replace('ME', '')))
        column_order.extend(me_columns)
        
        results_df = results_df[column_order]
        
        # Export
        if output_csv:
            results_df.to_csv(output_csv, index=False)
            print(f"✓ CSV exported to: {output_csv}")
        
        if output_json:
            results_json = results_df.to_dict(orient='records')
            with open(output_json, 'w') as f:
                json.dump(results_json, f, indent=2)
            print(f"✓ JSON exported to: {output_json}")
        
        return results_df
    
    def export_metrics_schema(self, output_path: str):
        """
        Export metric definitions as JSON schema.
        
        Useful for documentation and API integration.
        """
        schema = {
            "reporting_period_days": 180,
            "metrics": {
                # Expenses
                "ME012": {"name": "Monthly spend on non-discretionary expenses", "type": "money"},
                "ME013": {"name": "% of spend on non-discretionary expenses", "type": "percent"},
                "ME014": {"name": "Monthly spend on discretionary expenses", "type": "money"},
                "ME015": {"name": "% of spend on discretionary expenses", "type": "percent"},
                "ME016": {"name": "Monthly spend on other expenses", "type": "money"},
                "ME034": {"name": "Average Outgoings monthly", "type": "money"},
                "ME039": {"name": "Average outgoings excluding liabilities", "type": "money"},
                
                # Income
                "ME001": {"name": "# of identified salary sources", "type": "integer"},
                "ME002": {"name": "Average monthly amount from salary", "type": "money"},
                "ME003": {"name": "Salary has been stable for (months)", "type": "integer"},
                "ME004": {"name": "Other possible income monthly", "type": "money"},
                "ME033": {"name": "Average Income monthly (salary only)", "type": "money"},
                "ME035": {"name": "Total Income has been stable for (months)", "type": "integer"},
                "ME036": {"name": "Median monthly amount from Salary", "type": "money"},
                "ME037": {"name": "Median Income monthly (salary only)", "type": "money"},
                "ME040": {"name": "Average Monthly Credits", "type": "money"},
                "ME041": {"name": "Average Monthly Debits", "type": "money"},
                "ME042": {"name": "# of recent income sources", "type": "integer"},
                "ME043": {"name": "# of ongoing regular income sources", "type": "integer"},
                "ME045": {"name": "Total Income has been secure for (months)", "type": "integer"},
                
                # Financial Commitments
                "ME008": {"name": "Average monthly amount to lenders", "type": "money"},
                "ME009": {"name": "# of identified lending companies", "type": "integer"},
                "ME010": {"name": "Total credit card limit", "type": "money"},
                "ME011": {"name": "Total credit card balance", "type": "money"},
                "ME046": {"name": "Average monthly ongoing amount to lenders", "type": "money"},
                "ME048": {"name": "Ongoing Monthly Mortgage Repayment", "type": "money"},
                
                # Government Services
                "ME005": {"name": "Youth Allowance monthly", "type": "money"},
                "ME006": {"name": "Rental Assistance monthly", "type": "money"},
                "ME007": {"name": "Misc Government services monthly", "type": "money"},
                
                # Risk Flags
                "ME022": {"name": "Has recent changes to salary circumstances", "type": "boolean"},
                "ME023": {"name": "Has received crisis support payments", "type": "boolean"},
                "ME024": {"name": "Has superannuation credits", "type": "boolean"},
                "ME025": {"name": "Has cash advances", "type": "boolean"},
                "ME026": {"name": "Has redraws", "type": "boolean"},
                "ME027": {"name": "Has High-Cost Finance", "type": "boolean"},
                "ME028": {"name": "Missing non-discretionary expenses: groceries", "type": "boolean"},
                "ME029": {"name": "Missing non-discretionary expenses: telecommunication", "type": "boolean"},
                "ME030": {"name": "Missing non-discretionary expenses: utilities", "type": "boolean"},
                "ME031": {"name": "Has Unemployment Benefit", "type": "boolean"},
                "ME032": {"name": "Receives Child Support", "type": "boolean"},
                "ME047": {"name": "Has unshared mortgage account", "type": "boolean"},
                
                # Risk Metrics
                "ME017": {"name": "# of SACC loans", "type": "integer"},
                "ME018": {"name": "% of income withdrawn via ATM", "type": "percent"},
                "ME019": {"name": "# of financial dishonours", "type": "integer"},
                "ME020": {"name": "% of income spent on High Risk Activities", "type": "percent"},
                "ME021": {"name": "Total spend on High Risk Activities", "type": "money"},
            }
        }
        
        with open(output_path, 'w') as f:
            json.dump(schema, f, indent=2)
        
        print(f"✓ Metrics schema exported to: {output_path}")

