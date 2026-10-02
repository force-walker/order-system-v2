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

  expect((screen.getByLabelText('請求単位') as HTMLInputElement).value).toBe('KG');
  expect((screen.getByLabelText('請求単位') as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByLabelText('キャッチウェイト') as HTMLSelectElement).value).toBe('true');
  expect((screen.getByLabelText('キャッチウェイト') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByLabelText('重量入力必須') as HTMLSelectElement).value).toBe('true');
  expect((screen.getByLabelText('重量入力必須') as HTMLSelectElement).disabled).toBe(true);

  await actor.click(screen.getByRole('button', { name: '保存' }));
  expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({
    pricingBasisDefault: 'uom_kg',
    invoiceUom: 'KG',
    isCatchWeight: true,
    weightCaptureRequired: true,
  }));
});
