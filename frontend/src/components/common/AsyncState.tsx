type AsyncStateProps = {
  title: string;
  description?: string;
};

export const LoadingState = ({ title, description }: AsyncStateProps) => (
  <div className="state-box loading">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
  </div>
);

export const EmptyState = ({ title, description }: AsyncStateProps) => (
  <div className="state-box empty">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
  </div>
);

export const ErrorState = ({ title, description }: AsyncStateProps) => (
  <div className="state-box error">
    <h3>{title}</h3>
    {description ? <p>{description}</p> : null}
  </div>
);
