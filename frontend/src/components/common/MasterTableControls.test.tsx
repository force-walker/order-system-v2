// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { MasterDetailNavigation, useMasterDetailNavigation } from './MasterTableControls';

afterEach(cleanup);

const defaultFallback = async () => [1, 2, 3];
const Detail = ({ fallbackIds = defaultFallback }: { fallbackIds?: () => Promise<number[]> }) => {
  const { id } = useParams();
  const navigation = useMasterDetailNavigation({ currentId: Number(id), basePath: '/records', fallbackIds });
  return <><span>record-{id}</span><MasterDetailNavigation navigation={navigation} /><a href={navigation.listHref}>一覧</a></>;
};

it('moves through the list context and disables navigation at its ends', async () => {
  const actor = userEvent.setup();
  render(
    <MemoryRouter initialEntries={['/records/2?ids=3%2C2%2C1&list=q%3Dsea']}>
      <Routes><Route path="/records/:id" element={<Detail />} /></Routes>
    </MemoryRouter>,
  );
  expect(screen.getByRole('link', { name: '一覧' }).getAttribute('href')).toBe('/records?q=sea');
  await actor.click(screen.getByRole('button', { name: '← 前へ' }));
  expect(screen.getByText('record-3')).toBeTruthy();
  expect((screen.getByRole('button', { name: '← 前へ' }) as HTMLButtonElement).disabled).toBe(true);
  await actor.click(screen.getByRole('button', { name: '次へ →' }));
  expect(screen.getByText('record-2')).toBeTruthy();
});

it('uses a stable fallback order for a direct detail URL', async () => {
  const fallback = vi.fn().mockResolvedValue([1, 2, 3]);
  render(
    <MemoryRouter initialEntries={['/records/2']}>
      <Routes><Route path="/records/:id" element={<Detail fallbackIds={fallback} />} /></Routes>
    </MemoryRouter>,
  );
  await waitFor(() => expect((screen.getByRole('button', { name: '← 前へ' }) as HTMLButtonElement).disabled).toBe(false));
  expect(fallback).toHaveBeenCalledOnce();
  expect((screen.getByRole('button', { name: '次へ →' }) as HTMLButtonElement).disabled).toBe(false);
});
