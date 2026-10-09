import React, { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

export const ThemeToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('vaultrag_theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('vaultrag_theme', theme);
  }, [theme]);

  const toggle = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  };

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      className={`flex items-center gap-2 rounded-btn px-2.5 py-1.5 text-sm text-text-muted transition-colors hover:bg-surface-raised hover:text-text ${className}`}
    >
      {theme === 'dark' ? (
        <>
          <Sun size={16} aria-hidden="true" className="text-warning" />
          <span>Light theme</span>
        </>
      ) : (
        <>
          <Moon size={16} aria-hidden="true" className="text-accent" />
          <span>Dark theme</span>
        </>
      )}
    </button>
  );
};
