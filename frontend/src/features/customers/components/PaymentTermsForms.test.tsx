// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CustomerForm } from './CustomerForm';
import { SupplierForm } from 'features/suppliers/components/SupplierForm';

afterEach(cleanup);
it('clears existing customer payment terms with explicit nulls', async () => {
  const submit = vi.fn().mockResolvedValue(undefined); const user = userEvent.setup();
  render(<CustomerForm submitLabel="保存" initialValue={{ id: 1, customerCode: 'C1', name: 'C', active: true,
    paymentTermsType: 'days_after_issue', paymentTermsDays: 30 }} onSubmit={submit} />);
  await user.selectOptions(screen.getByLabelText('支払条件'), ''); await user.click(screen.getByRole('button', { name: '保存' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ paymentTermsType: null, paymentTermsDays: null }));
});
it('clears existing supplier payment terms with explicit nulls', async () => {
  const submit = vi.fn().mockResolvedValue(undefined); const user = userEvent.setup();
  render(<SupplierForm submitLabel="保存" initialValue={{ id: 1, supplierCode: 'S1', name: 'S', active: true,
    createdAt: '', updatedAt: '', paymentTermsType: 'end_of_next_month' }} onSubmit={submit} />);
  await user.selectOptions(screen.getByLabelText('支払条件'), ''); await user.click(screen.getByRole('button', { name: '保存' }));
  expect(submit).toHaveBeenCalledWith(expect.objectContaining({ paymentTermsType: null, paymentTermsDays: null }));
});
