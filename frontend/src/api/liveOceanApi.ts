import type {
  OceanEmbedApi,
  FieldId,
  FieldPoint,
  Profile,
  ArgoFloat,
  RunStatus,
  Coordinate,
} from "./types";

/**
 * Base URL for the backend API.
 * In dev, Vite proxies /api → http://localhost:8000 (see vite.config.ts).
 * In production, the backend serves the built SPA and /api is on the same origin.
 */
const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

/**
 * Map frontend FieldId → backend Zarr variable name.
 * "uncertainty" maps to "temp_spread" because the backend stores the ensemble
 * spread alongside each physical variable.
 */
const FIELD_MAP: Record<FieldId, string> = {
  temperature: "temp",
  salinity: "sal",
  uncertainty: "temp_spread",
  tchp: "tchp",
  d26: "d26",
  mld: "mld",
};

/**
 * Map backend gate_status → frontend gate status string.
 * The backend stores "pass" / "fail".
 * The frontend uses "published" / "blocked" / "stale".
 */
function mapGateStatus(
  backendStatus: string
): "published" | "stale" | "blocked" {
  if (backendStatus === "pass") return "published";
  if (backendStatus === "fail") return "blocked";
  return "stale";
}

export const liveOceanApi: OceanEmbedApi = {
  getStatus: async () => {
    const res = await fetch(`${API_BASE}/v1/ocean/health`);
    if (!res.ok) throw new Error(`health: ${res.status}`);
    const data = await res.json();
    return {
      analysisWeek: data.week_label ?? "unknown",
      modelVersion: data.model_version ?? "unknown",
      gateStatus: mapGateStatus(data.gate_status ?? ""),
      sourceWindow: data.source_window ?? "",
      lastUpdated: data.published_at ?? "",
    } satisfies RunStatus;
  },

  getField: async (field: FieldId, depth: number) => {
    const variable = FIELD_MAP[field];
    const res = await fetch(
      `${API_BASE}/v1/ocean/field_json?variable=${variable}&depth=${depth}`
    );
    if (!res.ok) throw new Error(`field_json: ${res.status}`);
    return (await res.json()) as FieldPoint[];
  },

  getProfile: async (location: Coordinate) => {
    const res = await fetch(
      `${API_BASE}/v1/ocean/profile?lat=${location.lat}&lon=${location.lon}`
    );
    if (!res.ok) throw new Error(`profile: ${res.status}`);
    return (await res.json()) as Profile;
  },

  getArgoFloats: async () => {
    const res = await fetch(`${API_BASE}/v1/ocean/argo_floats`);
    if (!res.ok) throw new Error(`argo_floats: ${res.status}`);
    return (await res.json()) as ArgoFloat[];
  },
};
