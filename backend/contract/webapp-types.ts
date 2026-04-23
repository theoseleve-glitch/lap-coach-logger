/**
 * TypeScript types for the Lap Coach webapp.
 *
 * Generated from backend/app/schemas.py via backend/openapi.json.
 * Keep in sync by running:
 *
 *   npx openapi-typescript http://localhost:8000/openapi.json -o lib/api-types.ts
 *
 * Or copy this file directly into your webapp's `lib/` directory.
 *
 * Last updated: 2026-04-16 from openapi.json (16 paths, 44KB).
 */

// =========================================================================
// Literals
// =========================================================================

export type SessionMode = "sprint" | "endurance" | "coaching" | "data";
export type Confidence = "high" | "medium" | "low";
export type CarClass = "GT3" | "GT4" | "GTE" | "LMP2" | "Hypercar" | "Formula" | "Cup" | "Touring";

// =========================================================================
// Auth
// =========================================================================

export interface LoginRequest {
    email: string;
    password: string;
}

export interface UserOut {
    id: string;        // UUID
    email: string;
    display_name: string;
}

// =========================================================================
// Ingest (desktop → backend) — included for reference, not used by webapp
// =========================================================================

export interface AcceptResponse {
    ok: true;
    envelope_id: string;     // UUID
    already_seen: boolean;
}

// =========================================================================
// Read (backend → webapp)
// =========================================================================

/**
 * GET /v1/sessions — one item per row.
 *
 * Canonical fields are null when the desktop's resolver didn't find a
 * match in its LUT. Webapp should show `raw_car` / `raw_track` as
 * fallback when `canonical_car_name` is null.
 */
export interface SessionSummary {
    session_id: string;
    sim: string;                          // raw sim_id, e.g. "iracing"
    track: string;                        // raw track name from sim
    car: string;                          // raw car name from sim
    mode: SessionMode;
    driver_name: string;
    start_time: string;                   // ISO 8601
    end_time: string | null;
    sample_count: number;
    lap_count: number;

    // Canonical (v2) — null if unresolved
    canonical_car_id: string | null;      // UUID
    canonical_car_name: string | null;    // "Ferrari 296 GT3"
    car_class: CarClass | null;           // "GT3"
    canonical_track_id: string | null;    // UUID
    canonical_track_name: string | null;  // "Monza"
    track_layout: string | null;          // "GP", "National", "Nordschleife"
}

/**
 * GET /v1/sessions/{session_id}
 */
export interface SessionDetail extends SessionSummary {
    source: string;                       // "desktop"
    schema_version: number;
    device_token: string;                 // last 8 chars shown in UI
    envelope_count: number;

    // v2 extensions
    bundle_hash: string | null;           // "sha256:..."
    analysis_json: AnalysisJson | null;

    // Child arrays
    laps: LapOut[];
    coaching: CoachingOut[];
    events: EventOut[];
}

// =========================================================================
// analysis_json — contents of the desktop's analysis.json
// =========================================================================

export interface AnalysisJson {
    schema_version: number;               // 1
    computed_at: string;                   // ISO 8601
    computed_by: "logger" | "backend";
    logger_version: string;

    session_quality: {
        overall_score: number;            // 0..1
        completeness: number;             // 0..1
        sample_rate_hz_measured: number;
        sample_rate_hz_target: number;
        telemetry_gaps_count: number;
        telemetry_gaps_total_s: number;
        channels_present_count: number;
        channels_missing_optional: string[];
    };

    lap_summary: {
        total_laps: number;
        valid_laps: number;
        invalid_laps: number;
        incomplete_laps: number;
        fastest_valid_lap_s: number | null;
        fastest_valid_lap_number: number | null;
        median_valid_lap_s: number | null;
        lap_time_std_dev_s: number | null;
        lap_consistency_pct: number | null;
    };

    stint_summary: {
        stint_count: number;
        longest_stint_laps: number;
        fuel_consumed_l: number;
        avg_fuel_per_lap_l: number | null;
        fuel_per_lap_std_l: number | null;
    };

    track_position: {
        best_sector_times_s: number[];
        best_theoretical_lap_s: number | null;
    };

    recommendation: {
        verdict: "ready_for_review" | "partial_data" | "not_recommended";
        blockers: string[];
        warnings: string[];
    };
}

// =========================================================================
// Child entities
// =========================================================================

export interface LapOut {
    lap_number: number;
    lap_time_s: number;
    valid: boolean;
    fuel_used_l: number;
    sector_times_s: number[];
    consistency_pct: number | null;
    std_dev_s: number | null;
}

export interface CoachingOut {
    consistency_score: number;
    trend: string;
    focus_area: string;
    recommendation: string;
    confidence: Confidence;
    emitted_at: string;                   // ISO 8601
}

export interface EventOut {
    event_type: string;
    occurred_at: string;                  // ISO 8601
    payload: Record<string, unknown>;
}

// =========================================================================
// Registry (desktop fetch at finalize time — webapp typically doesn't use)
// =========================================================================

export interface RegistrySnapshot {
    lut_version: string;
    cars: RegistryCar[];
    tracks: RegistryTrack[];
}

export interface RegistryCar {
    canonical_id: string;
    canonical_name: string;
    car_class: CarClass | null;
    manufacturer: string | null;
    model: string | null;
    year: number | null;
    aliases: { sim_id: string; raw_id: string }[];
}

export interface RegistryTrack {
    canonical_id: string;
    canonical_name: string;
    country: string | null;
    length_m: number | null;
    aliases: {
        sim_id: string;
        raw_id: string;
        raw_layout: string;
        canonical_layout: string | null;
    }[];
}

// =========================================================================
// Admin (curator tooling — webapp may display if curator role exists)
// =========================================================================

export interface CanonicalDrift {
    id: number;
    session_id: string;
    field: string;                        // "canonical_car_id" | "canonical_track_id" | "car_class" | "track_layout"
    submitted_value: string | null;
    backend_value: string | null;
    sim_id: string;
    raw_value: string;
    desktop_lut_version: string | null;
    backend_lut_version: string | null;
    detected_at: string;
}

export interface UnresolvedCanonical {
    id: number;
    sim_id: string;
    raw_car: string | null;
    raw_track: string | null;
    raw_track_layout: string | null;
    occurrence_count: number;
    first_seen_at: string;
    last_seen_at: string;
}
