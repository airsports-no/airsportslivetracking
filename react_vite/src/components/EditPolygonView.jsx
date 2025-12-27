import React from 'react';
import { X, Trash2 } from 'lucide-react';

const EditPolygonView = ({ polygon, updatePolygon, deletePolygon, onClose }) => {
  if (!polygon) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Zone</h3>
        <button 
          onClick={onClose} 
          className="p-1 hover:bg-gray-100 rounded text-gray-500"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>
      
      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Name</label>
        <input 
          className="w-full border rounded p-2"
          value={polygon.name} 
          onChange={(e) => updatePolygon('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="w-full border rounded p-2"
          value={polygon.type} 
          onChange={(e) => updatePolygon('type', e.target.value)}
        >
          <option value="prohibited">Prohibited (Red)</option>
          <option value="penalty">Penalty (Orange)</option>
          <option value="info">Info (Blue)</option>
          <option value="waypoint">Waypoint (Purple)</option>
        </select>
      </div>

      <div className="text-xs text-gray-500 italic">
        Points: {polygon.points.length}
      </div>

      <button 
        onClick={deletePolygon}
        className="w-full mt-4 bg-red-50 text-red-600 border border-red-200 p-2 rounded flex items-center justify-center space-x-2 hover:bg-red-100"
      >
        <Trash2 size={16} /> <span>Delete Zone</span>
      </button>
    </div>
  );
};

export default EditPolygonView;