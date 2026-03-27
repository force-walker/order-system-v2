import type { OrderDetail } from 'features/orders/types/order';

export const mockOrders: OrderDetail[] = [
  {
    id: 101,
    orderNo: 'ORD-20260327-001',
    customerName: 'テスト商事',
    deliveryDate: '2026-03-30',
    status: 'new',
    note: '朝一配送希望',
    createdAt: '2026-03-27T08:00:00Z',
    items: [
      { id: 1, productName: '鶏もも肉', quantity: 20, unit: 'kg', note: '皮付き' },
      { id: 2, productName: '玉ねぎ', quantity: 15, unit: 'kg' },
    ],
  },
  {
    id: 102,
    orderNo: 'ORD-20260327-002',
    customerName: 'デモフーズ',
    deliveryDate: '2026-04-01',
    status: 'confirmed',
    createdAt: '2026-03-27T09:30:00Z',
    items: [{ id: 1, productName: '豚ロース', quantity: 10, unit: 'kg' }],
  },
];
