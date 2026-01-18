import React from 'react';
import { MapPin } from 'lucide-react';
import { Contestant } from '../../competition-map/types';
import PublicityIcon from './PublicityIcon';
import { Route, Contest, NavigationTask } from '../types';
import TaskStatistics from './TaskStatistics';
import { formatDateInterval } from '../../../utils';

interface UpcomingFlightCardProps {
    flight: Contestant;
    contest: Contest;
    navTask: NavigationTask;
    onCancelClick: () => void;
}

const UpcomingFlightCard: React.FC<UpcomingFlightCardProps> = ({ flight, contest, navTask, onCancelClick }) => {
    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <h3 className="card-title flex items-center gap-2">
                    {navTask.name}
                    <PublicityIcon isPublic={navTask.is_public} isFeatured={navTask.is_featured} />
                    <div className="tooltip inline-flex" data-tip="View Live Tracking Map">
                        <a href={navTask.tracking_link} target="_blank" rel="noopener noreferrer" className="ml-2">
                            <MapPin size={20} />
                        </a>
                    </div>
                </h3>
                <p className="font-semibold">{contest.name}</p>
                
                <TaskStatistics route={navTask.route} flown_contestants_count={navTask.flown_contestants_count} />
                <p className="text-sm text-gray-500">{formatDateInterval(navTask.start_time, navTask.finish_time)}</p>

                <>
                    <p>Take-off: {new Date(flight.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: contest.time_zone })}</p>
                    {flight.latest_emaillink && (
                        <div className="text-sm mt-2">
                            <p className="font-semibold">Latest Flight Order:</p>
                            <a href={flight.latest_emaillink.url} className="link link-primary" target="_blank" rel="noopener noreferrer">
                                View Order (Generated: {new Date(flight.latest_emaillink.created_at).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })})
                            </a>
                        </div>
                    )}
                    <div className="grid grid-cols-3 gap-2 text-xs mt-2">
                        <div>
                            <p className="font-semibold">Planned Airspeed</p>
                            <p>{flight.air_speed} knots</p>
                        </div>
                        <div>
                            <p className="font-semibold">Wind Speed</p>
                            <p>{flight.wind_speed} knots</p>
                        </div>
                        <div>
                            <p className="font-semibold">Wind Direction</p>
                            <p>{flight.wind_direction}°</p>
                        </div>
                    </div>
                    <div className="card-actions justify-end">
                        <button onClick={onCancelClick} className="btn btn-error btn-sm">Cancel</button>
                    </div>
                </>
            </div>
        </div>
    );
};

export default UpcomingFlightCard;
