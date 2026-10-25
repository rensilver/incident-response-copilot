import type { IncidentReport, InvestigationRequest } from "../../lib/api/types";

const timestamp = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  year: "numeric",
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  fractionalSecondDigits: 3,
  hourCycle: "h23",
});
const score = new Intl.NumberFormat("en-US", { maximumSignificantDigits: 21 });

/** Present validated API observations without reconstructing telemetry. */
export function InvestigationReport({
  report,
  request,
}: Readonly<{
  report: IncidentReport;
  request: InvestigationRequest;
}>): React.JSX.Element {
  return (
    <article className="report">
      <h2>Investigation report</h2>
      <p className="submitted-question">{request.query}</p>
      <dl className="report-context">
        <div>
          <dt>Service</dt>
          <dd>{request.service ?? "All services"}</dd>
        </div>
        {report.investigation_window ? (
          <>
            <div>
              <dt>Queried start (UTC)</dt>
              <dd>
                <time dateTime={report.investigation_window.start}>
                  {timestamp.format(
                    new Date(report.investigation_window.start),
                  )}{" "}
                  UTC
                </time>
              </dd>
            </div>
            <div>
              <dt>Queried end (UTC)</dt>
              <dd>
                <time dateTime={report.investigation_window.end}>
                  {timestamp.format(new Date(report.investigation_window.end))}{" "}
                  UTC
                </time>
              </dd>
            </div>
          </>
        ) : (
          <div>
            <dt>Queried interval</dt>
            <dd>Investigation window unavailable</dd>
          </div>
        )}
      </dl>
      <section className="report-section" aria-labelledby="summary-title">
        <h3 id="summary-title">Summary</h3>
        <p>{report.summary}</p>
        <p className="confidence">
          Overall model confidence:{" "}
          <span>{score.format(report.confidence)} / 1</span>
        </p>
      </section>
      <section className="report-section" aria-labelledby="causes-title">
        <h3 id="causes-title">Possible causes</h3>
        <ol className="candidates" aria-label="Possible causes">
          {report.likely_causes.map((cause, index) => (
            <li key={index} className="candidate">
              <p className="candidate-rank">Candidate {index + 1}</p>
              <h4>{cause.title}</h4>
              <p>{cause.rationale}</p>
              <p className="confidence">
                Candidate model confidence:{" "}
                <span>{score.format(cause.confidence)} / 1</span>
              </p>
              <h5>Supporting observations</h5>
              <ul className="evidence">
                {cause.supporting_evidence.map((entry, position) => (
                  <li key={position}>
                    <span className="evidence-source">
                      {entry.source === "metrics" ? "Metrics" : "Logs"}
                    </span>
                    <p className={entry.source === "logs" ? "log-detail" : ""}>
                      {entry.detail}
                    </p>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ol>
      </section>
      <section className="report-section" aria-labelledby="steps-title">
        <h3 id="steps-title">Next steps</h3>
        <ul>
          {report.next_steps.map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ul>
      </section>
    </article>
  );
}
