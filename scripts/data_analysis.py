"""Example data analysis script for testing artifact management."""

import pandas as pd
import numpy as np

def analyze_sales_data(csv_path):
    """Analyze sales data from CSV file."""
    df = pd.read_csv(csv_path)

    # Basic statistics
    summary = df.describe()

    # Monthly trends
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        monthly = df.groupby(df['date'].dt.strftime('%Y-%m')).sum()

    return summary, monthly

if __name__ == "__main__":
    print("Data analysis script ready!")