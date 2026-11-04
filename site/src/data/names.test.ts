import { describe, expect, it } from 'vitest';

import { displayName } from './names';

// Every registrant in the universe with the name the Evidence site's SQL gave it, so the port
// is held to the names readers have already seen.
const EXPECTED: readonly (readonly [string, string])[] = [
  ['AMERICAN EXPRESS CO', 'American Express'],
  ['AMERIPRISE FINANCIAL INC', 'Ameriprise'],
  ['Ally Financial Inc.', 'Ally'],
  ['BANK OF AMERICA CORP /DE/', 'Bank of America'],
  ['BBVA USA Bancshares, Inc.', 'BBVA USA'],
  ['BOK FINANCIAL CORP', 'BOK'],
  ['Bank of New York Mellon Corp', 'Bank of New York Mellon'],
  ['CAPITAL ONE FINANCIAL CORP', 'Capital One'],
  ['CIT GROUP INC', 'CIT'],
  ['CITIGROUP INC', 'Citigroup'],
  ['CITIZENS FINANCIAL GROUP INC/RI', 'Citizens Financial'],
  ['COLUMBIA BANKING SYSTEM, INC.', 'Columbia Banking System'],
  ['COMERICA INC', 'Comerica'],
  ['CULLEN/FROST BANKERS, INC.', 'Cullen/Frost Bankers'],
  ['Discover Financial Services', 'Discover'],
  ['E TRADE FINANCIAL CORP', 'E*TRADE'],
  ['EAST WEST BANCORP INC', 'East West Bancorp'],
  ['FIFTH THIRD BANCORP', 'Fifth Third Bancorp'],
  ['FIRST CITIZENS BANCSHARES INC /DE/', 'First Citizens'],
  ['FIRST HORIZON CORP', 'First Horizon'],
  ['FLAGSTAR BANK, NATIONAL ASSOCIATION', 'Flagstar Bank'],
  ['GOLDMAN SACHS GROUP INC', 'Goldman Sachs'],
  ['HSBC USA INC /MD/', 'HSBC USA'],
  ['HUNTINGTON BANCSHARES INC /MD/', 'Huntington'],
  ['JPMORGAN CHASE & CO', 'JPMorgan Chase'],
  ['KEYCORP /NEW/', 'KeyCorp'],
  ['M&T BANK CORP', 'M&T Bank'],
  ['MORGAN STANLEY', 'Morgan Stanley'],
  ['MUFG Americas Holdings Corp', 'MUFG Americas Holdings'],
  ['NORTHERN TRUST CORP', 'Northern Trust'],
  ['PACWEST BANCORP', 'PacWest Bancorp'],
  ['PNC FINANCIAL SERVICES GROUP, INC.', 'PNC'],
  ['POPULAR, INC.', 'Popular'],
  ["People's United Financial, Inc.", "People's United"],
  ['RAYMOND JAMES FINANCIAL INC', 'Raymond James'],
  ['REGIONS FINANCIAL CORP', 'Regions'],
  ['SCHWAB CHARLES CORP', 'Charles Schwab'],
  ['STATE STREET CORP', 'State Street'],
  ['SUNTRUST BANKS INC', 'SunTrust Banks'],
  ['SVB FINANCIAL GROUP', 'SVB'],
  ['SYNOVUS FINANCIAL CORP', 'Synovus'],
  ['Santander Holdings USA, Inc.', 'Santander Holdings USA'],
  ['Synchrony Financial', 'Synchrony'],
  ['TRUIST FINANCIAL CORP', 'Truist'],
  ['US BANCORP \\DE\\', 'U.S. Bancorp'],
  ['VALLEY NATIONAL BANCORP', 'Valley National Bancorp'],
  ['WEBSTER FINANCIAL CORP', 'Webster'],
  ['WELLS FARGO & COMPANY/MN', 'Wells Fargo'],
  ['WESTERN ALLIANCE BANCORPORATION', 'Western Alliance'],
  ['WINTRUST FINANCIAL CORP', 'Wintrust'],
  ['ZIONS BANCORPORATION, NATIONAL ASSOCIATION /UT/', 'Zions'],
];

describe('displayName', () => {
  it.each(EXPECTED)('names %s as %s', (registrant, expected) => {
    expect(displayName(registrant)).toBe(expected);
  });
});
