import React from 'react';
import { 
  PlusCircle, 
  Navigation, 
  Anchor, 
  Activity,
  Camera,
  Hexagon
} from 'lucide-react';
import { Mode, LatLng } from '../types';

interface ToolbarProps {
    mode: Mode;
    setMode: (mode: Mode) => void;
    tempGatePoint: LatLng | null;
    setTempGatePoint: (point: LatLng | null) => void;
    setTempPolygonPoints: (points: LatLng[]) => void;
}

const Toolbar: React.FC<ToolbarProps> = ({ mode, setMode, tempGatePoint, setTempGatePoint, setTempPolygonPoints }) => {
  const helpText = (() => {
    if (mode === 'view') return "Select a point to edit or drag map.";
    if (mode === 'add_point') return "Click map to place next waypoint.";
    if (mode === 'add_observation') return "Click near route (< 0.5 NM) to add marker.";
    if (mode.includes('landing')) return !tempGatePoint ? "Click start of landing line." : "Click end of landing line.";
    if (mode.includes('takeoff')) return !tempGatePoint ? "Click start of take-off line." : "Click end of take-off line.";
    if (mode === 'add_polygon') return "Click to add points. Click the first point to close loop.";
    return "";
  })();

  return (
    <>
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-base-100/90 backdrop-blur-md shadow-lg rounded-full z-[1000] flex items-center p-1.5 gap-1 border border-base-300">
        <button 
          onClick={() => { setMode('view'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'view' ? 'btn-info' : 'btn-ghost'}`}
        >
          <Navigation size={18} />
          <span>View</span>
        </button>
        
        <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>

        <button 
          onClick={() => { setMode('add_point'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_point' ? 'btn-success' : 'btn-ghost'}`}
        >
          <PlusCircle size={18} />
          <span>Point</span>
        </button>

        <button 
          onClick={() => { setMode('add_observation'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_observation' ? 'btn-warning' : 'btn-ghost'}`}
        >
          <Camera size={18} />
          <span>Photo</span>
        </button>

        <button 
          onClick={() => { setMode('add_polygon'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_polygon' ? 'btn-secondary' : 'btn-ghost'}`}
        >
          <Hexagon size={18} />
          <span>Zone</span>
        </button>

        <button 
          onClick={() => { setMode('add_landing'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode.includes('landing') ? 'btn-primary' : 'btn-ghost'}`}
        >
          <Anchor size={18} />
          <span>Landing</span>
        </button>

        <button 
          onClick={() => { setMode('add_takeoff'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode.includes('takeoff') ? 'btn-warning' : 'btn-ghost'}`}
        >
          <Activity size={18} />
          <span>Take-off</span>
        </button>

      </div>

      <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-[999] pointer-events-none transition-opacity duration-300">
        <div className="bg-base-100/80 backdrop-blur-sm shadow-sm border border-base-200 rounded-full px-4 py-1 text-xs font-medium text-base-content/70">
          {helpText}
        </div>
      </div>
    </>
  );
};

export default Toolbar;