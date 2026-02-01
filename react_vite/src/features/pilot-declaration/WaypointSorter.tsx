import React, { useEffect } from 'react';
import { ChevronUp, ChevronDown, Plus, X } from 'lucide-react';

interface WaypointSorterProps {
    freePoints: any[];
    order: string[];
    onChange: (order: string[]) => void;
}

export const WaypointSorter: React.FC<WaypointSorterProps> = ({ freePoints, order, onChange }) => {
    
    // Ensure all points in order actually exist (cleanup)
    useEffect(() => {
        const validNames = new Set(freePoints.map(p => p.name));
        const validOrder = order.filter(name => validNames.has(name));
        if (validOrder.length !== order.length) {
            onChange(validOrder);
        }
    }, [freePoints]);

    const availablePoints = freePoints.filter(p => !order.includes(p.name));

    const addToOrder = (name: string) => {
        onChange([...order, name]);
    };

    const removeFromOrder = (index: number) => {
        const newOrder = [...order];
        newOrder.splice(index, 1);
        onChange(newOrder);
    };

    const move = (index: number, direction: -1 | 1) => {
        if (index + direction < 0 || index + direction >= order.length) return;
        const newOrder = [...order];
        const temp = newOrder[index];
        newOrder[index] = newOrder[index + direction];
        newOrder[index + direction] = temp;
        onChange(newOrder);
    };

    return (
        <div className="flex flex-col md:flex-row gap-4">
            {/* Selected Sequence */}
            <div className="flex-1 bg-base-100 p-4 rounded shadow">
                <h3 className="font-bold mb-2">Planned Sequence</h3>
                {order.length === 0 && <p className="text-gray-500 italic">No points selected.</p>}
                <ul className="space-y-2">
                    {order.map((name, index) => (
                        <li key={`${name}-${index}`} className="flex items-center justify-between bg-base-200 p-2 rounded">
                            <span>{index + 1}. {name}</span>
                            <div className="flex gap-1">
                                <button className="btn btn-xs btn-ghost" onClick={() => move(index, -1)} disabled={index === 0}>
                                    <ChevronUp size={16} />
                                </button>
                                <button className="btn btn-xs btn-ghost" onClick={() => move(index, 1)} disabled={index === order.length - 1}>
                                    <ChevronDown size={16} />
                                </button>
                                <button className="btn btn-xs btn-ghost text-error" onClick={() => removeFromOrder(index)}>
                                    <X size={16} />
                                </button>
                            </div>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Available Points */}
            <div className="flex-1 bg-base-100 p-4 rounded shadow">
                <h3 className="font-bold mb-2">Available Free Points</h3>
                {availablePoints.length === 0 && <p className="text-gray-500 italic">All points selected.</p>}
                <div className="flex flex-wrap gap-2">
                    {availablePoints.map(p => (
                        <button 
                            key={p.name} 
                            className="btn btn-sm btn-outline"
                            onClick={() => addToOrder(p.name)}
                        >
                            <Plus size={14} /> {p.name}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );
};
