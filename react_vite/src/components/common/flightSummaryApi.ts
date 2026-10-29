import { reverse } from '../../urls';
import { getCookie } from '../../utils/csrf';

export interface FlightSummarySection {
  emoji: string;
  title: string;
  text: string;
}

interface Wind {
  speed_kt: number;
  direction: number;
}

/** A leg of the route as display/services/flight_analysis.py works it out. */
export interface FlightLeg {
  from: string;
  to: string;
  distance_nm: number;
  track: number;
  planned_seconds: number | null;
  actual_seconds: number | null;
  offset_at_end_seconds: number | null;
  planned_headwind_kt: number;
  actual_wind: Wind | null;
  actual_headwind_kt: number | null;
  wind_effect_seconds: number | null;
}

export interface FlightAnalysis {
  planned_wind: Wind;
  weather_source: string | null;
  wind_height_ft_above_ground: number;
  legs: FlightLeg[];
}

/** The AI summary of a flight as the server describes it (display/services/flight_summaries.py's summary_state). */
export interface FlightSummaryState {
  enabled: boolean;
  status: 'pending' | 'done' | 'failed' | null;
  text: string;
  headline: string;
  sections: FlightSummarySection[];
  analysis: FlightAnalysis | null;
  requested_at: string | null;
  can_generate: boolean;
  can_regenerate: boolean;
  reason: string | null;
  remaining_today: number | null;
  // Superusers only
  model?: string;
  cost_usd?: string;
  error?: string;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return data.detail || response.statusText;
  } catch {
    return response.statusText;
  }
}

export async function fetchFlightSummary(contestantId: number): Promise<FlightSummaryState> {
  const response = await fetch(reverse('flight-summaries-detail', contestantId), { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await errorDetail(response));
  return response.json();
}

export async function requestFlightSummary(contestantId: number, regenerate = false): Promise<FlightSummaryState> {
  const response = await fetch(reverse('flight-summaries-generate', contestantId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')! },
    body: JSON.stringify({ regenerate }),
  });
  if (!response.ok) throw new Error(await errorDetail(response));
  return response.json();
}
