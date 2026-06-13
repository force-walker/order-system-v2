import {
  MasterImportPage,
  type PreflightErrorRow,
} from 'features/imports/components/MasterImportPage';
import { getSupplierImportFormat, importSuppliersUpsert } from 'features/suppliers/services/suppliersService';

const SAMPLE_JSON = `[
  {
    "import_key": "sup-001",
    "name": "テスト仕入先",
    "active": true
  }
]`;

const SAMPLE_CSV = `import_key,name,active
sup-001,テスト仕入先,true`;

const DROP_BEFORE_SEND_FIELDS = ['id', 'supplier_code', 'created_at', 'updated_at'] as const;

const normalizeEmptyStringToNull = (value: unknown): unknown => {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
};

const toBoolean = (value: unknown): { value: boolean; valid: boolean } => {
  if (typeof value === 'boolean') return { value, valid: true };
  if (typeof value === 'number') {
    if (value === 1) return { value: true, valid: true };
    if (value === 0) return { value: false, valid: true };
    return { value: false, valid: false };
  }
  if (typeof value !== 'string') return { value: false, valid: false };

  const normalized = value.trim().toLowerCase();
  if (['true', '1', 'yes', 'y', 'on'].includes(normalized)) return { value: true, valid: true };
  if (['false', '0', 'no', 'n', 'off'].includes(normalized)) return { value: false, valid: true };
  return { value: false, valid: false };
};

const normalizeItemsBeforeSubmit = (items: Record<string, unknown>[]) => {
  const errors: PreflightErrorRow[] = [];

  const normalized = items.map((raw, idx) => {
    const row = Object.fromEntries(
      Object.entries(raw).map(([key, value]) => [key, normalizeEmptyStringToNull(value)]),
    ) as Record<string, unknown>;

    for (const field of DROP_BEFORE_SEND_FIELDS) {
      delete row[field];
    }

    const active = toBoolean(row.active);
    if (!active.valid) {
      errors.push({ row: idx + 1, field: 'active', message: 'true / false を入力してください。' });
    } else {
      row.active = active.value;
    }

    return row;
  });

  return { normalized, errors };
};

export const SupplierImportPage = () => (
  <MasterImportPage
    title="仕入先マスタ IMPORT"
    apiPath="/api/v1/suppliers/import-upsert"
    backTo="/suppliers"
    backLabel="仕入先一覧へ戻る"
    sampleJson={SAMPLE_JSON}
    sampleCsv={SAMPLE_CSV}
    importAction={importSuppliersUpsert}
    fetchImportFormat={getSupplierImportFormat}
    normalizeItemsBeforeSubmit={normalizeItemsBeforeSubmit}
  />
);
