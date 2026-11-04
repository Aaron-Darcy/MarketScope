import { describe, expect, it } from 'vitest';

import { escapeHtml, tooltipHtml } from './base';
import { placement } from './comparison';
import { niceBounds } from './shared';

describe('tooltips', () => {
  it('escape labels taken from the data', () => {
    expect(escapeHtml(`<img src=x onerror="a">&'`)).toBe(
      '&lt;img src=x onerror=&quot;a&quot;&gt;&amp;&#39;',
    );
    expect(tooltipHtml('M&T <Bank>', [{ label: 'beta', value: '0.5' }])).toContain(
      'M&amp;T &lt;Bank&gt;',
    );
  });
});

describe('placement', () => {
  it('splits banks by how far they moved between quartiles', () => {
    expect(placement(0)).toBe('held');
    expect(placement(-1)).toBe('shifted');
    expect(placement(2)).toBe('moved');
    expect(placement(-3)).toBe('moved');
  });
});

describe('niceBounds', () => {
  it('rounds the range outward to the step', () => {
    const [low, high] = niceBounds([0.23, 0.81]);
    expect(low).toBeCloseTo(0.2);
    expect(high).toBeCloseTo(0.9);
  });
});
