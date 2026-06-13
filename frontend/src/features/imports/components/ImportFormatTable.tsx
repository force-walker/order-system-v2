import type { ImportFormat } from 'features/imports/types/importFormat';

type ImportFormatTableProps = {
  format: ImportFormat;
};

const REQUIRED_SCOPE_LABEL: Record<string, string> = {
  always: '必須',
  create: '作成時必須',
  never: '任意',
};

const formatExample = (value: unknown): string => {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
};

export const ImportFormatTable = ({ format }: ImportFormatTableProps) => (
  <div className="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ヘッダー名</th>
          <th>表示名</th>
          <th>必須</th>
          <th>補足説明</th>
          <th>入力例</th>
        </tr>
      </thead>
      <tbody>
        {format.fields.map((field) => (
          <tr key={field.name}>
            <td>
              <code>{field.name}</code>
            </td>
            <td>{field.label}</td>
            <td>
              <span className={`import-required-badge ${field.required ? 'required' : 'optional'}`}>
                {REQUIRED_SCOPE_LABEL[field.requiredScope] ?? (field.required ? '必須' : '任意')}
              </span>
            </td>
            <td>{field.description ?? '-'}</td>
            <td>
              <code>{formatExample(field.example)}</code>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
