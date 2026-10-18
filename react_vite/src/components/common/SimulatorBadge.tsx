import React from 'react';

interface SimulatorBadgeProps {
    /** The flight is a simulator flight (declared when it was booked, or tracked by the simulator). */
    isSimulator?: boolean;
    /** When positions were first ignored because of the task's simulator policy or the flight mode (the positions are not kept). */
    blockedPositionsAt?: string | null;
    /** When the phone first reported a simulated position (a fake-GPS app); the positions are still used. */
    mockPositionsAt?: string | null;
}

/** Marks a simulator flight, and tells organizers that positions were ignored (simulators are not accepted, or the other kind of flight). */
const SimulatorBadge: React.FC<SimulatorBadgeProps> = ({ isSimulator, blockedPositionsAt, mockPositionsAt }) => (
    <>
        {isSimulator && (
            <span className="badge badge-info badge-sm shrink-0" title="Flown in a flight simulator">SIM</span>
        )}
        {blockedPositionsAt && (
            <span
                className="badge badge-warning badge-sm shrink-0"
                title={`Positions were ignored from ${new Date(blockedPositionsAt).toLocaleString()}: a simulator position on a task that does not accept simulators, or a real position on a simulator flight (or the other way round).`}
            >
                ignored
            </span>
        )}
        {mockPositionsAt && (
            <span
                className="badge badge-error badge-sm shrink-0"
                title={`From ${new Date(mockPositionsAt).toLocaleString()} the pilot's phone reported simulated positions: a fake-GPS app or a simulated location was in use. The positions are scored as usual; check the flight.`}
            >
                fake GPS
            </span>
        )}
    </>
);

export default SimulatorBadge;
