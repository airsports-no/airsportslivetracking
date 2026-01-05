import React from 'react';
import { Contestant, DangerData, GateArrowData } from '../types'; // Remove NavigationTask import
import DangerThermometerDisplay from './DangerThermometerDisplay';
// Remove import for GateScoreArrowV2

interface Props {
    contestant: Contestant;
    score: number;
    dangerData?: DangerData;
    gateArrowData?: GateArrowData;
    // navTask prop is removed from TeamPresentation
}

const TeamPresentation = ({ contestant, score, dangerData, gateArrowData }: Props) => { // Remove navTask
    if (!contestant) return null;

    const { team } = contestant;
    const { crew, club } = team;

    return (
        <div className="flex items-end gap-4">
            {/* Main Content Box: Score and Crew Info */}
            <div className="bg-base-100/80 backdrop-blur-md shadow-lg rounded-lg p-3 w-auto"> {/* Removed fixed width, reduced padding */}
                {/* Top part with score (Gate Score Arrow placeholder removed) */}
                <div className="text-center mb-2"> {/* Simplified layout, smaller font for compactness */}
                    <div className="text-4xl font-bold text-primary">{score.toFixed(0)}</div>
                    <div className="text-xs opacity-60">CURRENT SCORE</div>
                </div>

                {/* Removed divider my-3 */}

                {/* Bottom part with crew info */}
                <div className="flex items-center gap-4">
                    {crew.member1.picture && (
                        <div className="avatar">
                            <div className="w-16 rounded-full ring ring-primary ring-offset-base-100 ring-offset-2">
                                <img src={crew.member1.picture} alt={`${crew.member1.first_name} ${crew.member1.last_name}`}/>
                            </div>
                        </div>
                    )}
                    <div>
                        <div className="font-bold">{crew.member1.first_name} {crew.member1.last_name}</div>
                        <div className="text-sm opacity-50">{club?.name ?? 'No club'}</div>
                    </div>

                    {crew.member2 && (
                        <>
                             {crew.member2.picture && (
                                <div className="avatar ml-4"> {/* Removed ml-4 for compactness */}
                                    <div className="w-16 rounded-full">
                                        <img src={crew.member2.picture} alt={`${crew.member2.first_name} ${crew.member2.last_name}`} />
                                    </div>
                                </div>
                            )}
                            <div>
                                <div className="font-bold">{crew.member2.first_name} {crew.member2.last_name}</div>
                            </div>
                        </>
                    )}
                </div>
            </div>
            
            {/* Thermometer Display (moved to the right) */}
            <DangerThermometerDisplay dangerData={dangerData} />
        </div>
    );
};

export default TeamPresentation;
