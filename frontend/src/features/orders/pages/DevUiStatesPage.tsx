import { EmptyState, ErrorState, LoadingState } from 'components/common/AsyncState';

export const DevUiStatesPage = () => {
  return (
    <section className="dev-ui-states">
      <div className="card">
        <h2>UI State Gallery (Dev)</h2>
        <p className="subtle">レビュー用に画面状態コンポーネントを一括表示します。</p>
      </div>

      <div className="state-gallery">
        <div className="card">
          <h3>LoadingState</h3>
          <LoadingState title="データを読み込み中" description="しばらくお待ちください。" />
        </div>

        <div className="card">
          <h3>EmptyState</h3>
          <EmptyState
            title="データがありません"
            description="条件を見直すか、データ登録後に再度お試しください。"
            actionLabel="再読み込み"
            onAction={() => window.alert('再読み込みアクション（デモ）')}
          />
        </div>

        <div className="card">
          <h3>ErrorState</h3>
          <ErrorState
            title="データの取得に失敗しました"
            description="APIへ接続できません。backend起動状態を確認してください。"
            actionLabel="再試行"
            onAction={() => window.alert('再試行アクション（デモ）')}
          />
        </div>

        <div className="card">
          <h3>409 Conflict Sample</h3>
          <ErrorState
            title="データの取得に失敗しました"
            description="顧客コードが既に存在します。"
            actionLabel="再試行"
            onAction={() => window.alert('409再試行（デモ）')}
          />
        </div>

        <div className="card">
          <h3>404 Not Found Sample</h3>
          <EmptyState
            title="データがありません"
            description="対象データが見つかりません。一覧から再度選択してください。"
            actionLabel="一覧へ戻る"
            onAction={() => window.alert('一覧へ戻る（デモ）')}
          />
        </div>
      </div>
    </section>
  );
};
