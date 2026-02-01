import React, { useState, useEffect } from 'react';
import { X, Trash2 } from 'lucide-react';
import ObservationThumbnail from './ObservationThumbnail';
import { RoutePoint } from '../../../types';

interface EditPointViewProps {
    point: RoutePoint;
    updatePoint: (field: keyof RoutePoint, value: any) => void;
    deletePoint: () => void;
    moveOrder: (direction: "up" | "down") => void;
    onClose: () => void;
}

const EditPointView: React.FC<EditPointViewProps> = ({ point, updatePoint, deletePoint, moveOrder, onClose }) => {
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
          <button onClick={() => moveOrder('up')} className="btn btn-ghost btn-xs btn-square" title="Move Up">↑</button>
          <button onClick={() => moveOrder('down')} className="btn btn-ghost btn-xs btn-square" title="Move Down">↓</button>
          <div className="w-px h-4 bg-gray-300 mx-1"></div>
          <button 
            onClick={onClose} 
            className="btn btn-ghost btn-sm btn-square"
            title="Close"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Name</label>
        <input 
          className="input input-bordered input-sm w-full"
          value={point.name} 
          onChange={(e) => updatePoint('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="select select-bordered select-sm w-full"
          value={point.type} 
          onChange={(e) => updatePoint('type', e.target.value)}
        >
          <option value="sp">Start Point</option>
          <option value="tp">Visible Turning Point</option>
          <option value="secret">Secret Point</option>
          <option value="fp">Finish Point</option>
          <option value="circle_center">Circle Center</option>
          <option value="circle_entry">Circle Entry</option>
          <option value="free_point">Free Point</option>
          <option value="speed_start">Speed Section Start</option>
          <option value="speed_end">Speed Section End</option>
        </select>
        {point.type === 'secret' && (
          <p className="text-xs text-amber-600 mt-1">
            Must be on a straight line between adjacent points.
          </p>
        )}
      </div>

      {point.type === 'circle_center' && (
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase">Radius (m)</label>
          <input 
            type="number"
            className="input input-bordered input-sm w-full"
            value={point.radius || 0} 
            onChange={(e) => updatePoint('radius', parseFloat(e.target.value))}
          />
        </div>
      )}

      {point.type === 'free_point' && (
        <div>
          <p className="text-xs text-info italic">Score is defined in the Task Scorecard.</p>
        </div>
      )}

      {['circle_center', 'circle_entry', 'speed_start', 'speed_end'].includes(point.type) && (
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase">Group ID</label>
          <input 
            className="input input-bordered input-sm w-full"
            value={point.groupId || ''} 
            onChange={(e) => updatePoint('groupId', e.target.value)}
          />
        </div>
      )}

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Satellite View</label>
        <ObservationThumbnail lat={point.lat} lng={point.lng} type="pin" />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Width (NM)</label>
        <input 
          type="number"
          step="0.01"
          className="input input-bordered input-sm w-full"
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
        <label className="flex items-center space-x-2 cursor-pointer">
          <input 
            type="checkbox" 
            className="checkbox checkbox-sm"
            checked={point.isTiming}
            onChange={(e) => updatePoint('isTiming', e.target.checked)}
          />
          <span className="text-sm">Timing Check</span>
        </label>
        <label className="flex items-center space-x-2 cursor-pointer">
          <input 
            type="checkbox" 
            className="checkbox checkbox-sm"
            checked={point.isPassing}
            onChange={(e) => updatePoint('isPassing', e.target.checked)}
          />
          <span className="text-sm">Passing Check</span>
        </label>
      </div>

      <button 
        onClick={deletePoint}
        className="btn btn-outline btn-error btn-sm w-full mt-4 gap-2"
      >
        <Trash2 size={16} /> <span>Delete Point</span>
      </button>
    </div>
  );
};

export default EditPointView;