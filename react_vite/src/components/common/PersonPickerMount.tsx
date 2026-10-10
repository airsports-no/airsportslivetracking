import React, { useState } from 'react';
import PersonPicker from './PersonPicker';
import { PersonOption } from './personOption';

interface PersonPickerMountProps {
    kind: 'person' | 'user';
    searchUrl: string;
    placeholder?: string;
    /** Called with the chosen id, or '' when cleared */
    onSelect: (id: string) => void;
}

/** Self-contained picker for server-rendered pages (see PersonPickerWidget.tsx). */
const PersonPickerMount: React.FC<PersonPickerMountProps> = ({ kind, searchUrl, placeholder, onSelect }) => {
    const [value, setValue] = useState<PersonOption | null>(null);
    return (
        <PersonPicker
            kind={kind}
            searchUrl={searchUrl}
            value={value}
            placeholder={placeholder}
            onChange={option => {
                setValue(option);
                onSelect(option ? String(option.value) : '');
            }}
        />
    );
};

export default PersonPickerMount;
