import React from 'react';
import { DISPLAY_KEYS } from '../../utils/displayKeys';
import { guideUrl } from '../../utils/helpLink';

/** The display's keys, over the map until "?" or Esc is pressed again. */
export default function DisplayKeysHelp({ onClose }: { onClose: () => void }) {
    return (
        <div className="hud absolute top-16 right-3 z-[1200] rounded-lg border hud-divider shadow-xl p-4 w-80" role="dialog" aria-label="Keys">
            <div className="flex items-center justify-between mb-2">
                <h2 className="font-semibold">Keys</h2>
                <button className="hud-button" onClick={onClose} aria-label="Close">Close</button>
            </div>
            <dl className="grid grid-cols-[4.5rem_1fr] gap-x-3 gap-y-1.5 text-sm">
                {DISPLAY_KEYS.map(([keys, does]) => (
                    <React.Fragment key={keys}>
                        <dt className="hud-figure">{keys}</dt>
                        <dd className="hud-muted">{does}</dd>
                    </React.Fragment>
                ))}
            </dl>
            <a className="hud-label underline mt-3 inline-block" href={guideUrl('broadcast')} target="_blank" rel="noreferrer">
                More in the guide to the live map
            </a>
        </div>
    );
}
