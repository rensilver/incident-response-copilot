/** Server-rendered framing. Future interaction belongs in client leaf components. */
export function InvestigationWorkspace(): React.JSX.Element {
  return (
    <>
      <h1>Investigate an incident</h1>
      <p className="introduction">
        Follow observations from metrics and logs to possible causes and next
        steps.
      </p>
      <section className="preview" aria-labelledby="preview-title">
        <h2 id="preview-title">Foundation preview</h2>
        <p>Investigation controls and reports will appear here.</p>
      </section>
    </>
  );
}
