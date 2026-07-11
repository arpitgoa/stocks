import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_data(filename='monthly_data.csv', tickers=['BRKB', 'SPY', 'GLD', 'QQQ'], start_date=None, end_date=None):
    df = pd.read_csv(filename, index_col=0, parse_dates=True)
    df.columns = ['BRKB', 'GLD', 'GSPC', 'GOLD', 'QQQ', 'SPY']
    df = df[tickers].dropna()
    
    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]
    
    return df

def run_individual_strategy(df, ticker, initial_investment, monthly_additional=0):
    shares = initial_investment / df[ticker].iloc[0]
    values = []
    for i in range(len(df)):
        if i > 0 and monthly_additional > 0:
            shares += monthly_additional / df[ticker].iloc[i]
        values.append(shares * df[ticker].iloc[i])
    return pd.Series(values, index=df.index)

def run_balanced_strategy(df, initial_investment, rebalance_months, monthly_additional=0):
    balanced = pd.DataFrame(index=df.index)
    target_weights = {ticker: 1/len(df.columns) for ticker in df.columns}
    total_invested = initial_investment
    
    for i, date in enumerate(df.index):
        if i > 0 and monthly_additional > 0:
            total_invested += monthly_additional
        
        if i == 0:
            for ticker in df.columns:
                shares = (initial_investment * target_weights[ticker]) / df[ticker].iloc[i]
                balanced.loc[date, f'{ticker}_shares'] = shares
        elif i % rebalance_months == 0:
            current_value = sum(balanced.loc[df.index[i-1], f'{ticker}_shares'] * df[ticker].iloc[i] for ticker in df.columns)
            if monthly_additional > 0:
                current_value += monthly_additional
            for ticker in df.columns:
                shares = (current_value * target_weights[ticker]) / df[ticker].iloc[i]
                balanced.loc[date, f'{ticker}_shares'] = shares
        else:
            for ticker in df.columns:
                prev_shares = balanced.loc[df.index[i-1], f'{ticker}_shares']
                if monthly_additional > 0:
                    prev_shares += (monthly_additional * target_weights[ticker]) / df[ticker].iloc[i]
                balanced.loc[date, f'{ticker}_shares'] = prev_shares
        
        for ticker in df.columns:
            balanced.loc[date, ticker] = balanced.loc[date, f'{ticker}_shares'] * df[ticker].iloc[i]
    
    return balanced[df.columns].sum(axis=1)

def plot_results(results, initial_investment):
    plt.figure(figsize=(12, 8))
    for col in results.columns:
        final_val = results[col].iloc[-1]
        ret = (final_val / initial_investment - 1) * 100
        plt.plot(results.index, results[col], label=f'{col}: ${final_val:,.0f} ({ret:.1f}%)', linewidth=2)
    plt.ylabel('Portfolio Value ($)')
    plt.xlabel('Date')
    plt.title(f'Portfolio Comparison - Each Starting with ${initial_investment:,.0f}')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('portfolio_performance.png', dpi=150)
    plt.show()

def print_results(results, initial_investment, rebalance_months):
    print(f"Each strategy starts with: ${initial_investment:,.0f}")
    print(f"Balanced rebalances every {rebalance_months} months\n")
    print(f"Final Values ({results.index[-1].strftime('%Y-%m')}):")
    for col in results.columns:
        final_val = results[col].iloc[-1]
        ret = (final_val / initial_investment - 1) * 100
        print(f"{col:8s}: ${final_val:>12,.2f} ({ret:>7.2f}%)")
    print(f"\nGraph saved to portfolio_performance.png")
    print(f"Results saved to portfolio_results.csv")

def run_simulation(initial_investment=10000, monthly_additional=0, rebalance_months=6, start_date=None, end_date=None):
    df = load_data(start_date=start_date, end_date=end_date)
    
    strategies = {}
    for ticker in df.columns:
        strategies[ticker] = run_individual_strategy(df, ticker, initial_investment, monthly_additional)
    
    strategies['Balanced'] = run_balanced_strategy(df, initial_investment, rebalance_months, monthly_additional)
    
    results = pd.DataFrame(strategies)
    results.to_csv('portfolio_results.csv')
    
    plot_results(results, initial_investment)
    print_results(results, initial_investment, rebalance_months)
    
    return results

if __name__ == '__main__':
    run_simulation(initial_investment=10000, monthly_additional=0, rebalance_months=6)
