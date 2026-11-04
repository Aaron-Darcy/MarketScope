import { Link } from 'react-router';

import { useDocumentTitle } from '../components/ui';

export function NotFound({
  message = 'There is no page at this address.',
}: {
  readonly message?: string;
}) {
  useDocumentTitle('Not found');
  return (
    <div className="container not-found">
      <div className="not-found-code">404</div>
      <h1>Nothing here</h1>
      <p>{message}</p>
      <Link to="/" className="button button-primary">
        Back to the overview
      </Link>
    </div>
  );
}
