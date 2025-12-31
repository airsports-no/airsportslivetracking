import React from 'react';
import { X, Trash2 } from 'lucide-react';
import ObservationThumbnail from './ObservationThumbnail';
import { ObservationMarker } from '../types';

interface EditObservationViewProps {
    observation: ObservationMarker;
    updateObservation: (field: keyof ObservationMarker, value: any) => void;
    deleteObservation: () => void;
    onClose: () => void;
}

const EditObservationView: React.FC<EditObservationViewProps> = ({ observation, updateObservation, deleteObservation, onClose }) => {
  if (!observation) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Observation</h3>
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
          value={observation.name} 
          onChange={(e) => updateObservation('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Satellite View (~500m)</label>
        <ObservationThumbnail lat={observation.lat} lng={observation.lng} />
        <p className="text-[10px] text-gray-400 mt-1 text-center">Circle Radius: 100m</p>
      </div>

      <button onClick={deleteObservation} className="btn btn-outline btn-error btn-sm w-full mt-4 gap-2">
        <Trash2 size={16} /> <span>Delete Marker</span>
      </button>
    </div>
  );
};

export default EditObservationView;