import React, { useRef, useState, useEffect } from 'react';
import { Contestant, DangerData, GateArrowData, NavigationTask } from '../types';
import DangerThermometerDisplay from './DangerThermometerDisplay';
import PlayingCards from './playing-cards/PlayingCards';
import GateScoreArrowV2 from './gateScoreArrow/GateScoreArrowV2';

interface Props {
    contestant: Contestant;
    score: number;
    dangerData?: DangerData;
    gateArrowData?: GateArrowData;
    navigationTask: NavigationTask | null;
    scale?: number;
}

const TeamPresentation = ({ contestant, score, dangerData, gateArrowData, navigationTask, scale = 1 }: Props) => {
    if (!contestant) return null;
    const { team } = contestant;
    const { crew, club } = team;
    const isPoker = navigationTask?.scorecard.task_type.includes("poker");

    return (
        <div className="flex flex-col sm:flex-row items-end gap-2 sm:gap-4" style={{ transform: `scale(${scale})`, transformOrigin: 'bottom right' }}>
            <div className="flex-shrink-0" style={{ width: isPoker ? 'auto' : '512px' }}>
                {isPoker ? (
                    contestant.playing_cards && contestant.playing_cards.length > 0 && (
                        <div className="mb-20 sm:mb-8">
                            <PlayingCards playingCards={contestant.playing_cards} />
                        </div>
                    )
                ) : (
                    <GateScoreArrowV2
                        contestant={contestant}
                        navigationTask={navigationTask}
                        gateArrowData={gateArrowData}
                    />
                )}
            </div>
            <div className="flex items-end gap-2 sm:gap-4 relative z-20">
                {/* Main Content Box: Score and Crew Info */}
                <div className="bg-base-100/80 backdrop-blur-md shadow-lg rounded-lg p-2 sm:p-3 w-auto"> 
                    <div className="flex items-center gap-3 sm:gap-4">
                        {/* Score moved inside for more horizontal layout */}
                        <div className="text-center px-2 border-r border-base-300">
                            <div className="text-2xl sm:text-4xl font-bold text-primary">{score.toFixed(0)}</div>
                            <div className="text-[8px] sm:text-xs opacity-60">SCORE</div>
                        </div>

                        <div className="avatar">
                            {crew.member1.picture ? (
                                <div className="w-16 h-20 sm:w-24 sm:h-32 rounded-lg ring ring-primary ring-offset-base-100 ring-offset-2 overflow-hidden">
                                    <img src={crew.member1.picture} alt={`${crew.member1.first_name} ${crew.member1.last_name}`} className="w-full h-full object-cover object-top" />
                                </div>
                            ) : (
                                <div className="placeholder bg-neutral-focus text-neutral-content w-16 h-20 sm:w-24 sm:h-32 rounded-lg ring ring-primary ring-offset-base-100 ring-offset-2">
                                    <span className="text-xl sm:text-3xl">{(crew.member1.first_name?.[0] || '') + (crew.member1.last_name?.[0] || '')}</span>
                                </div>
                            )}
                        </div>
                        <div className="max-w-[100px] sm:max-w-none">
                            <div className="font-bold text-sm sm:text-base truncate">{crew.member1.first_name} {crew.member1.last_name}</div>
                            <div className="text-[10px] sm:text-sm opacity-50 truncate">{club?.name ?? 'No club'}</div>
                        </div>

                        {crew.member2 && (
                            <>
                                <div className="avatar ml-2 sm:ml-4">
                                    {crew.member2.picture ? (
                                        <div className="w-16 h-20 sm:w-24 sm:h-32 rounded-lg overflow-hidden">
                                            <img src={crew.member2.picture} alt={`${crew.member2.first_name} ${crew.member2.last_name}`} className="w-full h-full object-cover object-top" />
                                        </div>
                                    ) : (
                                        <div className="placeholder bg-neutral-focus text-neutral-content w-16 h-20 sm:w-24 sm:h-32 rounded-lg">
                                            <span className="text-xl sm:text-3xl">{(crew.member2.first_name?.[0] || '') + (crew.member2.last_name?.[0] || '')}</span>
                                        </div>
                                    )}
                                </div>
                                <div className="max-w-[100px] sm:max-w-none">
                                    <div className="font-bold text-sm sm:text-base truncate">{crew.member2.first_name} {crew.member2.last_name}</div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
                
                {/* Thermometer Display (moved to the right) */}
                {dangerData && <DangerThermometerDisplay dangerData={dangerData} />}
            </div>
        </div>
    );
};

export default TeamPresentation;
