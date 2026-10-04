// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductForm } from './ProductForm';

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
  await actor.selectOptions(screen.getByLabelText('仕入単位'), 'case');
  expect((screen.getByLabelText('請求単位') as HTMLSelectElement).value).toBe('case');
  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    orderUom: 'piece',
    purchaseUom: 'case',
    invoiceUom: 'case',
    pricingBasisDefault: 'uom_count',
  }));
});
