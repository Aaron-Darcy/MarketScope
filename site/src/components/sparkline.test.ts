import { describe, expect, it } from 'vitest';

import { sparkPath } from './sparkline';

describe('sparkPath', () => {
  it('scales values into the box with y growing down', () => {
    expect(sparkPath([0, 1], 100, 10, [0, 1])).toBe('M0.0 10.0L100.0 0.0');
  });

  it('breaks the line at a missing value rather than bridging it', () => {
    expect(sparkPath([0, null, 1], 100, 10, [0, 1])).toBe('M0.0 10.0M100.0 0.0');
  });

  it('refuses an empty domain', () => {
    expect(() => sparkPath([1, 1], 100, 10, [1, 1])).toThrow(RangeError);
  });
});
