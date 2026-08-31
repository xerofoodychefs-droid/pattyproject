import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Trash2,
  Tag,
  ShoppingBag,
  ChevronRight,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Check,
  Copy,
  X,
  AlertCircle
} from 'lucide-react';
import { useCartStore } from '../../store/cartStore';
import { useShopHoursStore, formatTime12h } from '../../store/shopHoursStore';
import { api } from '../../api/client';

interface AvailableCoupon {
  code: string;
  name: string;
  description: string;
  coupon_type: string;
  discount_value: number;
  min_order_value: number;
  badge: string;
}

export const CustomerCart: React.FC = () => {
  const {
    items,
    updateQuantity,
    removeItem,
    applyCoupon,
    removeCoupon,
    couponCode,
    discountAmount,
    getSubtotal,
    getNetAmount,
    getVatAmount,
    getTotal
  } = useCartStore();

  const [promoInput, setPromoInput] = useState('');
  const [promoMsg, setPromoMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [showAvailablePromos, setShowAvailablePromos] = useState(false);
  const [availableCoupons, setAvailableCoupons] = useState<AvailableCoupon[]>([]);
  const [isCouponsLoaded, setIsCouponsLoaded] = useState(false);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const { isOpen, openingTime, closingTime, fetchShopStatus } = useShopHoursStore();

  useEffect(() => {
    fetchShopStatus();
  }, [fetchShopStatus]);

  // Load available promo codes from backend
  useEffect(() => {
    fetchAvailableCoupons();
  }, []);

  const fetchAvailableCoupons = async () => {
    try {
      const data = await api.get<AvailableCoupon[]>('/promotions/available');
      const validCoupons = Array.isArray(data) ? data : [];
      setAvailableCoupons(validCoupons);
      setIsCouponsLoaded(true);

      // Reconcile currently applied coupon against authoritative API response
      const currentAppliedCode = useCartStore.getState().couponCode;
      if (currentAppliedCode) {
        const isPresent = validCoupons.some(
          (c) => c.code.trim().toUpperCase() === currentAppliedCode.trim().toUpperCase()
        );
        if (!isPresent) {
          removeCoupon();
          setPromoInput('');
          setPromoMsg(null);
        }
      }
    } catch (e) {
      console.error('Failed to load available coupons:', e);
      setAvailableCoupons([]);
      setIsCouponsLoaded(true);

      // On API failure, clear any stale applied coupon for safety
      if (useCartStore.getState().couponCode) {
        removeCoupon();
        setPromoInput('');
        setPromoMsg(null);
      }
    }
  };

  // Continuously reconcile if applied coupon is invalidated or if availableCoupons update
  useEffect(() => {
    if (!isCouponsLoaded) return;
    if (couponCode) {
      const isPresent = availableCoupons.some(
        (c) => c.code.trim().toUpperCase() === couponCode.trim().toUpperCase()
      );
      if (!isPresent) {
        removeCoupon();
        setPromoInput('');
        setPromoMsg(null);
      }
    }
  }, [couponCode, availableCoupons, isCouponsLoaded, removeCoupon]);

  const handleApplyPromo = async (codeToApply?: string) => {
    const targetCode = (codeToApply || promoInput).trim().toUpperCase();
    if (!targetCode) {
      setPromoMsg({ text: 'Please enter a promo code', isError: true });
      return;
    }

    setIsLoading(true);
    setPromoMsg(null);

    try {
      const currentSubtotal = getSubtotal();
      const res: any = await api.get(`/promotions/validate?code=${targetCode}&subtotal=${currentSubtotal}`);
      const discount = res.discount_amount || res.calculated_discount || 0;
      applyCoupon(res.code, discount);
      setPromoInput(res.code);
      setPromoMsg({
        text: `Promo code "${res.code}" applied! Saved £${discount.toFixed(2)}`,
        isError: false
      });
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || err.message || 'Invalid or expired promo code';
      setPromoMsg({ text: errorMsg, isError: true });
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectPromoCard = (coupon: AvailableCoupon) => {
    setPromoInput(coupon.code);
    setCopiedCode(coupon.code);
    setTimeout(() => setCopiedCode(null), 2000);

    // Auto apply code
    handleApplyPromo(coupon.code);
  };

  const handleRemovePromo = () => {
    removeCoupon();
    setPromoInput('');
    setPromoMsg({ text: 'Promo code removed', isError: false });
  };

  const subtotal = getSubtotal();
  const net = getNetAmount();
  const vat = getVatAmount();
  const total = getTotal();

  const hasOutOfStockItems = items.some(
    (item) => item.product.is_available === false || (item.product.stock_quantity !== undefined && item.product.stock_quantity <= 0)
  );

  return (
    <div className="w-full max-w-[1060px] mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 pb-20 text-[#F5F5F5]">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-4 mb-6 border-b border-[#1C1C1C]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F5F5F5] tracking-tight">
            Your Cart
          </h1>
          <p className="text-xs sm:text-sm text-[#A1A1AA] font-normal mt-0.5">
            Review your selected items and options before checkout.
          </p>
        </div>

        <Link
          to="/order"
          className="flex items-center gap-1.5 text-xs sm:text-sm text-[#A1A1AA] hover:text-[#F5F5F5] font-medium transition-colors group"
        >
          <ArrowLeft className="w-4 h-4 text-[#FF5A00] group-hover:-translate-x-1 transition-transform" />
          <span>Continue Shopping</span>
        </Link>
      </div>

      {hasOutOfStockItems && (
        <div className="mb-5 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg p-3 text-xs text-[#EF4444] font-medium flex items-center gap-2">
          <span>Some items in your cart are currently out of stock at this location. Please remove them before proceeding to checkout.</span>
        </div>
      )}

      {items.length === 0 ? (
        /* Empty Cart State */
        <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-8 sm:p-12 text-center space-y-4 max-w-md mx-auto my-10 shadow-xl">
          <div className="w-12 h-12 rounded-lg bg-[#151515] border border-[#242424] flex items-center justify-center text-[#FF5A00] mx-auto">
            <ShoppingBag className="w-6 h-6" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-[#F5F5F5]">Your cart is empty</h2>
            <p className="text-xs text-[#A1A1AA] leading-relaxed">
              Looks like you haven't added any items to your cart yet.
            </p>
          </div>
          <Link
            to="/order"
            className="inline-flex h-10 items-center justify-center bg-[#FF5A00] hover:bg-[#E84F00] text-white px-5 rounded-lg text-xs sm:text-sm font-semibold transition-all shadow-md cursor-pointer"
          >
            Browse Menu
          </Link>
        </div>
      ) : (
        /* 2-Column Main Desktop Layout */
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          
          {/* LEFT COLUMN: Cart Items List */}
          <div className="lg:col-span-7 space-y-3">
            {items.map((item, idx) => {
              const displayImg = item.product.image_url || '/placeholder-burger.svg';
              const isItemOutOfStock = item.product.is_available === false || (item.product.stock_quantity !== undefined && item.product.stock_quantity <= 0);

              return (
                <div
                  key={idx}
                  className={`bg-[#0D0D0D] border rounded-[10px] p-3.5 sm:p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3.5 transition-colors ${
                    isItemOutOfStock ? 'border-[#EF4444]/40 bg-[#140808]' : 'border-[#242424] hover:border-[#333333]'
                  }`}
                >
                  {/* Product Image & Info Container */}
                  <div className="flex items-start gap-3 min-w-0 flex-1">
                    <div className="relative shrink-0">
                      <img
                        src={displayImg}
                        alt={item.product.name}
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                        className={`w-16 h-16 sm:w-18 sm:h-18 object-cover rounded-lg border border-[#1C1C1C] bg-[#111111] ${
                          isItemOutOfStock ? 'brightness-75' : ''
                        }`}
                      />
                      {isItemOutOfStock && (
                        <div className="absolute inset-0 bg-black/50 rounded-lg flex items-center justify-center">
                          <span className="text-[9px] font-black text-[#EF4444] bg-[#18181B]/90 px-1.5 py-0.5 rounded uppercase">
                            Out of Stock
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Product Details & Selected Modifiers */}
                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold text-[#F5F5F5] text-base truncate">
                          {item.product.name}
                        </h3>
                        {isItemOutOfStock && (
                          <span className="text-[10px] font-bold text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/30 px-2 py-0.5 rounded">
                            Out of Stock
                          </span>
                        )}
                      </div>
                      <p className="text-xs font-semibold text-[#FF5A00]">
                        £{item.product.base_price.toFixed(2)}
                      </p>

                      {item.selectedModifiers && item.selectedModifiers.length > 0 && (
                        <div className="pt-1 space-y-0.5">
                          <span className="text-[11px] font-medium text-[#71717A] block">
                            Add-ons:
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {item.selectedModifiers.map((mod, i) => (
                              <span
                                key={i}
                                className="text-xs bg-[#151515] border border-[#242424] text-[#A1A1AA] px-2 py-0.5 rounded font-normal"
                              >
                                {mod.name} (+£{mod.price.toFixed(2)})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {item.removedIngredients && item.removedIngredients.length > 0 && (
                        <div className="pt-1 flex flex-wrap gap-1">
                          {item.removedIngredients.map((ing, i) => (
                            <span
                              key={i}
                              className="text-[11px] bg-[#2A1215] border border-[#EF4444]/30 text-[#FCA5A5] px-2 py-0.5 rounded font-medium"
                            >
                              No {ing}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Quantity Controls, Line Total & Remove Action */}
                  <div className="flex items-center gap-4 self-end sm:self-center shrink-0">
                    {/* Quantity Control (Height 36px, 8px Radius) */}
                    <div className="flex items-center bg-[#151515] border border-[#242424] rounded-lg h-9 px-1 text-[#F5F5F5]">
                      <button
                        onClick={() => updateQuantity(idx, item.quantity - 1)}
                        className="w-7 h-7 flex items-center justify-center text-[#A1A1AA] hover:text-[#F5F5F5] rounded transition-colors cursor-pointer"
                        aria-label="Decrease quantity"
                      >
                        −
                      </button>
                      <span className="px-2.5 font-semibold text-xs min-w-[24px] text-center">
                        {item.quantity}
                      </span>
                      <button
                        onClick={() => updateQuantity(idx, item.quantity + 1)}
                        className="w-7 h-7 flex items-center justify-center text-[#A1A1AA] hover:text-[#F5F5F5] rounded transition-colors cursor-pointer"
                        aria-label="Increase quantity"
                      >
                        +
                      </button>
                    </div>

                    {/* Line Total */}
                    <div className="text-right min-w-[65px]">
                      <p className="font-semibold text-[#F5F5F5] text-base">
                        £{item.lineTotal.toFixed(2)}
                      </p>
                    </div>

                    {/* Remove Item Button */}
                    <button
                      onClick={() => removeItem(idx)}
                      title="Remove item"
                      aria-label="Remove item"
                      className="p-2 text-[#71717A] hover:text-[#EF4444] rounded-lg hover:bg-[#EF4444]/10 transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* RIGHT COLUMN: Promo Code & Order Summary Cards */}
          <div className="lg:col-span-5 space-y-5 sticky top-24">
            
            {/* Promo Code Card */}
            <div className="bg-[#0D0D0D] border border-[#242424] p-5 rounded-[10px] space-y-3.5 shadow-lg">
              {/* Header with Title and "Available Promo Codes" Trigger */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Tag className="w-4 h-4 text-[#FF5A00]" />
                  <h3 className="text-xs font-semibold text-[#F5F5F5] uppercase tracking-wider">
                    Promo Code
                  </h3>
                </div>

                <button
                  type="button"
                  onClick={() => setShowAvailablePromos(!showAvailablePromos)}
                  className="flex items-center gap-1.5 text-xs font-semibold text-[#FF5A00] hover:text-[#FF8844] bg-[#FF5A00]/10 hover:bg-[#FF5A00]/20 border border-[#FF5A00]/30 px-2.5 py-1 rounded-md transition-all cursor-pointer"
                >
                  <Sparkles className="w-3.5 h-3.5 animate-pulse" />
                  <span>Available Offers ({availableCoupons.length})</span>
                  {showAvailablePromos ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>

              {/* Promo Code Input & Apply / Remove Bar */}
              {couponCode ? (
                /* Already Applied State */
                <div className="flex items-center justify-between p-3 rounded-lg bg-[#22C55E]/10 border border-[#22C55E]/30">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-[#22C55E]/20 text-[#22C55E] flex items-center justify-center shrink-0">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-white tracking-wider">
                        CODE: <span className="text-[#22C55E]">{couponCode}</span>
                      </p>
                      <p className="text-[11px] text-[#A1A1AA]">
                        Discount: <span className="text-[#22C55E] font-semibold">-£{discountAmount.toFixed(2)}</span>
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleRemovePromo}
                    className="text-xs text-[#EF4444] hover:text-white hover:bg-[#EF4444] border border-[#EF4444]/40 px-2.5 py-1 rounded transition-colors cursor-pointer font-medium"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                /* Input Field Form */
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="ENTER PROMO CODE"
                    value={promoInput}
                    onChange={(e) => setPromoInput(e.target.value.toUpperCase())}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleApplyPromo();
                    }}
                    className="flex-1 h-10 bg-[#151515] border border-[#242424] rounded-lg px-3 text-xs text-[#F5F5F5] uppercase placeholder-[#71717A] focus:outline-none focus:border-[#FF5A00] transition-colors font-medium tracking-wide"
                  />
                  <button
                    type="button"
                    disabled={isLoading || !promoInput.trim()}
                    onClick={() => handleApplyPromo()}
                    className="h-10 px-4 bg-[#151515] border border-[#242424] hover:border-[#FF5A00] text-[#FF5A00] hover:bg-[#FF5A00] hover:text-white disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-xs font-semibold transition-colors cursor-pointer shrink-0"
                  >
                    {isLoading ? 'Applying...' : 'Apply'}
                  </button>
                </div>
              )}

              {/* Status Message */}
              {promoMsg && (
                <p className={`text-xs font-medium ${promoMsg.isError ? 'text-[#EF4444]' : 'text-[#22C55E]'}`}>
                  {promoMsg.text}
                </p>
              )}

              {/* ============================================================ */}
              {/* AVAILABLE PROMO CODES SMALL CARDS DROPDOWN */}
              {/* ============================================================ */}
              {showAvailablePromos && (
                <div className="pt-2 border-t border-[#222222] space-y-2">
                  <div className="flex items-center justify-between text-[11px] text-[#A1A1AA]">
                    <span className="font-semibold uppercase tracking-wider text-[#FF5A00]">
                      Click card to copy & auto-apply:
                    </span>
                    <span className="text-[10px] text-[#71717A]">
                      Current Subtotal: £{subtotal.toFixed(2)}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 gap-2 max-h-64 overflow-y-auto pr-1 scrollbar-thin">
                    {availableCoupons.map((coupon) => {
                      const isEligible = subtotal >= (coupon.min_order_value || 0);
                      const isCurrentlyApplied = couponCode?.toUpperCase() === coupon.code.toUpperCase();

                      return (
                        <div
                          key={coupon.code}
                          onClick={() => isEligible && handleSelectPromoCard(coupon)}
                          className={`p-2.5 rounded-lg border transition-all relative group ${
                            isCurrentlyApplied
                              ? 'bg-[#FF5A00]/10 border-[#FF5A00] shadow-sm'
                              : isEligible
                              ? 'bg-[#141414] border-[#262626] hover:border-[#FF5A00] hover:bg-[#1A1A1A] cursor-pointer'
                              : 'bg-[#101010] border-[#1E1E1E] opacity-55 cursor-not-allowed'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            {/* Details */}
                            <div className="min-w-0 flex-1 space-y-1">
                              <div className="flex items-center gap-1.5 flex-wrap">
                                <span className="text-[9px] font-black uppercase bg-[#FF5A00] text-white px-1.5 py-0.5 rounded shadow-sm">
                                  {coupon.badge}
                                </span>
                                <span className="font-mono font-bold text-xs text-white tracking-wider flex items-center gap-1 group-hover:text-[#FF5A00] transition-colors">
                                  {coupon.code}
                                  {copiedCode === coupon.code ? (
                                    <span className="text-[9px] text-[#22C55E] font-sans font-normal flex items-center">
                                      <Check className="w-3 h-3 inline" /> Copied!
                                    </span>
                                  ) : (
                                    <Copy className="w-3 h-3 text-[#71717A] group-hover:text-[#FF5A00]" />
                                  )}
                                </span>
                              </div>

                              <p className="text-[11px] font-semibold text-[#E4E4E7] truncate leading-tight">
                                {coupon.name}
                              </p>
                              <p className="text-[10px] text-[#A1A1AA] leading-tight">
                                {coupon.description}
                              </p>

                              {coupon.min_order_value > 0 && (
                                <p className="text-[10px] text-[#71717A] pt-0.5">
                                  Min. order: £{coupon.min_order_value.toFixed(2)}{' '}
                                  {!isEligible && (
                                    <span className="text-amber-400 font-medium">
                                      (Add £{(coupon.min_order_value - subtotal).toFixed(2)} more)
                                    </span>
                                  )}
                                </p>
                              )}
                            </div>

                            {/* Apply Button */}
                            <button
                              type="button"
                              disabled={!isEligible}
                              onClick={(e) => {
                                e.stopPropagation();
                                if (isEligible) handleSelectPromoCard(coupon);
                              }}
                              className={`h-7 px-3 rounded text-[11px] font-bold uppercase transition-all shrink-0 cursor-pointer ${
                                isCurrentlyApplied
                                  ? 'bg-[#22C55E] text-white'
                                  : isEligible
                                  ? 'bg-[#1F1F1F] hover:bg-[#FF5A00] text-white border border-[#333]'
                                  : 'bg-[#151515] text-[#555] cursor-not-allowed border border-[#222]'
                              }`}
                            >
                              {isCurrentlyApplied ? 'Applied ✓' : 'Apply'}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Order Summary Card */}
            <div className="bg-[#0D0D0D] border border-[#242424] p-6 rounded-[10px] space-y-4 shadow-xl">
              <h2 className="text-lg font-semibold text-[#F5F5F5]">
                Order Summary
              </h2>

              <div className="space-y-2.5 text-sm text-[#A1A1AA]">
                <div className="flex justify-between">
                  <span>Subtotal</span>
                  <span className="text-[#F5F5F5] font-medium">£{subtotal.toFixed(2)}</span>
                </div>

                {discountAmount > 0 && (
                  <div className="flex justify-between text-[#22C55E] font-medium bg-[#22C55E]/10 p-2 rounded border border-[#22C55E]/20">
                    <span className="flex items-center gap-1.5">
                      <Tag className="w-3.5 h-3.5" />
                      Promo Discount ({couponCode})
                    </span>
                    <span className="font-bold">-£{discountAmount.toFixed(2)}</span>
                  </div>
                )}

                <div className="flex justify-between text-xs text-[#71717A] pt-1">
                  <span>Net Amount</span>
                  <span>£{net.toFixed(2)}</span>
                </div>

                <div className="flex justify-between text-xs text-[#71717A]">
                  <span>VAT (20% Included)</span>
                  <span>£{vat.toFixed(2)}</span>
                </div>
              </div>

              <div className="pt-3.5 border-t border-[#242424] flex items-center justify-between">
                <div>
                  <span className="text-base font-semibold text-[#F5F5F5]">Total</span>
                  <p className="text-[10px] text-[#71717A]">VAT included in gross amount.</p>
                </div>
                <div className="text-right">
                  <span className="text-xl font-bold text-[#FF5A00]">£{total.toFixed(2)}</span>
                  {discountAmount > 0 && (
                    <p className="text-[10px] text-[#22C55E] font-semibold">
                      You saved £{discountAmount.toFixed(2)}!
                    </p>
                  )}
                </div>
              </div>

              {/* Delivery Minimum Order Disclaimer & Promotion Exemption */}
              {subtotal < 15.00 && !(couponCode && discountAmount > 0) ? (
                <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-lg p-3 text-xs text-[#EF4444] font-medium flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-[#EF4444] shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="font-bold text-[#EF4444] leading-snug">
                      Disclaimer: For the delivery service you must cart at least £15.
                    </p>
                    {subtotal > 0 && (
                      <p className="text-[11px] text-[#F87171] font-normal">
                        Add £{(15.00 - subtotal).toFixed(2)} more to reach the delivery minimum.
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                couponCode && discountAmount > 0 && subtotal < 15.00 && (
                  <div className="bg-[#22C55E]/10 border border-[#22C55E]/30 rounded-lg p-2.5 text-xs text-[#22C55E] flex items-center justify-center font-medium text-center">
                    <span>✓ Delivery unlocked via applied offer ({couponCode})</span>
                  </div>
                )
              )}

              {/* Shop Closed Warning */}
              {!isOpen && (
                <div className="bg-red-950/40 border border-red-800/40 rounded-lg p-3 text-xs text-red-300 font-medium flex items-start gap-2.5">
                  <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse shrink-0 mt-1.5" />
                  <div>
                    <p className="font-bold text-red-400">Shop is Currently Closed</p>
                    <p className="text-[11px] text-red-300/80 mt-0.5">
                      Ordering is available between {formatTime12h(openingTime)} and {formatTime12h(closingTime)}. Your cart will be saved.
                    </p>
                  </div>
                </div>
              )}

              <button
                disabled={!isOpen || hasOutOfStockItems}
                onClick={() => navigate('/checkout')}
                className={`w-full h-12 text-sm font-semibold rounded-lg shadow-lg transition-colors flex items-center justify-center gap-2 ${
                  !isOpen
                    ? 'bg-[#18181B] text-red-400 cursor-not-allowed border border-red-900/50'
                    : hasOutOfStockItems
                    ? 'bg-[#27272A] text-[#71717A] cursor-not-allowed border border-[#3F3F46]'
                    : 'bg-[#FF5A00] hover:bg-[#E84F00] text-white cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#FF5A00]/50'
                }`}
              >
                <span>
                  {!isOpen
                    ? `Shop Closed (Opens at ${formatTime12h(openingTime)})`
                    : hasOutOfStockItems
                    ? 'Resolve Out of Stock Items'
                    : 'Proceed to checkout'}
                </span>
                {isOpen && !hasOutOfStockItems && <ChevronRight className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomerCart;
