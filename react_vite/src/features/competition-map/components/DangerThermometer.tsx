import React from 'react';

export default function DangerThermometer({ value = 0, height = 120 }: { value?: number; height?: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className="flex flex-col items-center">
      <div className="relative w-6" style={{ height }}>
        <div className="absolute inset-0 rounded-full bg-base-300" />
        <div
          className="absolute bottom-0 w-full rounded-b-full bg-error"
          style={{ height: `${clamped}%` }}
        />
      </div>
      <div className="mt-1 text-xs opacity-70">{clamped.toFixed(0)}%</div>
    </div>
  );
}
