import React, { useEffect, useState, useSyncExternalStore } from 'react';
import { Contestant, DangerData, GateArrowData, Member, NavigationTask } from '../../types';
import GateScoreArrowV2 from '../gateScoreArrow/GateScoreArrowV2';
import PlayingCards from '../playing-cards/PlayingCards';

interface Props {
    contestant: Contestant;
    navigationTask: NavigationTask;
    score: number | string;
    /** 1-based place in the ranking; null while the contestant has not started. */
    rank: number | null;
    rankOf: number;
    gateArrowData?: GateArrowData;
    dangerData?: DangerData;
    /** Live: the gate countdown and arrow. Off in debrief, where the replay bar takes the bottom edge instead. */
    live: boolean;
    /** One slim row above the replay bar: crew, score and place at the replay's time. */
    slim?: boolean;
}

/** Room for the pilot and the navigator side by side: a tablet or wider, not a phone on its side. */
const BOTH_FIT = '(min-width: 768px) and (min-height: 501px)';
const subscribeToBothFit = (onChange: () => void) => {
    const query = window.matchMedia?.(BOTH_FIT);
    query?.addEventListener('change', onChange);
    return () => query?.removeEventListener('change', onChange);
};
const bothFit = () => !!window.matchMedia?.(BOTH_FIT).matches;

/** How long each crew member is shown when there is room for only one at a time. */
const CREW_SWITCH_MS = 6000;
const ROLES = ['Pilot', 'Navigator'];

/**
 * The crew: side by side where there is room, otherwise one at a time, switching between pilot and navigator by
 * itself, with a button for each to keep showing that one (pressed again, it switches by itself again).
 */
function Crew({ members, club, slim }: { members: Member[]; club?: string | null; slim: boolean }) {
    const both = useSyncExternalStore(subscribeToBothFit, bothFit, () => true);
    const [pinned, setPinned] = useState<number | null>(null);
    const [auto, setAuto] = useState(0);
    const rotating = !both && members.length > 1 && pinned === null;
    useEffect(() => {
        if (!rotating) return;
        const timer = window.setInterval(() => setAuto(index => (index + 1) % members.length), CREW_SWITCH_MS);
        return () => window.clearInterval(timer);
    }, [rotating, members.length]);

    if (both || members.length < 2) {
        return (
            <div className="flex items-center gap-4 min-w-0">
                {members.map((member, index) => (
                    <CrewMember key={index} person={member} club={index === 0 ? club : undefined} slim={slim} />
                ))}
            </div>
        );
    }
    const shown = pinned ?? auto;
    return (
        <div className="flex items-center gap-3 min-w-0">
            <CrewMember person={members[shown]} club={shown === 0 ? club : undefined} slim={slim} />
            <div className="flex flex-col gap-1 flex-none" role="group" aria-label="Pilot or navigator">
                {members.map((member, index) => (
                    <button key={index} type="button"
                        className="hud-label rounded px-1.5 py-0.5 text-left"
                        style={shown === index ? { background: 'var(--hud-raised)', color: 'var(--hud-text)' } : undefined}
                        aria-pressed={pinned === index}
                        title={pinned === index ? 'Switch between them again' : `Keep showing the ${ROLES[index].toLowerCase()}`}
                        onClick={() => setPinned(pinned === index ? null : index)}>
                        {ROLES[index]}
                    </button>
                ))}
            </div>
        </div>
    );
}

function CrewMember({ person, club, slim = false }: { person: Member; club?: string | null; slim?: boolean }) {
    const initials = `${person.first_name?.[0] ?? ''}${person.last_name?.[0] ?? ''}`;
    // Slim (above the replay bar): a small photo, the same size everywhere.
    const photo = slim
        ? 'w-8 h-10 min-[100rem]:w-12 min-[100rem]:h-[3.75rem]'
        : 'w-11 h-14 sm:w-14 sm:h-[4.5rem] min-[100rem]:w-24 min-[100rem]:h-[7.5rem]';
    return (
        <div className="flex items-center gap-2.5 min-[100rem]:gap-4 min-w-0">
            {person.picture ? (
                <img src={person.picture} alt="" className={`${photo} rounded-md object-cover object-top flex-none [@media(max-height:500px)]:hidden`} />
            ) : (
                <div className={`${photo} rounded-md flex-none flex items-center justify-center hud-figure text-xl [@media(max-height:500px)]:hidden`} style={{ background: 'var(--hud-raised)' }}>
                    {initials}
                </div>
            )}
            <div className="min-w-0">
                <div className="font-semibold text-sm sm:text-base min-[100rem]:text-2xl leading-tight truncate">{person.first_name} {person.last_name}</div>
                {club && <div className="hud-label min-[100rem]:text-base truncate">{club}</div>}
            </div>
        </div>
    );
}

/**
 * The selected contestant along the bottom edge of the map: who is flying, their score and place, and while they fly
 * the countdown to the next gate with the gate score arrow and the danger level. On a phone on its side (the
 * max-height:500px classes) it keeps to one row, without photos, so the map keeps most of the height. On a big screen
 * (100rem, 1600 px, and wider: the event display) everything is larger and the arrow takes the rest of the width.
 */
export default function FollowBar({ contestant, navigationTask, score, rank, rankOf, gateArrowData, dangerData, live, slim = false }: Props) {
    const crew = contestant.team?.crew;
    if (!crew?.member1) return null;
    const isPoker = navigationTask.scorecard.task_type.includes('poker');
    const danger = Math.max(0, Math.min(100, dangerData?.danger_level ?? 0));
    const showDanger = live && dangerData !== undefined;

    return (
        <section className={`hud border-t hud-divider px-3 sm:px-4 ${slim ? 'py-1.5' : 'py-2 sm:py-3 min-[100rem]:py-4'} min-[100rem]:px-6 z-[1100]`} aria-label={`Following ${crew.member1.first_name} ${crew.member1.last_name}`}>
            <div className={`flex ${slim ? 'flex-nowrap' : 'flex-wrap lg:flex-nowrap'} [@media(max-height:500px)]:flex-nowrap items-center gap-x-5 min-[100rem]:gap-x-10 gap-y-2`}>
                <div className="flex items-center gap-4 min-w-0 flex-1 lg:flex-none">
                    <Crew members={crew.member2 ? [crew.member1, crew.member2] : [crew.member1]} club={contestant.team.club?.name} slim={slim} />
                </div>

                <div className={`flex items-end gap-4 flex-none ${slim ? 'ml-auto' : ''}`}>
                    <div className="leading-none text-right">
                        {typeof score === 'number' ? (
                            <>
                                <div className={`hud-figure ${slim ? 'text-3xl min-[100rem]:text-5xl' : 'text-4xl sm:text-5xl min-[100rem]:text-7xl'} [@media(max-height:500px)]:text-3xl`}>{score.toFixed(0)}</div>
                                <div className="hud-label min-[100rem]:text-base mt-1">Score</div>
                            </>
                        ) : (
                            // "Not started" and the like: a status, not a score.
                            <div className="text-sm font-semibold hud-muted">{score}</div>
                        )}
                    </div>
                    {rank !== null && (
                        <div className="leading-none text-right">
                            <div className={`hud-figure hud-muted ${slim ? 'text-xl min-[100rem]:text-3xl' : 'text-2xl sm:text-3xl min-[100rem]:text-5xl'}`}>{rank}<span className="text-base min-[100rem]:text-2xl">/{rankOf}</span></div>
                            <div className="hud-label min-[100rem]:text-base mt-1">Place</div>
                        </div>
                    )}
                </div>

                {live && !isPoker && (
                    <div className={`w-full min-w-0 lg:w-auto lg:flex-1 lg:max-w-[36rem] lg:ml-auto min-[100rem]:max-w-none [@media(max-height:500px)]:w-auto [@media(max-height:500px)]:flex-1 [@media(max-height:500px)]:max-w-[22rem] [@media(max-height:500px)]:ml-auto`}>
                        <GateScoreArrowV2 contestant={contestant} navigationTask={navigationTask} gateArrowData={gateArrowData} />
                    </div>
                )}
                {isPoker && contestant.playing_cards && contestant.playing_cards.length > 0 && (
                    <div className="lg:ml-auto"><PlayingCards playingCards={contestant.playing_cards} /></div>
                )}

                {showDanger && (
                    // How close the pilot is to a penalty (outside the corridor, in a prohibited zone), as a level.
                    <div className="flex lg:flex-col items-center gap-2 flex-none" title="How close the contestant is to a penalty">
                        <div className="relative w-24 h-2 lg:w-2 lg:h-20 min-[100rem]:w-3 min-[100rem]:h-28 rounded-full overflow-hidden" style={{ background: 'var(--hud-raised)' }}>
                            {/* Fills from the left on narrow screens, from the bottom beside the arrow on wide ones. */}
                            <div className="absolute left-0 top-0 h-full lg:hidden" style={{ width: `${danger}%`, background: danger >= 100 ? 'var(--hud-red)' : 'var(--hud-warn)' }} />
                            <div className="absolute left-0 bottom-0 w-full hidden lg:block" style={{ height: `${danger}%`, background: danger >= 100 ? 'var(--hud-red)' : 'var(--hud-warn)' }} />
                        </div>
                        <div className="leading-none text-center">
                            <div className="hud-figure text-lg">{danger.toFixed(0)}%</div>
                            {danger >= 100 && (dangerData?.accumulated_score ?? 0) > 0 && (
                                <div className="hud-figure text-sm" style={{ color: 'var(--hud-red)' }}>+{dangerData!.accumulated_score}</div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </section>
    );
}
