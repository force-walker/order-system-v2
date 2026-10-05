import type { EntityId } from 'shared/entityId';
import { compareIds, newestInvoiceFirst } from 'shared/entityId';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorState, LoadingState } from 'components/common/AsyncState';
import {
  finalizeInvoiceDraftsBatch,
  listInvoiceDraftCandidates,
  listInvoiceDraftListRows,
  updateInvoiceDraftItem,
} from 'features/orders/services/invoiceService';
import { listCustomers } from 'features/orders/services/ordersService';
import { generateDraftInvoiceFromPurchase } from 'features/orders/services/purchaseService';
import type { CustomerOption, InvoiceDraftCandidate, InvoiceDraftListRow, InvoiceStatus } from 'features/orders/types/order';
import { getDefaultDeliveryDate } from 'features/orders/utils/deliveryDate';
import { toActionableMessage } from 'shared/error';

const currency = new Intl.NumberFormat('ja-JP', { style: 'currency', currency: 'HKD', maximumFractionDigits: 2 });
const numberFormatter = new Intl.NumberFormat('ja-JP', { maximumFractionDigits: 2 });
const percentFormatter = new Intl.NumberFormat('ja-JP', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

const STATUS_LABEL: Record<InvoiceStatus, string> = {
  draft: 'draft',
  finalized: 'finalized',
  sent: 'sent',
  cancelled: 'cancelled',
};

type ToastPayload = {
  type: 'success' | 'error';
  message: string;
};

type RowSelect = Record<EntityId, boolean>;
type PriceInputMap = Record<EntityId, string>;
type SavingMap = Record<EntityId, boolean>;
type InvoiceViewStatus = InvoiceStatus | 'uncreated' | '';
const ALL_CUSTOMERS_LABEL = '全取引先';

const customerName = (customer: CustomerOption) => {
  const afterId = customer.label.includes(':') ? customer.label.split(':').slice(1).join(':').trim() : customer.label;
  const suffix = customer.customerCode ? ` (${customer.customerCode})` : '';
  return suffix && afterId.endsWith(suffix) ? afterId.slice(0, -suffix.length).trim() : afterId.replace(/\s+\([^)]*\)\s*$/, '').trim();
};

const customerDisplayLabel = (customer: CustomerOption) => {
  const name = customerName(customer);
  return customer.customerCode ? `${name} (${customer.customerCode})` : name;
};

const formatNumber = (value: number | undefined) => {
  if (value === undefined) return '-';
  return numberFormatter.format(value);
};

const formatGrossMargin = (row: Pick<InvoiceDraftListRow, 'grossMarginPct' | 'grossMarginUnavailable'>) => {
  if (row.grossMarginUnavailable || row.grossMarginPct === undefined) return '-';
  return `${percentFormatter.format(row.grossMarginPct)}%`;
};

export const InvoiceDraftPage = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [rows, setRows] = useState<InvoiceDraftListRow[]>([]);
  const [candidates, setCandidates] = useState<InvoiceDraftCandidate[]>([]);
  const [customers, setCustomers] = useState<CustomerOption[]>([]);
  const [customerFilter, setCustomerFilter] = useState(ALL_CUSTOMERS_LABEL);
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | null>(null);
  const [dateFilter, setDateFilter] = useState(getDefaultDeliveryDate);
  const [statusFilter, setStatusFilter] = useState<InvoiceViewStatus>('');
  const [selectedByInvoiceId, setSelectedByInvoiceId] = useState<RowSelect>({});
  const [selectedByCandidateItemId, setSelectedByCandidateItemId] = useState<RowSelect>({});
  const [priceInputs, setPriceInputs] = useState<PriceInputMap>({});
  const [candidatePriceInputs, setCandidatePriceInputs] = useState<PriceInputMap>({});
  const [savingByItemId, setSavingByItemId] = useState<SavingMap>({});
  const [bulkFinalizing, setBulkFinalizing] = useState(false);
  const [creatingOrderId, setCreatingOrderId] = useState<EntityId | null>(null);
  const [toast, setToast] = useState<ToastPayload | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [nextRows, nextCandidates, customerOptions] = await Promise.all([
        listInvoiceDraftListRows(),
        listInvoiceDraftCandidates(),
        listCustomers(true),
      ]);
      setRows(nextRows);
      setCandidates(nextCandidates);
      setCustomers(customerOptions);
      setSelectedByInvoiceId((prev) =>
        Object.fromEntries([...new Set(nextRows.map((row) => row.invoiceId))].map((invoiceId) => [invoiceId, prev[invoiceId] ?? false])),
      );
      setPriceInputs(Object.fromEntries(nextRows.map((row) => [row.invoiceItemId, String(row.salesUnitPrice)])));
      setSelectedByCandidateItemId((prev) => Object.fromEntries(
        nextCandidates.flatMap((candidate) => candidate.items.map((item) => [item.orderItemId, prev[item.orderItemId] ?? false])),
      ));
      setCandidatePriceInputs((prev) => Object.fromEntries(
        nextCandidates.flatMap((candidate) => candidate.items.map((item) => [item.orderItemId, prev[item.orderItemId] ?? String(item.salesUnitPrice)])),
      ));
    } catch (e) {
      setError(toActionableMessage(e, '請求ドラフト一覧の取得に失敗しました。'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 4500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filtered = useMemo(() => {
    const customerQuery = customerFilter.trim().toLocaleLowerCase();
    const selectedCustomer = selectedCustomerId == null ? undefined : customers.find((customer) => customer.id === selectedCustomerId);
    const selectedCustomerName = selectedCustomer ? customerName(selectedCustomer).toLocaleLowerCase() : undefined;
    const matchingCustomerNames = new Set(
      customerQuery && customerQuery !== ALL_CUSTOMERS_LABEL.toLocaleLowerCase()
        ? customers
          .filter((customer) => [customer.label, customerName(customer), customer.customerCode ?? '']
            .some((value) => value.toLocaleLowerCase().includes(customerQuery)))
          .map((customer) => customerName(customer).toLocaleLowerCase())
        : [],
    );
    return rows
      .filter((row) => {
        if (statusFilter && row.status !== statusFilter) return false;
        if (dateFilter && row.deliveryDate !== dateFilter) return false;
        const rowCustomerName = row.customerName.toLocaleLowerCase();
        if (selectedCustomerName && rowCustomerName !== selectedCustomerName) return false;
        if (
          !selectedCustomerName
          && customerQuery
          && customerQuery !== ALL_CUSTOMERS_LABEL.toLocaleLowerCase()
          && !rowCustomerName.includes(customerQuery)
          && !matchingCustomerNames.has(rowCustomerName)
        ) return false;
        return true;
      })
      .sort((a, b) => newestInvoiceFirst(a, b) || compareIds(a.invoiceItemId, b.invoiceItemId));
  }, [rows, customers, customerFilter, selectedCustomerId, dateFilter, statusFilter]);

  const filteredCandidates = useMemo(() => {
    if (statusFilter && statusFilter !== 'uncreated') return [];
    const customerQuery = customerFilter.trim().toLocaleLowerCase();
    const selectedCustomer = selectedCustomerId == null ? undefined : customers.find((customer) => customer.id === selectedCustomerId);
    const selectedCustomerName = selectedCustomer ? customerName(selectedCustomer).toLocaleLowerCase() : undefined;
    const matchingCustomerNames = new Set(
      customerQuery && customerQuery !== ALL_CUSTOMERS_LABEL.toLocaleLowerCase()
        ? customers
          .filter((customer) => [customer.label, customerName(customer), customer.customerCode ?? '']
            .some((value) => value.toLocaleLowerCase().includes(customerQuery)))
          .map((customer) => customerName(customer).toLocaleLowerCase())
        : [],
    );
    return candidates.filter((candidate) => {
      if (dateFilter && candidate.deliveryDate !== dateFilter) return false;
      const name = candidate.customerName.toLocaleLowerCase();
      if (selectedCustomerName && name !== selectedCustomerName) return false;
      if (
        !selectedCustomerName
        && customerQuery
        && customerQuery !== ALL_CUSTOMERS_LABEL.toLocaleLowerCase()
        && !name.includes(customerQuery)
        && !matchingCustomerNames.has(name)
      ) return false;
      return true;
    });
  }, [candidates, customers, customerFilter, selectedCustomerId, dateFilter, statusFilter]);

  const resetCustomerFilter = () => {
    setSelectedCustomerId(null);
    setCustomerFilter(ALL_CUSTOMERS_LABEL);
  };

  const onCustomerFilterChange = (rawValue: string) => {
    const value = rawValue.trim();
    if (!value || value === ALL_CUSTOMERS_LABEL) {
      setSelectedCustomerId(null);
      setCustomerFilter(rawValue);
      return;
    }

    const normalized = value.toLocaleLowerCase();
    const exact = customers.find((customer) => (
      customer.label.toLocaleLowerCase() === normalized
      || customerDisplayLabel(customer).toLocaleLowerCase() === normalized
      || customerName(customer).toLocaleLowerCase() === normalized
      || customer.customerCode?.toLocaleLowerCase() === normalized
    ));
    setSelectedCustomerId(exact?.id ?? null);
    setCustomerFilter(exact ? customerDisplayLabel(exact) : rawValue);
  };

  const draftInvoiceIds = useMemo(() => [...new Set(rows.filter((row) => row.status === 'draft').map((row) => row.invoiceId))], [rows]);
  const finalizedInvoiceIds = useMemo(
    () => [...new Set(rows.filter((row) => row.status === 'finalized').map((row) => row.invoiceId))],
    [rows],
  );
  const visibleDraftIds = useMemo(
    () => [...new Set(filtered.filter((row) => row.status === 'draft').map((row) => row.invoiceId))],
    [filtered],
  );
  const selectedDraftIds = useMemo(
    () => visibleDraftIds.filter((invoiceId) => selectedByInvoiceId[invoiceId]),
    [selectedByInvoiceId, visibleDraftIds],
  );
  const visibleCandidateItems = useMemo(
    () => filteredCandidates.flatMap((candidate) => candidate.items.map((item) => ({ candidate, item }))),
    [filteredCandidates],
  );
  const selectedCandidateItems = useMemo(
    () => visibleCandidateItems.filter(({ item }) => selectedByCandidateItemId[item.orderItemId]),
    [selectedByCandidateItemId, visibleCandidateItems],
  );
  const selectableCount = visibleDraftIds.length + visibleCandidateItems.length;
  const selectedSelectableCount = selectedDraftIds.length + selectedCandidateItems.length;
  const allVisibleSelected = selectableCount > 0 && selectedSelectableCount === selectableCount;
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = selectedSelectableCount > 0 && !allVisibleSelected;
    }
  }, [allVisibleSelected, selectedSelectableCount]);

  const onToggleAll = (checked: boolean) => {
    setSelectedByInvoiceId((prev) => {
      const next = { ...prev };
      for (const invoiceId of visibleDraftIds) next[invoiceId] = checked;
      return next;
    });
    setSelectedByCandidateItemId((prev) => {
      const next = { ...prev };
      for (const { item } of visibleCandidateItems) next[item.orderItemId] = checked;
      return next;
    });
  };

  const onFinalizeBulk = async () => {
    if (selectedDraftIds.length === 0) {
      setToast({ type: 'error', message: '発行対象のドラフトを選択してください。' });
      return;
    }

    setBulkFinalizing(true);
    setError('');
    try {
      const result = await finalizeInvoiceDraftsBatch(selectedDraftIds);
      await load();
      const failed = (result.results ?? []).filter((row) => !row.ok);
      if (failed.length > 0) {
        const failedText = failed
          .slice(0, 3)
          .map((row) => `#${row.invoice_id}: ${row.reason_code ?? 'FAILED'}`)
          .join(', ');
        setToast({
          type: 'error',
          message: `一括発行は部分成功です。成功 ${result.success_count} / 失敗 ${result.failure_count}${failedText ? ` (${failedText})` : ''}`,
        });
      } else {
        setToast({ type: 'success', message: `${result.success_count}件の請求ドラフトを発行しました。` });
      }
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '請求ドラフトの一括発行に失敗しました。') });
    } finally {
      setBulkFinalizing(false);
    }
  };

  const onCreateDraft = async (candidate: InvoiceDraftCandidate, selectedItemIds: EntityId[]) => {
    const items = candidate.items.filter((item) => selectedItemIds.includes(item.orderItemId));
    if (items.length === 0) return;
    const invalid = items.find((item) => item.validationMessage);
    if (invalid) {
      setToast({ type: 'error', message: invalid.validationMessage! });
      return;
    }
    const salesUnitPrices: Record<EntityId, number> = {};
    for (const item of items) {
      const value = Number(candidatePriceInputs[item.orderItemId]);
      if (!Number.isFinite(value) || value < 0) {
        setToast({ type: 'error', message: `${item.productSku}: 請求単価には0以上の数値を入力してください。` });
        return;
      }
      salesUnitPrices[item.orderItemId] = value;
    }
    setCreatingOrderId(candidate.orderId);
    setError('');
    try {
      await generateDraftInvoiceFromPurchase({
        orderId: candidate.orderId,
        invoiceDate: new Date().toISOString().slice(0, 10),
        purchaseResultIds: items.flatMap((item) => item.purchaseResultIds),
        salesUnitPrices,
      });
      await load();
      setToast({ type: 'success', message: `請求ドラフトを作成しました: ${candidate.orderNo}` });
    } catch (e) {
      setToast({ type: 'error', message: toActionableMessage(e, '請求ドラフトの作成に失敗しました。') });
    } finally {
      setCreatingOrderId(null);
    }
  };

  const onCreateSelectedDrafts = async () => {
    const orderIds = [...new Set(selectedCandidateItems.map(({ candidate }) => candidate.orderId))];
    if (orderIds.length === 0) {
      setToast({ type: 'error', message: 'ドラフト作成対象の明細を選択してください。' });
      return;
    }
    for (const orderId of orderIds) {
      const candidate = candidates.find((row) => row.orderId === orderId);
      if (!candidate) continue;
      const itemIds = selectedCandidateItems
        .filter(({ candidate: row }) => row.orderId === orderId)
        .map(({ item }) => item.orderItemId);
      await onCreateDraft(candidate, itemIds);
    }
  };

  const commitSalesUnitPrice = async (row: InvoiceDraftListRow) => {
    const rawValue = priceInputs[row.invoiceItemId]?.trim() ?? '';
    if (rawValue.length === 0) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    const nextValue = Number(rawValue);
    if (!Number.isFinite(nextValue) || nextValue < 0) {
      setToast({ type: 'error', message: '請求単価には 0 以上の数値を入力してください。' });
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    if (nextValue === row.salesUnitPrice) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      return;
    }

    setSavingByItemId((prev) => ({ ...prev, [row.invoiceItemId]: true }));
    setError('');
    try {
      const updated = await updateInvoiceDraftItem(row.invoiceId, row.invoiceItemId, {
        billableQty: row.billableQty,
        salesUnitPrice: nextValue,
      });
      setRows((prev) =>
        prev.map((current) =>
          current.invoiceItemId === row.invoiceItemId
            ? {
                ...current,
                billableQty: updated.billableQty,
                billableUom: updated.billableUom,
                salesUnitPrice: updated.salesUnitPrice,
                unitCostBasis: updated.unitCostBasis,
                autoPriceError: updated.autoPriceError,
                lineAmount: updated.lineAmount,
                grossMarginPct: updated.grossMarginPct,
                grossMarginUnavailable: updated.grossMarginUnavailable,
              }
            : current,
        ),
      );
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(updated.salesUnitPrice) }));
      setToast({ type: 'success', message: `請求単価を更新しました: ${row.invoiceNo}` });
    } catch (e) {
      setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: String(row.salesUnitPrice) }));
      setToast({ type: 'error', message: toActionableMessage(e, '請求単価の更新に失敗しました。') });
    } finally {
      setSavingByItemId((prev) => ({ ...prev, [row.invoiceItemId]: false }));
    }
  };

  if (error) return <ErrorState title="請求ドラフト一覧の取得に失敗しました" description={error} />;
  if (loading) return <LoadingState title="請求ドラフト一覧を読み込み中" description="しばらくお待ちください。" />;

  return (
    <section>
      {toast ? <div className={`toast ${toast.type}`}>{toast.message}</div> : null}
      <div className="list-controls card" style={{ marginBottom: 16 }}>
        <label className="filter-label">
          取引先
          <input
            aria-label="取引先"
            list="invoice-draft-customer-options"
            value={customerFilter}
            onFocus={(event) => event.currentTarget.select()}
            onChange={(event) => onCustomerFilterChange(event.target.value)}
            onBlur={() => {
              if (!customerFilter.trim()) resetCustomerFilter();
            }}
            placeholder="取引先名 / 取引先コードで検索"
          />
          <datalist id="invoice-draft-customer-options">
            <option value={ALL_CUSTOMERS_LABEL} />
            {customers.map((customer) => (
              <option key={customer.id} value={customerDisplayLabel(customer)}>{customer.label}</option>
            ))}
          </datalist>
        </label>
        <button type="button" className="secondary" onClick={resetCustomerFilter}>全取引先</button>
        <label className="filter-label">
          納品日
          <input type="date" value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} />
        </label>
        <label className="filter-label">
          状態
          <select value={statusFilter} onChange={(e) => setStatusFilter((e.target.value || '') as InvoiceViewStatus)}>
            <option value="">all</option>
            <option value="uncreated">未作成</option>
            <option value="draft">draft</option>
            <option value="finalized">finalized</option>
            <option value="sent">sent</option>
            <option value="cancelled">cancelled</option>
          </select>
        </label>
      </div>
      <div className="card">
        <div className="list-header">
          <div>
            <h2>請求ドラフト</h2>
            <p className="subtle">未作成の注文と作成済みDraftを同じ一覧で確認します。Deliveryの作成は必要ありません。</p>
          </div>
          <div className="list-controls">
            <button type="button" className="secondary" onClick={() => void onCreateSelectedDrafts()} disabled={creatingOrderId !== null || selectedCandidateItems.length === 0}>
              {creatingOrderId !== null ? 'ドラフト作成中...' : `選択した候補からドラフト作成${selectedCandidateItems.length > 0 ? ` (${selectedCandidateItems.length})` : ''}`}
            </button>
            <button type="button" onClick={() => void onFinalizeBulk()} disabled={bulkFinalizing || selectedDraftIds.length === 0}>
              {bulkFinalizing ? '一括発行中...' : `選択した請求ドラフトを発行${selectedDraftIds.length > 0 ? ` (${selectedDraftIds.length})` : ''}`}
            </button>
          </div>
        </div>

        <div className="subtle" style={{ marginBottom: 12 }}>
          draft 件数: {draftInvoiceIds.length} / finalized 件数: {finalizedInvoiceIds.length}
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    aria-label="表示中の選択可能行を全選択"
                    checked={allVisibleSelected}
                    onChange={(e) => onToggleAll(e.target.checked)}
                    disabled={selectableCount === 0}
                  />
                </th>
                <th>詳細</th>
                <th>請求ヘッダー番号</th>
                <th>明細参照</th>
                <th>取引先名</th>
                <th>請求日</th>
                <th>納品日</th>
                <th>ステータス</th>
                <th style={{ textAlign: 'right' }}>仕入単価</th>
                <th style={{ textAlign: 'right' }}>請求単価</th>
                <th style={{ textAlign: 'right' }}>請求数量</th>
                <th style={{ textAlign: 'right' }}>請求金額</th>
                <th style={{ textAlign: 'right' }}>粗利額</th>
                <th style={{ textAlign: 'right' }}>粗利%</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredCandidates.length === 0 && filtered.length === 0 ? (
                <tr>
                  <td colSpan={15} className="subtle">条件に合う請求データがありません。</td>
                </tr>
              ) : (
                <>
                  {filteredCandidates.flatMap((candidate) => candidate.items.map((item, itemIndex) => {
                    const rawPrice = candidatePriceInputs[item.orderItemId] ?? String(item.salesUnitPrice);
                    const enteredPrice = Number(rawPrice);
                    const previewAmount = item.billableQty != null && Number.isFinite(enteredPrice) ? item.billableQty * enteredPrice : undefined;
                    const previewProfit = previewAmount != null && item.unitCostBasis != null
                      ? previewAmount - item.billableQty! * item.unitCostBasis
                      : undefined;
                    const previewMargin = previewAmount && previewProfit != null ? previewProfit / previewAmount * 100 : undefined;
                    return (
                    <tr key={`candidate-${candidate.orderId}-${item.orderItemId}`}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`${candidate.orderNo} ${item.productSku} を選択`}
                          checked={Boolean(selectedByCandidateItemId[item.orderItemId])}
                          disabled={creatingOrderId !== null}
                          onChange={(e) => setSelectedByCandidateItemId((prev) => ({ ...prev, [item.orderItemId]: e.target.checked }))}
                        />
                      </td>
                      <td>-</td>
                      <td>{candidate.orderNo}</td>
                      <td>{item.productSku}</td>
                      <td>{candidate.customerName}</td>
                      <td>-</td>
                      <td>{candidate.deliveryDate}</td>
                      <td>未作成</td>
                      <td style={{ textAlign: 'right' }}>
                        {formatNumber(item.unitCostBasis)}
                        <details className="pricing-breakdown">
                          <summary>原価内訳</summary>
                          <dl>
                            <div><dt>納品確認の仕入単価</dt><dd>{formatNumber(item.purchaseUnitCost)}</dd></div>
                            <div><dt>為替レート</dt><dd>{formatNumber(item.exchangeRate)}</dd></div>
                            <div><dt>日本粗利率</dt><dd>{percentFormatter.format(item.jpGrossMarginPct)}%</dd></div>
                            <div><dt>運賃重量</dt><dd>{formatNumber(item.freightWeight)} KG</dd></div>
                            <div><dt>運賃単価</dt><dd>{formatNumber(item.freightRate)} / KG</dd></div>
                            <div><dt>単位あたり運賃</dt><dd>{formatNumber(item.unitFreightCost)}</dd></div>
                            <div><dt>香港基準粗利率</dt><dd>{percentFormatter.format(item.hkGrossMarginPct)}%</dd></div>
                          </dl>
                        </details>
                      </td>
                      <td style={{ textAlign: 'right', minWidth: 140 }}>
                        <input
                          type="number"
                          aria-label={`${candidate.orderNo} ${item.productSku} 請求単価`}
                          inputMode="decimal"
                          min="0"
                          step="0.01"
                          value={rawPrice}
                          disabled={creatingOrderId !== null || Boolean(item.validationMessage)}
                          onChange={(e) => setCandidatePriceInputs((prev) => ({ ...prev, [item.orderItemId]: e.target.value }))}
                        />
                        {item.autoPriceError ? <div className="field-error">{item.autoPriceError}</div> : null}
                      </td>
                      <td style={{ textAlign: 'right' }}>{item.billableQty == null ? '-' : `${formatNumber(item.billableQty)} ${item.billableUom}`}</td>
                      <td style={{ textAlign: 'right' }}>{previewAmount == null ? '-' : currency.format(previewAmount)}</td>
                      <td style={{ textAlign: 'right' }}>{previewProfit == null ? '-' : currency.format(previewProfit)}</td>
                      <td style={{ textAlign: 'right' }}>{previewMargin == null ? '-' : `${percentFormatter.format(previewMargin)}%`}</td>
                      <td>
                        {item.validationMessage ? <span className="field-error">{item.validationMessage}</span> : itemIndex === 0 ? `${candidate.itemCount}明細` : '-'}
                      </td>
                    </tr>
                    );
                  }))}
                  {filtered.map((row) => {
                  const isDraft = row.status === 'draft';
                  const isSaving = Boolean(savingByItemId[row.invoiceItemId]);
                  return (
                    <tr key={row.invoiceItemId}>
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`請求書 ${row.invoiceNo} を選択`}
                          checked={Boolean(selectedByInvoiceId[row.invoiceId])}
                          disabled={!isDraft || bulkFinalizing}
                          onChange={(e) => {
                            const checked = e.target.checked;
                            setSelectedByInvoiceId((prev) => ({ ...prev, [row.invoiceId]: checked }));
                          }}
                        />
                      </td>
                      <td><Link to={`/invoices/drafts/${row.invoiceId}`}>詳細</Link></td>
                      <td>{row.invoiceNo}</td>
                      <td>{row.lineRef ?? '-'}</td>
                      <td>{row.customerName}</td>
                      <td>{row.invoiceDate}</td>
                      <td>{row.deliveryDate}</td>
                      <td>{STATUS_LABEL[row.status]}</td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(row.unitCostBasis)}</td>
                      <td style={{ textAlign: 'right', minWidth: 140 }}>
                        <input
                          type="number"
                          inputMode="decimal"
                          min="0"
                          step="0.01"
                          value={priceInputs[row.invoiceItemId] ?? String(row.salesUnitPrice)}
                          disabled={!isDraft || isSaving || bulkFinalizing}
                          onChange={(e) => {
                            const value = e.target.value;
                            setPriceInputs((prev) => ({ ...prev, [row.invoiceItemId]: value }));
                          }}
                          onBlur={() => void commitSalesUnitPrice(row)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.currentTarget.blur();
                            }
                          }}
                        />
                        {row.autoPriceError ? <div className="field-error">{row.autoPriceError}</div> : null}
                      </td>
                      <td style={{ textAlign: 'right' }}>{formatNumber(row.billableQty)}</td>
                      <td style={{ textAlign: 'right' }}>{currency.format(row.lineAmount)}</td>
                      <td style={{ textAlign: 'right' }}>
                        {row.unitCostBasis == null ? '-' : currency.format(row.lineAmount - row.billableQty * row.unitCostBasis)}
                      </td>
                      <td style={{ textAlign: 'right' }}>{formatGrossMargin(row)}</td>
                      <td>-</td>
                    </tr>
                  );
                  })}
                </>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
};
