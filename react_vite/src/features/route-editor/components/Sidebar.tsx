import React from 'react';
import { Link } from 'react-router-dom';
import {
  Save,
  Settings,
  HelpCircle,
  X,
  RefreshCcw,
} from 'lucide-react';
import EditPointView from './EditPointView';
import EditGateView from './EditGateView';
import EditObservationView from './EditObservationView';
import EditPolygonView from './EditPolygonView';
import RouteListView from './RouteListView';
import HelpView from './HelpView';
import TaskWizardPanel from './TaskWizardPanel';
import { RoutePoint, Gate, ObservationMarker, Polygon, SelectionType } from '../../../types';

interface SidebarProps {
  routePoints: RoutePoint[];
  standalonePoints: RoutePoint[];
  gates: Gate[];
  observationMarkers: ObservationMarker[];
  polygons: Polygon[];
  selectedId: string | null;
  selectionType: SelectionType | null;
  validationErrors: string[];
  showCorridor: boolean;
  setShowCorridor: (show: boolean) => void;
  hideLabels: boolean;
  setHideLabels: (hide: boolean) => void;
  setSelectedId: (id: string | null) => void;
  setSelectionType: (type: SelectionType | null) => void;
  updateSelectedPoint: (field: keyof RoutePoint, value: any) => void;
  updateSelectedGate: (field: keyof Gate, value: any) => void;
  updateSelectedObservation: (field: keyof ObservationMarker, value: any) => void;
  updateSelectedPolygon: (field: keyof Polygon, value: any) => void;
  deleteSelected: () => void;
  movePointOrder: (direction: "up" | "down") => void;
  handleSave: () => void;
  handleReverseRoute: () => void;
  handleRenumberWaypoints: () => void;
  maxObsDist: number;
  setMaxObsDist: (dist: number) => void;
  routeName: string;
  setRouteName: (name: string) => void;
  isAuthenticated: boolean;
  isDirty: boolean;
  totalLength: number;
  selectedTaskTemplateId: string | null;
  setSelectedTaskTemplateId: (id: string | null) => void;
  startWizardStep: (stepKey: string) => void;
  currentWizardActionLabel: string | null;
  visibleTaskTypeGroups?: string[];
}

const Sidebar: React.FC<SidebarProps> = ({
  routePoints,
  standalonePoints,
  gates,
  observationMarkers,
  polygons,
  selectedId,
  selectionType,
  validationErrors,
  showCorridor,
  setShowCorridor,
  hideLabels,
  setHideLabels,
  setSelectedId,
  setSelectionType,
  updateSelectedPoint,
  updateSelectedGate,
  updateSelectedObservation,
  updateSelectedPolygon,
  deleteSelected,
  movePointOrder,
  handleSave,
  handleReverseRoute,
  handleRenumberWaypoints,
  maxObsDist,
  setMaxObsDist,
  routeName,
  setRouteName,
  isAuthenticated,
  isDirty,
  totalLength,
  selectedTaskTemplateId,
  setSelectedTaskTemplateId,
  startWizardStep,
  currentWizardActionLabel,
  visibleTaskTypeGroups,
}) => {
  const renderContent = () => {
    const selectedPoint = routePoints.find(p => p.id === selectedId);
    const selectedGate = gates.find(g => g.id === selectedId);
    const selectedObs = observationMarkers.find(m => m.id === selectedId);
    const selectedPolygon = polygons?.find(p => p.id === selectedId);

    if ((selectionType === 'point' || selectionType === 'standalone_point') && selectedPoint) {
      return <EditPointView
        point={selectedPoint}
        updatePoint={updateSelectedPoint}
        deletePoint={deleteSelected}
        moveOrder={movePointOrder}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'gate' && selectedGate) {
      return <EditGateView
        gate={selectedGate}
        updateGate={updateSelectedGate}
        deleteGate={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'observation' && selectedObs) {
      return <EditObservationView
        observation={selectedObs}
        updateObservation={updateSelectedObservation}
        deleteObservation={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'polygon' && selectedPolygon) {
      return <EditPolygonView
        polygon={selectedPolygon}
        updatePolygon={updateSelectedPolygon}
        deletePolygon={deleteSelected}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'wizard') {
      return <TaskWizardPanel
        selectedTaskTemplateId={selectedTaskTemplateId}
        setSelectedTaskTemplateId={setSelectedTaskTemplateId}
        visibleTaskTypeGroups={visibleTaskTypeGroups}
        routePoints={routePoints}
        standalonePoints={standalonePoints}
        gates={gates}
        observationMarkers={observationMarkers}
        polygons={polygons}
        startWizardStep={startWizardStep}
        currentWizardActionLabel={currentWizardActionLabel}
        onClose={() => { setSelectedId(null); setSelectionType(null); }}
      />;
    }

    if (selectionType === 'settings') {
      return (
        <div className="p-4 space-y-4">
          <div className="flex items-center justify-between border-b pb-2">
            <h2 className="text-lg font-bold">Settings</h2>
            <button onClick={() => setSelectionType(null)} className="btn btn-ghost btn-sm btn-square">
              <X size={20} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="showCorridor"
              checked={showCorridor}
              onChange={(e) => setShowCorridor(e.target.checked)}
              className="checkbox checkbox-sm checkbox-primary"
            />
            <label htmlFor="showCorridor" className="text-sm font-medium text-gray-700">Show Corridor</label>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="hideLabels"
              checked={hideLabels}
              onChange={(e) => setHideLabels(e.target.checked)}
              className="checkbox checkbox-sm checkbox-primary"
            />
            <label htmlFor="hideLabels" className="text-sm font-medium text-gray-700">Hide Labels</label>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-700">
              Max Observation Distance
            </label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                step="0.1"
                value={parseFloat((maxObsDist / 1852).toFixed(2))}
                onChange={(e) => setMaxObsDist(Number(e.target.value) * 1852)}
                className="input input-bordered input-sm w-full"
              />
              <span className="text-sm text-gray-500">NM</span>
            </div>
            <p className="text-xs text-gray-500">
              Default: 0.5 NM. Maximum distance a photo point can be from the route.
            </p>
          </div>
        </div>
      );
    }

    if (selectionType === 'help') {
      return <HelpView onClose={() => { setSelectedId(null); setSelectionType(null); }} />;
    }

    return <RouteListView
      routePoints={routePoints}
      standalonePoints={standalonePoints}
      gates={gates}
      observationMarkers={observationMarkers}
      polygons={polygons}
      validationErrors={validationErrors}
      onSelect={(id: string, type: SelectionType) => { setSelectedId(id); setSelectionType(type); }}
    />;
  };

  return (
    <div className="h-full flex flex-col bg-base-100 border-r">
      <div className="flex-1 overflow-y-auto p-4">
        <input
          type="text"
          value={routeName}
          onChange={(e) => setRouteName(e.target.value)}
          placeholder="Route Name"
          className="input input-bordered w-full mb-4 text-lg font-bold"
        />

        <div className="flex flex-col mb-6 p-4 bg-base-200/50 rounded-xl border border-base-300">
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-sm font-bold text-gray-500 uppercase">Total Route Length</span>
            <span className="text-sm font-bold font-black text-primary">{(totalLength / 1852).toFixed(2)}</span>
            <span className="text-sm font-bold opacity-70">NM</span>
          </div>
        </div>

        {renderContent()}
      </div>

      <div className="p-4 border-t bg-base-200 space-y-2">
        {isAuthenticated ? (
          <div className="flex flex-col gap-2">
            <div className="flex space-x-2">
              <Link
                to="/routeeditor/"
                onClick={(e) => {
                  if (isDirty && !confirm("Route has unsaved changes. Leave anyway?")) {
                    e.preventDefault();
                  }
                }}
                className="btn btn-neutral btn-sm"
              >
                Back
              </Link>
              <button
                onClick={handleSave}
                className="btn btn-primary btn-sm flex-1 gap-2"
              >
                <Save size={14} /> <span>Save Route</span>
              </button>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={handleReverseRoute}
                className="btn btn-neutral btn-sm flex-1"
                title="Reverse Route"
              >
                <RefreshCcw size={14} /> <span>Reverse</span>
              </button>
              <button
                onClick={handleRenumberWaypoints}
                className="btn btn-neutral btn-sm flex-1"
                title="Renumber Waypoints"
              >
                <RefreshCcw size={14} /> <span>Renumber</span>
              </button>
              <button
                onClick={() => { setSelectedId(null); setSelectionType('settings'); }}
                className="btn btn-outline btn-sm btn-square"
                title="Settings"
              >
                <Settings size={14} />
              </button>
              <button
                onClick={() => { setSelectedId(null); setSelectionType('help'); }}
                className="btn btn-outline btn-sm btn-square"
                title="Help"
              >
                <HelpCircle size={14} />
              </button>
            </div>
          </div>
        ) : (
          <div className="text-sm text-center text-gray-500">
            You must <a href="/accounts/login/?next=/routeditor/create/" className="link link-primary">log in</a> or <a href="/accounts/signup/" className="link link-primary">register</a> to save routes.
          </div>
        )}
      </div>
    </div>
  );
};

export default Sidebar;
