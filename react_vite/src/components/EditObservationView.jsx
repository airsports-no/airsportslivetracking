import React from 'react';
import { X, Trash2 } from 'lucide-react';
import ObservationThumbnail from './ObservationThumbnail';

const EditObservationView = ({ observation, updateObservation, deleteObservation, onClose }) => {
  if (!observation) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Observation</h3>
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
          value={observation.name} 
          onChange={(e) => updateObservation('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase mb-1">Satellite View (~500m)</label>
        <ObservationThumbnail lat={observation.lat} lng={observation.lng} />
        <p className="text-[10px] text-gray-400 mt-1 text-center">Circle Radius: 100m</p>
      </div>

      <button onClick={deleteObservation} className="w-full mt-4 bg-red-50 text-red-600 border border-red-200 p-2 rounded flex items-center justify-center space-x-2 hover:bg-red-100">
        <Trash2 size={16} /> <span>Delete Marker</span>
      </button>
    </div>
  );
};

export default EditObservationView;