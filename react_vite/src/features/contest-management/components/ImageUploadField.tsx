import React, { useEffect, useRef, useState } from 'react';

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
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Synchronizing with an external system (the browser's object-URL store), not deriving
    // render state from a prop - creating the URL here (rather than during render, e.g. via
    // useMemo) means a discarded/re-run render (React StrictMode's double-invoke, a render that
    // throws) never leaks a URL that this effect's own cleanup wouldn't know to revoke.
    useEffect(() => {
        if (!value) {
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setPreviewUrl(null);
            return;
        }
        const url = URL.createObjectURL(value);
        setPreviewUrl(url);
        return () => URL.revokeObjectURL(url);
    }, [value]);

    const clear = () => {
        onChange(null);
        // Reset the native input too, not just our own value - otherwise re-selecting the exact
        // same file after clearing fires no change event (the input's own value didn't change
        // from the browser's point of view), so the clear would silently do nothing.
        if (inputRef.current) inputRef.current.value = '';
    };

    return (
        <label className="form-control w-full">
            <div className="label py-1"><span className="label-text">{label} (optional)</span></div>
            <div className="flex items-center gap-2">
                {previewUrl && <img src={previewUrl} alt="" className="w-8 h-8 rounded object-cover border border-base-300 flex-shrink-0" />}
                <input
                    ref={inputRef}
                    type="file"
                    accept="image/*"
                    className="file-input file-input-bordered file-input-xs w-full"
                    onChange={e => onChange(e.target.files?.[0] ?? null)}
                />
                {previewUrl && (
                    <button type="button" className="btn btn-ghost btn-xs flex-shrink-0" onClick={clear}>
                        Clear
                    </button>
                )}
            </div>
        </label>
    );
};

export default ImageUploadField;
