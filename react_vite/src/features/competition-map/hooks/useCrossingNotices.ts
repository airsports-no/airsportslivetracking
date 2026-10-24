import { RefObject, useCallback, useEffect, useRef } from 'react';
import L from 'leaflet';
import { Contestant, CrossingEvent, NavigationTask } from '../types';
import { replayCrossings } from '../utils/replayCrossings';

/** How long a notice stays, and how many are on the map at once (the oldest goes first). */
const NOTICE_MS = 6000;
const MAX_NOTICES = 3;

function escapeHtml(text: string): string {
    return text.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

/**
 * A short notice at the gate on the map whenever any contestant crosses a timed gate ("TP3 Nadal +2 s"), green within
 * the gate's grace period and red outside it, fading after a few seconds: live from the server's crossing messages,
 * in a replay from the gate results as the replay passes them. Secret and unknown-leg gates only where secrets show.
 */
export function useCrossingNotices({ mapRef, mode, navTask, contestants, liveCrossings, currentTime, showSecrets, playbackSpeed = 1 }: {
    mapRef: RefObject<L.Map | null>;
    mode: 'realtime' | 'playback';
    navTask: NavigationTask | null;
    contestants: Contestant[];
    liveCrossings: CrossingEvent[];
    currentTime: Date;
    showSecrets: boolean;
    playbackSpeed?: number;
}) {
    const shownRef = useRef<{ marker: L.Marker; timer: number }[]>([]);
    const seenLiveRef = useRef(new Set<string>());
    const lastReplayTimeRef = useRef<Date | null>(null);

    /** 'wait' when the map or the data is not there yet (try again later); 'skip' when it is not to be shown. */
    const show = useCallback((event: CrossingEvent): 'shown' | 'wait' | 'skip' => {
        const map = mapRef.current;
        if (!map || !navTask) return 'wait';
        const waypoint = navTask.route.waypoints.find(w => w.name === event.gate);
        if (!waypoint) return 'skip';
        if ((waypoint.type === 'secret' || waypoint.type === 'ul') && !showSecrets) return 'skip';
        const contestant = contestants.find(c => c.id === event.contestantId);
        if (!contestant) return 'wait';
        const name = contestant?.team?.crew?.member1?.last_name ?? `#${contestant?.contestant_number ?? ''}`;
        const rule = navTask.scorecard?.gatescore_set?.find(g => g.gate_type === waypoint.type);
        const offset = Math.round(event.offsetSeconds);
        const onTime = !event.missed && (offset < 0
            ? -offset <= (rule?.graceperiod_before ?? 0)
            : offset <= (rule?.graceperiod_after ?? 0));
        const result = event.missed ? 'missed' : `${offset > 0 ? '+' : ''}${offset} s`;
        const html = `<div class="hud-notice ${onTime ? 'hud-notice-ok' : 'hud-notice-off'}">`
            + `<span class="hud-notice-gate">${escapeHtml(event.gate)}</span> ${escapeHtml(name)} `
            + `<span class="hud-notice-result">${escapeHtml(result)}</span></div>`;
        const marker = L.marker([waypoint.latitude, waypoint.longitude], {
            icon: L.divIcon({ html, className: 'hud-notice-anchor', iconSize: undefined, iconAnchor: [0, 40] }),
            interactive: false,
            keyboard: false,
        }).addTo(map);
        const timer = window.setTimeout(() => {
            marker.remove();
            shownRef.current = shownRef.current.filter(n => n.marker !== marker);
        }, NOTICE_MS);
        shownRef.current.push({ marker, timer });
        while (shownRef.current.length > MAX_NOTICES) {
            const oldest = shownRef.current.shift()!;
            window.clearTimeout(oldest.timer);
            oldest.marker.remove();
        }
        return 'shown';
    }, [mapRef, navTask, contestants, showSecrets]);

    // Live: each crossing once, as it arrives.
    useEffect(() => {
        if (mode !== 'realtime') return;
        for (const event of liveCrossings) {
            if (seenLiveRef.current.has(event.key)) continue;
            // One that has to wait is tried again when the map or the contestants have arrived.
            if (show(event) !== 'wait') seenLiveRef.current.add(event.key);
        }
    }, [mode, liveCrossings, show]);

    // Replay: the crossings the replay has just played past.
    useEffect(() => {
        if (mode !== 'playback') {
            lastReplayTimeRef.current = null;
            return;
        }
        const from = lastReplayTimeRef.current;
        lastReplayTimeRef.current = currentTime;
        if (!from) return;
        for (const event of replayCrossings(contestants, from, currentTime, playbackSpeed)) show(event);
    }, [mode, currentTime, contestants, show, playbackSpeed]);

    // Nothing is left behind when the page goes.
    useEffect(() => () => {
        for (const n of shownRef.current) {
            window.clearTimeout(n.timer);
            n.marker.remove();
        }
        shownRef.current = [];
    }, []);
}
