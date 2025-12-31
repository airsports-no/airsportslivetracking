import React, { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css';
import './routeeditorapp.css'
import { EditableRouteRouter } from './EditableRouteRouter';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <EditableRouteRouter />
  </StrictMode>,
)
