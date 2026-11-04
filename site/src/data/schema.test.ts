import { describe, expect, it } from 'vitest';

import { decodeRows, nullable, required, SchemaError } from './schema';

const spec = {
  cik: required('integer'),
  name: required('string'),
  beta: nullable('number'),
  failed: required('boolean'),
  filed: nullable('date'),
};
const columns = ['cik', 'name', 'beta', 'failed', 'filed', 'unused'];

describe('decodeRows', () => {
  it('converts BigInt keys, dates and nulls to the types the pages use', () => {
    const [row] = decodeRows('t', spec, columns, [
      {
        cik: 19617n,
        name: 'JPMORGAN CHASE & CO',
        beta: null,
        failed: false,
        filed: new Date('2023-03-31T00:00:00Z'),
        unused: 'ignored',
      },
    ]);
    expect(row).toEqual({
      cik: 19617,
      name: 'JPMORGAN CHASE & CO',
      beta: null,
      failed: false,
      filed: '2023-03-31',
    });
  });

  it('refuses a table without a declared column', () => {
    expect(() => decodeRows('t', spec, ['cik'], [{ cik: 1n }])).toThrow(
      new SchemaError('t has no column name'),
    );
  });

  it('refuses an empty table', () => {
    expect(() => decodeRows('t', spec, columns, [])).toThrow(SchemaError);
  });

  it('refuses a null in a required column', () => {
    const raw = [{ cik: 1n, name: null, beta: 0.5, failed: false, filed: null }];
    expect(() => decodeRows('t', spec, columns, raw)).toThrow('t.name, row 0 is null');
  });

  it('refuses a value of the wrong type rather than coercing it', () => {
    const raw = [{ cik: 1n, name: 'A', beta: '0.5', failed: false, filed: null }];
    expect(() => decodeRows('t', spec, columns, raw)).toThrow('t.beta, row 0 is not a number');
  });

  it('refuses a non-finite number', () => {
    const raw = [{ cik: 1n, name: 'A', beta: Number.NaN, failed: false, filed: null }];
    expect(() => decodeRows('t', spec, columns, raw)).toThrow(SchemaError);
  });

  it('refuses an integer beyond the range a double holds exactly', () => {
    const raw = [{ cik: 2n ** 60n, name: 'A', beta: null, failed: false, filed: null }];
    expect(() => decodeRows('t', spec, columns, raw)).toThrow('is not a integer');
  });
});
