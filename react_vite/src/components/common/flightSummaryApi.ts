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

export interface CrewGate {
  offset_seconds: number | null;
  points?: number;
}

export interface FieldAtGate {
  median_offset_seconds: number;
  other_crews: number;
  your_rank_by_precision?: number;
}

export interface FlightTiming {
  timed_gates: number;
  mean_absolute_offset_seconds: number;
  largest_absolute_offset_seconds: number;
  gates_within_2_seconds: number;
  gates_within_5_seconds: number;
  field_median_of_mean_absolute_offset_seconds: number;
  your_rank_by_mean_absolute_offset: number;
  crews_ranked: number;
}

export interface FlightAnalysis {
  planned_wind: Wind;
  weather_source: string | null;
  wind_height_ft_above_ground: number;
  legs: FlightLeg[];
  crews?: { crew: string; rank: number; score: number; gates: Record<string, CrewGate>; you?: boolean }[];
  field_at_gates?: Record<string, FieldAtGate>;
  timing?: FlightTiming | null;
}

export interface FlightSummaryStyle {
  key: string;
  label: string;
  /** Whether a summary in this style has been written for the flight's current scores. */
  written: boolean;
}

/** The AI summary of a flight as the server describes it (display/services/flight_summaries.py's summary_state). */
export interface FlightSummaryState {
  flight: { crew: string; contestant_number: number; task: string; contest: string };
  style: string;
  styles: FlightSummaryStyle[];
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

export async function fetchFlightSummary(contestantId: number, style: string): Promise<FlightSummaryState> {
  const url = `${reverse('flight-summaries-detail', contestantId)}?style=${encodeURIComponent(style)}`;
  const response = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(await errorDetail(response));
  return response.json();
}

export async function requestFlightSummary(
  contestantId: number,
  style: string,
  regenerate = false
): Promise<FlightSummaryState> {
  const response = await fetch(reverse('flight-summaries-generate', contestantId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')! },
    body: JSON.stringify({ regenerate, style }),
  });
  if (!response.ok) throw new Error(await errorDetail(response));
  return response.json();
}
