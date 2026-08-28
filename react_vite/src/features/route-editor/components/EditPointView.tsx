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
          onChange={(e) => {
            const value = e.target.value as RoutePoint['type'];
            const preserveDummyBranchFeatureType = point.featureType === 'dummy_branch_waypoint' && value === 'dummy';
            const featureTypeMap: Partial<Record<RoutePoint['type'], NonNullable<RoutePoint['featureType']>>> = {
              sp: 'route_waypoint',
              tp: 'route_waypoint',
              secret: 'route_waypoint',
              fp: 'route_waypoint',
              anrtp: 'route_waypoint',
              ul: 'route_waypoint',
              dummy: 'route_waypoint',
              timed_turnpoint: 'known_time_gate',
              catalogue_turnpoint: 'catalogue_turnpoint',
              circle_center: 'circle_center_marker',
              circle_start: 'circle_start_marker',
              circle_entry: 'circle_entry_marker',
              circle_exit: 'circle_exit_marker',
            };
            updatePoint('type', value);
            if (preserveDummyBranchFeatureType) {
              updatePoint('featureType', 'dummy_branch_waypoint');
            } else if (featureTypeMap[value]) {
              updatePoint('featureType', featureTypeMap[value]);
            }
          }}
        >
          <option value="sp">Start Point</option>
          <option value="tp">Visible Turning Point</option>
          <option value="secret">Secret Point</option>
          <option value="fp">Finish Point</option>
          <option value="dummy">Dummy Point</option>
          <option value="timed_turnpoint">Timed Turnpoint (standalone)</option>
          <option value="ul">Unknown Leg</option>
          <option value="catalogue_turnpoint">Catalogue Turnpoint</option>
          <option value="circle_center">Circle Center</option>
          <option value="circle_start">Circle Start</option>
          <option value="circle_entry">Circle Entry</option>
          <option value="circle_exit">Circle Exit</option>
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

      {point.featureType === 'catalogue_turnpoint' && (
        <div>
          <label className="block text-xs font-semibold text-gray-500 uppercase">Score Value</label>
          <input
            type="number"
            step="0.1"
            className="input input-bordered input-sm w-full"
            value={point.scoreValue ?? ''}
            onChange={(e) => updatePoint('scoreValue', e.target.value === '' ? null : Number(e.target.value))}
            placeholder="Optional"
          />
        </div>
      )}

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
