type AsyncStateProps = {
  title?: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
};

const StateAction = ({ actionLabel, onAction }: Pick<AsyncStateProps, 'actionLabel' | 'onAction'>) => {
  if (!actionLabel || !onAction) return null;
  return (
    <div className="state-actions">
      <button type="button" className="secondary" onClick={onAction}>{actionLabel}</button>
    </div>
  );
};

export const LoadingState = ({ title = '読み込み中', description = 'しばらくお待ちください。' }: AsyncStateProps) => (
  <div className="state-box loading">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
  </div>
);

export const EmptyState = ({
  title = 'データがありません',
  description = '条件を見直すか、データ登録後に再度お試しください。',
  actionLabel,
  onAction,
}: AsyncStateProps) => (
  <div className="state-box empty">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
    <StateAction actionLabel={actionLabel} onAction={onAction} />
  </div>
);

export const ErrorState = ({
  title = '表示に失敗しました',
  description = '時間をおいて再試行してください。',
  actionLabel = '再試行',
  onAction,
}: AsyncStateProps) => (
  <div className="state-box error">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
    <StateAction actionLabel={actionLabel} onAction={onAction} />
  </div>
);
