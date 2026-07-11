import { useState, useEffect } from 'react';
import DefaultPortfolio from './components/DefaultPortfolio';
import CustomPortfolio from './components/CustomPortfolio';

function App() {
  const [allDates, setAllDates] = useState([]);
  const [allTickers, setAllTickers] = useState([]);
  const [page, setPage] = useState(window.location.pathname === '/custom' ? 'custom' : 'default');

  useEffect(() => {
    // Fetch metadata from Flask
    fetch('http://127.0.0.1:5000/api/metadata')
      .then(res => res.json())
      .then(data => {
        console.log('Metadata loaded:', data);
        setAllDates(data.dates);
        setAllTickers(data.tickers);
      })
      .catch(err => {
        console.error('Failed to load metadata:', err);
        alert('Failed to connect to Flask backend. Make sure Flask is running on port 5000.');
      });

    // Handle browser back/forward
    const handlePopState = () => {
      setPage(window.location.pathname === '/custom' ? 'custom' : 'default');
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (path) => {
    window.history.pushState({}, '', path);
    setPage(path === '/custom' ? 'custom' : 'default');
  };

  // Override link clicks
  useEffect(() => {
    const handleClick = (e) => {
      if (e.target.tagName === 'A' && e.target.href.startsWith(window.location.origin)) {
        e.preventDefault();
        navigate(new URL(e.target.href).pathname);
      }
    };
    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, []);

  if (allDates.length === 0) {
    return <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', fontSize: 18 }}>Loading...</div>;
  }

  return page === 'custom' 
    ? <CustomPortfolio allDates={allDates} allTickers={allTickers} />
    : <DefaultPortfolio allDates={allDates} />;
}

export default App;
