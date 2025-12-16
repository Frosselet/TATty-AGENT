"""Plot generation script for testing artifact management."""

import matplotlib.pyplot as plt
import pandas as pd

def create_sales_plot(data_path, output_path):
    """Create sales visualization from data."""
    df = pd.read_csv(data_path)

    plt.figure(figsize=(10, 6))
    plt.plot(df['date'], df['sales'])
    plt.title('Sales Trends')
    plt.xlabel('Date')
    plt.ylabel('Sales')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

    print(f"Plot saved to {output_path}")

if __name__ == "__main__":
    create_sales_plot("../data/sample_sales.csv", "../visualization/sales_trend.png")