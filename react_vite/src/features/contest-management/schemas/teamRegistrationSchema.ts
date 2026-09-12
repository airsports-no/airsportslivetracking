import { z } from 'zod';

// Mirrors TeamMemberSelectionSerialiser (src/display/serialisers.py): a discriminated union of
// an existing Person id, or the fields to create a new one. Copilot additionally allows "skip".
const personCreateFields = {
    first_name: z.string().min(1, 'First name is required'),
    last_name: z.string().min(1, 'Last name is required'),
    email: z.string().email('Invalid email').or(z.literal('')).optional(),
    phone: z.string().optional(),
    country: z.string().optional(),
};

export const pilotSelectionSchema = z.discriminatedUnion('mode', [
    z.object({ mode: z.literal('existing'), person: z.number() }),
    z.object({ mode: z.literal('create'), ...personCreateFields }),
]);

export const copilotSelectionSchema = z.discriminatedUnion('mode', [
    z.object({ mode: z.literal('skip') }),
    z.object({ mode: z.literal('existing'), person: z.number() }),
    z.object({ mode: z.literal('create'), ...personCreateFields }),
]);

// Mirrors AdminTeamRegistrationSerialiser's non-pilot/copilot fields.
export const teamRegistrationSchema = z.object({
    pilot: pilotSelectionSchema,
    copilot: copilotSelectionSchema,
    aeroplane: z.object({
        registration: z.string().min(1, 'Registration is required'),
        type: z.string().optional(),
        colour: z.string().optional(),
    }),
    club: z.object({
        name: z.string().min(1, 'Club name is required'),
        country: z.string().optional(),
    }),
    air_speed: z.coerce.number().positive('Airspeed must be positive'),
    tracking_service: z.string().min(1),
    tracking_device: z.string().min(1),
    tracker_device_id: z.string().optional(),
});

export type PilotSelection = z.infer<typeof pilotSelectionSchema>;
export type CopilotSelection = z.infer<typeof copilotSelectionSchema>;
// air_speed's z.coerce.number() has a different input (unknown, e.g. a string from an <input>)
// and output (number) type - see navigationTaskSchema.ts's NavigationTaskDetailsInput/FormValues
// split for the same zodResolver/react-hook-form generic mismatch this avoids.
export type TeamRegistrationFormInput = z.input<typeof teamRegistrationSchema>;
export type TeamRegistrationFormValues = z.output<typeof teamRegistrationSchema>;

export const teamRegistrationDefaults: TeamRegistrationFormValues = {
    pilot: { mode: 'create', first_name: '', last_name: '', email: '', phone: '', country: '' },
    copilot: { mode: 'skip' },
    aeroplane: { registration: '', type: '', colour: '' },
    club: { name: '', country: '' },
    air_speed: 70,
    tracking_service: 'traccar',
    tracking_device: 'pilot_app',
    tracker_device_id: '',
};

// Mirrors display.utilities.tracking_definitions.TRACKING_DEVICES. The fourth option's backend
// constant (TRACKING_PILOT_AND_COPILOT) used to be a corrupted, unusable value
// ("pilot_app_or_copilot_a[[") - fixed (with a data migration for any existing rows) to
// "pilot_app_or_copilot_app", so it's included here now.
export const TRACKING_DEVICE_CHOICES: { value: string; label: string }[] = [
    { value: 'device', label: 'Hardware GPS tracker' },
    { value: 'pilot_app', label: "Pilot's Air Sports Live Tracking app" },
    { value: 'copilot_app', label: "Copilot's Air Sports Live Tracking app" },
    { value: 'pilot_app_or_copilot_app', label: "Pilot's or copilot's Air Sports Live Tracking app" },
];

// Mirrors display.utilities.tracking_definitions.TrackingService.
export const TRACKING_SERVICE_CHOICES: { value: string; label: string }[] = [
    { value: 'traccar', label: 'Airsports' },
    { value: 'flymaster', label: 'Flymaster' },
];
