import React from 'react';
import { X } from 'lucide-react';

const HelpView = ({ onClose }) => {
  return (
    <div className="p-4 space-y-4">
      <div className="flex justify-between items-center border-b pb-2">
        <h2 className="text-lg font-bold">Help & Documentation</h2>
        <button onClick={onClose} className="text-gray-500 hover:text-gray-700">
          <X size={20} />
        </button>
      </div>
      
      <div className="space-y-4 text-sm text-gray-700">
        <section>
          <h3 className="font-bold text-gray-900 border-b border-gray-200 mb-1">Route Elements</h3>
          <ul className="list-disc pl-4 space-y-1">
            <li><strong>Waypoints:</strong> Click "Point" to add. First is Start (SP), last is Finish (FP).</li>
            <li><strong>Gates:</strong> "Landing" and "Take-off" modes create gates defined by two points.</li>
            <li><strong>Zones:</strong> "Zone" mode creates polygons. Click the first point to close the loop.</li>
          </ul>
        </section>

        <section className="bg-blue-50 p-3 rounded border border-blue-100">
          <h3 className="font-bold text-blue-900 mb-1">Photo Points (Observations)</h3>
          <p className="mb-2">
            Add markers using the "Photo" mode to indicate observation tasks.
          </p>
          <div className="text-xs bg-white p-2 rounded border border-blue-200">
            <strong className="text-red-600">Constraint:</strong> 
            Markers must be located within the configured <strong>Max Observation Distance</strong> (default 0.5 NM) of the route path. 
            The editor prevents placing markers too far away and prevents moving route legs if it would leave a marker "orphaned" outside this distance.
          </div>
        </section>

        <section className="bg-blue-50 p-3 rounded border border-blue-100">
          <h3 className="font-bold text-blue-900 mb-1">Secret Points</h3>
          <p className="mb-2">
            Create secret timing points by clicking directly on a route leg line while in "View" mode.
          </p>
          <div className="text-xs bg-white p-2 rounded border border-blue-200">
            <strong className="text-red-600">Constraint:</strong> 
            Secret points are strictly enforced to lie on a <strong>straight line</strong> between the previous and next waypoints. 
            Moving a secret point will snap it to this line. This constraint is disabled if the segment is curved.
          </div>
        </section>

        <section>
          <h3 className="font-bold text-gray-900 border-b border-gray-200 mb-1">Curved Segments</h3>
          <p>
            Route legs can be curved. Toggle "Add Curved Leg" when creating points, or select an existing point and click "Make Curved" to adjust the path.
          </p>
        </section>
      </div>
    </div>
  );
};

export default HelpView;