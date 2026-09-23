// Types mirror the Pydantic schemas in backend/app/schemas/.

export type Item = {
  id: number;
  title: string;
  description: string | null;
};

export type ItemCreate = Pick<Item, "title"> & { description?: string | null };

export type ProductCard = {
  id: number;
  article: string;
  name: string;
  category: string | null;
  price: number | null;
  stock: number;
  in_stock: boolean;
  stores: Record<string, number>;
  specs: Record<string, string>;
  min_qty: number;
  certificate_url: string | null;
  url: string | null;
  image: string | null;
};

export type Analog = ProductCard & { reason: string };

export type PendingAdd = {
  pending_id: string;
  product_id: number;
  article: string;
  name: string;
  price: number | null;
  qty: number;
  requested_qty: number;
  max_qty: number;
};

export type CartItem = {
  product_id: number;
  article: string;
  name: string;
  price: number | null;
  qty: number;
};

export type Cart = { cart_id: string; items: CartItem[]; total: number };

export type ChatRequest = { session_id: string; message: string; cart_id: string | null };

export type ChatResponse = {
  reply: string;
  products: ProductCard[];
  analogs: Analog[];
  pending: PendingAdd | null;
  cart_id: string;
  cart_url: string | null;
};

export type SpecStatus = "in_stock" | "partial" | "out_of_stock" | "not_found";

export type SpecLine = {
  row: number;
  query: string;
  requested_qty: number;
  status: SpecStatus;
  product: ProductCard | null;
  analog: Analog | null;
};

export type UploadResponse = ChatResponse & {
  filename: string;
  spec: SpecLine[];
  skipped_rows: number;
};

export const SPEC_ACCEPT = ".csv,.xlsx,.docx";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // JSON bodies get a JSON header; FormData (file upload) sets its own multipart header.
  const json = typeof init?.body === "string";
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { ...(json ? { "Content-Type": "application/json" } : {}), ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : response.statusText;
    throw new ApiError(response.status, detail);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  listItems: () => request<Item[]>("/items"),
  createItem: (data: ItemCreate) =>
    request<Item>("/items", { method: "POST", body: JSON.stringify(data) }),
  deleteItem: (id: number) => request<void>(`/items/${id}`, { method: "DELETE" }),

  chat: (data: ChatRequest) =>
    request<ChatResponse>("/chat", { method: "POST", body: JSON.stringify(data) }),
  uploadSpec: (file: File, sessionId: string, cartId: string | null) => {
    const form = new FormData();
    form.append("file", file);
    form.append("session_id", sessionId);
    if (cartId) form.append("cart_id", cartId);
    return request<UploadResponse>("/chat/upload", { method: "POST", body: form });
  },
  getCart: (cartId: string) => request<Cart>(`/cart/${encodeURIComponent(cartId)}`),
  confirmAdd: (cartId: string, pendingId: string) =>
    request<Cart>(`/cart/${encodeURIComponent(cartId)}/confirm`, {
      method: "POST",
      body: JSON.stringify({ pending_id: pendingId }),
    }),
  rejectAdd: (cartId: string, pendingId: string) =>
    request<void>(`/cart/${encodeURIComponent(cartId)}/reject`, {
      method: "POST",
      body: JSON.stringify({ pending_id: pendingId }),
    }),
};

export function formatPrice(value: number | null): string {
  return value === null ? "цена по запросу" : `${value.toLocaleString("ru-RU")} ₸`;
}
