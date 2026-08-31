// In-memory session set to ensure each accepted order is auto-printed at most once
const autoPrintedOrderIds = new Set<string>();

export const hasAutoPrinted = (orderId: string): boolean => {
  return autoPrintedOrderIds.has(orderId);
};

export const markAutoPrinted = (orderId: string): void => {
  autoPrintedOrderIds.add(orderId);
};
