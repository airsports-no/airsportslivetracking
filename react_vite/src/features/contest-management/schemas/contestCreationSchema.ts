import { z } from 'zod';

// Mirrors ContestSerialiser's writable fields (src/display/serialisers.py) for the subset this
// inline-creation step collects. `country` is deliberately omitted - the backend derives it from
// `location` in ContestSerialiser.validate(), unlike the Django wizard's ContestForm, which had a
// real bug here (see the migration plan's "real bugs fixed" list). header_image/logo uploads are
// out of scope for this quick-create step - they can be added afterwards via the classic contest
// update page (linked from the management page's "Advanced settings").
export const contestCreationSchema = z.object({
    name: z.string().min(1, 'Name is required').max(100),
    time_zone: z.string().min(1, 'Choose a timezone'),
    location: z
        .string()
        .min(1, 'Location is required')
        .regex(/^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$/, 'Expected "latitude,longitude"'),
    start_time: z.string().min(1, 'Start time is required'),
    finish_time: z.string().min(1, 'Finish time is required'),
    organizing_club: z.number().nullable(),
});

export type ContestCreationFormValues = z.infer<typeof contestCreationSchema>;

export const contestCreationDefaults: ContestCreationFormValues = {
    name: '',
    time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    location: '',
    start_time: '',
    finish_time: '',
    organizing_club: null,
};
