import { HealthIndicator } from "./health-indicator";
import { InvestigationSession } from "./investigation-session";

/** Static framing with independent health and investigation client leaves. */
export function InvestigationWorkspace(): React.JSX.Element {
  return (
    <>
      <h1>Investigate an incident</h1>
      <p className="introduction">
        Follow observations from metrics and logs to possible causes and next
        steps.
      </p>
      <HealthIndicator />
      <InvestigationSession />
    </>
  );
}
