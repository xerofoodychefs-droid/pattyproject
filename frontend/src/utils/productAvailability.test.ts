import assert from 'node:assert/strict';
import test from 'node:test';
import { isProductSoldOut, sortProductsWithSoldOutAtBottom } from './productAvailability.ts';
import type { Product } from '../types/index.ts';

const createMockProduct = (id: string, name: string, overrides: Partial<Product> = {}): Product => ({
  id,
  name,
  sku: `SKU-${id}`,
  category_id: 'cat-1',
  base_price: 10,
  rating: 5,
  reviews_count: 10,
  is_bestseller: false,
  has_tax: true,
  has_service_charge: false,
  vat_category: 'STANDARD',
  is_active: true,
  is_available: true,
  is_out_of_stock: false,
  modifiers: [],
  ...overrides,
});

test('isProductSoldOut matches exact CustomerMenu SOLD OUT render condition', () => {
  // 1. Available product => false
  const availableProd = createMockProduct('1', 'Burger Available');
  assert.equal(isProductSoldOut(availableProd), false);

  // 2. is_available false => true
  const unavailableProd = createMockProduct('2', 'Burger Unavailable', { is_available: false });
  assert.equal(isProductSoldOut(unavailableProd), true);

  // 3. stock_quantity 0 => true
  const zeroStockProd = createMockProduct('3', 'Burger Zero Stock', { stock_quantity: 0 });
  assert.equal(isProductSoldOut(zeroStockProd), true);

  // 4. stock_quantity negative => true
  const negativeStockProd = createMockProduct('4', 'Burger Negative Stock', { stock_quantity: -1 });
  assert.equal(isProductSoldOut(negativeStockProd), true);

  // 5. Positive stock => false
  const positiveStockProd = createMockProduct('5', 'Burger Positive Stock', { stock_quantity: 15 });
  assert.equal(isProductSoldOut(positiveStockProd), false);

  // 6. is_active false alone => false (not classified as SOLD OUT by CustomerMenu badge)
  const inactiveOnlyProd = createMockProduct('6', 'Burger Inactive Only', { is_active: false, is_available: true, stock_quantity: 10 });
  assert.equal(isProductSoldOut(inactiveOnlyProd), false);

  // 7. is_out_of_stock true alone => false (CustomerMenu badge specifically relies on is_available and stock_quantity)
  const outOfStockOnlyProd = createMockProduct('7', 'Burger OOS Flag Only', { is_out_of_stock: true, is_available: true, stock_quantity: 10 });
  assert.equal(isProductSoldOut(outOfStockOnlyProd), false);
});

test('sortProductsWithSoldOutAtBottom moves sold-out items to bottom while preserving relative order', () => {
  // Scenario: Available A, Sold-out C, Available B, Sold-out D
  const prodA = createMockProduct('A', 'Product A (Available)');
  const prodC = createMockProduct('C', 'Product C (Sold Out: is_available false)', { is_available: false });
  const prodB = createMockProduct('B', 'Product B (Available)');
  const prodD = createMockProduct('D', 'Product D (Sold Out: stock_quantity 0)', { stock_quantity: 0 });

  const input = [prodA, prodC, prodB, prodD];
  const sorted = sortProductsWithSoldOutAtBottom(input);

  // 1. Available products appear first
  assert.equal(sorted[0].id, 'A');
  assert.equal(sorted[1].id, 'B');

  // 2. Sold-out products appear at bottom
  assert.equal(sorted[2].id, 'C');
  assert.equal(sorted[3].id, 'D');

  // 3. Relative order of available products preserved (A before B)
  assert.equal(sorted.indexOf(prodA) < sorted.indexOf(prodB), true);

  // 4. Relative order of sold-out products preserved (C before D)
  assert.equal(sorted.indexOf(prodC) < sorted.indexOf(prodD), true);
});

test('sortProductsWithSoldOutAtBottom handles all-available, all-soldout, and empty lists', () => {
  const p1 = createMockProduct('1', 'P1');
  const p2 = createMockProduct('2', 'P2');
  assert.deepEqual(
    sortProductsWithSoldOutAtBottom([p1, p2]).map((p) => p.id),
    ['1', '2']
  );

  const s1 = createMockProduct('s1', 'S1', { is_available: false });
  const s2 = createMockProduct('s2', 'S2', { stock_quantity: 0 });
  assert.deepEqual(
    sortProductsWithSoldOutAtBottom([s1, s2]).map((p) => p.id),
    ['s1', 's2']
  );

  assert.deepEqual(sortProductsWithSoldOutAtBottom([]), []);
});
