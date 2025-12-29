import React from 'react';
import { X, Trash2 } from 'lucide-react';

const EditGateView = ({ gate, updateGate, deleteGate, onClose }) => {
  if (!gate) return null;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h3 className="font-bold text-lg">Edit Gate</h3>
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
          value={gate.name} 
          onChange={(e) => updateGate('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="select select-bordered select-sm w-full"
          value={gate.type} 
          onChange={(e) => updateGate('type', e.target.value)}
        >
          <option value="landing">Landing Gate</option>
          <option value="takeoff">Take-off Gate</option>
        </select>
      </div>

      <button 
        onClick={deleteGate}
        className="btn btn-outline btn-error btn-sm w-full mt-4 gap-2"
      >
        <Trash2 size={16} /> <span>Delete Gate</span>
      </button>
    </div>
  );
};

export default EditGateView;