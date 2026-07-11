import { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useLocalStorage } from '../hooks/useLocalStorage';
import CustomDropdown from './CustomDropdown';

export default function CustomPortfolio({ allDates, allTickers }) {
  const [state, setState] = useLocalStorage('customPortfolio', {
    initial: 10000,
    monthly: 0,
    rebalance: 6,
    startIdx: 0,
    endIdx: allDates.length - 1,
    stocks: [],
    weights: {},
    compareSpy: false,
    compareQqq: false,
    customCompare: ''
  });

  const [search, setSearch] = useState('');
  const [results, setResults] = useState(null);
  const [startYear, setStartYear] = useState(allDates[state.startIdx].split('-')[0]);
  const [endYear, setEndYear] = useState(allDates[state.endIdx].split('-')[0]);

  useEffect(() => {
    setStartYear(allDates[state.startIdx].split('-')[0]);
  }, [state.startIdx, allDates]);

  useEffect(() => {
    setEndYear(allDates[state.endIdx].split('-')[0]);
  }, [state.endIdx, allDates]);

  useEffect(() => {
    if (state.stocks.length > 0) fetchResults();
  }, [state]);

  const fetchResults = async () => {
    const weights = { ...state.weights };
    if (state.compareSpy) weights.SPY = 0;
    if (state.compareQqq) weights.QQQ = 0;
    if (state.customCompare && allTickers.includes(state.customCompare.toUpperCase())) {
      weights[state.customCompare.toUpperCase()] = 0;
    }

    const res = await fetch('http://127.0.0.1:5000/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        initial: state.initial,
        monthly: state.monthly,
        rebalance: state.rebalance,
        start_date: allDates[state.startIdx] + '-01',
        end_date: allDates[state.endIdx] + '-01',
        weights
      })
    });
    const data = await res.json();
    setResults(data);
  };

  const updateState = (updates) => setState({ ...state, ...updates });
  
  const addStock = (ticker) => {
    if (state.stocks.length >= 10 || state.stocks.includes(ticker)) return;
    const newStocks = [...state.stocks, ticker];
    const equalWeight = Math.floor(100 / newStocks.length);
    const newWeights = Object.fromEntries(newStocks.map(t => [t, equalWeight]));
    setState({ ...state, stocks: newStocks, weights: newWeights });
    setSearch('');
  };

  const removeStock = (ticker) => {
    const newStocks = state.stocks.filter(t => t !== ticker);
    const newWeights = { ...state.weights };
    delete newWeights[ticker];
    setState({ ...state, stocks: newStocks, weights: newWeights });
  };

  const updateWeight = (ticker, value) => 
    setState({ ...state, weights: { ...state.weights, [ticker]: value } });

  const total = Object.values(state.weights).reduce((a, b) => a + b, 0);
  const debt = Math.max(0, 100 - total);

  const filtered = search ? allTickers.filter(t => t.includes(search.toUpperCase())).slice(0, 20) : [];

  const reset = () => {
    setState({
      initial: 10000,
      monthly: 0,
      rebalance: 6,
      startIdx: 0,
      endIdx: allDates.length - 1,
      stocks: [],
      weights: {},
      compareSpy: false,
      compareQqq: false,
      customCompare: ''
    });
  };

  const chartData = results ? results.dates.map((date, i) => {
    const point = { date };
    Object.entries(results.results).forEach(([name, data]) => {
      point[name] = data.values[i];
    });
    return point;
  }) : [];

  const colors = ['#2196F3', '#4CAF50', '#FF9800', '#F44336', '#9C27B0'];

  const yearlyData = results ? (() => {
    const compareNames = ['Balanced', 'SPY', 'QQQ', 'GOLD'];
    const yearlyReturns = {};
    
    results.dates.forEach((date, i) => {
      const year = date.substring(0, 4);
      if (!yearlyReturns[year]) yearlyReturns[year] = {};
      
      compareNames.forEach(name => {
        if (results.results[name]) {
          const values = results.results[name].values;
          if (i === 0 || date.substring(0, 4) !== results.dates[i-1].substring(0, 4)) {
            yearlyReturns[year][`${name}_start`] = values[i];
          }
          yearlyReturns[year][`${name}_end`] = values[i];
        }
      });
    });
    
    return Object.entries(yearlyReturns).map(([year, data]) => {
      const point = { year };
      compareNames.forEach(name => {
        if (data[`${name}_start`] && data[`${name}_end`]) {
          point[name] = ((data[`${name}_end`] - data[`${name}_start`]) / data[`${name}_start`] * 100).toFixed(1);
        }
      });
      return point;
    });
  })() : [];

  return (
    <div style={{ display: 'flex', height: '100vh' }}>
      <div style={{ width: 320, background: 'white', padding: 20, overflowY: 'auto', boxShadow: '2px 0 10px rgba(0,0,0,0.1)' }}>
        <a href="/" style={{ display: 'inline-block', padding: '8px 15px', background: '#2196F3', color: 'white', textDecoration: 'none', borderRadius: 4, fontSize: 12, marginBottom: 15 }}>← Back to Default</a>
        <h1 style={{ fontSize: 20, marginBottom: 20 }}>📊 Custom Portfolio</h1>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Add Stock (Max 10)</label>
          <input 
            type="text" 
            placeholder="Search stocks..." 
            value={search} 
            onChange={e => setSearch(e.target.value)}
            style={{ width: '100%', padding: 8, border: '1px solid #ddd', borderRadius: 4, fontSize: 13, marginBottom: 5 }}
          />
          {filtered.length > 0 && (
            <div style={{ border: '1px solid #ddd', borderRadius: 4, maxHeight: 200, overflowY: 'auto' }}>
              {filtered.map(ticker => (
                <div 
                  key={ticker} 
                  onClick={() => addStock(ticker)}
                  style={{ padding: '8px 12px', cursor: 'pointer', fontSize: 13, borderBottom: '1px solid #f0f0f0' }}
                  onMouseEnter={e => e.target.style.background = '#f5f5f5'}
                  onMouseLeave={e => e.target.style.background = 'white'}
                >
                  {ticker}
                </div>
              ))}
            </div>
          )}
          {state.stocks.length >= 10 && <div style={{ color: '#ff9800', fontSize: 11, marginTop: 5 }}>Maximum 10 stocks allowed</div>}
        </div>

        <hr style={{ margin: '15px 0', border: '1px solid #e0e0e0' }} />
        <h3 style={{ fontSize: 14, margin: '15px 0 10px 0', color: '#666' }}>Selected Stocks</h3>
        {state.stocks.length === 0 ? (
          <p style={{ color: '#999', fontSize: 12 }}>No stocks selected</p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {state.stocks.map(ticker => (
              <div key={ticker} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white', borderRadius: 6, fontSize: 13, fontWeight: 500, boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
                <span>{ticker}</span>
                <button onClick={() => removeStock(ticker)} style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', cursor: 'pointer', fontSize: 18, lineHeight: 1, padding: '2px 6px', borderRadius: 3, fontWeight: 'bold', transition: 'background 0.2s' }} onMouseOver={e => e.target.style.background = 'rgba(255,255,255,0.3)'} onMouseOut={e => e.target.style.background = 'rgba(255,255,255,0.2)'}>×</button>
              </div>
            ))}
          </div>
        )}

        <hr style={{ margin: '15px 0', border: '1px solid #e0e0e0' }} />
        <h3 style={{ fontSize: 14, margin: '15px 0 10px 0', color: '#666' }}>Comparisons</h3>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', margin: '12px 0' }}>
          <label style={{ fontSize: 13 }}>
            <input type="checkbox" checked={state.compareSpy} onChange={e => updateState({ compareSpy: e.target.checked })} /> SPY
          </label>
          <label style={{ fontSize: 13 }}>
            <input type="checkbox" checked={state.compareQqq} onChange={e => updateState({ compareQqq: e.target.checked })} /> QQQ
          </label>
          <input 
            type="text" 
            placeholder="Custom" 
            value={state.customCompare} 
            onChange={e => updateState({ customCompare: e.target.value.toUpperCase() })}
            style={{ width: 80, padding: '4px 8px', border: '1px solid #ddd', borderRadius: 4, fontSize: 12 }}
          />
        </div>
        {state.customCompare && !allTickers.includes(state.customCompare) && (
          <span style={{ fontSize: 11, color: '#f44336', display: 'block', marginTop: -8 }}>Ticker not found</span>
        )}

        <hr style={{ margin: '15px 0', border: '1px solid #e0e0e0' }} />

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Initial Investment</label>
          <input type="number" min="0" max="10000000" value={state.initial} onChange={e => updateState({ initial: +e.target.value })} style={{ width: '100%', padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, outline: 'none' }} />
        </div>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Recurring Investment</label>
          <input type="number" min="0" max="10000" value={state.monthly} onChange={e => updateState({ monthly: +e.target.value })} style={{ width: '100%', padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, outline: 'none' }} />
        </div>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Rebalance Frequency (months)</label>
          <CustomDropdown 
            value={state.rebalance}
            options={[1,2,3,4,5,6,7,8,9,10,11,12].map(n => ({ value: n, label: n.toString() }))}
            onChange={n => updateState({ rebalance: n })}
          />
        </div>

        <hr style={{ margin: '15px 0', border: '1px solid #e0e0e0' }} />
        <h3 style={{ fontSize: 14, margin: '15px 0 10px 0', color: '#666' }}>Allocation <span style={{ color: total === 100 ? '#4CAF50' : total > 100 ? '#f44336' : '#ff9800' }}>({total}%)</span></h3>

        {state.stocks.map(ticker => (
          <div key={ticker} style={{ margin: '12px 0' }}>
            <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>{ticker} %</label>
            <input type="range" min="0" max="100" step="1" value={state.weights[ticker] || 0} onChange={e => updateWeight(ticker, +e.target.value)} style={{ width: '100%' }} />
            <span style={{ fontWeight: 'bold', color: '#2196F3', fontSize: 14 }}>{state.weights[ticker] || 0}%</span>
          </div>
        ))}

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Debt (3% growth)</label>
          <span style={{ fontWeight: 'bold', color: '#ff9800', fontSize: 14 }}>{debt}%</span>
        </div>

        <hr style={{ margin: '15px 0', border: '1px solid #e0e0e0' }} />

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Start Month</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <CustomDropdown 
              value={allDates[state.startIdx].split('-')[1]}
              options={['01','02','03','04','05','06','07','08','09','10','11','12'].map((m, i) => ({ value: m, label: ['January','February','March','April','May','June','July','August','September','October','November','December'][i] }))}
              onChange={m => { const [year] = allDates[state.startIdx].split('-'); const idx = allDates.indexOf(`${year}-${m}`); if (idx !== -1) updateState({ startIdx: idx }); }}
              style={{ flex: 1 }}
            />
            <input 
              type="number" 
              min="1980" 
              max="2026" 
              value={startYear} 
              onChange={e => { 
                setStartYear(e.target.value);
                if (e.target.value.length === 4) {
                  const [, month] = allDates[state.startIdx].split('-'); 
                  const idx = allDates.indexOf(`${e.target.value}-${month}`); 
                  if (idx !== -1) updateState({ startIdx: idx }); 
                }
              }}
              style={{ flex: 1, padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', fontWeight: '500', outline: 'none' }}
            />
          </div>
        </div>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>End Month</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <CustomDropdown 
              value={allDates[state.endIdx].split('-')[1]}
              options={['01','02','03','04','05','06','07','08','09','10','11','12'].map((m, i) => ({ value: m, label: ['January','February','March','April','May','June','July','August','September','October','November','December'][i] }))}
              onChange={m => { const [year] = allDates[state.endIdx].split('-'); const idx = allDates.indexOf(`${year}-${m}`); if (idx !== -1) updateState({ endIdx: idx }); }}
              style={{ flex: 1 }}
            />
            <input 
              type="number" 
              min="1980" 
              max="2026" 
              value={endYear} 
              onChange={e => { 
                setEndYear(e.target.value);
                if (e.target.value.length === 4) {
                  const [, month] = allDates[state.endIdx].split('-'); 
                  const idx = allDates.indexOf(`${e.target.value}-${month}`); 
                  if (idx !== -1) updateState({ endIdx: idx }); 
                }
              }}
              style={{ flex: 1, padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', fontWeight: '500', outline: 'none' }}
            />
          </div>
        </div>

        <button onClick={reset} style={{ width: '100%', padding: 10, background: '#f44336', color: 'white', border: 'none', borderRadius: 5, cursor: 'pointer', fontSize: 13, marginTop: 15, fontWeight: 500 }}>Reset All</button>
      </div>

      <div style={{ flex: 1, padding: 30, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
        {state.stocks.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', fontSize: 18, color: '#999' }}>
            Select stocks to begin
          </div>
        ) : (
          <>
            {results && (
              <table style={{ marginBottom: 20, borderCollapse: 'collapse', fontSize: 13, alignSelf: 'flex-start' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #ddd' }}>
                    <th style={{ padding: '8px 12px', textAlign: 'left' }}>Portfolio</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Final Value</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Return %</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>XIRR %</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Max DD %</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(results.results)
                    .filter(([name]) => {
                      if (!state.compareSpy && !state.compareQqq && !state.customCompare) return true;
                      return name === 'Balanced' || name === 'SPY' || name === 'QQQ' || name === state.customCompare;
                    })
                    .sort(([, a], [, b]) => b.return - a.return)
                    .map(([name, data], i) => {
                      const maxDD = (() => {
                        let peak = data.values[0];
                        let maxDrawdown = 0;
                        data.values.forEach(val => {
                          if (val > peak) peak = val;
                          const dd = ((peak - val) / peak) * 100;
                          if (dd > maxDrawdown) maxDrawdown = dd;
                        });
                        return maxDrawdown;
                      })();
                      
                      return (
                      <tr key={name} style={{ borderBottom: '1px solid #eee' }}>
                        <td style={{ padding: '8px 12px', display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ width: 12, height: 12, backgroundColor: name === 'Balanced' ? '#FF6B35' : colors[Object.keys(results.results).indexOf(name) % colors.length], borderRadius: 2 }}></span>
                          {name}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 500 }}>${Math.round(data.final).toLocaleString()}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 500, color: '#4CAF50' }}>{data.return.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1})}%</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>{data.xirr ? `${data.xirr.toFixed(2)}%` : '-'}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', color: '#f44336' }}>-{maxDD.toFixed(1)}%</td>
                      </tr>
                      );
                    })}
                </tbody>
              </table>
            )}

            <ResponsiveContainer width="100%" height={600}>
              <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <defs>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                    <feMerge>
                      <feMergeNode in="coloredBlur"/>
                      <feMergeNode in="SourceGraphic"/>
                    </feMerge>
                  </filter>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis 
                  dataKey="date" 
                  tickFormatter={(date) => {
                    const [year, month] = date.split('-');
                    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                    return `${months[parseInt(month) - 1]} '${year.slice(2)}`;
                  }}
                />
                <YAxis tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(value) => `$${Math.round(value).toLocaleString()}`} />
                {results && Object.entries(results.results)
                  .filter(([name]) => {
                    if (!state.compareSpy && !state.compareQqq && !state.customCompare) return true;
                    return name === 'Balanced' || name === 'SPY' || name === 'QQQ' || name === state.customCompare;
                  })
                  .map(([name, data], i) => (
                  <Line 
                    key={name} 
                    type="monotone" 
                    dataKey={name} 
                    stroke={name === 'Balanced' ? '#FF6B35' : colors[i % colors.length]} 
                    strokeWidth={name === 'Balanced' ? 4 : 2}
                    dot={false}
                    filter={name === 'Balanced' ? 'url(#glow)' : undefined}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>

            {results && (
              <>
                <h2 style={{ marginTop: 40, marginBottom: 20 }}>Yearly Returns Comparison</h2>
                <ResponsiveContainer width="100%" height={400}>
                  <BarChart data={yearlyData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="year" />
                    <YAxis label={{ value: 'Return %', angle: -90, position: 'insideLeft' }} />
                    <Tooltip formatter={(value) => `${value}%`} />
                    <Legend />
                    <Bar dataKey="Balanced" fill="#FF6B35" />
                    <Bar dataKey="SPY" fill="#2196F3" />
                    <Bar dataKey="QQQ" fill="#4CAF50" />
                    <Bar dataKey="GOLD" fill="#FF9800" />
                  </BarChart>
                </ResponsiveContainer>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
