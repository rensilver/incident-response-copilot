import type { Ref } from "react";
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
  headingRef,
}: Readonly<{
  report: IncidentReport;
  request: InvestigationRequest;
  headingRef: Ref<HTMLHeadingElement>;
}>): React.JSX.Element {
  return (
    <article className="report">
      <h2 ref={headingRef} tabIndex={-1}>
        Investigation report
      </h2>
      <p className="submitted-question">{request.query}</p>
      <dl className="report-context">
        <div>
          <dt>Service</dt>
          <dd translate="no">{request.service ?? "All services"}</dd>
        </div>
        {report.investigation_window ? (
          <>
            <div>
              <dt>Queried start (UTC)</dt>
              <dd>
                <time
                  translate="no"
                  dateTime={report.investigation_window.start}
                >
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
                <time translate="no" dateTime={report.investigation_window.end}>
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
        <p>{report.summary.trim() ? report.summary : "Summary unavailable."}</p>
        <p className="confidence">
          Overall model confidence:{" "}
          <span>{score.format(report.confidence)} / 1</span>
        </p>
      </section>
      <p className="report-note">
        Model confidence is not a calibrated probability or measured accuracy.
      </p>
      <section className="report-section" aria-labelledby="causes-title">
        <h3 id="causes-title">Possible causes</h3>
        <p className="report-note">
          Candidates are ranked by the model. Rank does not indicate severity or
          prove causality.
        </p>
        {report.likely_causes.length === 0 ? (
          <p>No supported cause candidates returned.</p>
        ) : null}
        <ol className="candidates" aria-label="Possible causes">
          {report.likely_causes.map((cause, index) => (
            <li key={index} className="candidate">
              <p className="candidate-rank">Candidate {index + 1}</p>
              <h4>
                {cause.title.trim()
                  ? cause.title
                  : "Candidate title unavailable."}
              </h4>
              <p>
                {cause.rationale.trim()
                  ? cause.rationale
                  : "Rationale unavailable."}
              </p>
              <p className="confidence">
                Candidate model confidence:{" "}
                <span>{score.format(cause.confidence)} / 1</span>
              </p>
              <h5>Supporting observations</h5>
              <p className="report-note">
                Report citations; verify against the source before acting.
              </p>
              {cause.supporting_evidence.length === 0 ? (
                <p>No supporting observations returned.</p>
              ) : null}
              <ul className="evidence">
                {cause.supporting_evidence.map((entry, position) => (
                  <li key={position}>
                    <span className="evidence-source">
                      {entry.source === "metrics" ? "Metrics" : "Logs"}
                    </span>
                    <p
                      translate="no"
                      className={entry.source === "logs" ? "log-detail" : ""}
                    >
                      {entry.detail.trim()
                        ? entry.detail
                        : "Observation text unavailable."}
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
        <p className="report-note">Suggested actions for review.</p>
        {report.next_steps.length === 0 ? <p>No next steps returned.</p> : null}
        <ul>
          {report.next_steps.map((step, index) => (
            <li key={index}>
              {step.trim() ? step : "Next step text unavailable."}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
