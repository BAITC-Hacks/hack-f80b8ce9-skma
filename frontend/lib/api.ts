export type Item = {
  id: number;
  title: string;
  description: string | null;
};

export type ItemCreate = Pick<Item, "title"> & { description?: string | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  listItems: () => request<Item[]>("/items"),
  createItem: (data: ItemCreate) =>
    request<Item>("/items", { method: "POST", body: JSON.stringify(data) }),
  deleteItem: (id: number) => request<void>(`/items/${id}`, { method: "DELETE" }),
};
