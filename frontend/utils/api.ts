/**
 * Unified API and WebSocket URL resolver for RE-PLAN-V frontend.
 * Remediates DEF-10 by avoiding hardcoded host:port combinations and
 * respecting NEXT_PUBLIC_API_URL / NEXT_PUBLIC_WS_URL environment overrides.
 */

export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    const port = process.env.NEXT_PUBLIC_API_PORT || "8080";
    return `http://${host}:${port}`;
  }
  return "http://127.0.0.1:8080";
}

export function getWebSocketUrl(path: string = "/ws/pipeline"): string {
  if (process.env.NEXT_PUBLIC_WS_URL) {
    const base = process.env.NEXT_PUBLIC_WS_URL.replace(/\/+$/, "");
    return `${base}${path.startsWith("/") ? path : `/${path}`}`;
  }
  if (typeof window !== "undefined") {
    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.hostname || "127.0.0.1";
    const port = process.env.NEXT_PUBLIC_API_PORT || "8080";
    return `${wsProtocol}//${host}:${port}${path.startsWith("/") ? path : `/${path}`}`;
  }
  return `ws://127.0.0.1:8080${path.startsWith("/") ? path : `/${path}`}`;
}
