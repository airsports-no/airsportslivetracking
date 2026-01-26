import React from 'react';
import { MapPin, AlertTriangle, HelpCircle } from 'lucide-react';
import { Contestant } from '../../competition-map/types';
import PublicityIcon from './PublicityIcon';
import { Route, Contest, NavigationTask } from '../types';
import TaskStatistics from './TaskStatistics';
import { formatDateInterval } from '../../../utils';
import { reverse } from '../../../urls';

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
                    {flight.overlap_warnings && flight.overlap_warnings.length > 0 && (
                        <div className="alert alert-warning text-sm shadow-sm p-3">
                            <AlertTriangle size={20} className="shrink-0" />
                            <div className="flex-1">
                                <span className="font-semibold">Overlapping contestants detected on this tracker.</span>
                                <div className="dropdown dropdown-top dropdown-end ml-1 align-middle inline-block">
                                    <label tabIndex={0} className="cursor-pointer text-warning-content/70 hover:text-warning-content"><HelpCircle size={16} /></label>
                                    <div tabIndex={0} className="dropdown-content z-[1] card card-compact w-80 p-2 shadow bg-base-100 text-base-content">
                                        <div className="card-body">
                                            <p>This tracker is shared by multiple contestants, causing simultaneous active flights in different tasks. To prevent data contamination, when a contestant crosses the start line, any earlier overlapping flights are automatically terminated.</p>
                                            {flight.overlapping_tasks && flight.overlapping_tasks.length > 0 && (
                                                <div className="mt-2">
                                                    <p className="font-semibold mb-1">Overlapping Tasks:</p>
                                                    <ul className="list-disc list-inside">
                                                        {flight.overlapping_tasks.map((task, idx) => (
                                                            <li key={idx}>
                                                                <a href={reverse('navigationtask_detail', task.task_id)} className="link" target="_blank" rel="noopener noreferrer">
                                                                    {task.task_name} ({task.reason})
                                                                </a>
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {flight.adaptive_start ? (
                        <div className="bg-info/10 border border-info/20 rounded-lg p-3 text-sm mb-2">
                            <p className="font-bold text-info mb-1 uppercase text-xs tracking-wider">Adaptive start</p>
                            <p>You must start and complete your flight within the following interval (contest time):</p>
                            <p className="font-mono mt-1">
                                {new Date(flight.tracker_start_time).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: contest.time_zone })} - {new Date(flight.finished_by_time).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: contest.time_zone })}
                            </p>
                        </div>
                    ) : (
                        <p>Take-off: {new Date(flight.takeoff_time).toLocaleString('en-GB', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: contest.time_zone })}</p>
                    )}
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
