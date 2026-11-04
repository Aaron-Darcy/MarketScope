import type { TierLabel } from '../data/model';

export type Mode = 'light' | 'dark';

export interface ChartTheme {
  readonly mode: Mode;
  readonly surface: string;
  readonly ink: string;
  readonly secondary: string;
  readonly muted: string;
  readonly grid: string;
  readonly axis: string;
  readonly blue: string;
  readonly orange: string;
  readonly aqua: string;
  readonly grey: string;
  readonly wash: string;
  readonly sequential: readonly [string, string];
  readonly tiers: Readonly<Record<TierLabel, string>>;
}

// The reference categorical palette's first three slots, the only ones that stay
// distinguishable to colour-blind readers in every pairing, so a scatter may use all three.
// Dark mode takes the same hues stepped for the dark surface rather than an inversion.
export const THEMES: Readonly<Record<Mode, ChartTheme>> = {
  light: {
    mode: 'light',
    surface: '#ffffff',
    ink: '#0b0b0b',
    secondary: '#52514e',
    muted: '#898781',
    grid: '#e9e8e3',
    axis: '#c3c2b7',
    blue: '#2a78d6',
    orange: '#eb6834',
    aqua: '#1baf7a',
    grey: '#b4b2ab',
    wash: 'rgba(42, 120, 214, 0.12)',
    sequential: ['#eef4fc', '#104281'],
    // Ordinal: more ink for a more precise tier. Tier X, a failed reconstruction, is the
    // second categorical hue so it reads as a different kind of thing, not a fourth step.
    tiers: {
      'Tier 1': '#104281',
      'Tier 2': '#2a78d6',
      'Tier 3': '#86b6ef',
      'Tier X': '#eb6834',
      'Balance only': '#dddcd6',
    },
  },
  dark: {
    mode: 'dark',
    surface: '#15181d',
    ink: '#f0efec',
    secondary: '#c3c2b7',
    muted: '#898781',
    grid: '#2a2d33',
    axis: '#3b3f46',
    blue: '#3987e5',
    orange: '#d95926',
    aqua: '#199e70',
    grey: '#6b6a64',
    wash: 'rgba(57, 135, 229, 0.18)',
    sequential: ['#1b2533', '#86b6ef'],
    tiers: {
      'Tier 1': '#9ec5f4',
      'Tier 2': '#3987e5',
      'Tier 3': '#184f95',
      'Tier X': '#d95926',
      'Balance only': '#383835',
    },
  },
};

export const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
