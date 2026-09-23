import { CartView } from "./cart-view";

export default async function CartPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <CartView cartId={id} />
    </main>
  );
}
