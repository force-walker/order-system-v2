import {
  MasterImportPage,
  type PreflightErrorRow,
} from 'features/imports/components/MasterImportPage';
import { getProductImportFormat, importProductsUpsert } from 'features/products/services/productsService';

const SAMPLE_JSON = `[
  {
    "legacy_code": "LEG-100",
    "name": "Imported Product",
    "order_uom": "count",
    "purchase_uom": "count",
    "invoice_uom": "count",
    "freight_weight": 0.5,
    "pricing_basis_default": "uom_count"
  }
]`;

const STRING_NULLABLE_FIELDS = ['legacy_unit_code', 'owner_code', 'origin_code', 'jan_code'] as const;
const DECIMAL_NULLABLE_FIELDS = [
  'sales_price',
  'sales_price_1',
  'sales_price_2',
  'sales_price_3',
  'sales_price_4',
  'sales_price_5',
  'sales_price_6',
  'purchase_price',
  'inventory_price',
  'list_price',
  'customs_reference_price',
  'freight_weight',
] as const;
const INTEGER_NULLABLE_FIELDS = ['pack_size'] as const;
const DROP_BEFORE_SEND_FIELDS = ['created_at', 'updated_at'] as const;

const normalizeEmptyStringToNull = (v: unknown): string | null | unknown => {
  if (typeof v !== 'string') return v;
  const trimmed = v.trim();
  return trimmed === '' ? null : trimmed;
};

const toDecimalOrNull = (v: unknown): { value: number | null; valid: boolean } => {
  if (v === null || v === undefined) return { value: null, valid: true };
  if (typeof v === 'number') return Number.isFinite(v) ? { value: v, valid: true } : { value: null, valid: false };
  if (typeof v !== 'string') return { value: null, valid: false };

  const trimmed = v.trim();
  if (!trimmed) return { value: null, valid: true };
  const numeric = trimmed.replace(/,/g, '');
  const n = Number(numeric);
  if (!Number.isFinite(n)) return { value: null, valid: false };
  return { value: n, valid: true };
};

const toIntegerOrNull = (v: unknown): { value: number | null; valid: boolean } => {
  if (v === null || v === undefined) return { value: null, valid: true };
  if (typeof v === 'number') return Number.isInteger(v) ? { value: v, valid: true } : { value: null, valid: false };
  if (typeof v !== 'string') return { value: null, valid: false };

  const trimmed = v.trim();
  if (!trimmed) return { value: null, valid: true };
  const normalized = trimmed.replace(/,/g, '');
  if (!/^[-+]?\d+$/.test(normalized)) return { value: null, valid: false };
  const n = Number(normalized);
  if (!Number.isInteger(n)) return { value: null, valid: false };
  return { value: n, valid: true };
};

const normalizeItemsBeforeSubmit = (items: Record<string, unknown>[]) => {
  const errors: PreflightErrorRow[] = [];

  const normalized = items.map((raw, idx) => {
    const row = { ...raw } as Record<string, unknown>;

    for (const field of DROP_BEFORE_SEND_FIELDS) {
      delete row[field];
    }

    for (const field of STRING_NULLABLE_FIELDS) {
      row[field] = normalizeEmptyStringToNull(row[field]);
    }

    for (const field of DECIMAL_NULLABLE_FIELDS) {
      const converted = toDecimalOrNull(row[field]);
      if (!converted.valid) {
        errors.push({ row: idx + 1, field, message: '数値を入力してください（空欄は null として扱います）' });
      } else {
        row[field] = converted.value;
      }
    }

    for (const field of INTEGER_NULLABLE_FIELDS) {
      const converted = toIntegerOrNull(row[field]);
      if (!converted.valid) {
        errors.push({ row: idx + 1, field, message: '整数を入力してください（空欄は null として扱います）' });
      } else {
        row[field] = converted.value;
      }
    }

    return row;
  });

  return { normalized, errors };
};

export const ProductImportPage = () => (
  <MasterImportPage
    title="商品マスタ IMPORT"
    apiPath="/api/v1/products/import-upsert"
    backTo="/products"
    backLabel="商品一覧へ戻る"
    sampleJson={SAMPLE_JSON}
    importAction={importProductsUpsert}
    fetchImportFormat={getProductImportFormat}
    normalizeItemsBeforeSubmit={normalizeItemsBeforeSubmit}
  />
);
