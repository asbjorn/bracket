import { CapacityBody, CapacityResponse } from '@openapi';
import { awaitRequestAndHandleError } from './adapter';

export async function calculateCapacity(body: CapacityBody) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post<CapacityResponse>('capacity', body),
  );
}
