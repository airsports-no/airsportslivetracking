import { z } from 'zod';

// Extends contestCreationSchema.ts with the rest of the classic ContestForm's non-image fields.
// header_image/logo uploads stay out of scope (multipart, foreign to this JSON API client) - same
// deliberate scope reduction as contestCreationSchema.ts.
export const contestSettingsSchema = z.object({
    name: z.string().min(1, 'Name is required').max(100),
    time_zone: z.string().min(1, 'Choose a timezone'),
    location: z
        .string()
        .min(1, 'Location is required')
        .regex(/^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$/, 'Expected "latitude,longitude"'),
    start_time: z.string().min(1, 'Start time is required'),
    finish_time: z.string().min(1, 'Finish time is required'),
    organizing_club: z.number().nullable(),
    contest_website: z.string().url('Must be a valid URL').or(z.literal('')),
    summary_score_sorting_direction: z.enum(['asc', 'desc']),
    autosum_scores: z.boolean(),
});

export type ContestSettingsFormValues = z.infer<typeof contestSettingsSchema>;
