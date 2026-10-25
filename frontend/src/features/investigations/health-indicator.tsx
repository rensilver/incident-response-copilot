"use client";

import { useEffect, useState } from "react";
import { createApiClient } from "../../lib/api/client";
import type { Health } from "../../lib/api/types";

const dependencyNames: Record<string, string> = {
  prometheus: "Prometheus",
  elasticsearch: "Elasticsearch",
  llm: "Model",
};

/** An independent reachability check never gates a deliberate submission. */
export function HealthIndicator(): React.JSX.Element {
  const [health, setHealth] = useState<Health | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void createApiClient()
      .health({ signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setHealth(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setUnavailable(true);
      });
    return () => controller.abort();
  }, []);

  return (
    <aside className="dependency-status" aria-label="Dependency checks">
      <p role="status">
        {unavailable
          ? "Dependency check unavailable"
          : health
            ? health.status === "ok"
              ? "Dependencies reachable"
              : "Dependencies degraded"
            : "Checking dependencies…"}
      </p>
      {health ? (
        <>
          <ul>
            {Object.entries(health.dependencies).map(([name, reachable]) => (
              <li key={name} className={reachable ? "" : "caution"}>
                {dependencyNames[name] ?? "Other dependency"}:{" "}
                {reachable ? "reachable" : "unreachable"}
              </li>
            ))}
          </ul>
          <p>Reachability does not guarantee a usable investigation.</p>
        </>
      ) : null}
    </aside>
  );
}
