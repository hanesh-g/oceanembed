/**
 * API toggle — selects mock or live backend based on VITE_USE_MOCK env var.
 *
 * Usage in components:
 *   import { api } from "./api";
 *   const data = await api.getField("temperature", 50);
 *
 * To run frontend without a backend:
 *   VITE_USE_MOCK=true npm run dev
 */
import type { OceanEmbedApi } from "./types";
import { mockOceanApi } from "./mockOceanApi";
import { liveOceanApi } from "./liveOceanApi";

export const api: OceanEmbedApi =
  import.meta.env.VITE_USE_MOCK === "true" ? mockOceanApi : liveOceanApi;
