import React, { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css';
import './frontendapp.css'
import { FrontendRouter } from './FrontendRouter';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <FrontendRouter />
  </StrictMode>,
)
