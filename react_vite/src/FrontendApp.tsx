import React, { StrictMode, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import * as Sentry from '@sentry/react';
import 'leaflet/dist/leaflet.css';
import './frontendapp.css';
import { FrontendRouter } from './FrontendRouter';
import { initUrls } from './urls';
import { Loading } from './features/route-editor/components/basicComponents';

// sentryDsn/release are injected server-side into document.configuration (base_tailwind.html,
// from display.context_processors.sentry_settings) rather than baked in at Vite build time -
// this bundle is built once and deployed to every environment, so the DSN can't be a build-time
// constant. Sentry stays inactive (no-op) whenever the DSN is unset, e.g. local dev.
if (document.configuration.sentryDsn) {
  Sentry.init({
    dsn: document.configuration.sentryDsn,
    release: document.configuration.release || undefined,
    sendDefaultPii: false,
  });
}

const App = () => {
  const [urlsInitialized, setUrlsInitialized] = useState(false);

  useEffect(() => {
    initUrls().then(() => {
      setUrlsInitialized(true);
    });
  }, []);

  if (!urlsInitialized) {
    return <div className="w-screen h-screen flex items-center justify-center"><Loading /></div>;
  }

  return <FrontendRouter />;
};

function ErrorFallback() {
  return (
    <div className="w-screen h-screen flex flex-col items-center justify-center gap-4">
      <p>Something went wrong. Please reload the page.</p>
      <button className="btn btn-primary" onClick={() => window.location.reload()}>
        Reload
      </button>
    </div>
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={<ErrorFallback />}>
      <App />
    </Sentry.ErrorBoundary>
  </StrictMode>,
)
