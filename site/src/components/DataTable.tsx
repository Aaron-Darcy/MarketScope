import { useMemo, useState, type ReactNode } from 'react';

export interface Column<R> {
  readonly key: string;
  readonly title: string;
  readonly render: (row: R) => ReactNode;
  /** Present when the column can be sorted; nulls always sort last. */
  readonly sortValue?: (row: R) => number | string | null;
  readonly align?: 'left' | 'right' | 'center';
}

interface DataTableProps<R> {
  readonly rows: readonly R[];
  readonly columns: readonly Column<R>[];
  readonly rowKey: (row: R) => string | number;
  readonly onRowClick?: (row: R) => void;
  readonly caption: string;
}

type Sort = { readonly key: string; readonly descending: boolean } | null;

function compare(a: number | string | null, b: number | string | null): number {
  if (a === null) return b === null ? 0 : 1;
  if (b === null) return -1;
  return typeof a === 'number' && typeof b === 'number'
    ? a - b
    : String(a).localeCompare(String(b));
}

export function DataTable<R>({ rows, columns, rowKey, onRowClick, caption }: DataTableProps<R>) {
  const [sort, setSort] = useState<Sort>(null);

  const sorted = useMemo(() => {
    const column = sort && columns.find((c) => c.key === sort.key);
    const value = column?.sortValue;
    if (!sort || !value) return rows;
    return [...rows].sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      if (va === null || vb === null) return compare(va, vb);
      return sort.descending ? compare(vb, va) : compare(va, vb);
    });
  }, [rows, columns, sort]);

  const toggle = (key: string) => {
    setSort((current) =>
      current?.key === key ? { key, descending: !current.descending } : { key, descending: false },
    );
  };

  return (
    <div className="table-wrap">
      <table className="data-table">
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => {
              const active = sort?.key === column.key;
              return (
                <th
                  key={column.key}
                  className={`align-${column.align ?? 'left'}`}
                  aria-sort={active ? (sort.descending ? 'descending' : 'ascending') : undefined}
                >
                  {column.sortValue ? (
                    <button
                      type="button"
                      onClick={() => {
                        toggle(column.key);
                      }}
                    >
                      {column.title}
                      <span className="sort-mark">
                        {active ? (sort.descending ? '↓' : '↑') : '↕'}
                      </span>
                    </button>
                  ) : (
                    column.title
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? 'clickable' : undefined}
              onClick={
                onRowClick
                  ? () => {
                      onRowClick(row);
                    }
                  : undefined
              }
            >
              {columns.map((column) => (
                <td key={column.key} className={`align-${column.align ?? 'left'}`}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
