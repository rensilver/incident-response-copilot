export interface paths {
    "/api/v1/investigations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Investigate an incident
         * @description Run an investigation and return the structured report.
         */
        post: operations["create_investigation_api_v1_investigations_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Check application and dependency health
         * @description Report liveness and downstream reachability.
         *
         *     Probes run concurrently: each carries its own timeout, so awaiting them one
         *     after another would let ``/health`` outlast the timeout of whatever polls it.
         */
        get: operations["health_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * EvidenceRef
         * @description A pointer to the observation that supports a claim.
         */
        EvidenceRef: {
            /** Detail */
            detail: string;
            source: components["schemas"]["EvidenceSource"];
        };
        /**
         * EvidenceSource
         * @description Which subsystem a piece of evidence came from.
         * @enum {string}
         */
        EvidenceSource: "metrics" | "logs";
        /**
         * HealthResponse
         * @description Liveness plus reachability of each downstream dependency.
         */
        HealthResponse: {
            /** Dependencies */
            dependencies: {
                [key: string]: boolean;
            };
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "degraded";
        };
        /**
         * IncidentReport
         * @description The structured output of an investigation.
         */
        IncidentReport: {
            /** Confidence */
            confidence: number;
            /** @description Authoritative query interval, populated by the service after generation */
            investigation_window?: components["schemas"]["TimeWindow"] | null;
            /** Likely Causes */
            likely_causes: components["schemas"]["LikelyCause"][];
            /** Next Steps */
            next_steps: string[];
            /** Summary */
            summary: string;
        };
        /**
         * InvestigationErrorResponse
         * @description Sanitized response when an investigation cannot produce a usable report.
         */
        InvestigationErrorResponse: {
            /** Detail */
            detail: string;
        };
        /**
         * InvestigationRequest
         * @description What an engineer asks the copilot to look into.
         */
        InvestigationRequest: {
            /**
             * Minutes Back
             * @description Window length
             * @default 60
             */
            minutes_back?: number;
            /**
             * Query
             * @description The incident question
             */
            query: string;
            /**
             * Service
             * @description Service to focus on
             */
            service?: string | null;
        };
        /**
         * LikelyCause
         * @description One candidate root cause.
         */
        LikelyCause: {
            /** Confidence */
            confidence: number;
            /** Rationale */
            rationale: string;
            /** Supporting Evidence */
            supporting_evidence: components["schemas"]["EvidenceRef"][];
            /** Title */
            title: string;
        };
        /**
         * RequestErrorResponse
         * @description Sanitized validation errors using FastAPI's field-location convention.
         */
        RequestErrorResponse: {
            /** Detail */
            detail: components["schemas"]["ValidationIssue"][];
        };
        /**
         * TimeWindow
         * @description A closed time interval to investigate.
         */
        TimeWindow: {
            /**
             * End
             * Format: date-time
             */
            end: string;
            /**
             * Start
             * Format: date-time
             */
            start: string;
        };
        /**
         * ValidationIssue
         * @description A rejected field without its input, context, or parser diagnostics.
         */
        ValidationIssue: {
            /** Loc */
            loc: (string | number)[];
            /** Msg */
            msg: string;
            /** Type */
            type: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    create_investigation_api_v1_investigations_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InvestigationRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["IncidentReport"];
                };
            };
            /** @description Invalid request. */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequestErrorResponse"];
                };
            };
            /** @description Internal server error. */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvestigationErrorResponse"];
                };
            };
            /** @description Investigation unavailable: no usable report was produced. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvestigationErrorResponse"];
                };
            };
            /** @description Total investigation deadline exceeded. */
            504: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvestigationErrorResponse"];
                };
            };
        };
    };
    health_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthResponse"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InvestigationErrorResponse"];
                };
            };
        };
    };
}
