import { useEffect, useMemo, useState } from 'react';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { generatePurchaseConfirmationPdf, getShippingReport, type ShippingReportMode, type ShippingReportRow } from 'features/orders/services/shippingReportService';
import { toActionableMessage } from 'shared/error';

export const ShippingReportPage = () => {
  const [shippedDate, setShippedDate] = useState('');
  const [mode, setMode] = useState<ShippingReportMode | ''>('');
  const [rows, setRows] = useState<ShippingReportRow[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [error, setError] = useState('');

  const load = async () => {
    if (!shippedDate || !mode) {
      setRows(null);
      setError('');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await getShippingReport(shippedDate, mode);
      setRows(result);
      setSelectedIds([]);
    } catch (e) {
      setError(toActionableMessage(e, '帳票リストの取得に失敗しました。'));
      setRows(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [shippedDate, mode]);

  const selectedCount = selectedIds.length;
  const selectableIds = useMemo(() => (rows ?? []).map((r) => r.orderItemId), [rows]);
  const allVisibleSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));

  const toggleSelectAll = (checked: boolean) => {
    if (checked) setSelectedIds(selectableIds);
    else setSelectedIds([]);
  };

  const toggleOne = (id: number, checked: boolean) => {
    setSelectedIds((prev) => (checked ? Array.from(new Set([...prev, id])) : prev.filter((x) => x !== id)));
  };

  const generatePdf = async () => {
    if (selectedIds.length === 0) return;
    setPdfGenerating(true);
    try {
      const blob = await generatePurchaseConfirmationPdf(selectedIds);
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank', 'noopener,noreferrer');
    } catch (e) {
      setError(toActionableMessage(e, 'PDF生成に失敗しました。'));
    } finally {
      setPdfGenerating(false);
    }
  };

  return (
    <section>
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="list-header">
          <div>
            <h2>帳票作成</h2>
            <p className="subtle">出荷日と表示モードを指定すると帳票リストを自動表示します。</p>
          </div>
        </div>

        <div className="list-controls" style={{ marginTop: 8 }}>
          <label className="filter-label">
            出荷日 *
            <input type="date" value={shippedDate} onChange={(e) => setShippedDate(e.target.value)} />
          </label>

          <label className="filter-label">
            表示モード
            <select value={mode} onChange={(e) => setMode((e.target.value || '') as ShippingReportMode | '')}>
              <option value="">選択してください</option>
              <option value="supplier_product">仕入先→商品順</option>
              <option value="customer">顧客順</option>
            </select>
          </label>

          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="subtle">{selectedCount}件選択中</span>
            <button type="button" className="btn secondary" disabled={selectedCount === 0 || pdfGenerating} onClick={() => void generatePdf()}>
              {pdfGenerating ? 'PDF生成中...' : 'PDF作成'}
            </button>
          </div>
        </div>
      </div>

      {loading ? (
        <LoadingState title="帳票リストを読み込み中" description="しばらくお待ちください。" />
      ) : error ? (
        <ErrorState title="帳票リストの取得に失敗しました" description={error} actionLabel="再試行" onAction={load} />
      ) : rows == null ? (
        <EmptyState title="未表示" description="出荷日と表示モードを選択すると自動で表示されます。" />
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th><input type="checkbox" checked={allVisibleSelected} onChange={(e) => toggleSelectAll(e.target.checked)} /></th>
                  <th>出荷日</th>
                  <th>仕入先</th>
                  <th>顧客</th>
                  <th>商品</th>
                  <th>数量</th>
                  <th>単位</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="subtle">指定した出荷日・表示モードでは帳票対象が0件です。</td>
                  </tr>
                ) : rows.map((r, idx) => (
                  <tr key={`${r.orderItemId}-${r.shippedDate}-${idx}`}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(r.orderItemId)}
                        onChange={(e) => toggleOne(r.orderItemId, e.target.checked)}
                      />
                    </td>
                    <td>{r.shippedDate}</td>
                    <td>{r.supplierName}</td>
                    <td>{r.customerName}</td>
                    <td>{r.productName}</td>
                    <td>{r.quantity}</td>
                    <td>{r.unit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
};
