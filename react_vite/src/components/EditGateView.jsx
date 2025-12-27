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
          value={gate.name} 
          onChange={(e) => updateGate('name', e.target.value)}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase">Type</label>
        <select 
          className="w-full border rounded p-2"
          value={gate.type} 
          onChange={(e) => updateGate('type', e.target.value)}
        >
          <option value="landing">Landing Gate</option>
          <option value="takeoff">Take-off Gate</option>
        </select>
      </div>

      <button 
        onClick={deleteGate}
        className="w-full mt-4 bg-red-50 text-red-600 border border-red-200 p-2 rounded flex items-center justify-center space-x-2 hover:bg-red-100"
      >
        <Trash2 size={16} /> <span>Delete Gate</span>
      </button>
    </div>
  );
};

export default EditGateView;