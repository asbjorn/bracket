import { awaitRequestAndHandleError } from './adapter';

export interface CategoryValues {
  name: string;
  age: number | null;
  results_public: boolean;
}

export async function createCategory(tournament_id: number, values: CategoryValues) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.post(`tournaments/${tournament_id}/categories`, values),
  );
}

export async function updateCategory(
  tournament_id: number,
  category_id: number,
  values: CategoryValues,
) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.put(`tournaments/${tournament_id}/categories/${category_id}`, values),
  );
}

export async function deleteCategory(tournament_id: number, category_id: number) {
  return awaitRequestAndHandleError(async (axios) =>
    axios.delete(`tournaments/${tournament_id}/categories/${category_id}`),
  );
}
