import { create } from 'zustand';
import { CartItem, Product, ProductModifier, Branch } from '../types';

export const MIN_DELIVERY_SUBTOTAL = 15.00;

interface CartState {
  items: CartItem[];
  orderType: 'DELIVERY' | 'COLLECTION';
  selectedBranch: Branch | null;
  nearestBranchForCollection: Branch | null;
  deliveryDistanceMiles: number | null;
  isDeliveryEligible: boolean;
  userCoords: { lat: number; lng: number; accuracy?: number } | null;
  userPostcode: string | null;
  locationErrorMsg: string | null;
  couponCode: string | null;
  discountAmount: number;
  isProductModalOpen: boolean;
  
  setOrderType: (type: 'DELIVERY' | 'COLLECTION') => void;
  setSelectedBranch: (
    branch: Branch | null,
    distanceMiles?: number | null,
    isEligible?: boolean,
    nearestBranch?: Branch | null,
    locationMsg?: string | null,
    coords?: { lat: number; lng: number; accuracy?: number } | null,
    postcode?: string | null
  ) => void;
  setUserCoords: (coords: { lat: number; lng: number; accuracy?: number } | null, postcode?: string | null) => void;
  setLocationErrorMsg: (msg: string | null) => void;
  setProductModalOpen: (open: boolean) => void;
  addItem: (product: Product, quantity: number, selectedModifiers: ProductModifier[], removedIngredients?: string[]) => void;
  updateQuantity: (index: number, quantity: number) => void;
  removeItem: (index: number) => void;
  applyCoupon: (code: string, discount: number) => void;
  removeCoupon: () => void;
  clearCart: () => void;
  reconcileActiveBranches: (activeBranches: Branch[]) => void;
  
  getSubtotal: () => number;
  getDeliveryFee: () => number;
  getServiceFee: () => number;
  getTotal: () => number;
  isDeliverySubtotalEligible: () => boolean;
  getDeliveryShortfall: () => number;
}

const safeGetStorage = <T>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
};

const safeSetStorage = (key: string, value: any) => {
  try {
    if (value === null || value === undefined) {
      localStorage.removeItem(key);
    } else {
      localStorage.setItem(key, JSON.stringify(value));
    }
  } catch {}
};

const initialBranch = safeGetStorage<Branch | null>('patty_selected_branch', null);
const initialItems = safeGetStorage<CartItem[]>('patty_cart_items', []);
const initialOrderType = safeGetStorage<'DELIVERY' | 'COLLECTION'>('patty_order_type', 'COLLECTION');
const initialCoords = safeGetStorage<{ lat: number; lng: number; accuracy?: number } | null>('patty_user_coords', null);
const initialPostcode = safeGetStorage<string | null>('patty_user_postcode', null);

export const useCartStore = create<CartState>((set, get) => ({
  items: initialItems,
  orderType: initialOrderType,
  selectedBranch: initialBranch,
  nearestBranchForCollection: initialBranch,
  deliveryDistanceMiles: null,
  isDeliveryEligible: false,
  userCoords: initialCoords,
  userPostcode: initialPostcode,
  locationErrorMsg: null,
  couponCode: null,
  discountAmount: 0,
  isProductModalOpen: false,

  setOrderType: (type) => {
    const { isDeliveryEligible, deliveryDistanceMiles, isDeliverySubtotalEligible, getDeliveryShortfall } = get();
    // Non-negotiable rule 1: Distance radius <= 2.0 miles
    if (type === 'DELIVERY' && (!isDeliveryEligible || (deliveryDistanceMiles !== null && deliveryDistanceMiles > 2.0))) {
      safeSetStorage('patty_order_type', 'COLLECTION');
      set({ orderType: 'COLLECTION', locationErrorMsg: 'WE PROVIDE DELIVERY UP TO 2 MILES ONLY' });
      return;
    }
    // Non-negotiable rule 2: Minimum cart subtotal >= €15.00 OR valid promotion applied
    if (type === 'DELIVERY' && !isDeliverySubtotalEligible()) {
      const shortfall = getDeliveryShortfall();
      safeSetStorage('patty_order_type', 'COLLECTION');
      set({
        orderType: 'COLLECTION',
        locationErrorMsg: `Add €${shortfall.toFixed(2)} more to unlock delivery.`
      });
      return;
    }
    safeSetStorage('patty_order_type', type);
    set({ orderType: type, locationErrorMsg: null });
  },

  setSelectedBranch: (branch, distanceMiles, isEligible, nearestBranch, locationMsg, coords, postcode) => {
    const dist = distanceMiles ?? null;
    const eligible = Boolean(isEligible ?? (dist !== null && dist <= 2.0));
    const effectiveBranch = branch ?? nearestBranch ?? null;

    safeSetStorage('patty_selected_branch', effectiveBranch);
    if (coords !== undefined) safeSetStorage('patty_user_coords', coords);
    if (postcode !== undefined) safeSetStorage('patty_user_postcode', postcode);

    set({
      selectedBranch: effectiveBranch,
      nearestBranchForCollection: nearestBranch || effectiveBranch,
      deliveryDistanceMiles: dist,
      isDeliveryEligible: eligible,
      orderType: eligible ? get().orderType : 'COLLECTION', // Auto-switch to COLLECTION if outside 2 miles
      locationErrorMsg: locationMsg || (eligible ? null : 'WE PROVIDE DELIVERY UP TO 2 MILES ONLY'),
      userCoords: coords !== undefined ? coords : get().userCoords,
      userPostcode: postcode !== undefined ? postcode : get().userPostcode
    });
  },

  setUserCoords: (coords, postcode) => {
    safeSetStorage('patty_user_coords', coords);
    if (postcode !== undefined) safeSetStorage('patty_user_postcode', postcode);
    set({ userCoords: coords, userPostcode: postcode ?? get().userPostcode });
  },

  setLocationErrorMsg: (msg) => set({ locationErrorMsg: msg }),

  setProductModalOpen: (open) => set({ isProductModalOpen: open }),

  addItem: (product, quantity, selectedModifiers, removedIngredients = []) => {
    const isOutOfStock = product.is_available === false || (product.stock_quantity !== undefined && product.stock_quantity <= 0);
    if (isOutOfStock) return;

    const modCost = selectedModifiers.reduce((acc, m) => acc + m.price, 0);
    const unitPrice = product.base_price + modCost;
    const lineTotal = unitPrice * quantity;

    const newItems = [...get().items, { product, quantity, selectedModifiers, removedIngredients, lineTotal }];
    safeSetStorage('patty_cart_items', newItems);
    set({ items: newItems });
  },

  updateQuantity: (index, quantity) => {
    if (quantity <= 0) {
      get().removeItem(index);
      return;
    }
    const newItems = [...get().items];
    const item = newItems[index];
    if (!item) return;
    const modCost = item.selectedModifiers.reduce((acc, m) => acc + m.price, 0);
    const unitPrice = item.product.base_price + modCost;
    newItems[index] = {
      ...item,
      quantity,
      lineTotal: unitPrice * quantity
    };
    safeSetStorage('patty_cart_items', newItems);
    set({ items: newItems });
  },

  removeItem: (index) => {
    const newItems = get().items.filter((_, i) => i !== index);
    safeSetStorage('patty_cart_items', newItems);
    set({ items: newItems });
  },

  applyCoupon: (code, discount) => set({ couponCode: code, discountAmount: discount }),
  removeCoupon: () => set({ couponCode: null, discountAmount: 0 }),
  clearCart: () => {
    safeSetStorage('patty_cart_items', []);
    set({ items: [], couponCode: null, discountAmount: 0 });
  },

  reconcileActiveBranches: (activeBranches) => {
    const { selectedBranch } = get();
    if (!activeBranches || activeBranches.length === 0) return;
    if (!selectedBranch) return;

    // 1. Authoritative UUID match check
    const uuidMatch = activeBranches.find((b) => b.id === selectedBranch.id && b.is_active !== false);
    if (uuidMatch) {
      if (JSON.stringify(uuidMatch) !== JSON.stringify(selectedBranch)) {
        safeSetStorage('patty_selected_branch', uuidMatch);
        set({ selectedBranch: uuidMatch, nearestBranchForCollection: uuidMatch });
      }
      return;
    }

    // 2. Only when stored UUID is invalid/deleted: Exact unique code or name recovery
    const exactCodeMatches = activeBranches.filter(
      (b) => b.code && selectedBranch.code && b.code.trim().toUpperCase() === selectedBranch.code.trim().toUpperCase() && b.is_active !== false
    );
    if (exactCodeMatches.length === 1) {
      const recovered = exactCodeMatches[0];
      safeSetStorage('patty_selected_branch', recovered);
      set({ selectedBranch: recovered, nearestBranchForCollection: recovered });
      return;
    }

    const exactNameMatches = activeBranches.filter(
      (b) => b.name && selectedBranch.name && b.name.trim().toLowerCase() === selectedBranch.name.trim().toLowerCase() && b.is_active !== false
    );
    if (exactNameMatches.length === 1) {
      const recovered = exactNameMatches[0];
      safeSetStorage('patty_selected_branch', recovered);
      set({ selectedBranch: recovered, nearestBranchForCollection: recovered });
      return;
    }

    // 3. If invalid UUID and no exact recovery, reset branch to require explicit customer selection
    safeSetStorage('patty_selected_branch', null);
    set({ selectedBranch: null, nearestBranchForCollection: null });
  },

  getSubtotal: () => {
    return get().items.reduce((acc, item) => acc + item.lineTotal, 0);
  },

  getDeliveryFee: () => {
    // Patty Project delivery is FREE (£0.00 / €0.00). Radius and subtotal are eligibility checks.
    return 0.0;
  },

  getServiceFee: () => {
    return get().items.length > 0 ? 0.99 : 0.0;
  },

  getTotal: () => {
    const subtotal = get().getSubtotal();
    const delivery = get().getDeliveryFee();
    const service = get().getServiceFee();
    const discount = get().discountAmount;
    return Math.max(0, subtotal - discount + delivery + service);
  },

  isDeliverySubtotalEligible: () => {
    const subtotal = get().getSubtotal();
    const hasValidPromo = Boolean(get().couponCode && get().discountAmount > 0);
    return subtotal >= MIN_DELIVERY_SUBTOTAL || hasValidPromo;
  },

  getDeliveryShortfall: () => {
    const subtotal = get().getSubtotal();
    const hasValidPromo = Boolean(get().couponCode && get().discountAmount > 0);
    if (hasValidPromo || subtotal >= MIN_DELIVERY_SUBTOTAL) return 0.0;
    return Math.max(0, MIN_DELIVERY_SUBTOTAL - subtotal);
  }
}));;
