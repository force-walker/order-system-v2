type PdfExportButtonProps = {
  busy: boolean;
  disabled?: boolean;
  idleLabel?: string;
  busyLabel?: string;
  onClick: () => void;
};

export const PdfExportButton = ({
  busy,
  disabled = false,
  idleLabel = 'PDF出力',
  busyLabel = 'ダウンロード中...',
  onClick,
}: PdfExportButtonProps) => (
  <button type="button" className="secondary" onClick={onClick} disabled={disabled || busy}>
    {busy ? busyLabel : idleLabel}
  </button>
);
