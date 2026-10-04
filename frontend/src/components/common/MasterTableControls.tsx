import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

export type SortDirection = 'asc' | 'desc';

export const compareNullable = <T,>(left: T | null | undefined, right: T | null | undefined, compare: (a: T, b: T) => number) => {
  if (left == null && right == null) return 0;
  if (left == null) return 1;
  if (right == null) return -1;
  return compare(left, right);
};

export const compareText = (left: string | null | undefined, right: string | null | undefined) =>
  compareNullable(left, right, (a, b) => a.localeCompare(b, 'ja', { numeric: true, sensitivity: 'base' }));

export const SortableHeader = <T extends string>({
  column,
  label,
  activeColumn,
  direction,
  onSort,
}: {
  column: T;
  label: string;
  activeColumn: T;
  direction: SortDirection;
  onSort: (column: T) => void;
}) => {
  const active = activeColumn === column;
  return (
    <th aria-sort={active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className="sortable-header" onClick={() => onSort(column)}>
        {label}{active ? (direction === 'asc' ? ' ▲' : ' ▼') : ''}
      </button>
    </th>
  );
};

export const useVisibleRowSelection = (visibleIds: number[]) => {
  const [selectedIds, setSelectedIds] = useState<Set<number>>(() => new Set());
  const visibleKey = visibleIds.join(',');

  useEffect(() => {
    const visible = new Set(visibleIds);
    setSelectedIds((current) => {
      const next = new Set([...current].filter((id) => visible.has(id)));
      if (next.size === current.size && [...next].every((id) => current.has(id))) return current;
      return next;
    });
  }, [visibleKey]);

  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.has(id));
  const partiallySelected = !allSelected && visibleIds.some((id) => selectedIds.has(id));

  return {
    selectedIds,
    allSelected,
    partiallySelected,
    toggle: (id: number) => setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    }),
    toggleAll: () => setSelectedIds(allSelected ? new Set() : new Set(visibleIds)),
  };
};

export const SelectionHeaderCheckbox = ({
  checked,
  indeterminate,
  onChange,
  label,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
  label: string;
}) => {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return <input ref={ref} type="checkbox" checked={checked} onChange={onChange} aria-label={label} />;
};

export const buildDetailHref = (basePath: string, id: number, orderedIds: number[], listSearch: string) => {
  const params = new URLSearchParams();
  params.set('ids', orderedIds.join(','));
  if (listSearch) params.set('list', listSearch.replace(/^\?/, ''));
  return `${basePath}/${id}?${params.toString()}`;
};

const parseIds = (raw: string | null) => (raw ?? '')
  .split(',')
  .map((value) => Number(value))
  .filter((value) => Number.isInteger(value) && value > 0);

export const useMasterDetailNavigation = ({
  currentId,
  basePath,
  fallbackIds,
}: {
  currentId: number;
  basePath: string;
  fallbackIds: () => Promise<number[]>;
}) => {
  const location = useLocation();
  const navigate = useNavigate();
  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const contextIds = useMemo(() => parseIds(params.get('ids')), [params]);
  const [ids, setIds] = useState<number[]>(contextIds);

  useEffect(() => {
    if (contextIds.length > 0) {
      setIds(contextIds);
      return;
    }
    let cancelled = false;
    void fallbackIds()
      .then((rows) => { if (!cancelled) setIds(rows); })
      .catch(() => { if (!cancelled) setIds([currentId]); });
    return () => { cancelled = true; };
  }, [contextIds.join(','), currentId, fallbackIds]);

  const index = ids.indexOf(currentId);
  const previousId = index > 0 ? ids[index - 1] : null;
  const nextId = index >= 0 && index < ids.length - 1 ? ids[index + 1] : null;
  const listQuery = params.get('list') ?? '';
  const query = contextIds.length > 0 ? location.search : '';

  return {
    previousId,
    nextId,
    listHref: `${basePath}${listQuery ? `?${listQuery}` : ''}`,
    goPrevious: () => { if (previousId != null) navigate(`${basePath}/${previousId}${query}`); },
    goNext: () => { if (nextId != null) navigate(`${basePath}/${nextId}${query}`); },
  };
};

export const MasterDetailNavigation = ({ navigation }: { navigation: ReturnType<typeof useMasterDetailNavigation> }) => (
  <div className="detail-record-navigation" aria-label="レコード移動">
    <button type="button" className="secondary" disabled={navigation.previousId == null} onClick={navigation.goPrevious}>← 前へ</button>
    <button type="button" className="secondary" disabled={navigation.nextId == null} onClick={navigation.goNext}>次へ →</button>
  </div>
);
