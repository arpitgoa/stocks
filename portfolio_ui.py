import pandas as pd
import numpy as np
import plotly.graph_objects as go
from ipywidgets import interact, IntSlider, DatePicker, IntText
from datetime import datetime

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
    
    for i, date in enumerate(df.index):
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

def update_plot(initial_investment, monthly_additional, rebalance_months, start_date, end_date):
    df = load_data(start_date=start_date, end_date=end_date)
    
    strategies = {}
    for ticker in df.columns:
        strategies[ticker] = run_individual_strategy(df, ticker, initial_investment, monthly_additional)
    
    strategies['Balanced'] = run_balanced_strategy(df, initial_investment, rebalance_months, monthly_additional)
    
    results = pd.DataFrame(strategies)
    
    fig = go.Figure()
    for col in results.columns:
        final_val = results[col].iloc[-1]
        ret = (final_val / initial_investment - 1) * 100
        fig.add_trace(go.Scatter(
            x=results.index, 
            y=results[col], 
            mode='lines',
            name=f'{col}: ${final_val:,.0f} ({ret:.1f}%)',
            line=dict(width=2)
        ))
    
    fig.update_layout(
        title=f'Portfolio Comparison - Initial: ${initial_investment:,}, Monthly: ${monthly_additional:,}',
        xaxis_title='Date',
        yaxis_title='Portfolio Value ($)',
        hovermode='x unified',
        height=600
    )
    
    fig.show()

# Get date range from data
df_full = load_data()
min_date = df_full.index.min().date()
max_date = df_full.index.max().date()

interact(
    update_plot,
    initial_investment=IntSlider(min=1000, max=100000, step=1000, value=10000, description='Initial $'),
    monthly_additional=IntSlider(min=0, max=5000, step=100, value=0, description='Monthly $'),
    rebalance_months=IntSlider(min=1, max=12, step=1, value=6, description='Rebalance'),
    start_date=DatePicker(value=min_date, description='Start Date'),
    end_date=DatePicker(value=max_date, description='End Date')
)
