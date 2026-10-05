// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductForm } from './ProductForm';
import type { ProductDetail } from 'features/products/types/product';
import { ServiceError } from 'shared/error';

afterEach(cleanup);

it('enforces the uom_kg product fields before submit', async () => {
  const actor = userEvent.setup();
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProductForm submitLabel="保存" onSubmit={onSubmit} />);

  await actor.type(screen.getByLabelText('商品名 *'), 'Cross-unit fish');
  await actor.selectOptions(screen.getByLabelText('課金基準'), 'uom_kg');

  expect((screen.getByLabelText('仕入単位') as HTMLSelectElement).value).toBe('kg');
  expect((screen.getByLabelText('仕入単位') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('kg');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('キャッチウェイト') as HTMLSelectElement).value).toBe('true');
  expect((screen.getByLabelText('キャッチウェイト') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('重量入力必須') as HTMLSelectElement).value).toBe('true');
  expect((screen.getByLabelText('重量入力必須') as HTMLSelectElement).disabled).toBe(true);

  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    pricingBasisDefault: 'uom_kg',
    purchaseUom: 'kg',
    invoiceUom: 'kg',
    isCatchWeight: true,
    weightCaptureRequired: true,
  }));
});

it('offers exactly the canonical UOM values and keeps count pricing countable', () => {
  render(<ProductForm submitLabel="保存" onSubmit={vi.fn()} />);
  for (const label of ['注文単位', '仕入単位', '請求単位']) {
    const select = screen.getByLabelText(label) as HTMLSelectElement;
    expect(Array.from(select.options).map((option) => option.value)).toEqual(['piece', 'kg', 'case']);
  }
  const orderUom = screen.getByLabelText('注文単位') as HTMLSelectElement;
  expect(Array.from(orderUom.options).find((option) => option.value === 'kg')?.disabled).toBe(true);
});

it('keeps purchase and invoice UOM equal for uom_count', async () => {
  const actor = userEvent.setup();
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProductForm submitLabel="保存" onSubmit={onSubmit} />);

  await actor.type(screen.getByLabelText('商品名 *'), 'Case purchase product');
  await actor.type(screen.getByLabelText('運賃重量（KG / piece）'), '0.25');
  await actor.selectOptions(screen.getByLabelText('仕入単位'), 'case');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('case');
  expect(screen.getByLabelText('運賃重量（KG / case）')).toBeTruthy();
  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    orderUom: 'piece',
    purchaseUom: 'case',
    invoiceUom: 'case',
    pricingBasisDefault: 'uom_count',
  }));
});

it('requires a positive freight weight for uom_count', async () => {
  const actor = userEvent.setup();
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProductForm submitLabel="保存" onSubmit={onSubmit} />);
  await actor.type(screen.getByLabelText('商品名 *'), 'Freight product');
  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(await screen.findByText(/Freight Weight.*必須/)).toBeTruthy();
  expect(onSubmit).not.toHaveBeenCalled();
  await actor.type(screen.getByLabelText('運賃重量（KG / piece）'), '0.25');
  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ freightWeight: 0.25 }));
});

it('sets and locks freight weight at one for uom_kg and clears it when returning to count pricing', async () => {
  const actor = userEvent.setup();
  render(<ProductForm submitLabel="保存" onSubmit={vi.fn()} />);
  const freight = screen.getByLabelText('運賃重量（KG / piece）') as HTMLInputElement;
  await actor.selectOptions(screen.getByLabelText('課金基準'), 'uom_kg');
  expect(freight.closest('label')?.textContent).toContain('運賃重量（KG / kg）');
  expect(freight.value).toBe('1');
  expect(freight.disabled).toBe(true);
  await actor.selectOptions(screen.getByLabelText('課金基準'), 'uom_count');
  expect(freight.value).toBe('');
  expect(freight.disabled).toBe(false);
});

const legacyProduct = {
  id: 15,
  sku: 'SKU-000015',
  name: 'ムキ牡蠣(生食用)',
  orderUom: 'PC',
  purchaseUom: 'PC',
  invoiceUom: 'PC',
  freightWeight: undefined,
  pricingBasisDefault: 'uom_count',
  isCatchWeight: false,
  weightCaptureRequired: false,
  active: true,
} as ProductDetail;

it('shows legacy UOMs explicitly and submits canonical synchronized UOMs after correction', async () => {
  const actor = userEvent.setup();
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  render(<ProductForm initialValue={legacyProduct} submitLabel="商品を保存" onSubmit={onSubmit} />);

  expect((screen.getByLabelText('注文単位') as HTMLSelectElement).value).toBe('PC');
  expect(screen.getAllByRole('option', { name: 'PC（旧値・要変更）', selected: true })).toHaveLength(3);
  expect((screen.getByLabelText('仕入単位') as HTMLSelectElement).value).toBe('PC');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('PC');
  expect(screen.getByLabelText('運賃重量（KG / PC・旧値）')).toBeTruthy();

  await actor.selectOptions(screen.getByLabelText('注文単位'), 'piece');
  await actor.selectOptions(screen.getByLabelText('仕入単位'), 'piece');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('piece');
  expect(screen.getByLabelText('運賃重量（KG / piece）')).toBeTruthy();
  await actor.type(screen.getByLabelText('運賃重量（KG / piece）'), '0.25');
  await actor.click(screen.getByRole('button', { name: '商品を保存' }));

  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    orderUom: 'piece',
    purchaseUom: 'piece',
    invoiceUom: 'piece',
    freightWeight: 0.25,
    pricingBasisDefault: 'uom_count',
    isCatchWeight: false,
    weightCaptureRequired: false,
  }));

  await actor.selectOptions(screen.getByLabelText('仕入単位'), 'case');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('case');
  expect(screen.getByLabelText('運賃重量（KG / case）')).toBeTruthy();
});

it('keeps kg purchase and invoice UOM fixed for uom_kg after loading a legacy product', async () => {
  const actor = userEvent.setup();
  render(<ProductForm initialValue={legacyProduct} submitLabel="商品を保存" onSubmit={vi.fn()} />);
  await actor.selectOptions(screen.getByLabelText('課金基準'), 'uom_kg');
  expect((screen.getByLabelText('仕入単位') as HTMLSelectElement).value).toBe('kg');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('kg');
  expect((screen.getByLabelText('仕入単位') as HTMLSelectElement).disabled).toBe(true);
  const freight = screen.getByRole('spinbutton') as HTMLInputElement;
  expect(freight.closest('label')?.textContent).toContain('運賃重量（KG / kg）');
  expect(freight.disabled).toBe(true);
});

it('shows Product consistency field and rule details returned by the Backend', async () => {
  const actor = userEvent.setup();
  const onSubmit = vi.fn().mockRejectedValue(new ServiceError(
    'product master UOM/pricing configuration is inconsistent',
    {
      code: 'PRODUCT_MASTER_INCONSISTENT',
      status: 422,
      details: [{
        field: 'invoice_uom',
        rule: 'PRODUCT_UOM_INVALID',
        message: 'invoice_uom must be one of: case, kg, piece.',
      }],
    },
  ));
  render(<ProductForm initialValue={{ ...legacyProduct, freightWeight: 0.25 }} submitLabel="商品を保存" onSubmit={onSubmit} />);
  await actor.click(screen.getByRole('button', { name: '商品を保存' }));
  expect(await screen.findByText(/請求単位 "PC" は使用できません/)).toBeTruthy();
  expect(screen.getByText(/piece \/ kg \/ caseから選択してください/)).toBeTruthy();
});
