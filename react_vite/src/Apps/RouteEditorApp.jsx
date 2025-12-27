import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'leaflet/dist/leaflet.css';
import './routeeditor.css'
import RouteEditor from '../containers/RouteEditor.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <RouteEditor />
  </StrictMode>,
)
