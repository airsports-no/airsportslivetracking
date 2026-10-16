// Real flights versus simulator flights: the task's policy and the flight mode a pilot declares when booking a flight
// (see documentation/PLAN_simulator_separation.md).

export type SimulatorPolicy = 'not_allowed' | 'allowed' | 'simulator_only';
export type FlightMode = 'real' | 'simulator';

export const SIMULATOR_POLICY_OPTIONS: { value: SimulatorPolicy; label: string }[] = [
    { value: 'not_allowed', label: 'Not allowed' },
    { value: 'allowed', label: 'Allowed, marked as simulator flights' },
    { value: 'simulator_only', label: 'Simulator only' },
];

export const SIMULATOR_POLICY_HELP =
    'Whether flights flown in a flight simulator are accepted. "Not allowed": positions from simulators are ignored (the default, ' +
    'for contests with real pilots). "Allowed": simulator flights count like any other and are marked as simulator flights. ' +
    '"Simulator only": positions from real trackers and the app are ignored. Changes take effect within about a minute.';

export const policyAcceptsMode = (policy: SimulatorPolicy | undefined, mode: FlightMode): boolean => {
    if (policy === 'not_allowed') return mode === 'real';
    if (policy === 'simulator_only') return mode === 'simulator';
    return true;
};

/** The clients that embed web pages tell the server who they are (see EmbedModeMiddleware); the website has no client. */
export const embedClient = (): string => document.configuration?.embedClient ?? '';

/** The flight mode a client implies (the MSFS client flies in the simulator, the phone apps fly real aircraft). */
export const impliedFlightMode = (client: string): FlightMode | null =>
    client === 'msfs' ? 'simulator' : client === 'android' || client === 'ios' ? 'real' : null;
