import React from 'react';
import {
  PlusCircle,
  Navigation,
  Anchor,
  Activity,
  Camera,
  EyeOff,
  Hexagon,
  MoveHorizontal,
  Wand2,
  Undo2,
  Redo2,
} from 'lucide-react';
import { Mode, LatLng } from '../../../types';
import { undoShortcutLabels } from '../routeEditorKeys';

interface ToolbarProps {
  mode: Mode;
  setMode: (mode: Mode) => void;
  setTempGatePoint: (point: LatLng | null) => void;
  setTempPolygonPoints: (points: LatLng[]) => void;
  // Back to select mode: stops the tool and a guide step, clears a half-drawn gate or zone (the same as Esc).
  onSelect: () => void;
  openWizard: () => void;
  openGateWidths: () => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
}

const Toolbar: React.FC<ToolbarProps> = ({ mode, setMode, setTempGatePoint, setTempPolygonPoints, onSelect, openWizard, openGateWidths, canUndo, canRedo, onUndo, onRedo }) => {
  const shortcuts = undoShortcutLabels();

  return (
    <>
      <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-base-100/90 backdrop-blur-md shadow-lg rounded-full z-[1000] flex items-center p-1.5 gap-1 border border-base-300">
        <button
          onClick={onSelect}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'view' ? 'btn-info' : 'btn-ghost'}`}
          title="Select mode: click a point to select it, drag it to move it (Esc)"
        >
          <Navigation size={18} />
          <span>Select</span>
        </button>

        <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>

        <button
          onClick={openWizard}
          className="btn btn-sm rounded-full gap-2 border-none btn-primary"
        >
          <Wand2 size={18} />
          <span>Task Wizard</span>
        </button>

        <button
          onClick={() => { setMode('add_point'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_point' ? 'btn-success' : 'btn-ghost'}`}
        >
          <PlusCircle size={18} />
          <span>Backbone</span>
        </button>

        <button
          onClick={() => { setMode('add_catalogue_turnpoint'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_catalogue_turnpoint' ? 'btn-secondary' : 'btn-ghost'}`}
        >
          <PlusCircle size={18} />
          <span>Catalogue</span>
        </button>

        <button
          onClick={() => { setMode('add_hidden_gate'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_hidden_gate' ? 'btn-info' : 'btn-ghost'}`}
          title="Hidden gate: click a leg of the route to place one"
        >
          <EyeOff size={18} />
          <span>Hidden gate</span>
        </button>

        <button
          onClick={() => { setMode('add_observation'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_observation' ? 'btn-warning' : 'btn-ghost'}`}
        >
          <Camera size={18} />
          <span>Photo</span>
        </button>

        <button
          onClick={() => { setMode('add_polygon'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode === 'add_polygon' ? 'btn-secondary' : 'btn-ghost'}`}
        >
          <Hexagon size={18} />
          <span>Zone</span>
        </button>

        <button
          onClick={() => { setMode('add_landing'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode.includes('landing') ? 'btn-primary' : 'btn-ghost'}`}
        >
          <Anchor size={18} />
          <span>Landing</span>
        </button>

        <button
          onClick={() => { setMode('add_takeoff'); setTempGatePoint(null); setTempPolygonPoints([]); }}
          className={`btn btn-sm rounded-full gap-2 border-none ${mode.includes('takeoff') ? 'btn-warning' : 'btn-ghost'}`}
        >
          <Activity size={18} />
          <span>Take-off</span>
        </button>

        <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>

        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="btn btn-sm btn-circle border-none btn-ghost"
          title={`Undo (${shortcuts.undo})`}
          aria-label="Undo"
        >
          <Undo2 size={18} />
        </button>

        <button
          onClick={onRedo}
          disabled={!canRedo}
          className="btn btn-sm btn-circle border-none btn-ghost"
          title={`Redo (${shortcuts.redo})`}
          aria-label="Redo"
        >
          <Redo2 size={18} />
        </button>

        <div className="w-px h-5 bg-gray-300 mx-1 self-center"></div>

        <button
          onClick={openGateWidths}
          className="btn btn-sm rounded-full gap-2 border-none btn-ghost"
          title="Set the width of several gates at once"
        >
          <MoveHorizontal size={18} />
          <span>Gate widths</span>
        </button>
      </div>
    </>
  );
};

export default Toolbar;
