import React from 'react';
import { X } from 'lucide-react';

interface HelpViewProps {
  onClose: () => void;
}

interface HelpSectionProps {
  title: string;
  tone?: 'plain' | 'info';
  children: React.ReactNode;
}

const HelpSection: React.FC<HelpSectionProps> = ({ title, tone = 'plain', children }) => (
  <div className={`card ${tone === 'info' ? 'bg-info/10' : 'bg-base-200'} shadow-sm compact rounded-box`}>
    <div className="card-body p-3">
      <h3 className="card-title text-sm border-b border-base-300 pb-1 mb-1">{title}</h3>
      {children}
    </div>
  </div>
);

const Constraint: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="bg-base-100 p-2 rounded border border-info/20 text-xs w-full">
    <strong className="text-error">Constraint: </strong>
    {children}
  </div>
);

const HelpView: React.FC<HelpViewProps> = ({ onClose }) => {
  return (
    <div className="bg-base-100">
      <div className="flex justify-between items-center pb-2 mb-2 border-b border-base-200">
        <h2 className="text-base font-bold">Help & Docs</h2>
        <button onClick={onClose} className="btn btn-ghost btn-xs btn-square" aria-label="Close help" title="Close help">
          <X size={16} />
        </button>
      </div>

      <div className="space-y-2">
        <HelpSection title="Starting a route">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li>A new route opens with the question "What is this route for?". Choose a task and the guide opens on it, or choose "Build without a guide" and place everything yourself.</li>
            <li>Open the guide later with <strong>Task Wizard</strong> in the toolbar. You can change the task there and close the guide at any time. Closing it never changes the route.</li>
          </ul>
        </HelpSection>

        <HelpSection title="The guide">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li>Each step is something the task needs. Its button starts the tool that places it, and the step is ticked when the route meets it.</li>
            <li>A step with a fixed number of elements ends by itself when the last one is placed, and the next unmet step starts.</li>
            <li>A step without a fixed number shows <strong>Done, next step</strong>. Press it when you have placed enough.</li>
            <li>Optional steps are only started from the list.</li>
            <li>The guide helps, it does not lock: you can still edit any point by hand.</li>
          </ul>
        </HelpSection>

        <HelpSection title="Modes, Select and Esc">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li><strong>Select</strong> is the normal mode. Click a point to select it, drag it to move it. The cursor is an arrow.</li>
            <li>In every placing mode (waypoints, hidden gate, photos, zones, gates, and the guide's tools) a banner over the map says what a click does, and the cursor is a crosshair.</li>
            <li>Press <strong>Esc</strong>, or the stop button in the banner, to go back to Select.</li>
          </ul>
        </HelpSection>

        <HelpSection title="Undo and redo">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li>Ctrl+Z undoes and Ctrl+Shift+Z (or Ctrl+Y) redoes the last change to points, gates, photos and zones. The toolbar has buttons for both.</li>
            <li>A drag is one step. Undo also brings back what the editor removed because a leg changed.</li>
          </ul>
        </HelpSection>

        <HelpSection title="Waypoints">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li>Choose "Point" and click the map. The first waypoint is the start, the last is the finish.</li>
            <li>The blue dot in the middle of a straight leg adds a waypoint when you drag it. Pressing it without dragging does nothing.</li>
            <li>To change what a placed point is (a known time gate, circle marker, catalogue turn point or unknown-leg point), select it and use the point editor.</li>
          </ul>
        </HelpSection>

        <HelpSection title="Hidden gates" tone="info">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li>Choose "Hidden gate" in the toolbar, then click a leg of the route to place one. The tool stays on for more gates. Press Esc to stop. In Select mode a click on a leg does nothing.</li>
            <li>On a curved leg the gate sits on the curve. The curve is split in two there without changing its shape. A click too close to the end of the leg is refused.</li>
            <li>The newly placed gate pulses briefly so you can see where it went.</li>
          </ul>
          <Constraint>
            A hidden gate cannot bend the route. When a leg changes (a waypoint at either end is moved, deleted or added, or the curve is reshaped), the hidden gates on it are removed. The editor lists what it removed, and Undo brings it back. While you drag, the gates that would be removed are shown faded.
          </Constraint>
          <p className="text-xs">
            When a hidden gate leaves a curve, the parts of the curve become one curve again. If you reshaped one part, the joined curve follows the shape you gave it.
          </p>
        </HelpSection>

        <HelpSection title="Curved legs">
          <p className="text-xs">
            Tick "Add Curved Leg" while placing waypoints, or select the point at the end of a leg and choose "Make Curved". To change the curve, select that point in Select mode and drag the control point that appears.
          </p>
        </HelpSection>

        <HelpSection title="Photos" tone="info">
          <p className="text-xs mb-2">
            Choose "Photo" and click the map where the photo was taken.
          </p>
          <Constraint>
            A photo must be within <strong>Max Obs Dist</strong> (0.5 NM unless you change it in the settings) of the route. If a change to the route leaves a photo farther away than that, the photo is removed and the editor tells you.
          </Constraint>
        </HelpSection>

        <HelpSection title="Zones and gates">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li><strong>Zone:</strong> click the map to add corners and click the first corner to close it. Drag a corner to move it, or drag the zone to move all of it.</li>
            <li><strong>Landing</strong> and <strong>Take-off</strong> gates take two clicks, one for each end of the line.</li>
          </ul>
        </HelpSection>

        <HelpSection title="Made for and Also suitable for">
          <ul className="list-disc pl-3 text-xs space-y-1">
            <li><strong>Made for</strong> is what you chose: the task picked in the guide plus the task types you tick in the route settings.</li>
            <li><strong>Also suitable for</strong> is what the route's content happens to meet. It is worked out for you and never changes what the route is made for.</li>
            <li>The route list shows both on each route and can filter by either.</li>
          </ul>
        </HelpSection>
      </div>
    </div>
  );
};

export default HelpView;
