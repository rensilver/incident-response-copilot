/** Public wire types generated from FastAPI; dates remain ISO strings. */
import type { paths } from './generated/openapi.js';

type Investigation = paths['/api/v1/investigations']['post'];
export type InvestigationRequest = Investigation['requestBody']['content']['application/json'];
export type IncidentReport = Investigation['responses'][200]['content']['application/json'];
export type InvestigationError = Investigation['responses'][503]['content']['application/json'];
export type RequestError = Investigation['responses'][422]['content']['application/json'];
export type Health = paths['/health']['get']['responses'][200]['content']['application/json'];
