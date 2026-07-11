import { useState, useEffect, useRef } from 'react';

export default function CustomDropdown({ value, options, onChange, style = {} }) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const dropdownRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
        setSearchTerm('');
        setHighlightedIndex(-1);
      }
    };

    const handleKeyDown = (event) => {
      const filtered = searchTerm 
        ? options.filter(opt => opt.label.toLowerCase().includes(searchTerm.toLowerCase()))
        : options;

      if (event.key === 'ArrowDown') {
        event.preventDefault();
        event.stopPropagation();
        setHighlightedIndex(prev => {
          const next = prev < filtered.length - 1 ? prev + 1 : prev;
          return next;
        });
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        event.stopPropagation();
        setHighlightedIndex(prev => prev > 0 ? prev - 1 : 0);
      } else if (event.key === 'Enter') {
        event.preventDefault();
        event.stopPropagation();
        if (highlightedIndex >= 0 && filtered[highlightedIndex]) {
          onChange(filtered[highlightedIndex].value);
          setIsOpen(false);
          setSearchTerm('');
          setHighlightedIndex(-1);
        }
      } else if (event.key === 'Escape') {
        event.preventDefault();
        setIsOpen(false);
        setSearchTerm('');
        setHighlightedIndex(-1);
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        setSearchTerm(prev => prev + event.key);
        setHighlightedIndex(0);
      } else if (event.key === 'Backspace') {
        event.preventDefault();
        setSearchTerm(prev => prev.slice(0, -1));
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown, true);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown, true);
    };
  }, [isOpen, searchTerm, highlightedIndex, options, onChange]);

  const handleKeyDown = (e) => {
    if (!isOpen) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    const filtered = options.filter(opt => 
      opt.label.toLowerCase().includes(searchTerm.toLowerCase())
    );

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex(prev => Math.min(prev + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (highlightedIndex >= 0 && filtered[highlightedIndex]) {
        onChange(filtered[highlightedIndex].value);
        setIsOpen(false);
        setSearchTerm('');
        setHighlightedIndex(-1);
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false);
      setSearchTerm('');
      setHighlightedIndex(-1);
    } else if (e.key.length === 1) {
      setSearchTerm(prev => prev + e.key);
    } else if (e.key === 'Backspace') {
      setSearchTerm(prev => prev.slice(0, -1));
    }
  };

  const filteredOptions = searchTerm 
    ? options.filter(opt => opt.label.toLowerCase().includes(searchTerm.toLowerCase()))
    : options;

  return (
    <div ref={dropdownRef} style={{ position: 'relative', ...style }}>
      <button 
        onClick={() => setIsOpen(!isOpen)} 
        style={{ 
          width: '100%', 
          padding: '10px 12px', 
          paddingRight: '36px', 
          border: '2px solid #e0e0e0', 
          borderRadius: 6, 
          fontSize: 13, 
          backgroundColor: '#f8f9fa', 
          cursor: 'pointer', 
          fontWeight: '500', 
          outline: 'none', 
          textAlign: 'left' 
        }}
      >
        {options.find(opt => opt.value === value)?.label || value}
      </button>
      <svg 
        width="12" 
        height="12" 
        viewBox="0 0 12 12" 
        style={{ 
          position: 'absolute', 
          right: '12px', 
          top: '50%', 
          transform: isOpen ? 'translateY(-50%) rotate(180deg)' : 'translateY(-50%)', 
          pointerEvents: 'none', 
          transition: 'transform 0.2s' 
        }}
      >
        <path fill="#666" d="M6 9L1 4h10z"/>
      </svg>
      {isOpen && (
        <div 
          style={{ 
            position: 'absolute', 
            top: '100%', 
            left: 0, 
            right: 0, 
            marginTop: '4px', 
            background: 'white', 
            border: '1px solid #e0e0e0', 
            borderRadius: 8, 
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)', 
            maxHeight: '300px', 
            overflowY: 'auto', 
            zIndex: 1000 
          }}
        >
          {searchTerm && (
            <div style={{ padding: '8px 16px', fontSize: 11, color: '#999', borderBottom: '1px solid #f0f0f0' }}>
              Searching: {searchTerm}
            </div>
          )}
          {filteredOptions.map((opt, idx) => (
            <div 
              key={opt.value} 
              onClick={() => { 
                onChange(opt.value); 
                setIsOpen(false); 
                setSearchTerm('');
                setHighlightedIndex(-1);
              }} 
              style={{ 
                padding: '10px 16px', 
                cursor: 'pointer', 
                fontSize: 13, 
                fontWeight: value === opt.value ? '500' : '400', 
                background: idx === highlightedIndex ? '#e3f2fd' : (value === opt.value ? '#f0f0f0' : 'transparent')
              }} 
              onMouseEnter={e => { 
                setHighlightedIndex(idx);
                e.currentTarget.style.background = '#f8f9fa';
              }} 
              onMouseLeave={e => { 
                e.currentTarget.style.background = idx === highlightedIndex ? '#e3f2fd' : (value === opt.value ? '#f0f0f0' : 'transparent');
              }}
            >
              {opt.label}
            </div>
          ))}
          {filteredOptions.length === 0 && (
            <div style={{ padding: '10px 16px', fontSize: 13, color: '#999', textAlign: 'center' }}>
              No matches
            </div>
          )}
        </div>
      )}
    </div>
  );
}
