import {
  createContext,
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { THEMES, type ChartTheme, type Mode } from '../charts/theme';

const STORAGE_KEY = 'marketscope-theme';

interface ThemeState {
  readonly mode: Mode;
  readonly toggle: () => void;
}

const ThemeContext = createContext<ThemeState | null>(null);

function initialMode(): Mode {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { readonly children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(initialMode);

  useEffect(() => {
    document.documentElement.dataset.theme = mode;
  }, [mode]);

  const toggle = useCallback(() => {
    setMode((current) => {
      const next = current === 'light' ? 'dark' : 'light';
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const value = useMemo(() => ({ mode, toggle }), [mode, toggle]);
  return <ThemeContext value={value}>{children}</ThemeContext>;
}

export function useThemeMode(): ThemeState {
  const state = use(ThemeContext);
  if (!state) throw new Error('useThemeMode is used outside ThemeProvider');
  return state;
}

export function useChartTheme(): ChartTheme {
  return THEMES[useThemeMode().mode];
}
