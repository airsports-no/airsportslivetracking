import React, { StrictMode, useState, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import 'leaflet/dist/leaflet.css';
import './frontendapp.css';
import { FrontendRouter } from './FrontendRouter';
import { initUrls } from './urls';
import { Loading } from './features/route-editor/components/basicComponents';

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

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
