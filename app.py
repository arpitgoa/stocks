from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pandas as pd
import json
from pyxirr import xirr
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Load data once at startup
df_full = pd.read_csv('combined_monthly_data.csv', index_col=0, parse_dates=True)
ALL_DATES = df_full.index.strftime('%Y-%m').tolist()
ALL_TICKERS = df_full.columns.tolist()

def load_data(start_date=None, end_date=None):
    df = df_full.copy()
    # Don't drop NaN - we have 1371 stocks, not all have data for all dates
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
    return values

def run_balanced_strategy(df, initial_investment, rebalance_months, monthly_additional=0, weights=None):
    if weights is None:
        weights = {ticker: 0.25 for ticker in df.columns}
    
    # Normalize weights to only include non-zero allocations
    active_weights = {k: v for k, v in weights.items() if v > 0}
    if not active_weights:
        # If all weights are 0, return initial investment (no growth)
        return [initial_investment] * len(df)
    
    total_weight = sum(active_weights.values())
    debt_weight = max(0, 1.0 - total_weight)
    
    balanced = pd.DataFrame(index=df.index)
    
    # Initialize
    debt_value = initial_investment * debt_weight
    
    for i, date in enumerate(df.index):
        if i == 0:
            # Initial allocation
            for ticker in df.columns:
                if ticker in active_weights:
                    shares = (initial_investment * active_weights[ticker]) / df[ticker].iloc[i]
                    balanced.loc[date, f'{ticker}_shares'] = shares
                else:
                    balanced.loc[date, f'{ticker}_shares'] = 0
        elif i % rebalance_months == 0:
            # Rebalance
            equity_value = sum(balanced.loc[df.index[i-1], f'{ticker}_shares'] * df[ticker].iloc[i] for ticker in df.columns if f'{ticker}_shares' in balanced.columns)
            total_value = equity_value + debt_value
            
            for ticker in df.columns:
                if ticker in active_weights:
                    shares = (total_value * active_weights[ticker]) / df[ticker].iloc[i]
                    balanced.loc[date, f'{ticker}_shares'] = shares
                else:
                    balanced.loc[date, f'{ticker}_shares'] = 0
            
            debt_value = total_value * debt_weight
        else:
            # Hold shares
            for ticker in df.columns:
                balanced.loc[date, f'{ticker}_shares'] = balanced.loc[df.index[i-1], f'{ticker}_shares']
            
            # Grow debt at 3% annually (0.25% monthly)
            if debt_weight > 0:
                debt_value = debt_value * (1 + 0.03/12)
        
        # Add monthly contribution
        if i > 0 and monthly_additional > 0:
            for ticker in df.columns:
                if ticker in active_weights:
                    balanced.loc[date, f'{ticker}_shares'] += (monthly_additional * active_weights[ticker]) / df[ticker].iloc[i]
            if debt_weight > 0:
                debt_value += monthly_additional * debt_weight
        
        # Calculate total value
        equity_value = sum(balanced.loc[date, f'{ticker}_shares'] * df[ticker].iloc[i] for ticker in df.columns if f'{ticker}_shares' in balanced.columns)
        balanced.loc[date, 'total'] = equity_value + debt_value
    
    return balanced['total'].tolist()

@app.route('/')
def index():
    df = load_data()
    dates = df.index.strftime('%Y-%m').tolist()
    return render_template('index.html', 
                         min_date=dates[0],
                         max_date=dates[-1],
                         all_dates=dates)

@app.route('/custom')
def custom():
    df = load_data()
    dates = df.index.strftime('%Y-%m').tolist()
    tickers = sorted(df.columns.tolist())
    return render_template('custom.html', 
                         min_date=dates[0],
                         max_date=dates[-1],
                         all_dates=dates,
                         tickers=tickers)

def calculate_xirr(df, initial_investment, monthly_additional):
    dates = []
    amounts = []
    
    # Initial investment (negative = outflow)
    dates.append(df.index[0])
    amounts.append(-initial_investment)
    
    # Monthly contributions
    for i in range(1, len(df)):
        if monthly_additional > 0:
            dates.append(df.index[i])
            amounts.append(-monthly_additional)
    
    # Final value (positive = inflow)
    dates.append(df.index[-1])
    amounts.append(df.iloc[-1])
    
    try:
        return xirr(dates, amounts) * 100  # Convert to percentage
    except:
        return None

@app.route('/calculate', methods=['POST'])
def calculate():
    data = request.json
    initial = data['initial']
    monthly = data['monthly']
    rebalance = data['rebalance']
    start = data.get('start_date')
    end = data.get('end_date')
    weights = data.get('weights', {})
    
    df = load_data(start, end)
    
    # Separate active tickers (weight > 0) from comparison tickers (weight = 0)
    active_tickers = [ticker for ticker, weight in weights.items() if weight > 0]
    comparison_tickers = [ticker for ticker, weight in weights.items() if weight == 0]
    
    # Filter df to include both active and comparison tickers
    all_tickers = active_tickers + comparison_tickers
    df_filtered = df[all_tickers].dropna(subset=all_tickers, how='any')
    
    # Update dates to match filtered data
    dates = df_filtered.index.strftime('%Y-%m-%d').tolist()
    
    if len(df_filtered) == 0:
        return jsonify({'dates': [], 'results': {}, 'error': 'No overlapping data for selected stocks'})
    
    print(f"\n=== DEBUG ===")
    print(f"Date range: {df_filtered.index[0]} to {df_filtered.index[-1]}")
    print(f"Total months: {len(df_filtered)}")
    print(f"Active stocks: {active_tickers}")
    print(f"Comparison stocks: {comparison_tickers}")
    print(f"Initial investment: ${initial}")
    
    results = {}
    
    # Calculate for active tickers
    for ticker in active_tickers:
        values = run_individual_strategy(df_filtered, ticker, initial, monthly)
        print(f"\n{ticker}:")
        print(f"  First value: ${values[0]:,.2f}")
        print(f"  Last value: ${values[-1]:,.2f}")
        print(f"  Return: {(values[-1] / initial - 1) * 100:.2f}%")
        
        series = pd.Series(values, index=df_filtered.index)
        xirr_val = calculate_xirr(series, initial, monthly)
        results[ticker] = {
            'values': values,
            'final': values[-1],
            'return': (values[-1] / initial - 1) * 100,
            'xirr': xirr_val
        }
    
    # Calculate for comparison tickers
    for ticker in comparison_tickers:
        values = run_individual_strategy(df_filtered, ticker, initial, monthly)
        series = pd.Series(values, index=df_filtered.index)
        xirr_val = calculate_xirr(series, initial, monthly)
        results[ticker] = {
            'values': values,
            'final': values[-1],
            'return': (values[-1] / initial - 1) * 100,
            'xirr': xirr_val
        }
    
    # Convert weights from percentages to decimals (only for active tickers)
    weight_dict = {k: v/100 for k, v in weights.items() if v > 0}
    
    # Only calculate balanced if there are active tickers
    if active_tickers:
        balanced_values = run_balanced_strategy(df_filtered[active_tickers], initial, rebalance, monthly, weight_dict)
        balanced_series = pd.Series(balanced_values, index=df_filtered.index)
        xirr_val = calculate_xirr(balanced_series, initial, monthly)
        results['Balanced'] = {
            'values': balanced_values,
            'final': balanced_values[-1],
            'return': (balanced_values[-1] / initial - 1) * 100,
            'xirr': xirr_val
        }
    
    return jsonify({'dates': dates, 'results': results})

@app.route('/api/metadata')
def metadata():
    return jsonify({
        'dates': ALL_DATES,
        'tickers': ALL_TICKERS
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
