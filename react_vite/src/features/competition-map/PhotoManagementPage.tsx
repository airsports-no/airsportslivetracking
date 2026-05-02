import React, { useEffect, useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import L from 'leaflet';
import useMapInit from '../route-editor/components/map/useMapInit';
import RouteRenderer from './components/track-renderers/RouteRenderer';
import ProhibitedRenderer from './components/track-renderers/ProhibitedRenderer';
import { fetchNavigationTask, createPhoto, deletePhoto, uploadPhotoFile, fetchPhotos } from './api';
import { NavigationTask, Photo } from './types';
import { Loading } from '../route-editor/components/basicComponents';
import { Trash2, Upload, ChevronLeft, MapPin, Plus, Magnet } from 'lucide-react';
import { reverse } from '../../urls';
import { getDistanceFromLine } from '../../utils/geoUtils';

export default function PhotoManagementPage() {
    const { contestId, navigationTaskId } = useParams();
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [photos, setPhotos] = useState<Photo[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isInitialLoad, setIsInitialLoad] = useState(true);
    const [forceNearLeg, setForceNearLeg] = useState(true);
    const [maxObsDist] = useState(926); // 0.5 NM
    const mapRef = useMapInit();
    const tileLayerRef = useRef<L.TileLayer | null>(null);
    const photoMarkersRef = useRef<Record<number, L.Marker>>({});

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        if (tileLayerRef.current) {
            tileLayerRef.current.remove();
        }

        const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            opacity: 0.6
        }).addTo(map);
        tileLayerRef.current = osm;
    }, [mapRef]);

    useEffect(() => {
        if (contestId && navigationTaskId) {
            setLoading(true);
            Promise.all([
                fetchNavigationTask(Number(contestId), Number(navigationTaskId)),
                fetchPhotos(Number(contestId), Number(navigationTaskId))
            ]).then(([task, photosData]) => {
                setNavTask(task);
                setPhotos(photosData);
            }).catch(err => {
                console.error(err);
                setError(err.message || "Failed to load data");
            }).finally(() => {
                setLoading(false);
            });
        }
    }, [contestId, navigationTaskId]);

    useEffect(() => {
        const map = mapRef.current;
        if (!map || !photos) return;

        // Clear existing markers
        Object.values(photoMarkersRef.current).forEach(m => m.remove());
        photoMarkersRef.current = {};

        photos.forEach((photo, index) => {
            const marker = L.marker([photo.latitude, photo.longitude], {
                icon: L.divIcon({
                    className: 'photo-marker',
                    html: `<div class="bg-primary text-primary-content rounded-full w-8 h-8 flex items-center justify-center font-bold border-2 border-white shadow-lg">${index + 1}</div>`,
                    iconSize: [32, 32],
                    iconAnchor: [16, 16]
                })
            }).addTo(map);
            
            marker.bindTooltip(photo.name);
            photoMarkersRef.current[photo.id] = marker;
        });

    }, [photos, mapRef]);

    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        const onMapClick = async (e: L.LeafletMouseEvent) => {
            if (!navTask) return;

            if (forceNearLeg) {
                const waypoints = navTask.route.waypoints;
                if (waypoints.length < 2) {
                    alert("Route must have at least 2 points to define legs.");
                    return;
                }

                let minDist = Infinity;
                const clickedPt = { lat: e.latlng.lat, lng: e.latlng.lng };

                for (let i = 0; i < waypoints.length - 1; i++) {
                    const wp1 = waypoints[i];
                    const wp2 = waypoints[i + 1];
                    const p1 = { lat: wp1.latitude, lng: wp1.longitude };
                    const p2 = { lat: wp2.latitude, lng: wp2.longitude };

                    let d = Infinity;
                    if (wp2.is_procedure_turn && wp2.procedure_turn_points) {
                        let prev = p1;
                        for (const pt of wp2.procedure_turn_points) {
                            const curr = { lat: pt[0], lng: pt[1] };
                            const segDist = getDistanceFromLine(clickedPt, prev, curr);
                            if (segDist < d) d = segDist;
                            prev = curr;
                        }
                        const finalSegDist = getDistanceFromLine(clickedPt, prev, p2);
                        if (finalSegDist < d) d = finalSegDist;
                    } else {
                        d = getDistanceFromLine(clickedPt, p1, p2);
                    }

                    if (d < minDist) minDist = d;
                }

                if (minDist > maxObsDist) {
                    alert(`Photo points must be within ${(maxObsDist / 1852).toFixed(2)} NM of the route line when snapping is enabled.`);
                    return;
                }
            }
            
            const name = `Photo ${photos.length + 1}`;
            const photoData = {
                name: name,
                route: navTask.route.id,
                latitude: e.latlng.lat,
                longitude: e.latlng.lng
            };

            try {
                const newPhoto = await createPhoto(photoData);
                setPhotos(prev => [...prev, newPhoto]);
            } catch (err) {
                console.error("Failed to create photo:", err);
            }
        };

        map.on('click', onMapClick);
        return () => {
            map.off('click', onMapClick);
        };
    }, [mapRef, navTask, photos, forceNearLeg, maxObsDist]);

    const handleDeletePhoto = async (photoId: number) => {
        if (!window.confirm("Are you sure you want to delete this photo point?")) return;
        try {
            await deletePhoto(photoId);
            setPhotos(prev => prev.filter(p => p.id !== photoId));
        } catch (err) {
            console.error("Failed to delete photo:", err);
        }
    };

    const handleFileUpload = async (photoId: number, e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            const updatedPhoto = await uploadPhotoFile(photoId, file);
            setPhotos(prev => prev.map(p => p.id === photoId ? updatedPhoto : p));
        } catch (err) {
            console.error("Failed to upload photo:", err);
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <div className="bg-base-100 border-b border-base-300 p-4 flex justify-between items-center shadow-sm z-10">
                <div className="flex items-center gap-4">
                    <a href={reverse('navigationtask_detail', navigationTaskId!)} className="btn btn-ghost btn-sm">
                        <ChevronLeft size={16} />
                        Back to Task
                    </a>
                    <h1 className="text-xl font-bold">Photo Management: {navTask?.name || 'Loading...'}</h1>
                </div>
                <div className="flex gap-2 text-xs opacity-70">
                    <MapPin size={14} />
                    Click on the map to add a new photo point
                </div>
            </div>

            <div className="flex-1 flex overflow-hidden relative">
                {/* Overlay for loading/error */}
                {(loading || error || !navTask) && (
                    <div className="absolute inset-0 z-[2000] flex items-center justify-center bg-base-100/60 backdrop-blur-sm">
                        {loading ? (
                            <Loading />
                        ) : error ? (
                            <div className="alert alert-error max-w-md shadow-lg">
                                <div>
                                    <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    <span>{error}</span>
                                </div>
                            </div>
                        ) : (
                            <div className="alert alert-warning max-w-md shadow-lg">
                                <div>
                                    <svg xmlns="http://www.w3.org/2000/svg" className="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                    <span>Task not found</span>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* Sidebar */}
                <div className="w-80 sm:w-96 bg-base-100 border-r border-base-300 overflow-y-auto p-4 flex flex-col gap-4 shadow-inner">
                    <h2 className="font-bold text-lg flex items-center gap-2">
                        <Plus size={18} />
                        Photo Points ({photos.length})
                    </h2>

                    <div className="flex items-center gap-2 bg-base-200 p-2 rounded-lg border border-base-300">
                        <Magnet size={16} className={forceNearLeg ? 'text-primary' : 'text-base-content/50'} />
                        <span className="text-sm font-medium flex-1">Snap to Route Leg</span>
                        <input 
                            type="checkbox" 
                            className="toggle toggle-primary toggle-sm" 
                            checked={forceNearLeg} 
                            onChange={(e) => setForceNearLeg(e.target.checked)} 
                        />
                    </div>
                    
                    {photos.length === 0 && !loading && (
                        <div className="alert alert-info text-sm">
                            No photo points yet. Click on the map to add one.
                        </div>
                    )}

                    <div className="flex flex-col gap-3">
                        {photos.map((photo, index) => (
                            <div key={photo.id} className="card bg-base-200 shadow-sm border border-base-300">
                                <div className="card-body p-3">
                                    <div className="flex justify-between items-start">
                                        <div className="flex items-center gap-2">
                                            <span className="badge badge-primary font-bold">{index + 1}</span>
                                            <span className="font-bold truncate max-w-[150px]">{photo.name}</span>
                                        </div>
                                        <button 
                                            onClick={() => handleDeletePhoto(photo.id)}
                                            className="btn btn-ghost btn-xs text-error btn-square"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                    
                                    {photo.file ? (
                                        <div className="mt-2 relative group">
                                            <img 
                                                src={photo.file} 
                                                alt={photo.name} 
                                                className="w-full h-32 object-cover rounded-md border border-base-300" 
                                            />
                                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-md">
                                                <label className="btn btn-xs btn-primary gap-1 cursor-pointer">
                                                    <Upload size={12} />
                                                    Change
                                                    <input 
                                                        type="file" 
                                                        className="hidden" 
                                                        accept="image/*"
                                                        onChange={(e) => handleFileUpload(photo.id, e)} 
                                                    />
                                                </label>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="mt-2 h-32 bg-base-300 rounded-md flex flex-col items-center justify-center text-xs opacity-50 border-2 border-dashed border-base-content/20">
                                            <span>No image yet</span>
                                            <label className="btn btn-xs btn-outline mt-2 gap-1 cursor-pointer">
                                                <Upload size={12} />
                                                Upload
                                                <input 
                                                    type="file" 
                                                    className="hidden" 
                                                    accept="image/*"
                                                    onChange={(e) => handleFileUpload(photo.id, e)} 
                                                />
                                            </label>
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {/* Map */}
                <div className="flex-1 relative">
                    <div id="map-container" className="h-full w-full" />
                    {navTask && (
                        <>
                            <ProhibitedRenderer map={mapRef.current} navTask={navTask} />
                            <RouteRenderer
                                map={mapRef.current}
                                route={navTask.route}
                                taskType={navTask.scorecard.task_type}
                                navTaskDisplaySecrets={true}
                                displaySecrets={true}
                                contestants={{}}
                                selectedContestantId={null}
                                isInitialLoad={isInitialLoad}
                                onMapFit={setIsInitialLoad}
                            />
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
