import { create } from 'zustand';
import { CartItem, Product, ProductModifier, SelectedChoice, Branch, User } from '../types';
import { api, getSafeStorage, setSafeStorage, removeSafeStorage } from '../api/client';

export const MIN_DELIVERY_SUBTOTAL = 15.00;

export interface ExtendedCartItem extends CartItem {
  id?: string; // Server CartItem ID
}

interface CartState {
  items: ExtendedCartItem[];
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
  isLoading: boolean;
  
  initCart: () => Promise<void>;
  fetchCart: () => Promise<void>;
  onAuthChange: (user: User | null) => Promise<void>;
  resetCartOnLogout: () => void;

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
  addItem: (product: Product, quantity: number, selectedModifiers: ProductModifier[], removedIngredients?: string[], selectedChoices?: SelectedChoice[]) => Promise<void>;
  updateQuantity: (index: number, quantity: number) => Promise<void>;
  removeItem: (index: number) => Promise<void>;
  applyCoupon: (code: string, discount: number) => void;
  removeCoupon: () => void;
  clearCart: () => Promise<void>;
  reconcileActiveBranches: (activeBranches: Branch[]) => void;
  
  getSubtotal: () => number;
  getDeliveryFee: () => number;
  getServiceFee: () => number;
  getNetAmount: () => number;
  getVatAmount: () => number;
  getTotal: () => number;
  isDeliverySubtotalEligible: () => boolean;
  getDeliveryShortfall: () => number;
}

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function getOrInitGuestSessionId(): string {
  let sid = getSafeStorage('patty_guest_session_id');
  if (!sid || sid.trim() === '') {
    sid = generateUUID();
    setSafeStorage('patty_guest_session_id', sid);
  }
  return sid;
}

export function getCartHeaders(): Record<string, string> {
  const token = getSafeStorage('patty_token');
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  } else {
    headers['X-Guest-Session-ID'] = getOrInitGuestSessionId();
  }
  return headers;
}

const safeGetStorage = <T>(key: string, fallback: T): T => {
  try {
    const raw = getSafeStorage(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
};

const safeSetStorage = (key: string, value: any) => {
  try {
    if (value === null || value === undefined) {
      removeSafeStorage(key);
    } else {
      setSafeStorage(key, JSON.stringify(value));
    }
  } catch {}
};

function mapServerCartResponse(data: any): ExtendedCartItem[] {
  if (!data || !Array.isArray(data.items)) return [];
  return data.items.map((i: any) => {
    const product: Product = {
      id: i.product?.id || i.product_id,
      name: i.product?.name || 'Product',
      sku: i.product?.sku || '',
      base_price: i.product?.base_price ?? 0,
      image_url: i.product?.image_url,
      is_active: i.product?.is_active ?? true,
      category_id: i.product?.category_id || '',
      rating: 5,
      reviews_count: 0,
      is_bestseller: false,
      has_tax: true,
      has_service_charge: false,
      vat_category: 'STANDARD',
      modifiers: []
    };

    const selectedModifiers: ProductModifier[] = (i.selected_modifiers || []).map((m: any) => ({
      id: m.name,
      name: m.name,
      price: Number(m.price) || 0,
      is_required: false,
      is_active: true
    }));

    return {
      id: i.id,
      product,
      quantity: i.quantity,
      selectedModifiers,
      selectedChoices: i.selected_choices || [],
      removedIngredients: i.removed_ingredients || [],
      lineTotal: i.line_total ?? (i.unit_price ? i.unit_price * i.quantity : product.base_price * i.quantity)
    };
  });
}

const initialBranch = safeGetStorage<Branch | null>('patty_selected_branch', null);
const initialOrderType = safeGetStorage<'DELIVERY' | 'COLLECTION'>('patty_order_type', 'COLLECTION');
const initialCoords = safeGetStorage<{ lat: number; lng: number; accuracy?: number } | null>('patty_user_coords', null);
const initialPostcode = safeGetStorage<string | null>('patty_user_postcode', null);

export const useCartStore = create<CartState>((set, get) => ({
  items: [],
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
  isLoading: false,

  initCart: async () => {
    await get().fetchCart();
  },

  fetchCart: async () => {
    try {
      set({ isLoading: true });
      const headers = getCartHeaders();
      const res: any = await api.get('/cart', { headers });
      if (res) {
        const mapped = mapServerCartResponse(res);
        set({
          items: mapped,
          couponCode: res.coupon_code || get().couponCode,
          orderType: (res.order_type as any) || get().orderType,
          isLoading: false
        });
      }
    } catch (err) {
      console.warn('[CartStore] Failed to fetch server cart:', err);
      set({ isLoading: false });
    }
  },

  onAuthChange: async (user: User | null) => {
    if (user) {
      // Authenticated login / merge flow
      const guestSessionId = getSafeStorage('patty_guest_session_id');
      try {
        if (guestSessionId) {
          const token = getSafeStorage('patty_token');
          await api.post(
            '/cart/merge',
            { guest_session_id: guestSessionId },
            {
              headers: {
                Authorization: `Bearer ${token}`,
                'X-Guest-Session-ID': guestSessionId
              }
            }
          );
          removeSafeStorage('patty_guest_session_id');
        }
      } catch (err) {
        console.warn('[CartStore] Merge failed or not needed:', err);
      }
      await get().fetchCart();
    } else {
      get().resetCartOnLogout();
    }
  },

  resetCartOnLogout: () => {
    // 1. Clear in-memory cart
    set({
      items: [],
      couponCode: null,
      discountAmount: 0
    });

    // 2. Remove all generic and user-scoped storage items
    removeSafeStorage('patty_cart_items');
    removeSafeStorage('patty_guest_cart_cache');

    // 3. Generate a brand new, unguessable guest session ID
    const newGuestSessionId = generateUUID();
    setSafeStorage('patty_guest_session_id', newGuestSessionId);
  },

  setOrderType: (type) => {
    const { isDeliveryEligible, deliveryDistanceMiles, isDeliverySubtotalEligible, getDeliveryShortfall } = get();
    // Non-negotiable rule 1: Distance radius <= 2.0 miles
    if (type === 'DELIVERY' && (!isDeliveryEligible || (deliveryDistanceMiles !== null && deliveryDistanceMiles > 2.0))) {
      safeSetStorage('patty_order_type', 'COLLECTION');
      set({ orderType: 'COLLECTION', locationErrorMsg: 'WE PROVIDE DELIVERY UP TO 2 MILES ONLY' });
      return;
    }
    // Non-negotiable rule 2: Minimum cart subtotal >= £15.00 OR valid promotion applied
    if (type === 'DELIVERY' && !isDeliverySubtotalEligible()) {
      const shortfall = getDeliveryShortfall();
      safeSetStorage('patty_order_type', 'COLLECTION');
      set({
        orderType: 'COLLECTION',
        locationErrorMsg: `Add £${shortfall.toFixed(2)} more to unlock delivery.`
      });
      return;
    }
    safeSetStorage('patty_order_type', type);
    set({ orderType: type, locationErrorMsg: null });

    // Sync settings to server
    const headers = getCartHeaders();
    api.patch('/cart/settings', { order_type: type }, { headers }).catch(() => {});
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

    if (effectiveBranch?.id) {
      const headers = getCartHeaders();
      api.patch('/cart/settings', { branch_id: effectiveBranch.id }, { headers }).catch(() => {});
    }
  },

  setUserCoords: (coords, postcode) => {
    safeSetStorage('patty_user_coords', coords);
    if (postcode !== undefined) safeSetStorage('patty_user_postcode', postcode);
    set({ userCoords: coords, userPostcode: postcode ?? get().userPostcode });
  },

  setLocationErrorMsg: (msg) => set({ locationErrorMsg: msg }),

  setProductModalOpen: (open) => set({ isProductModalOpen: open }),

  addItem: async (product, quantity, selectedModifiers, removedIngredients = [], selectedChoices = []) => {
    const isOutOfStock = product.is_available === false || product.is_active === false || (product.stock_quantity !== undefined && product.stock_quantity <= 0);
    if (isOutOfStock) return;

    const modCost = (selectedModifiers || []).reduce((acc, m) => acc + m.price, 0);
    const choiceCost = (selectedChoices || []).reduce((acc, c) => acc + c.price_delta, 0);
    const unitPrice = product.base_price + modCost + choiceCost;
    const lineTotal = unitPrice * quantity;

    // Optimistic update
    const prevItems = get().items;
    const optimisticItem: ExtendedCartItem = {
      product,
      quantity,
      selectedModifiers,
      selectedChoices,
      removedIngredients,
      lineTotal
    };
    set({ items: [...prevItems, optimisticItem] });

    try {
      const headers = getCartHeaders();
      const payload = {
        product_id: product.id,
        quantity,
        selected_modifiers: (selectedModifiers || []).map((m) => ({ name: m.name, price: m.price })),
        selected_choices: (selectedChoices || []).map((c) => ({
          group_id: c.group_id,
          group_name: c.group_name,
          option_id: c.option_id,
          option_name: c.option_name,
          price_delta: c.price_delta
        })),
        removed_ingredients: removedIngredients || []
      };
      const res: any = await api.post('/cart/items', payload, { headers });
      if (res) {
        set({ items: mapServerCartResponse(res) });
      }
    } catch (err) {
      console.error('[CartStore] Failed to add item to server cart:', err);
      // Revert to fetched state
      await get().fetchCart();
    }
  },

  updateQuantity: async (index, quantity) => {
    const currentItems = [...get().items];
    const item = currentItems[index];
    if (!item) return;

    if (quantity <= 0) {
      await get().removeItem(index);
      return;
    }

    const modCost = (item.selectedModifiers || []).reduce((acc, m) => acc + m.price, 0);
    const choiceCost = (item.selectedChoices || []).reduce((acc, c) => acc + c.price_delta, 0);
    const unitPrice = item.product.base_price + modCost + choiceCost;
    currentItems[index] = {
      ...item,
      quantity,
      lineTotal: unitPrice * quantity
    };
    set({ items: currentItems });

    try {
      const headers = getCartHeaders();
      if (item.id) {
        const res: any = await api.patch(`/cart/items/${item.id}`, { quantity }, { headers });
        if (res) {
          set({ items: mapServerCartResponse(res) });
        }
      } else {
        await get().fetchCart();
      }
    } catch (err) {
      console.error('[CartStore] Failed to update item quantity:', err);
      await get().fetchCart();
    }
  },

  removeItem: async (index) => {
    const currentItems = [...get().items];
    const item = currentItems[index];
    if (!item) return;

    set({ items: currentItems.filter((_, i) => i !== index) });

    try {
      const headers = getCartHeaders();
      if (item.id) {
        const res: any = await api.delete(`/cart/items/${item.id}`, { headers });
        if (res) {
          set({ items: mapServerCartResponse(res) });
        }
      } else {
        await get().fetchCart();
      }
    } catch (err) {
      console.error('[CartStore] Failed to remove item from cart:', err);
      await get().fetchCart();
    }
  },

  applyCoupon: (code, discount) => {
    set({ couponCode: code, discountAmount: discount });
    const headers = getCartHeaders();
    api.patch('/cart/settings', { coupon_code: code }, { headers }).catch(() => {});
  },

  removeCoupon: () => {
    set({ couponCode: null, discountAmount: 0 });
    const headers = getCartHeaders();
    api.patch('/cart/settings', { coupon_code: null }, { headers }).catch(() => {});
  },

  clearCart: async () => {
    set({ items: [], couponCode: null, discountAmount: 0 });
    try {
      const headers = getCartHeaders();
      await api.delete('/cart', { headers });
    } catch (err) {
      console.warn('[CartStore] Failed to clear server cart:', err);
    }
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
    return Math.round(get().items.reduce((acc, item) => acc + item.lineTotal, 0) * 100) / 100;
  },

  getDeliveryFee: () => {
    return 0.0;
  },

  getServiceFee: () => {
    return 0.0;
  },

  getVatAmount: () => {
    const subtotal = get().getSubtotal();
    const discount = get().discountAmount;
    const gross = Math.max(0, Math.round((subtotal - discount) * 100) / 100);
    return Math.round((gross * 20 / 120) * 100) / 100;
  },

  getNetAmount: () => {
    const subtotal = get().getSubtotal();
    const discount = get().discountAmount;
    const gross = Math.max(0, Math.round((subtotal - discount) * 100) / 100);
    const vat = Math.round((gross * 20 / 120) * 100) / 100;
    return Math.round((gross - vat) * 100) / 100;
  },

  getTotal: () => {
    const subtotal = get().getSubtotal();
    const discount = get().discountAmount;
    const gross = Math.max(0, Math.round((subtotal - discount) * 100) / 100);
    const delivery = get().getDeliveryFee();
    const service = get().getServiceFee();
    return Math.round((gross + delivery + service) * 100) / 100;
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
}));
