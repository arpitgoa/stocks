# React Portfolio Simulator

## ✅ Conversion Complete!

Your portfolio simulator has been converted from vanilla JavaScript to React.

## 🚀 Running the App

**React Frontend (Vite):**
- URL: http://localhost:5173
- Dev server with hot reload

**Flask Backend:**
- URL: http://127.0.0.1:5000
- Serves API endpoints

## 📁 Project Structure

```
/Users/ajhanwa/workspace/stocks/
├── frontend/                    # React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── DefaultPortfolio.jsx    # Default portfolio page
│   │   │   └── CustomPortfolio.jsx     # Custom portfolio page
│   │   ├── hooks/
│   │   │   └── useLocalStorage.js      # localStorage persistence hook
│   │   ├── App.jsx                     # Main app with routing
│   │   ├── main.jsx                    # Entry point
│   │   └── index.css                   # Global styles
│   └── package.json
├── app.py                       # Flask backend (updated with CORS)
└── combined_monthly_data.csv    # Stock data
```

## 🎯 Key Improvements

### Before (Vanilla JS):
- ~500+ lines per page
- Manual DOM manipulation
- Repetitive `getElementById` calls
- Manual state sync with localStorage
- Hard to maintain and extend

### After (React):
- ~200 lines per component
- Declarative UI updates
- Single `setState()` updates everything
- Auto-save with `useLocalStorage` hook
- Easy to add features

## 🔧 Features Preserved

✅ Default portfolio (BRKB, GOLD, QQQ, SPY)
✅ Custom portfolio (search & select up to 10 stocks)
✅ Compare to SPY/QQQ benchmarks
✅ All sliders (initial, monthly, rebalance, dates, weights)
✅ localStorage persistence (survives page refresh & navigation)
✅ Real-time chart updates
✅ Plotly interactive charts
✅ Responsive layout

## 📝 Code Highlights

**Auto-save state:**
```jsx
const [state, setState] = useLocalStorage('portfolio', defaultState);
// Any setState() call automatically saves to localStorage!
```

**Update any field:**
```jsx
updateState({ initial: 15000 })  // Updates initial investment
updateWeight('BRKB', 50)         // Updates BRKB allocation to 50%
```

**No more manual saveState() calls everywhere!**

## 🛠️ Development Commands

```bash
# Start React dev server
cd frontend && npm run dev

# Build for production
cd frontend && npm run build

# Preview production build
cd frontend && npm run preview
```

## 🌐 URLs

- Default Portfolio: http://localhost:5173/
- Custom Portfolio: http://localhost:5173/custom

## 📦 Dependencies Added

- `react` & `react-dom` - Core React
- `plotly.js-dist-min` - Plotly charts
- `react-plotly.js` - React wrapper for Plotly
- `flask-cors` - Enable CORS on Flask backend

## 🔄 Migration Notes

- Old HTML templates in `/templates` are no longer used
- Flask now only serves API endpoints (`/calculate`, `/api/metadata`)
- All UI rendering happens in React
- localStorage keys changed to `defaultPortfolio` and `customPortfolio`
- Users will need to reconfigure their portfolios once (old state won't migrate)

## 🎉 Next Steps

The React app is ready to use! Open http://localhost:5173 in your browser.

All your previous features work exactly the same, but the code is now:
- Cleaner
- Easier to maintain
- Easier to extend
- More performant (no unnecessary re-renders)
