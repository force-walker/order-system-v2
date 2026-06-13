export type ImportRequiredScope = 'always' | 'create' | 'never';

export type ImportFormatField = {
  name: string;
  label: string;
  required: boolean;
  requiredScope: ImportRequiredScope;
  description?: string | null;
  example?: unknown;
};

export type ImportFormat = {
  entity: string;
  fields: ImportFormatField[];
};
