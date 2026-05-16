import React from 'react';
import { X, Trash2 } from 'lucide-react';
import { Polygon } from '../../../types';

interface EditPolygonViewProps {
    polygon: Polygon;
    updatePolygon: (field: keyof Polygon, value: any) => void;
    deletePolygon: () => void;
    onClose: () => void;
}

const EditPolygonView: React.FC<EditPolygonViewProps> = ({ polygon, updatePolygon, deletePolygon, onClose }) => {
  if (!polygon) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Zone</h3>
        <button 
          onClick={onClose} 
          className="btn btn-ghost btn-sm btn-square"
          title="Close"
        >
          <X size={18} />
        </button>
      </div>
      
      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Name</label>
        <input 
          className="input input-bordered input-sm w-full"
          value={polygon.name} 
          onChange={(e) => updatePolygon('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="select select-bordered select-sm w-full"
          value={polygon.type} 
          onChange={(e) => updatePolygon('type', e.target.value)}
        >
          <option value="prohibited">Prohibited (Red)</option>
          <option value="penalty">Penalty (Orange)</option>
          <option value="info">Info (Blue)</option>
        </select>
      </div>

      <div className="text-xs text-gray-500 italic">
        Points: {polygon.points.length}
      </div>

      <button 
        onClick={deletePolygon}
        className="btn btn-outline btn-error btn-sm w-full mt-4 gap-2"
      >
        <Trash2 size={16} /> <span>Delete Zone</span>
      </button>
    </div>
  );
};

export default EditPolygonView;