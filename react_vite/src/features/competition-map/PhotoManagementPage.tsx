import React, { useEffect, useMemo, useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import L from 'leaflet';
import useMapInit from '../route-editor/components/map/useMapInit';
import RouteRenderer from './components/track-renderers/RouteRenderer';
import ProhibitedRenderer from './components/track-renderers/ProhibitedRenderer';
import { fetchNavigationTask, uploadPhotoFile, revertPhotoToSatellite, fetchPhotos } from './api';
import { NavigationTask, Photo } from './types';
import { Loading } from '../route-editor/components/basicComponents';
import { RotateCcw, Upload, ChevronLeft, MapPin } from 'lucide-react';
import { reverse } from '../../urls';

export default function PhotoManagementPage() {
    const { contestId, navigationTaskId } = useParams();
    const [navTask, setNavTask] = useState<NavigationTask | null>(null);
    const [photos, setPhotos] = useState<Photo[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isInitialLoad, setIsInitialLoad] = useState(true);
    const mapRef = useMapInit();
    const tileLayerRef = useRef<L.TileLayer | null>(null);
    const photoMarkersRef = useRef<Record<number, L.Marker>>({});
    const photoTargets = useMemo(() => photos.map((photo) => ({
        ...photo,
        coordinates: photo.compiled_coordinates ?? [photo.longitude, photo.latitude] as [number, number],
    })), [photos]);

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
        if (!map) return;

        // Clear existing markers
        Object.values(photoMarkersRef.current).forEach(m => m.remove());
        photoMarkersRef.current = {};

        photos.forEach((photo, index) => {
            const marker = L.marker([photo.latitude, photo.longitude], {
                interactive: false,
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
        return;
    }, [mapRef, navTask, photos]);

    const handleRevertPhoto = async (photoId: number) => {
        try {
            const revertedPhoto = await revertPhotoToSatellite(photoId);
            setPhotos(prev => prev.map(p => p.id === photoId ? revertedPhoto : p));
        } catch (err) {
            console.error("Failed to revert photo:", err);
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
                    Review waypoint photos and upload replacements where needed
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
                        <MapPin size={18} />
                        Photo Targets ({photos.length})
                    </h2>

                    {photos.length === 0 && !loading && (
                        <div className="alert alert-info text-sm">
                            No waypoint photo targets available for this task.
                        </div>
                    )}

                    <div className="flex flex-col gap-3">
                        {photos.map((photo, index) => (
                            <div key={photo.id} className="card bg-base-200 shadow-sm border border-base-300">
                                <div className="card-body p-3">
                                    <div className="flex justify-between items-start">
                                        <div className="flex items-center gap-2">
                                            <span className="badge badge-primary font-bold">{index + 1}</span>
                                            <div>
                                                <div className="font-bold truncate max-w-[150px]">{photo.name}</div>
                                                <div className="text-xs opacity-60">{photo.target_kind === 'catalogue_turnpoint' ? 'Catalogue turnpoint' : 'Route waypoint'}</div>
                                            </div>
                                        </div>
                                    </div>
                                    
                                    {photo.file ? (
                                        <div className="mt-2 relative group">
                                            <img 
                                                src={photo.file} 
                                                alt={photo.name} 
                                                className="w-full h-32 object-cover rounded-md border border-base-300" 
                                            />
                                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center rounded-md gap-2">
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
                                                <button type="button" className="btn btn-xs btn-outline btn-warning gap-1" onClick={() => handleRevertPhoto(photo.id)}>
                                                    <RotateCcw size={12} />
                                                    Revert
                                                </button>
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
                                taskCatalogueTargets={navTask.task_catalogue_targets ?? []}
                                taskConfig={navTask.task_config ?? {}}
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
