"""
Financial Metrics Module
=========================
XIRR calculation, max drawdown, and other portfolio metrics.
"""

from scipy.optimize import brentq


def xirr(cashflows):
    """
    Calculate the Internal Rate of Return for irregular cashflows.
    
    Args:
        cashflows: List of (date, amount) tuples. Negative = investment, positive = withdrawal.
        
    Returns:
        Annualized IRR as a decimal (e.g., 0.35 = 35%)
    """
    if not cashflows:
        return 0.0
    dates = [cf[0] for cf in cashflows]
    amounts = [cf[1] for cf in cashflows]
    d0 = dates[0]
    days = [(d - d0).days / 365.25 for d in dates]

    def npv(rate):
        return sum(amt / (1 + rate) ** t for amt, t in zip(amounts, days))

    try:
        return brentq(npv, -0.5, 10.0, maxiter=1000)
    except (ValueError, RuntimeError):
        return 0.0


def max_drawdown(values):
    """
    Calculate maximum drawdown from a series of portfolio values.
    
    Args:
        values: List of portfolio values over time
        
    Returns:
        Tuple of (max_dd_fraction, peak_index, trough_index)
    """
    peak = values[0]
    peak_idx = 0
    max_dd = 0
    max_dd_peak_idx = 0
    max_dd_trough_idx = 0
    for i, val in enumerate(values):
        if val > peak:
            peak = val
            peak_idx = i
        dd = (peak - val) / peak
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_idx = peak_idx
            max_dd_trough_idx = i
    return max_dd, max_dd_peak_idx, max_dd_trough_idx
