import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import useMapInit from '../route-editor/components/map/useMapInit';
import { fetchNavigationTask, fetchContestantPaginatedTrack, makeWebSocket } from './api';
import type { NavigationTask, TrackPosition } from './types';
import { planeIcon } from './components/icons';
import ResultsTable from './components/ResultsTable';
import { useParams, Link } from 'react-router-dom';
import ProhibitedRenderer from "./components/track-renderers/ProhibitedRenderer";
import RouteRenderer from "./components/track-renderers/RouteRenderer";

interface ContestantLayers {
  marker: L.Marker;
  recentTrail: L.Polyline;
  fullTrail: L.Polyline;
}

function hslColor(index: number, total: number): string {
  const hue = Math.round((index / Math.max(1, total)) * 360);
  return `hsl(${hue}, 70%, 50%)`;
}

function lastMinutesPositions(all: TrackPosition[], minutes: number, currentTime: Date): TrackPosition[] {
  const cutoff = new Date(currentTime.getTime() - minutes * 60_000);
  return all.filter(p => new Date(p.time) >= cutoff);
}

export default function CompetitionMapPage() {
  const { contestId, navigationTaskId } = useParams();
  const contestIdNum = Number(contestId ?? 632);
  const navigationTaskIdNum = Number(navigationTaskId ?? 2129);

  const mapRef = useMapInit();
  const [navTask, setNavTask] = useState<NavigationTask | null>(null);
  const [positionsByContestant, setPositionsByContestant] = useState<Record<number, TrackPosition[]>>({});
  const [showFullTrails, setShowFullTrails] = useState(false);
  const [mode, setMode] = useState<'realtime' | 'playback'>('realtime');
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, etc.
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const wsRef = useRef<WebSocket | null>(null);
  const playbackTimerRef = useRef<number | null>(null);
  const layersRef = useRef<Record<number, ContestantLayers>>({});

  // Fetch navigation task
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const task = await fetchNavigationTask(contestIdNum, navigationTaskIdNum);
      if (!cancelled) setNavTask(task);
    })().catch(console.error);
    return () => { cancelled = true; };
  }, [contestIdNum, navigationTaskIdNum]);

  // Fetch initial tracks for playback
  useEffect(() => {
    if (!navTask) return;
    let cancelled = false;
    (async () => {
      const updates: Record<number, TrackPosition[]> = {};
      for (const c of navTask.contestant_set) {
        try {
          let cursor: string | null | undefined = undefined;
          const allPositions: TrackPosition[] = [];
          // Pull all pages sequentially
          // Note: consider server limits; this can be optimized with batching if needed
          // eslint-disable-next-line no-constant-condition
          while (true) {
            const page = await fetchContestantPaginatedTrack(contestIdNum, navigationTaskIdNum, c.id, cursor);
            allPositions.push(...page.results);
            if (!page.next) break;
            cursor = page.next;
          }
          updates[c.id] = allPositions.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
        } catch (e) {
          console.error('Failed to fetch track for contestant', c.id, e);
        }
      }
      if (!cancelled) setPositionsByContestant(prev => ({ ...prev, ...updates }));
    })();
    return () => { cancelled = true; };
  }, [navTask, contestIdNum, navigationTaskIdNum]);

  // WebSocket for realtime updates
  useEffect(() => {
    if (!navTask) return;
    const ws = makeWebSocket(navigationTaskIdNum);
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as { type: string; data: string };
        if (msg.type === 'current_time') {
          const iso = JSON.parse(msg.data);
          setCurrentTime(new Date(iso));
        } else if (msg.type === 'position') {
          const payload = JSON.parse(msg.data) as (TrackPosition & { contestant_id: number });
          setPositionsByContestant(prev => {
            const arr = prev[payload.contestant_id] ? [...prev[payload.contestant_id]] : [];
            arr.push(payload);
            return { ...prev, [payload.contestant_id]: arr };
          });
        } else if (msg.type === 'contestant') {
          // New contestant might join mid-flight
          const c = JSON.parse(msg.data);
          setNavTask(prev => prev ? { ...prev, contestant_set: [...prev.contestant_set.filter(x => x.id !== c.id), c] } : prev);
        } else if (msg.type === 'contestant_delete') {
          const c = JSON.parse(msg.data);
          setNavTask(prev => prev ? { ...prev, contestant_set: prev.contestant_set.filter(x => x.id !== c.id) } : prev);
        }
      } catch (e) {
        console.error('WS parse error', e);
      }
    };
    ws.onclose = () => { /* auto-reconnect could be added */ };
    ws.onerror = () => { /* log */ };
    return () => {
      try { ws.close(); } catch { /* noop */ }
      wsRef.current = null;
    };
  }, [navTask, navigationTaskIdNum]);

  // Playback timer
  useEffect(() => {
    if (mode !== 'playback') {
      if (playbackTimerRef.current) {
        window.clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
      return;
    }
    // Determine overall time range from known positions
    const all = Object.values(positionsByContestant).flat();
    if (!all.length) return;
    const start = new Date(Math.min(...all.map(p => new Date(p.time).getTime())));
    let t = new Date(start);
    setCurrentTime(t);
    const intervalMs = 1000 / Math.max(0.25, playbackSpeed); // speed up or slow down logical seconds
    playbackTimerRef.current = window.setInterval(() => {
      t = new Date(t.getTime() + 1000);
      setCurrentTime(new Date(t));
    }, intervalMs);
    return () => {
      if (playbackTimerRef.current) {
        window.clearInterval(playbackTimerRef.current);
        playbackTimerRef.current = null;
      }
    };
  }, [mode, playbackSpeed, positionsByContestant]);

  // Create/update Leaflet layers
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !navTask) return;
    const total = navTask.contestant_set.length;

    for (const [index, c] of navTask.contestant_set.entries()) {
      const color = hslColor(index, total);
      const positions = positionsByContestant[c.id] ?? [];
      const visiblePositions = showFullTrails ? positions : lastMinutesPositions(positions, 5, currentTime);

      if (!layersRef.current[c.id]) {
        // Initialize layers
        const marker = L.marker([positions[0]?.latitude ?? 0, positions[0]?.longitude ?? 0], {
          icon: planeIcon(c.contestant_number, color, positions[positions.length - 1]?.course ?? 0),
        }).addTo(map);
        const recentTrail = L.polyline([], { color, weight: 3, opacity: 0.9 }).addTo(map);
        const fullTrail = L.polyline([], { color, weight: 2, opacity: 0.3 }).addTo(map);
        layersRef.current[c.id] = { marker, recentTrail, fullTrail };
      }
      const { marker, recentTrail, fullTrail } = layersRef.current[c.id];

      // Update marker position & orientation
      const latest = positions[positions.length - 1];
      if (latest) {
        marker.setLatLng([latest.latitude, latest.longitude]);
        marker.setIcon(planeIcon(c.contestant_number, color, latest.course ?? 0));
      }

      // Update trails
      const recentLatLngs = visiblePositions.map(p => [p.latitude, p.longitude] as [number, number]);
      recentTrail.setLatLngs(recentLatLngs);
      const fullLatLngs = positions.map(p => [p.latitude, p.longitude] as [number, number]);
      fullTrail.setLatLngs(fullLatLngs);
      if (showFullTrails) {
        fullTrail.addTo(map);
      } else {
        // keep full trail but low opacity; toggle visibility by opacity
        fullTrail.setStyle({ opacity: 0 });
      }
    }

    // Cleanup on navTask change or unmount
    return () => {
      Object.values(layersRef.current).forEach(l => {
        l.marker.remove();
        l.recentTrail.remove();
        l.fullTrail.remove();
      });
      layersRef.current = {};
    };
  }, [mapRef, navTask, positionsByContestant, showFullTrails, currentTime]);

  const standings = useMemo(() => {
    if (!navTask) return [] as { id: number; name: string; score: number }[];
    const dir = navTask.score_sorting_direction;
    return [...navTask.contestant_set]
      .map(c => ({ id: c.id, name: `#${c.contestant_number} ${c.team?.crew?.member1?.first_name ?? ''} ${c.team?.crew?.member1?.last_name ?? ''}`, score: c.contestanttrack?.score ?? 0 }))
      .sort((a, b) => dir === 'asc' ? a.score - b.score : b.score - a.score);
  }, [navTask]);

  return (
    <div className="flex flex-col h-screen">
      <div className="navbar bg-base-200 px-4">
        <div className="flex-1">
          <Link to="/" className="btn btn-ghost text-xl">Home</Link>
          <span className="mx-2">Competition Map</span>
          {navTask && <span className="opacity-60">{navTask.name}</span>}
        </div>
        <div className="flex items-center gap-4">
          <label className="label cursor-pointer">
            <span className="label-text">Show full trails</span>
            <input type="checkbox" className="toggle toggle-primary ml-2" checked={showFullTrails} onChange={e => setShowFullTrails(e.target.checked)} />
          </label>
          <div className="form-control">
            <label className="label cursor-pointer">
              <span className="label-text">Realtime</span>
              <input type="radio" name="mode" className="radio ml-2" checked={mode === 'realtime'} onChange={() => setMode('realtime')} />
            </label>
          </div>
          <div className="form-control">
            <label className="label cursor-pointer">
              <span className="label-text">Playback</span>
              <input type="radio" name="mode" className="radio ml-2" checked={mode === 'playback'} onChange={() => setMode('playback')} />
            </label>
          </div>
          {mode === 'playback' && (
            <div className="flex items-center gap-2">
              <span className="label-text">Speed</span>
              <input type="range" min={0.25} max={8} step={0.25} value={playbackSpeed} onChange={e => setPlaybackSpeed(Number(e.target.value))} className="range range-xs w-32" />
              <span className="badge">{playbackSpeed}x</span>
            </div>
          )}
        </div>
      </div>
      <div className="flex-1 relative">
        <div id="map-container" className="h-full w-full" />
        <ProhibitedRenderer map={mapRef.current} navTask={navTask} />
        <RouteRenderer map={mapRef.current} navTask={navTask} />
        <div className="absolute top-4 left-4 z-[1000] bg-base-100/80 backdrop-blur-sm border border-base-300 rounded-lg shadow-lg w-96">
          <ResultsTable rows={standings} />
        </div>
      </div>
    </div>
  );
}
