import type { Product } from '../types/index.ts';

/**
 * Exact condition used by CustomerMenu to render the "SOLD OUT" badge/overlay:
 * p.is_available === false || (p.stock_quantity !== undefined && p.stock_quantity <= 0)
 */
export const isProductSoldOut = (p: Product): boolean => {
  return p.is_available === false || (p.stock_quantity !== undefined && p.stock_quantity <= 0);
};

/**
 * Stable partition: available items first, sold-out items at bottom.
 * Guarantees 100% preservation of relative order within both available and sold-out groups.
 */
export const sortProductsWithSoldOutAtBottom = (products: Product[]): Product[] => {
  const available: Product[] = [];
  const soldOut: Product[] = [];
  for (const p of products) {
    if (isProductSoldOut(p)) {
      soldOut.push(p);
    } else {
      available.push(p);
    }
  }
  return [...available, ...soldOut];
};
