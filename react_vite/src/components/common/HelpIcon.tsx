import React from 'react';

interface HelpIconProps {
    text: string;
}

// The daisyUI tooltip shows on hover and on keyboard focus of its content, so the icon is made a
// focusable element that also carries the text as its accessible name.
const HelpIcon: React.FC<HelpIconProps> = ({ text }) => (
    <div
        className="tooltip tooltip-bottom ml-1 cursor-help before:z-50 before:max-w-64 before:whitespace-normal before:text-left"
        data-tip={text}
    >
        <span tabIndex={0} role="img" aria-label={text} className="inline-flex rounded focus-visible:outline focus-visible:outline-2">
            <svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" className="stroke-current text-info shrink-0 w-4 h-4"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        </span>
    </div>
);

export default HelpIcon;
