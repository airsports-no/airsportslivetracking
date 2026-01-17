import React from 'react';
import { Route } from '../types';
import {
    Milestone,
    MoveHorizontal,
    ShieldX,
    ShieldAlert,
    PlaneTakeoff,
    PlaneLanding,
    Camera,
    Plane
} from 'lucide-react';

interface TaskStatisticsProps {
    route: Route;
    flown_contestants_count: number;
}

const StatItem = ({ icon, label, value }: { icon: React.ReactNode, label: string, value: string | number }) => (
    <div className="flex items-center text-sm">
        <div className="tooltip" data-tip={label}>
            {icon}
        </div>
        <span className="ml-2">{value}</span>
    </div>
);


const TaskStatistics: React.FC<TaskStatisticsProps> = ({ route, flown_contestants_count }) => {
    return (
        <div className="card bg-base-200 shadow-inner mt-2">
            <div className="card-body p-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                    <StatItem icon={<Milestone size={20} />} label="Waypoints" value={route.number_of_wayoints} />
                    <StatItem icon={<MoveHorizontal size={20} />} label="Route Length" value={`${route.route_length_nm.toFixed(2)} NM`} />
                    <StatItem icon={<ShieldX size={20} />} label="Prohibited Zones" value={route.number_of_prohibited_zones} />
                    <StatItem icon={<ShieldAlert size={20} />} label="Penalty Zones" value={route.number_of_penalty_zones} />
                    <StatItem icon={<PlaneTakeoff size={20} />} label="Takeoff Gate" value={route.has_takeoff_gate ? 'Yes' : 'No'} />
                    <StatItem icon={<PlaneLanding size={20} />} label="Landing Gate" value={route.has_landing_gate ? 'Yes' : 'No'} />
                    <StatItem icon={<Camera size={20} />} label="Photos" value={route.number_of_photos} />
                    <StatItem icon={<Plane size={20} />} label="Flights Started" value={flown_contestants_count} />
                </div>
            </div>
        </div>
    );
};

export default TaskStatistics;
