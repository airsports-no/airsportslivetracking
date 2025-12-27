import React, { useState, useEffect } from 'react';
import { X, Trash2 } from 'lucide-react';
import ObservationThumbnail from './ObservationThumbnail';

const EditPointView = ({ point, updatePoint, deletePoint, moveOrder, onClose }) => {
  const [widthInput, setWidthInput] = useState(point ? (point.width / 1852).toFixed(2) : "0.00");

  useEffect(() => {
    if (point) setWidthInput((point.width / 1852).toFixed(2));
  }, [point?.id]);

  if (!point) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Point</h3>
        <div className="flex items-center space-x-1">
          <button onClick={() => moveOrder('up')} className="p-1 hover:bg-gray-100 rounded" title="Move Up">↑</button>
          <button onClick={() => moveOrder('down')} className="p-1 hover:bg-gray-100 rounded" title="Move Down">↓</button>
          <div className="w-px h-4 bg-gray-300 mx-1"></div>
          <button 
            onClick={onClose} 
            className="p-1 hover:bg-gray-100 rounded text-gray-500"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Name</label>
        <input 
          className="w-full border rounded p-2"
          value={point.name} 
          onChange={(e) => updatePoint('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="w-full border rounded p-2"
          value={point.type} 
          onChange={(e) => updatePoint('type', e.target.value)}
        >
          <option value="sp">Start Point</option>
          <option value="tp">Visible Turning Point</option>
          <option value="secret">Secret Point</option>
          <option value="fp">Finish Point</option>
        </select>
        {point.type === 'secret' && (
          <p className="text-xs text-amber-600 mt-1">
            Must be on a straight line between adjacent points.
          </p>
        )}
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Satellite View</label>
        <ObservationThumbnail lat={point.lat} lng={point.lng} type="pin" />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Width (NM)</label>
        <input 
          type="number"
          step="0.01"
          className="w-full border rounded p-2"
          value={widthInput} 
          onChange={(e) => {
            setWidthInput(e.target.value);
            const val = parseFloat(e.target.value);
            if (!isNaN(val)) {
              updatePoint('width', Math.round(val * 1852));
            }
          }}
        />
      </div>

      <div className="space-y-2 pt-2">
        <label className="flex items-center space-x-2">
          <input 
            type="checkbox" 
            checked={point.isTiming}
            onChange={(e) => updatePoint('isTiming', e.target.checked)}
          />
          <span className="text-sm">Timing Check</span>
        </label>
        <label className="flex items-center space-x-2">
          <input 
            type="checkbox" 
            checked={point.isPassing}
            onChange={(e) => updatePoint('isPassing', e.target.checked)}
          />
          <span className="text-sm">Passing Check</span>
        </label>
      </div>

      <button 
        onClick={deletePoint}
        className="w-full mt-4 bg-red-50 text-red-600 border border-red-200 p-2 rounded flex items-center justify-center space-x-2 hover:bg-red-100"
      >
        <Trash2 size={16} /> <span>Delete Point</span>
      </button>
    </div>
  );
};

export default EditPointView;