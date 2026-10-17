import React from 'react';
import HelpIcon from './HelpIcon';
import { SIMULATOR_POLICY_HELP, SimulatorPolicy } from '../../utils/simulatorPolicy';

interface SimulatorPolicyChoiceProps {
    value: SimulatorPolicy;
    onChange: (value: SimulatorPolicy) => void;
    /** Radio group name: must be unique on the page. */
    name?: string;
    /** Self-management is off: tell organizers of a simulator-only task that pilots then cannot book their own flights. */
    suggestSelfManagement?: boolean;
}

const CHOICES: { value: SimulatorPolicy; title: string; description: string }[] = [
    {
        value: 'not_allowed',
        title: 'Real pilots only',
        description: 'Positions from flight simulators are ignored. Choose this for real competitions: simulator pilots cannot disturb the results.',
    },
    {
        value: 'allowed',
        title: 'Real and simulator pilots',
        description: 'Simulator flights count like any other flight and are marked SIM in the results.',
    },
    {
        value: 'simulator_only',
        title: 'Simulator pilots only',
        description: 'Positions from real trackers and the app are ignored. For tasks that are flown in a flight simulator.',
    },
];

/** "Who will fly this task?": the task's simulator policy as three plain choices, with what each one means for the positions. */
const SimulatorPolicyChoice: React.FC<SimulatorPolicyChoiceProps> = ({ value, onChange, name = 'simulator_policy', suggestSelfManagement }) => (
    <fieldset className="form-control w-full rounded-lg border border-base-300 p-3">
        <legend className="label-text inline-flex items-center px-1 font-semibold">
            Who will fly this task?<HelpIcon text={SIMULATOR_POLICY_HELP} />
        </legend>
        <div className="space-y-2">
            {CHOICES.map((choice) => (
                <label key={choice.value} className="flex cursor-pointer items-start gap-3">
                    <input
                        type="radio"
                        className="radio radio-sm mt-1"
                        name={name}
                        value={choice.value}
                        checked={value === choice.value}
                        onChange={() => onChange(choice.value)}
                    />
                    <span>
                        <span className="block font-medium">{choice.title}</span>
                        <span className="block text-sm text-base-content/70">{choice.description}</span>
                    </span>
                </label>
            ))}
        </div>
        {value === 'simulator_only' && suggestSelfManagement && (
            <p className="mt-2 text-sm text-info">
                Tip: tick "Allow self-management" further down so that simulator pilots can book their own flights.
            </p>
        )}
    </fieldset>
);

export default SimulatorPolicyChoice;
