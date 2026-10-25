import { ApiError } from "../../lib/api/client";

/** Map safe transport categories; never display error bodies or SDK diagnostics. */
export function failureMessage(error: unknown): string {
  if (!(error instanceof ApiError))
    return "The investigation could not complete. Check the backend before trying again.";
  switch (error.kind) {
    case "timeout":
      return "No response received within 5 minutes. Backend work may still be running. Review the question or window before trying again.";
    case "aborted":
      return "Request abandoned. Backend work may still be running.";
    case "network":
      return "The API could not be reached or the connection was lost. Check the backend connection before trying again. Backend work may still be running.";
    case "invalid-response":
      return "The API returned an invalid response. Check the backend before trying again.";
    case "http":
      switch (error.status) {
        case 401:
        case 403:
          return "The request was rejected. Check backend access settings before trying again.";
        case 422:
          return "The request was rejected. Review the question, service and window before trying again.";
        case 429:
          return "A request rate or quota limit was reached. Check provider limits before trying again.";
        case 503:
          return "Investigation unavailable. Check backend dependencies or model access before trying again.";
        case 504:
          return "Investigation deadline exceeded. Review the question or window before trying again.";
        case 500:
          return "The server could not complete the investigation. Check the backend before trying again.";
        default:
          return "The API returned an unsuccessful response. Check the backend before trying again.";
      }
  }
}
