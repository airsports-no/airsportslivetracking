import React from 'react';

interface Props {
    label: string;
    /** What the setting does, in a line, under its name. */
    hint: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    /** Why the setting cannot be changed; the setting is then off limits and this replaces the hint. */
    disabledReason?: string;
}

/** A switch in the map's settings menu, with its name and a line saying what it does (or why it is not available). */
export default function SettingToggle({ label, hint, checked, onChange, disabledReason }: Props) {
    const disabled = disabledReason !== undefined;
    return (
        <li title={disabledReason ?? hint}>
            <label className={`flex items-start justify-between gap-3 py-1 ${disabled ? 'opacity-60' : 'cursor-pointer'}`}>
                <span className="flex flex-col text-left min-w-0">
                    <span className="label-text text-xs">{label}</span>
                    <span className="text-[10px] leading-snug opacity-70">{disabledReason ?? hint}</span>
                </span>
                <input
                    type="checkbox"
                    className="toggle toggle-primary toggle-xs mt-0.5 flex-none"
                    checked={checked}
                    onChange={(e) => onChange(e.target.checked)}
                    disabled={disabled}
                />
            </label>
        </li>
    );
}
