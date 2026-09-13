import React, { useEffect, useMemo } from 'react';

interface ImageUploadFieldProps {
    label: string;
    value: File | null | undefined;
    onChange: (file: File | null) => void;
}

// A small (32px) thumbnail preview next to a native file input - used by PersonSearchOrCreate/
// AeroplaneSearchOrCreate/ClubSearchOrCreate's "create new" branch. Deliberately optional and
// deliberately tiny: this is a convenience for organizers who happen to have a photo/logo handy
// during registration, not a required step, and it must not push the rest of the form (which
// needs to work on a phone during a briefing) off screen.
const ImageUploadField: React.FC<ImageUploadFieldProps> = ({ label, value, onChange }) => {
    // useMemo (not state) for the URL itself - the effect below only ever revokes it, it never
    // needs to set React state, which is what the "no setState in an effect body" lint rule cares
    // about; an object URL is a stable derivation of `value`, not something to synchronize in.
    const previewUrl = useMemo(() => (value ? URL.createObjectURL(value) : null), [value]);
    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
        };
    }, [previewUrl]);

    return (
        <label className="form-control w-full">
            <div className="label py-1"><span className="label-text">{label} (optional)</span></div>
            <div className="flex items-center gap-2">
                {previewUrl && <img src={previewUrl} alt="" className="w-8 h-8 rounded object-cover border border-base-300 flex-shrink-0" />}
                <input
                    type="file"
                    accept="image/*"
                    className="file-input file-input-bordered file-input-xs w-full"
                    onChange={e => onChange(e.target.files?.[0] ?? null)}
                />
                {previewUrl && (
                    <button type="button" className="btn btn-ghost btn-xs flex-shrink-0" onClick={() => onChange(null)}>
                        Clear
                    </button>
                )}
            </div>
        </label>
    );
};

export default ImageUploadField;
