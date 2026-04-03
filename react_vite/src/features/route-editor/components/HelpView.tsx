import React from 'react';
import { X } from 'lucide-react';

interface HelpViewProps {
    onClose: () => void;
}

const HelpView: React.FC<HelpViewProps> = ({ onClose }) => {
  return (
    <div className="bg-base-100">
      <div className="flex justify-between items-center pb-2 mb-2 border-b border-base-200">
        <h2 className="text-base font-bold">Help & Docs</h2>
        <button onClick={onClose} className="btn btn-ghost btn-xs btn-square">
          <X size={16} />
        </button>
      </div>
      
      <div className="space-y-2">
        <div className="card bg-base-200 shadow-sm compact rounded-box">
          <div className="card-body p-3">
            <h3 className="card-title text-sm border-b border-base-300 pb-1 mb-1">Route Elements</h3>
            <ul className="list-disc pl-3 text-xs space-y-1">
              <li><strong>Waypoints:</strong> Click "Point". First=Start, Last=Finish.</li>
              <li><strong>Gates:</strong> "Landing"/"Take-off" = 2 points.</li>
              <li><strong>Zones:</strong> Polygons. Click 1st point to close.</li>
            </ul>
          </div>
        </div>

        <div className="card bg-info/10 shadow-sm compact rounded-box">
          <div className="card-body p-3">
            <h3 className="card-title text-sm text-info-content border-b border-info/20 pb-1 mb-1">Photo Points</h3>
            <p className="text-xs mb-2">
              "Photo" mode for observations.
            </p>
            <div className="bg-base-100 p-2 rounded border border-info/20 text-xs w-full">
              <strong className="text-error">Constraint: </strong> 
              Must be within <strong>Max Obs Dist</strong> (0.5 NM) of route. This constraint is configurable for this secession in the settings page.
            </div>
          </div>
        </div>

        <div className="card bg-info/10 shadow-sm compact rounded-box">
          <div className="card-body p-3">
            <h3 className="card-title text-sm text-info-content border-b border-info/20 pb-1 mb-1">Secret Points</h3>
            <p className="text-xs mb-2">
              Click leg line in "View" mode. If you want a regular turning point, change the point type to "Waypoint" in the sidebar after selecting the point.
            </p>
            <div className="bg-base-100 p-2 rounded border border-info/20 text-xs w-full">
              <strong className="text-error">Constraint: </strong> 
              Must lie on straight line between waypoints (unless curved).
            </div>
          </div>
        </div>

        <div className="card bg-base-200 shadow-sm compact rounded-box">
          <div className="card-body p-3">
            <h3 className="card-title text-sm border-b border-base-300 pb-1 mb-1">Curved Segments</h3>
            <p className="text-xs">
              Toggle "Add Curved Leg" or select point & "Make Curved". To changed the curvature over a curved leg, select the point after the curved segment while in "view" mode. Drag the control point that becomes visible to adjust the curvature.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HelpView;