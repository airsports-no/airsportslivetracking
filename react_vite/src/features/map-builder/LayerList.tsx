import React, { useEffect, useRef } from 'react';

import type { LayerDefinition } from './engine/layers';
import { LAYER_GROUPS, LAYERS } from './engine/layers';
import { drawSwatch } from './engine/render';
import { sourcesForLayer } from './engine/sources';

const Swatch: React.FC<{ layer: LayerDefinition }> = ({ layer }) => {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    useEffect(() => {
        if (canvasRef.current) drawSwatch(canvasRef.current, layer);
    }, [layer]);
    return <canvas ref={canvasRef} width={40} height={16} className="rounded-sm border border-base-300 shrink-0" aria-hidden />;
};

interface Props {
    selection: Record<string, boolean>;
    sourceId: string;
    disabled: boolean;
    onChange(selection: Record<string, boolean>): void;
}

/** The map elements, grouped, each with a sample of its style and where its data comes from. */
const LayerList: React.FC<Props> = ({ selection, sourceId, disabled, onChange }) => (
    <div className="space-y-3">
        {LAYER_GROUPS.map(group => {
            const layers = LAYERS.filter(layer => layer.group === group.id)
                .map(layer => ({ layer, sources: sourcesForLayer(layer, sourceId) }))
                .filter(entry => entry.sources.length > 0);
            if (!layers.length) return null;
            return (
                <div key={group.id}>
                    <div className="text-xs font-semibold uppercase tracking-wide opacity-60 mb-1">{group.label}</div>
                    <div className="space-y-0.5">
                        {layers.map(({ layer, sources }) => (
                            <label key={layer.id} className="flex items-center gap-2 cursor-pointer py-0.5">
                                <input
                                    type="checkbox"
                                    className="checkbox checkbox-xs"
                                    checked={!!selection[layer.id]}
                                    disabled={disabled}
                                    onChange={event => onChange({ ...selection, [layer.id]: event.target.checked })}
                                />
                                <Swatch layer={layer} />
                                <span className="text-sm flex-1">{layer.label}</span>
                                <span
                                    className="badge badge-ghost badge-xs whitespace-nowrap"
                                    title={sources.map(source => source.name).join(' + ')}
                                >
                                    {sources.map(source => source.shortName).join('+')}
                                </span>
                            </label>
                        ))}
                    </div>
                </div>
            );
        })}
    </div>
);

export default LayerList;
