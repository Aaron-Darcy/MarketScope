import { describe, expect, it } from 'vitest';

import { linearFit, median, quantile } from './stats';

describe('median and quantile', () => {
  it('interpolate between the middle values', () => {
    expect(median([4, 1, 3, 2])).toBe(2.5);
    expect(quantile([1, 2, 3, 4, 5], 0.25)).toBe(2);
    expect(quantile([1, 2, 3, 4], 0.75)).toBe(3.25);
  });

  it('refuse an empty input rather than return nothing', () => {
    expect(() => median([])).toThrow(RangeError);
    expect(() => quantile([], 0.5)).toThrow(RangeError);
  });
});

describe('linearFit', () => {
  it('recovers an exact line', () => {
    const fit = linearFit([
      [0, 1],
      [1, 3],
      [2, 5],
    ]);
    expect(fit.slope).toBeCloseTo(2);
    expect(fit.intercept).toBeCloseTo(1);
    expect(fit.pearson).toBeCloseTo(1);
    expect(fit.r2).toBeCloseTo(1);
  });

  it('refuses too few points or no variation', () => {
    expect(() =>
      linearFit([
        [0, 1],
        [1, 2],
      ]),
    ).toThrow(RangeError);
    expect(() =>
      linearFit([
        [1, 1],
        [1, 2],
        [1, 3],
      ]),
    ).toThrow(RangeError);
  });
});
