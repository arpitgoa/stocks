import { useState, useEffect, useRef } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useLocalStorage } from '../hooks/useLocalStorage';
import CustomDropdown from './CustomDropdown';

export default function DefaultPortfolio({ allDates }) {
  const [startMonthOpen, setStartMonthOpen] = useState(false);
  const [endMonthOpen, setEndMonthOpen] = useState(false);
  
  const startMonthRef = useRef(null);
  const endMonthRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (startMonthRef.current && !startMonthRef.current.contains(event.target)) {
        setStartMonthOpen(false);
      }
      if (endMonthRef.current && !endMonthRef.current.contains(event.target)) {
        setEndMonthOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  const [state, setState] = useLocalStorage('defaultPortfolio', {
    initial: 10000,
    monthly: 0,
    rebalance: 6,
    startIdx: 0,
    endIdx: allDates.length - 1,
    weights: { BRKB: 25, GOLD: 25, QQQ: 25, SPY: 25 }
  });

  const [results, setResults] = useState(null);
  const [startYear, setStartYear] = useState(allDates[0].split('-')[0]);
  const [endYear, setEndYear] = useState(allDates[allDates.length - 1].split('-')[0]);

  useEffect(() => {
    setStartYear(allDates[state.startIdx].split('-')[0]);
  }, [state.startIdx, allDates]);

  useEffect(() => {
    setEndYear(allDates[state.endIdx].split('-')[0]);
  }, [state.endIdx, allDates]);

  useEffect(() => {
    fetchResults();
  }, [state]);

  const fetchResults = async () => {
    const res = await fetch('http://127.0.0.1:5000/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        initial: state.initial,
        monthly: state.monthly,
        rebalance: state.rebalance,
        start_date: allDates[state.startIdx] + '-01',
        end_date: allDates[state.endIdx] + '-01',
        weights: state.weights
      })
    });
    const data = await res.json();
    setResults(data);
  };

  const updateState = (updates) => setState({ ...state, ...updates });
  const updateWeight = (ticker, value) => 
    setState({ ...state, weights: { ...state.weights, [ticker]: value } });

  const total = Object.values(state.weights).reduce((a, b) => a + b, 0);
  const debt = Math.max(0, 100 - total);

  const reset = () => {
    setState({
      initial: 10000,
      monthly: 0,
      rebalance: 6,
      startIdx: 0,
      endIdx: allDates.length - 1,
      weights: { BRKB: 25, GOLD: 25, QQQ: 25, SPY: 25 }
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
        <h1 style={{ fontSize: 20, marginBottom: 20 }}>📈 Portfolio Simulator</h1>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Initial Investment</label>
          <input type="number" min="0" max="10000000" value={state.initial} onChange={e => updateState({ initial: +e.target.value })} style={{ width: '100%', padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500', outline: 'none', appearance: 'none', backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12"%3E%3Cpath fill="%23666" d="M6 9L1 4h10z"/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center', paddingRight: '36px' }} />
        </div>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Recurring Investment</label>
          <input type="number" min="0" max="10000" value={state.monthly} onChange={e => updateState({ monthly: +e.target.value })} style={{ width: '100%', padding: '10px 12px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500', outline: 'none', appearance: 'none', backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12"%3E%3Cpath fill="%23666" d="M6 9L1 4h10z"/%3E%3C/svg%3E")', backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center', paddingRight: '36px' }} />
        </div>

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Rebalance Frequency (months)</label>
          <CustomDropdown 
            value={state.rebalance}
            options={[1,2,3,4,5,6,7,8,9,10,11,12].map(n => ({ value: n, label: n.toString() }))}
            onChange={n => updateState({ rebalance: n })}
          />
        </div>

        <hr style={{ margin: '20px 0', border: '1px solid #ddd' }} />
        <h3 style={{ fontSize: 16, marginBottom: 15 }}>Balanced Portfolio Allocation <span style={{ color: total === 100 ? '#4CAF50' : total > 100 ? '#f44336' : '#ff9800' }}>({total}%)</span></h3>

        {['BRKB', 'GOLD', 'QQQ', 'SPY'].map(ticker => (
          <div key={ticker} style={{ margin: '12px 0' }}>
            <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>{ticker} %</label>
            <input type="range" min="0" max="100" step="1" value={state.weights[ticker]} onChange={e => updateWeight(ticker, +e.target.value)} style={{ width: '100%' }} />
            <span style={{ fontWeight: 'bold', color: '#2196F3', fontSize: 14 }}>{state.weights[ticker]}%</span>
          </div>
        ))}

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Debt (3% growth)</label>
          <span style={{ fontWeight: 'bold', color: '#ff9800', fontSize: 14 }}>{debt}%</span>
        </div>

        <hr style={{ margin: '20px 0', border: '1px solid #ddd' }} />

        <div style={{ margin: '12px 0' }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 13, marginBottom: 3 }}>Start Month</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <div ref={startMonthRef} style={{ position: 'relative', flex: 1 }}>
              <button onClick={() => { setStartMonthOpen(!startMonthOpen); }} style={{ width: '100%', padding: '10px 12px', paddingRight: '36px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', cursor: 'pointer', fontWeight: '500', outline: 'none', textAlign: 'left' }}>
                {['January','February','March','April','May','June','July','August','September','October','November','December'][parseInt(allDates[state.startIdx].split('-')[1])-1]}
              </button>
              <svg width="12" height="12" viewBox="0 0 12 12" style={{ position: 'absolute', right: '12px', top: '50%', transform: startMonthOpen ? 'translateY(-50%) rotate(180deg)' : 'translateY(-50%)', pointerEvents: 'none', transition: 'transform 0.2s' }}>
                <path fill="#666" d="M6 9L1 4h10z"/>
              </svg>
              {startMonthOpen && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '4px', background: 'white', border: '1px solid #e0e0e0', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: '300px', overflowY: 'auto', zIndex: 1000 }}>
                  {['01','02','03','04','05','06','07','08','09','10','11','12'].map((m, i) => (
                    <div key={m} onClick={() => { const [year] = allDates[state.startIdx].split('-'); const newDate = `${year}-${m}`; const idx = allDates.indexOf(newDate); if (idx !== -1) updateState({ startIdx: idx }); setStartMonthOpen(false); }} style={{ padding: '10px 16px', cursor: 'pointer', fontSize: 13, fontWeight: allDates[state.startIdx].split('-')[1] === m ? '500' : '400', background: allDates[state.startIdx].split('-')[1] === m ? '#f0f0f0' : 'transparent' }} onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'} onMouseLeave={e => e.currentTarget.style.background = allDates[state.startIdx].split('-')[1] === m ? '#f0f0f0' : 'transparent'}>
                      {['January','February','March','April','May','June','July','August','September','October','November','December'][i]}
                    </div>
                  ))}
                </div>
              )}
            </div>
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
            <div ref={endMonthRef} style={{ position: 'relative', flex: 1 }}>
              <button onClick={() => { setEndMonthOpen(!endMonthOpen); }} style={{ width: '100%', padding: '10px 12px', paddingRight: '36px', border: '2px solid #e0e0e0', borderRadius: 6, fontSize: 13, backgroundColor: '#f8f9fa', cursor: 'pointer', fontWeight: '500', outline: 'none', textAlign: 'left' }}>
                {['January','February','March','April','May','June','July','August','September','October','November','December'][parseInt(allDates[state.endIdx].split('-')[1])-1]}
              </button>
              <svg width="12" height="12" viewBox="0 0 12 12" style={{ position: 'absolute', right: '12px', top: '50%', transform: endMonthOpen ? 'translateY(-50%) rotate(180deg)' : 'translateY(-50%)', pointerEvents: 'none', transition: 'transform 0.2s' }}>
                <path fill="#666" d="M6 9L1 4h10z"/>
              </svg>
              {endMonthOpen && (
                <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: '4px', background: 'white', border: '1px solid #e0e0e0', borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.1)', maxHeight: '300px', overflowY: 'auto', zIndex: 1000 }}>
                  {['01','02','03','04','05','06','07','08','09','10','11','12'].map((m, i) => (
                    <div key={m} onClick={() => { const [year] = allDates[state.endIdx].split('-'); const newDate = `${year}-${m}`; const idx = allDates.indexOf(newDate); if (idx !== -1) updateState({ endIdx: idx }); setEndMonthOpen(false); }} style={{ padding: '10px 16px', cursor: 'pointer', fontSize: 13, fontWeight: allDates[state.endIdx].split('-')[1] === m ? '500' : '400', background: allDates[state.endIdx].split('-')[1] === m ? '#f0f0f0' : 'transparent' }} onMouseEnter={e => e.currentTarget.style.background = '#f8f9fa'} onMouseLeave={e => e.currentTarget.style.background = allDates[state.endIdx].split('-')[1] === m ? '#f0f0f0' : 'transparent'}>
                      {['January','February','March','April','May','June','July','August','September','October','November','December'][i]}
                    </div>
                  ))}
                </div>
              )}
            </div>
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

        <a href="/custom" style={{ display: 'inline-block', width: '100%', padding: '10px 15px', background: '#4CAF50', color: 'white', textDecoration: 'none', borderRadius: 5, fontSize: 13, marginTop: 15, fontWeight: 500, textAlign: 'center', boxSizing: 'border-box' }}>→ Custom Stocks</a>

        <button onClick={reset} style={{ width: '100%', padding: 10, background: '#f44336', color: 'white', border: 'none', borderRadius: 5, cursor: 'pointer', transition: 'all 0.2s', fontWeight: '500', fontSize: 13, marginTop: 10, fontWeight: 500 }}>Reset All</button>
      </div>

      <div style={{ flex: 1, padding: 30, display: 'flex', flexDirection: 'column', overflowY: 'auto' }}>
        <h2 style={{ marginBottom: 20 }}>Portfolio Performance</h2>
        
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
            {results && Object.entries(results.results).map(([name, data], i) => (
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
      </div>
    </div>
  );
}
