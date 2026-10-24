import React from 'react';
import { Activity, PanelLeftClose, PanelLeftOpen, PlayCircle } from 'lucide-react';

export type PanelTab = 'ranking' | 'log';

interface Props {
    title: string;
    /** The map's time (the replay's time in replay), shown in the task's time zone. */
    time: Date;
    timeZone?: string;
    mode: 'realtime' | 'playback';
    onModeChange: (mode: 'realtime' | 'playback') => void;
    collapsed: boolean;
    onToggleCollapsed: () => void;
    /** Settings, trails, task info and the links, as icon buttons. */
    toolbar: React.ReactNode;
    /** A line under the header, e.g. that live data is delayed. */
    notice?: React.ReactNode;
    /** The selected contestant's name; with it the panel offers the ranking and their navigation log as tabs. */
    selectedName?: string | null;
    tab: PanelTab;
    onTabChange: (tab: PanelTab) => void;
    onClearSelection?: () => void;
    children: React.ReactNode;
    footer?: React.ReactNode;
}

function formatClock(time: Date, timeZone?: string): { clock: string; zone?: string } {
    const clock = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
    const zone = new Intl.DateTimeFormat([], { timeZone, timeZoneName: 'short' }).formatToParts(time).find(p => p.type === 'timeZoneName')?.value;
    return { clock, zone };
}

function LiveOrReplay({ mode, onModeChange }: { mode: 'realtime' | 'playback'; onModeChange: (mode: 'realtime' | 'playback') => void }) {
    return (
        <div className="hud-segmented" role="group" aria-label="Live or replay">
            <button className="hud-button" aria-pressed={mode === 'realtime'} onClick={() => onModeChange('realtime')}>
                <Activity size={14} /> Live
            </button>
            <button className="hud-button" aria-pressed={mode === 'playback'} onClick={() => onModeChange('playback')}>
                <PlayCircle size={14} /> Replay
            </button>
        </div>
    );
}

/**
 * The map's one panel, docked to its left edge: the task and its clock, Live or Replay, then the ranking or the selected
 * contestant's navigation log. On a phone it sits across the top and folds up to its header.
 */
export default function SidePanel({
    title, time, timeZone, mode, onModeChange, collapsed, onToggleCollapsed, toolbar, notice,
    selectedName, tab, onTabChange, onClearSelection, children, footer,
}: Props) {
    const { clock, zone } = formatClock(time, timeZone);

    if (collapsed) {
        // Desktop: a narrow rail that keeps the clock in view. Phone: the header strip alone.
        return (
            <aside className="hud flex sm:flex-col items-center gap-2 px-2 py-2 sm:py-3 sm:w-14 border-b sm:border-b-0 sm:border-r hud-divider z-[1100]">
                <button className="hud-button" onClick={onToggleCollapsed} aria-label="Show the ranking panel" title="Show the ranking panel">
                    <PanelLeftOpen size={18} />
                </button>
                <span className="font-semibold text-sm truncate sm:hidden flex-1">{title}</span>
                <span className="hud-figure text-lg sm:text-sm sm:[writing-mode:vertical-rl] sm:rotate-180">{clock}</span>
            </aside>
        );
    }

    return (
        <aside className="hud flex flex-col w-full sm:w-[22rem] max-h-[40vh] sm:max-h-none sm:h-full border-b sm:border-b-0 sm:border-r hud-divider z-[1100]">
            <header className="px-4 pt-3 pb-2 flex flex-col gap-2">
                {/* Phone: two rows (title, clock; tools, Live or Replay) so the list keeps most of the panel. */}
                <div className="flex items-center justify-between gap-2">
                    <h1 className="font-semibold text-base leading-tight min-w-0 truncate sm:whitespace-normal" title={title}>{title}</h1>
                    <span className="hud-figure text-2xl leading-none sm:hidden flex-none">{clock}</span>
                    <button className="hud-button -mr-2 flex-none" onClick={onToggleCollapsed} aria-label="Hide the ranking panel" title="Hide the ranking panel">
                        <PanelLeftClose size={18} />
                    </button>
                </div>
                <div className="hidden sm:flex items-end justify-between gap-2">
                    <div className="leading-none">
                        <span className="hud-figure text-4xl">{clock}</span>
                        {zone && <span className="hud-label ml-1.5">{zone}</span>}
                    </div>
                    <LiveOrReplay mode={mode} onModeChange={onModeChange} />
                </div>
                <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-0.5 -mx-2">{toolbar}</div>
                    <div className="sm:hidden"><LiveOrReplay mode={mode} onModeChange={onModeChange} /></div>
                </div>
                {notice}
            </header>

            {selectedName && (
                <div className="px-4 pb-2 flex items-center gap-2 border-b hud-divider">
                    <div className="hud-segmented flex-1" role="tablist" aria-label="Ranking or navigation log">
                        <button role="tab" className="hud-button flex-1" aria-pressed={tab === 'ranking'} aria-selected={tab === 'ranking'} onClick={() => onTabChange('ranking')}>
                            Ranking
                        </button>
                        <button role="tab" className="hud-button flex-1 min-w-0" aria-pressed={tab === 'log'} aria-selected={tab === 'log'} onClick={() => onTabChange('log')}>
                            <span className="truncate">Log: {selectedName}</span>
                        </button>
                    </div>
                    {onClearSelection && (
                        <button className="hud-button flex-none" onClick={onClearSelection} title="Back to all contestants">Clear</button>
                    )}
                </div>
            )}
            {!selectedName && <div className="border-b hud-divider" />}

            <div className="flex-1 min-h-0 overflow-y-auto hud-scroll py-1">{children}</div>

            {footer && <footer className="border-t hud-divider px-4 py-3 hidden sm:block">{footer}</footer>}
        </aside>
    );
}
