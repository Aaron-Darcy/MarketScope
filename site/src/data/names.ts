// Registrant names whose stem would read wrongly once corporate words are removed.
const OVERRIDES: Readonly<Record<string, string>> = {
  'SCHWAB CHARLES CORP': 'Charles Schwab',
  'E TRADE FINANCIAL CORP': 'E*TRADE',
};

const WORD_CASE: Readonly<Record<string, string>> = {
  JPMORGAN: 'JPMorgan',
  PACWEST: 'PacWest',
  SUNTRUST: 'SunTrust',
  KEYCORP: 'KeyCorp',
  'CULLEN/FROST': 'Cullen/Frost',
  'M&T': 'M&T',
  US: 'U.S.',
};

const ACRONYMS = new Set(['PNC', 'BOK', 'CIT', 'SVB', 'HSBC', 'USA', 'BBVA', 'MUFG']);

function titleWord(word: string): string {
  const upper = word.toUpperCase();
  const fixed = WORD_CASE[upper];
  if (fixed !== undefined) return fixed;
  if (ACRONYMS.has(upper)) return upper;
  const lower = word.toLowerCase();
  if (lower === 'of' || lower === '&') return lower;
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/**
 * The registrant name as a reader knows the bank: the SEC's state suffix and corporate words
 * removed, and capitals only where the bank uses them.
 */
export function displayName(registrantName: string): string {
  const override = OVERRIDES[registrantName];
  if (override !== undefined) return override;

  // Two passes of corporate words, so "FINANCIAL GROUP INC" loses all three in order.
  const stem = registrantName
    .replace(/\s*[/\\][A-Za-z]{2,3}[/\\]?\s*$/, '')
    .replace(/,.*$/, '')
    .replace(/\s+(INC|CORP|CORPORATION|CO|COMPANY|GROUP|HOLDINGS)\.?$/i, '')
    .replace(
      /\s+(INC|CORP|CORPORATION|CO|COMPANY|GROUP|FINANCIAL|FINANCIAL SERVICES|BANCSHARES|BANCORPORATION)\.?$/i,
      '',
    )
    .replace(/\s*&$/, '')
    .trim();

  if (stem !== stem.toUpperCase()) return stem;
  return stem.split(' ').map(titleWord).join(' ');
}
