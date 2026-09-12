import { z } from 'zod';

// Mirrors NavigationTaskForm (src/display/forms.py) - the 14 fields the "details" step of
// navigation-task creation collects, independent of which task family/route entry point got us
// here. Server-side validation (NavigationTaskEditableRoutReferenceSerialiser) remains
// authoritative; this only gives the user immediate feedback before submitting.
export const navigationTaskDetailsSchema = z.object({
    name: z.string().min(1, 'Name is required').max(200),
    start_time: z.string().min(1, 'Start time is required'),
    finish_time: z.string().min(1, 'Finish time is required'),
    original_scorecard: z.string().min(1, 'Choose a scorecard'),
    display_background_map: z.boolean(),
    display_secrets: z.boolean(),
    minutes_to_starting_point: z.coerce.number(),
    planning_time: z.coerce.number().int(),
    minutes_to_landing: z.coerce.number(),
    wind_speed: z.coerce.number().min(0).max(40),
    wind_direction: z.coerce.number().min(0).max(360),
    allow_self_management: z.boolean(),
    calculation_delay_minutes: z.coerce.number().min(0),
});

// react-hook-form's field values are the pre-coercion shape (numeric inputs may arrive as
// strings from <input type="number">); zodResolver coerces them to the post-parse shape on
// submit. Keeping both named avoids a Resolver<> generic mismatch between the two.
export type NavigationTaskDetailsInput = z.input<typeof navigationTaskDetailsSchema>;
export type NavigationTaskDetailsFormValues = z.output<typeof navigationTaskDetailsSchema>;

export const navigationTaskDetailsDefaults: NavigationTaskDetailsInput = {
    name: '',
    start_time: '',
    finish_time: '',
    original_scorecard: '',
    display_background_map: true,
    display_secrets: true,
    minutes_to_starting_point: 5,
    planning_time: 45,
    minutes_to_landing: 30,
    wind_speed: 0,
    wind_direction: 0,
    allow_self_management: false,
    calculation_delay_minutes: 0,
};
