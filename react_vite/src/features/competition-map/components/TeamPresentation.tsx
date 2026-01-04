import React from 'react';
import { Contestant, DangerData, GateArrowData } from '../types'; // Remove NavigationTask import
import DangerThermometerDisplay from './DangerThermometerDisplay';
// Remove import for GateScoreArrowV2

interface Props {
    contestant: Contestant;
    score: number;
    dangerData?: DangerData;
    gateArrowData?: GateArrowData;
    // Remove navTask prop
}

const TeamPresentation = ({ contestant, score, dangerData, gateArrowData }: Props) => { // Remove navTask
    if (!contestant) return null;

    const { team } = contestant;
    const { crew, club } = team;

    return (
        <div className="flex items-end gap-4">
            {/* Right side: Thermometer */}
            <DangerThermometerDisplay dangerData={dangerData} />

            <div className="bg-base-100/80 backdrop-blur-md shadow-lg rounded-lg p-4 w-[450px]">
                {/* Top part with score and gate arrow */}
                <div className="grid grid-cols-2 gap-4 items-center">
                    <div>
                        <div className="text-5xl font-bold text-primary">{score.toFixed(0)}</div>
                        <div className="text-xs opacity-60">CURRENT SCORE</div>
                    </div>
                    <div className="bg-black/20 rounded-lg">
                        {/* Gate Score Arrow will be rendered externally */}
                        <div className="w-48 h-24 bg-base-300/50 rounded flex items-center justify-center text-sm text-white/70">Gate Score Arrow</div>
                    </div>
                </div>

                <div className="divider my-3"></div>

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
                                <div className="avatar ml-4">
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
        </div>
    );
};

export default TeamPresentation;
