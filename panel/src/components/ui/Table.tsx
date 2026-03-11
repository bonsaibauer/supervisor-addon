import type { ReactNode } from 'react';

interface Column<T> {
  key: string;
  title: string;
  render: (row: T) => ReactNode;
}

interface Props<T> {
  columns: Array<Column<T>>;
  rows: T[];
  emptyText?: string;
}

export function Table<T>({ columns, rows, emptyText = 'No data' }: Props<T>) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.title}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="table__empty">
                {emptyText}
              </td>
            </tr>
          )}
          {rows.map((row, index) => (
            <tr key={index}>
              {columns.map((col) => (
                <td key={col.key}>{col.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
