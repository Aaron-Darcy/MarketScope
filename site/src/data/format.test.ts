import { describe, expect, it } from 'vitest';

import { dollars, longDate, percent, pValue, quarterLabel, signed } from './format';

describe('formatting', () => {
  it('signs correlations with a true minus', () => {
    expect(signed(0.59)).toBe('+0.59');
    expect(signed(-0.356, 3)).toBe('−0.356');
  });

  it('reads fractions as percentages and nulls as a dash', () => {
    expect(percent(0.0533, 2)).toBe('5.33%');
    expect(percent(null)).toBe('–');
  });

  it('labels quarters and dates', () => {
    expect(quarterLabel('2022-03-31')).toBe('2022Q1');
    expect(quarterLabel('2023-12-31')).toBe('2023Q4');
    expect(longDate('2023-03-10')).toBe('10 March 2023');
    expect(() => longDate('2023-13-01')).toThrow(RangeError);
  });

  it('scales dollars', () => {
    expect(dollars(2.1e12)).toBe('$2.10tn');
    expect(dollars(4.12e11)).toBe('$412bn');
    expect(dollars(3.8e10)).toBe('$38.0bn');
  });

  it('shows small p-values to their first significant digits', () => {
    expect(pValue(0.002)).toBe('0.0020');
    expect(pValue(0.0412)).toBe('0.041');
  });
});
