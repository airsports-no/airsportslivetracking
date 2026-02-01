import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { fetchDeclarationData, saveDeclarationData, fetchNavigationTask } from './api';
import { Loading } from '../route-editor/components/basicComponents';
import { SpeedTable } from './SpeedTable';
import { WaypointSorter } from './WaypointSorter';
import { ChevronLeft, Save } from 'lucide-react';

export const PilotDeclarationPage = () => {
    const { contestantId } = useParams<{ contestantId: string }>();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [contestant, setContestant] = useState<any>(null);
    const [task, setTask] = useState<any>(null);
    
    const [activeTab, setActiveTab] = useState<'speeds' | 'sequence'>('speeds');
    const [legSpeeds, setLegSpeeds] = useState<Record<string, number>>({});
    const [waypointOrder, setWaypointOrder] = useState<string[]>([]);

    useEffect(() => {
        const loadData = async () => {
            if (!contestantId) return;
            try {
                const c = await fetchDeclarationData(contestantId);
                setContestant(c);
                
                if (c.declared_configuration) {
                    if (c.declared_configuration.leg_speeds) setLegSpeeds(c.declared_configuration.leg_speeds);
                    if (c.declared_configuration.waypoint_order) setWaypointOrder(c.declared_configuration.waypoint_order);
                }

                if (c.contest_id && c.navigation_task) {
                    const t = await fetchNavigationTask(c.contest_id, c.navigation_task);
                    setTask(t);
                    
                    // Default tab logic
                    const route = t.route;
                    const allWaypoints = [...(route.waypoints || []), ...(route.standalone_waypoints || [])];
                    const hasFreePoints = allWaypoints.some((wp: any) => wp.is_free_point);
                    if (hasFreePoints) setActiveTab('sequence');
                }
            } catch (e) {
                console.error(e);
                // alert("Failed to load data.");
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, [contestantId]);

    const handleSave = async () => {
        if (!contestantId) return;
        setSaving(true);
        try {
            const config = {
                ...contestant.declared_configuration,
                leg_speeds: legSpeeds,
                waypoint_order: waypointOrder
            };
            await saveDeclarationData(contestantId, config);
            alert("Declaration saved successfully!");
        } catch (e) {
            console.error(e);
            alert("Error saving declaration.");
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <Loading />;
    if (!task || !contestant) return (
        <div className="p-8 text-center text-error">
            <h2 className="text-xl font-bold">Error loading task data</h2>
            <p>Please try again or contact the organizer.</p>
        </div>
    );

    const route = task.route;
    const allWaypoints = [...(route.waypoints || []), ...(route.standalone_waypoints || [])];
    const freePoints = allWaypoints.filter((wp: any) => wp.is_free_point);
    const hasFreePoints = freePoints.length > 0;

    // Determine current sequence for speed table
    let speedTableSequence = route.waypoints || [];
    if (waypointOrder && waypointOrder.length > 0) {
        const wpMap = new Map(allWaypoints.map(wp => [wp.name, wp]));
        speedTableSequence = waypointOrder.map(name => wpMap.get(name)).filter(Boolean);
    }

    return (
        <div className="min-h-screen bg-base-200 p-4 md:p-8">
            <div className="max-w-4xl mx-auto space-y-6">
                
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <a href={`/navigationtask/${task.id}/`} className="btn btn-circle btn-ghost">
                            <ChevronLeft />
                        </a>
                        <div>
                            <h1 className="text-2xl font-bold">Pilot Declaration</h1>
                            <p className="text-base-content/70">
                                Contestant #{contestant.contestant_number} - {task.name}
                            </p>
                        </div>
                    </div>
                    
                    <button 
                        onClick={handleSave} 
                        disabled={saving}
                        className={`btn btn-primary gap-2 ${saving ? 'loading' : ''}`}
                    >
                        <Save size={18} />
                        Save Changes
                    </button>
                </div>

                {/* Tabs */}
                <div className="tabs tabs-boxed">
                    <a 
                        className={`tab ${activeTab === 'speeds' ? 'tab-active' : ''}`}
                        onClick={() => setActiveTab('speeds')}
                    >
                        Leg Speeds
                    </a>
                    {hasFreePoints && (
                        <a 
                            className={`tab ${activeTab === 'sequence' ? 'tab-active' : ''}`}
                            onClick={() => setActiveTab('sequence')}
                        >
                            Point Sequence
                        </a>
                    )}
                </div>

                {/* Content */}
                <div className="bg-base-100 rounded-box shadow p-6">
                    {activeTab === 'speeds' && (
                        <div>
                            <h3 className="font-bold text-lg mb-4">Declared Ground Speeds</h3>
                            <p className="text-sm mb-4">Enter your planned ground speed (Knots) for each leg. This will determine your target crossing times.</p>
                            <SpeedTable 
                                waypoints={speedTableSequence} 
                                speeds={legSpeeds} 
                                onChange={setLegSpeeds} 
                            />
                        </div>
                    )}

                    {activeTab === 'sequence' && hasFreePoints && (
                        <div>
                            <h3 className="font-bold text-lg mb-4">Route Sequence</h3>
                            <p className="text-sm mb-4">Define the full sequence of waypoints you intend to visit, including the Start, Middle, and Finish points.</p>
                            <WaypointSorter 
                                freePoints={allWaypoints.filter((wp: any) => wp.type !== 'dummy')} 
                                order={waypointOrder} 
                                onChange={setWaypointOrder} 
                            />
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
};

export default PilotDeclarationPage;