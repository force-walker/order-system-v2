import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';
import { listProducts } from 'features/orders/services/ordersService';
import type { ProductOption } from 'features/orders/types/order';
import { toUserMessage } from 'shared/error';

export const ProductListPage = () => {
  const [products, setProducts] = useState<ProductOption[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    listProducts()
      .then(setProducts)
      .catch((e) => setError(toUserMessage(e, '商品一覧の取得に失敗しました')));
  }, []);

  if (error) return <ErrorState title="商品一覧の取得に失敗" description={error} />;
  if (!products) return <LoadingState title="商品一覧を読み込み中" description="しばらくお待ちください" />;
  if (products.length === 0) return <EmptyState title="商品データがありません" description="商品マスタを登録してください" />;

  return (
    <section className="card">
      <div className="list-header">
        <div>
          <h2>商品マスタ</h2>
          <p className="subtle">参照用（読み取り専用）</p>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>商品名</th>
              <th>注文単位</th>
              <th>課金基準</th>
              <th>詳細</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td>{p.id}</td>
                <td>{p.name}</td>
                <td>{p.orderUom}</td>
                <td>{p.pricingBasisDefault}</td>
                <td>
                  <Link to={`/products/${p.id}`} className="order-link">詳細</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
