import React from 'react';
import { 
  PlusCircle, 
  Navigation, 
  Anchor, 
  Activity,
  Camera,
  Hexagon
} from 'lucide-react';

const Toolbar = ({ mode, setMode, tempGatePoint, setTempGatePoint, setTempPolygonPoints }) => {
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
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-md shadow-lg rounded-full z-[1000] flex items-center p-1.5 gap-1 border border-gray-200">
        <button 
          onClick={() => { setMode('view'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-4 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode === 'view' ? 'bg-blue-100 text-blue-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <Navigation size={18} />
          <span>View</span>
        </button>
        
        <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>

        <button 
          onClick={() => { setMode('add_point'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-3 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode === 'add_point' ? 'bg-green-100 text-green-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <PlusCircle size={18} />
          <span>Point</span>
        </button>

        <button 
          onClick={() => { setMode('add_observation'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-3 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode === 'add_observation' ? 'bg-yellow-100 text-yellow-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <Camera size={18} />
          <span>Photo</span>
        </button>

        <button 
          onClick={() => { setMode('add_polygon'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-3 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode === 'add_polygon' ? 'bg-pink-100 text-pink-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <Hexagon size={18} />
          <span>Zone</span>
        </button>

        <button 
          onClick={() => { setMode('add_landing'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-3 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode.includes('landing') ? 'bg-purple-100 text-purple-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <Anchor size={18} />
          <span>Landing</span>
        </button>

        <button 
          onClick={() => { setMode('add_takeoff'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`px-3 py-2 rounded-full flex items-center gap-2 text-sm font-medium transition-all ${mode.includes('takeoff') ? 'bg-orange-100 text-orange-700 shadow-sm' : 'hover:bg-gray-100 text-gray-600'}`}
        >
          <Activity size={18} />
          <span>Take-off</span>
        </button>

      </div>

      <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-[999] pointer-events-none transition-opacity duration-300">
        <div className="bg-white/80 backdrop-blur-sm shadow-sm border border-gray-200 rounded-full px-4 py-1 text-xs font-medium text-gray-600">
          {helpText}
        </div>
      </div>
    </>
  );
};

export default Toolbar;