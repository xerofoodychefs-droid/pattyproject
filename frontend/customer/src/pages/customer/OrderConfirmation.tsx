import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  CheckCircle2,
  Clock,
  MapPin,
  CreditCard,
  Phone,
  Mail,
  AlertTriangle,
  XCircle,
  AlertCircle,
  ArrowRight,
  ShoppingBag,
  Truck,
  Copy,
  Check,
  RefreshCw,
  Loader2,
  Sparkles,
  ChevronRight,
  RotateCcw
} from 'lucide-react';
import { api } from '../../api/client';
import { Order } from '../../types';
import { useAuthStore } from '../../store/authStore';

export const OrderConfirmation: React.FC = () => {
  const { orderNumber } = useParams<{ orderNumber?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();

  // Multi-format order identifier resolution
  const resolvedIdentifier = (
    orderNumber ||
    searchParams.get('order_number') ||
    searchParams.get('order_id') ||
    searchParams.get('reference_id') ||
    searchParams.get('id') ||
    ''
  ).trim();

  // Guest email resolution
  const initialEmail = (
    searchParams.get('email') ||
    searchParams.get('guest_email') ||
    user?.email ||
    localStorage.getItem('patty_last_order_email') ||
    ''
  ).trim();

  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [guestEmailInput, setGuestEmailInput] = useState<string>(initialEmail);
  const [isUnauthorizedGuest, setIsUnauthorizedGuest] = useState<boolean>(false);
  const [copiedOrderNumber, setCopiedOrderNumber] = useState<boolean>(false);
  const [pollCount, setPollCount] = useState<number>(0);

  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchOrderDetails = useCallback(
    async (emailOverride?: string, isBackgroundRefresh = false) => {
      if (!resolvedIdentifier) {
        setError('No order number or reference provided.');
        setLoading(false);
        return;
      }

      if (!isBackgroundRefresh) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }
      setError('');
      setIsUnauthorizedGuest(false);

      const effectiveEmail = (emailOverride || guestEmailInput || user?.email || localStorage.getItem('patty_last_order_email') || '').trim();

      try {
        let endpoint = `/orders/${encodeURIComponent(resolvedIdentifier)}`;
        if (effectiveEmail && !user) {
          endpoint += `?email=${encodeURIComponent(effectiveEmail)}`;
        }

        const data = await api.get<Order>(endpoint);
        setOrder(data);
        if (effectiveEmail) {
          localStorage.setItem('patty_last_order_email', effectiveEmail);
        }
      } catch (err: any) {
        const statusCode = err?.response?.status || err?.status;
        if (statusCode === 401 || statusCode === 403) {
          setIsUnauthorizedGuest(true);
        } else {
          setError(err?.message || 'Could not retrieve authoritative order confirmation details.');
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [resolvedIdentifier, guestEmailInput, user]
  );

  // Initial Fetch
  useEffect(() => {
    fetchOrderDetails();
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, [resolvedIdentifier]);

  // Payment & Order Status Classification
  const paymentStatus = (order?.payment_status || 'PENDING').toUpperCase();
  const orderStatus = (order?.status || 'PENDING_PAYMENT').toUpperCase();

  const isPaid =
    paymentStatus === 'PAID' ||
    paymentStatus === 'COMPLETED' ||
    paymentStatus === 'SUCCESS' ||
    ['INCOMING', 'ACCEPTED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'READY_FOR_COLLECTION', 'DELIVERED', 'COLLECTED'].includes(orderStatus);

  const isCancelled = !isPaid && (paymentStatus === 'CANCELLED' || orderStatus === 'CANCELLED');
  const isFailed = !isPaid && (paymentStatus === 'FAILED' || orderStatus === 'REJECTED');
  const isExpired = !isPaid && paymentStatus === 'EXPIRED';
  const isPending = !isPaid && !isCancelled && !isFailed && !isExpired;

  // Auto-polling when in pending state
  useEffect(() => {
    if (isPending && order && pollCount < 8) {
      pollTimerRef.current = setTimeout(() => {
        setPollCount((prev) => prev + 1);
        fetchOrderDetails(undefined, true);
      }, 4000);
    }
    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
      }
    };
  }, [isPending, order, pollCount, fetchOrderDetails]);

  const handleCopyOrderNumber = () => {
    if (!order?.order_number) return;
    navigator.clipboard.writeText(order.order_number);
    setCopiedOrderNumber(true);
    setTimeout(() => setCopiedOrderNumber(false), 2000);
  };

  const handleGuestEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!guestEmailInput.trim()) return;
    fetchOrderDetails(guestEmailInput.trim());
  };

  const formatDateTime = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  const formatPaymentMethod = (method?: string) => {
    if (!method) return 'Card Payment';
    const m = method.toUpperCase();
    if (m === 'APPLE_PAY') return 'Apple Pay';
    if (m === 'GOOGLE_PAY') return 'Google Pay';
    if (m === 'CARD') return 'Debit / Credit Card';
    return method;
  };

  // 1. Initial Loading State
  if (loading && !order) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center px-4 py-20 text-center space-y-4">
        <div className="relative">
          <div className="w-16 h-16 rounded-full bg-[#FF5A00]/10 border border-[#FF5A00]/20 flex items-center justify-center animate-pulse">
            <Loader2 className="w-8 h-8 text-[#FF5A00] animate-spin" />
          </div>
        </div>
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-white tracking-wide">Retrieving Order Details</h2>
          <p className="text-xs text-[#A1A1AA]">Verifying payment records with the backend...</p>
        </div>
      </div>
    );
  }

  // 2. Unauthorized Guest Verification Required State
  if (isUnauthorizedGuest) {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center space-y-6">
        <div className="w-16 h-16 bg-[#FF5A00]/10 text-[#FF5A00] border border-[#FF5A00]/30 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-[#FF5A00]/10">
          <Mail className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-black text-white uppercase tracking-tight">Verify Your Email</h1>
          <p className="text-xs text-[#A1A1AA] leading-relaxed">
            Please enter the email address used when placing order <strong className="text-white">{resolvedIdentifier}</strong> to view your confirmation.
          </p>
        </div>
        <form onSubmit={handleGuestEmailSubmit} className="space-y-3">
          <input
            type="email"
            required
            value={guestEmailInput}
            onChange={(e) => setGuestEmailInput(e.target.value)}
            placeholder="e.g. name@example.com"
            className="w-full h-12 bg-[#121212] border border-[#2B2B2B] focus:border-[#FF5A00] rounded-xl px-4 text-sm text-white placeholder-[#52525B] focus:outline-none transition-colors"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <span>View Order Details</span>}
          </button>
        </form>
        <Link to="/order" className="inline-block text-xs text-[#71717A] hover:text-white transition-colors">
          Return to Menu
        </Link>
      </div>
    );
  }

  // 3. Error / Order Not Found State
  if (error || !order) {
    return (
      <div className="max-w-md mx-auto px-4 py-16 text-center space-y-6">
        <div className="w-16 h-16 bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/30 rounded-2xl flex items-center justify-center mx-auto shadow-lg shadow-[#EF4444]/10">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-black text-white uppercase tracking-tight">Order Not Found</h1>
          <p className="text-xs text-[#A1A1AA] leading-relaxed">
            {error || `We could not locate order details for "${resolvedIdentifier}". Please verify your reference or contact support.`}
          </p>
        </div>
        <div className="flex flex-col sm:flex-row gap-3 justify-center pt-2">
          <button
            onClick={() => fetchOrderDetails()}
            className="px-6 py-3 bg-[#1E1E1E] hover:bg-[#282828] border border-[#333333] text-white rounded-xl font-bold text-xs uppercase tracking-wider transition-all flex items-center justify-center gap-2"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Try Again</span>
          </button>
          <Link
            to="/order"
            className="px-6 py-3 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-xl font-bold text-xs uppercase tracking-wider transition-all shadow-lg shadow-[#FF5A00]/20 flex items-center justify-center gap-2"
          >
            <span>Return to Menu</span>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-12 pb-28 space-y-6">
      {/* ========================================================
          1. STATUS HERO BANNER
      ======================================================== */}
      {isPaid && (
        <div className="bg-gradient-to-b from-[#10B981]/15 to-[#121212] border border-[#10B981]/30 rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl relative overflow-hidden">
          <div className="w-16 h-16 bg-[#10B981]/20 text-[#10B981] border border-[#10B981]/40 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-[#10B981]/20 animate-in zoom-in-90 duration-300">
            <CheckCircle2 className="w-9 h-9 stroke-[2.5]" />
          </div>
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#10B981]/20 text-[#34D399] border border-[#10B981]/30">
              <Sparkles className="w-3.5 h-3.5" />
              Payment Successful & Verified
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Thank you! Your order is confirmed.
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA] max-w-lg mx-auto">
              We've received your order and the kitchen has begun preparation. A confirmation receipt has been sent to{' '}
              <span className="text-white font-semibold">{order.customer_email}</span>.
            </p>
          </div>
        </div>
      )}

      {isCancelled && (
        <div className="bg-gradient-to-b from-[#F59E0B]/15 to-[#121212] border border-[#F59E0B]/30 rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl">
          <div className="w-16 h-16 bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-[#F59E0B]/20">
            <XCircle className="w-9 h-9 stroke-[2.5]" />
          </div>
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#F59E0B]/20 text-[#FBBF24] border border-[#F59E0B]/30">
              Order Unpaid
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Payment Cancelled
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA] max-w-lg mx-auto">
              Your payment session was cancelled and your order has not been placed. No funds have been deducted from your account.
            </p>
          </div>
        </div>
      )}

      {isFailed && (
        <div className="bg-gradient-to-b from-[#EF4444]/15 to-[#121212] border border-[#EF4444]/30 rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl">
          <div className="w-16 h-16 bg-[#EF4444]/20 text-[#EF4444] border border-[#EF4444]/40 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-[#EF4444]/20">
            <AlertCircle className="w-9 h-9 stroke-[2.5]" />
          </div>
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#EF4444]/20 text-[#F87171] border border-[#EF4444]/30">
              Transaction Declined
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Payment Failed
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA] max-w-lg mx-auto">
              Your payment could not be processed. Please check your card balance, billing details, or try another payment method.
            </p>
          </div>
        </div>
      )}

      {isPending && (
        <div className="bg-gradient-to-b from-[#EAB308]/15 to-[#121212] border border-[#EAB308]/30 rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl">
          <div className="w-16 h-16 bg-[#EAB308]/20 text-[#EAB308] border border-[#EAB308]/40 rounded-full flex items-center justify-center mx-auto shadow-xl shadow-[#EAB308]/20 animate-pulse">
            <Clock className="w-9 h-9 stroke-[2.5]" />
          </div>
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#EAB308]/20 text-[#FDE047] border border-[#EAB308]/30">
              Awaiting Gateway Confirmation
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Payment Processing
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA] max-w-lg mx-auto">
              We are verifying your transaction with the payment gateway. This page will update automatically once confirmed.
            </p>
          </div>
          <div className="pt-2">
            <button
              type="button"
              onClick={() => fetchOrderDetails(undefined, true)}
              disabled={refreshing}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#1C1C1C] hover:bg-[#282828] border border-[#333333] rounded-lg text-xs font-bold text-white transition-all cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-[#FF5A00]' : ''}`} />
              <span>{refreshing ? 'Checking status...' : 'Refresh Status'}</span>
            </button>
          </div>
        </div>
      )}

      {isExpired && (
        <div className="bg-gradient-to-b from-[#71717A]/15 to-[#121212] border border-[#3F3F46] rounded-3xl p-6 sm:p-8 text-center space-y-4 shadow-2xl">
          <div className="w-16 h-16 bg-[#27272A] text-[#A1A1AA] border border-[#3F3F46] rounded-full flex items-center justify-center mx-auto">
            <Clock className="w-9 h-9 stroke-[2.5]" />
          </div>
          <div className="space-y-1.5">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-black uppercase tracking-wider bg-[#27272A] text-[#D4D4D8] border border-[#3F3F46]">
              Session Timed Out
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Payment Expired
            </h1>
            <p className="text-xs sm:text-sm text-[#A1A1AA] max-w-lg mx-auto">
              This payment session has expired. Please return to the menu to place a new order.
            </p>
          </div>
        </div>
      )}

      {/* ========================================================
          2. ORDER METRICS & QUICK SUMMARY CARD
      ======================================================== */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-[#121212] border border-[#242424] p-4 sm:p-5 rounded-2xl shadow-xl text-left">
        {/* Order Number */}
        <div className="space-y-1">
          <p className="text-[10px] text-[#71717A] uppercase font-bold tracking-wider">Order Number</p>
          <div className="flex items-center gap-1.5">
            <span className="font-extrabold text-sm text-[#FF5A00] tracking-tight">{order.order_number}</span>
            <button
              type="button"
              onClick={handleCopyOrderNumber}
              title="Copy Order Number"
              className="p-1 text-[#71717A] hover:text-white rounded transition-colors cursor-pointer"
            >
              {copiedOrderNumber ? <Check className="w-3.5 h-3.5 text-[#10B981]" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Fulfillment */}
        <div className="space-y-1">
          <p className="text-[10px] text-[#71717A] uppercase font-bold tracking-wider">Fulfillment</p>
          <div className="flex items-center gap-1.5 font-bold text-xs sm:text-sm text-white">
            {order.order_type === 'DELIVERY' ? (
              <>
                <Truck className="w-3.5 h-3.5 text-[#FF5A00]" />
                <span>Delivery</span>
              </>
            ) : (
              <>
                <ShoppingBag className="w-3.5 h-3.5 text-[#FF5A00]" />
                <span>Collection</span>
              </>
            )}
          </div>
        </div>

        {/* Payment Status & Method */}
        <div className="space-y-1">
          <p className="text-[10px] text-[#71717A] uppercase font-bold tracking-wider">Payment</p>
          <p
            className={`font-extrabold text-xs sm:text-sm ${
              isPaid
                ? 'text-[#10B981]'
                : isCancelled
                ? 'text-[#F59E0B]'
                : isFailed
                ? 'text-[#EF4444]'
                : 'text-[#EAB308]'
            }`}
          >
            {isPaid ? 'PAID' : isCancelled ? 'CANCELLED' : isFailed ? 'FAILED' : 'PENDING'}
          </p>
          <p className="text-[10px] text-[#71717A]">{formatPaymentMethod(order.payment_method)}</p>
        </div>

        {/* Total Amount Paid */}
        <div className="space-y-1">
          <p className="text-[10px] text-[#71717A] uppercase font-bold tracking-wider">Total Amount</p>
          <p className="font-black text-sm sm:text-base text-white tracking-tight">
            £{Number(order.total_amount || 0).toFixed(2)}
          </p>
          {order.created_at && (
            <p className="text-[10px] text-[#71717A] truncate">{formatDateTime(order.created_at)}</p>
          )}
        </div>
      </div>

      {/* ========================================================
          3. FULFILLMENT DESTINATION & RECIPIENT DETAILS
      ======================================================== */}
      <div className="bg-[#121212] border border-[#242424] p-5 rounded-2xl space-y-3 text-left">
        <h2 className="text-xs uppercase font-extrabold text-[#A1A1AA] tracking-wider flex items-center gap-2">
          <MapPin className="w-4 h-4 text-[#FF5A00]" />
          <span>Fulfillment & Customer Details</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs text-[#D4D4D8] pt-1">
          <div className="space-y-1">
            <p className="text-[10px] text-[#71717A] uppercase font-bold">Recipient</p>
            <p className="font-bold text-white">{order.customer_name}</p>
            <p className="text-[#A1A1AA]">{order.customer_email}</p>
            {order.customer_phone && <p className="text-[#A1A1AA]">{order.customer_phone}</p>}
          </div>

          <div className="space-y-1">
            {order.order_type === 'DELIVERY' ? (
              <>
                <p className="text-[10px] text-[#71717A] uppercase font-bold">Delivery Address</p>
                {order.delivery_address ? (
                  <p className="font-medium text-white leading-relaxed">
                    {order.delivery_address.address_line1 || order.delivery_address.line1 || ''}
                    {order.delivery_address.city ? `, ${order.delivery_address.city}` : ''}
                    {order.delivery_address.postcode ? `, ${order.delivery_address.postcode}` : ''}
                  </p>
                ) : (
                  <p className="text-[#A1A1AA]">Delivery address recorded on file.</p>
                )}
                {order.delivery_instructions && (
                  <p className="text-[11px] text-[#FF5A00] font-medium pt-1">
                    Note: "{order.delivery_instructions}"
                  </p>
                )}
              </>
            ) : (
              <>
                <p className="text-[10px] text-[#71717A] uppercase font-bold">Collection Information</p>
                <p className="font-medium text-white">Patty Project Store Collection</p>
                <p className="text-[#A1A1AA]">Freshly prepared for counter collection upon arrival.</p>
                {order.collection_slot_time && (
                  <p className="text-[11px] text-[#FF5A00] font-medium pt-1">
                    Slot: {formatDateTime(order.collection_slot_time)}
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================
          4. ITEMIZED PRODUCTS ORDER LIST
      ======================================================== */}
      <div className="bg-[#121212] border border-[#242424] rounded-2xl overflow-hidden shadow-xl text-left">
        <div className="px-5 py-4 border-b border-[#242424] flex items-center justify-between">
          <h2 className="text-xs uppercase font-extrabold text-[#A1A1AA] tracking-wider flex items-center gap-2">
            <ShoppingBag className="w-4 h-4 text-[#FF5A00]" />
            <span>Ordered Items ({order.items?.length || 0})</span>
          </h2>
          <span className="text-xs font-bold text-white">
            Subtotal: £{Number(order.subtotal || 0).toFixed(2)}
          </span>
        </div>

        <div className="divide-y divide-[#1F1F1F]">
          {order.items && order.items.length > 0 ? (
            order.items.map((item, idx) => (
              <div key={item.id || idx} className="p-4 sm:p-5 flex items-start justify-between gap-4">
                <div className="flex items-start gap-3.5">
                  {/* Thumbnail / Placeholder */}
                  <div className="w-14 h-14 rounded-xl bg-[#1A1A1A] border border-[#2A2A2A] overflow-hidden flex-shrink-0 flex items-center justify-center">
                    {item.image_url ? (
                      <img
                        src={item.image_url}
                        alt={item.product_name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                      />
                    ) : (
                      <img
                        src="/placeholder-burger.svg"
                        alt="Product"
                        className="w-8 h-8 opacity-70"
                      />
                    )}
                  </div>

                  {/* Product Details & Modifiers */}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-extrabold text-sm text-white">{item.product_name}</span>
                      <span className="text-[11px] font-black px-1.5 py-0.5 rounded bg-[#242424] text-[#FF5A00]">
                        {item.quantity}x
                      </span>
                    </div>

                    <p className="text-xs text-[#71717A]">
                      £{Number(item.unit_price || 0).toFixed(2)} each
                    </p>

                    {/* Custom Modifiers / Choices */}
                    {item.selected_modifiers && item.selected_modifiers.length > 0 && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {item.selected_modifiers.map((mod: any, mIdx: number) => {
                          const modName = typeof mod === 'string' ? mod : mod.name || mod.option_name || 'Modifier';
                          const modPrice = typeof mod === 'object' && mod.price ? Number(mod.price) : 0;
                          return (
                            <span
                              key={mIdx}
                              className="text-[10px] bg-[#1A1A1A] text-[#A1A1AA] border border-[#2D2D2D] px-2 py-0.5 rounded"
                            >
                              +{modName} {modPrice > 0 ? `(£${modPrice.toFixed(2)})` : ''}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>

                {/* Line Total */}
                <div className="text-right flex-shrink-0">
                  <span className="font-extrabold text-sm text-white">
                    £{Number(item.total_price || (item.unit_price * item.quantity) || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="p-6 text-center text-xs text-[#71717A]">No item details recorded.</div>
          )}
        </div>
      </div>

      {/* ========================================================
          5. BILLING & FINANCIAL BREAKDOWN
      ======================================================== */}
      <div className="bg-[#121212] border border-[#242424] p-5 rounded-2xl space-y-3 text-xs text-left shadow-xl">
        <h2 className="text-xs uppercase font-extrabold text-[#A1A1AA] tracking-wider flex items-center gap-2 pb-1 border-b border-[#1F1F1F]">
          <CreditCard className="w-4 h-4 text-[#FF5A00]" />
          <span>Payment & Billing Summary</span>
        </h2>

        <div className="space-y-2 pt-1 text-[#A1A1AA]">
          <div className="flex justify-between">
            <span>Items Subtotal</span>
            <span className="font-semibold text-white">£{Number(order.subtotal || 0).toFixed(2)}</span>
          </div>

          {order.order_type === 'DELIVERY' && (
            <div className="flex justify-between">
              <span>Delivery Fee</span>
              <span className="font-semibold text-white">
                {Number(order.delivery_fee) > 0 ? `£${Number(order.delivery_fee).toFixed(2)}` : 'FREE'}
              </span>
            </div>
          )}

          {Number(order.service_fee) > 0 && (
            <div className="flex justify-between">
              <span>Service Fee</span>
              <span className="font-semibold text-white">£{Number(order.service_fee).toFixed(2)}</span>
            </div>
          )}

          {Number(order.vat_amount) > 0 && (
            <div className="flex justify-between text-[11px] text-[#71717A]">
              <span>VAT (20% Included)</span>
              <span>£{Number(order.vat_amount).toFixed(2)}</span>
            </div>
          )}

          {Number(order.discount_amount) > 0 && (
            <div className="flex justify-between text-[#10B981] font-medium">
              <span>
                Discount Savings {order.coupon_code ? `[${order.coupon_code}]` : ''}
              </span>
              <span>-£{Number(order.discount_amount).toFixed(2)}</span>
            </div>
          )}

          {Number(order.points_redeemed) > 0 && (
            <div className="flex justify-between text-[#10B981] font-medium">
              <span>Patty Points Redeemed</span>
              <span>-{order.points_redeemed.toLocaleString()} pts</span>
            </div>
          )}

          {Number(order.points_earned) > 0 && isPaid && (
            <div className="flex justify-between text-[#FF5A00] font-medium pt-1 border-t border-[#1F1F1F]">
              <span className="flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                Patty Points Earned
              </span>
              <span>+{order.points_earned.toLocaleString()} pts</span>
            </div>
          )}

          <div className="flex justify-between items-center pt-3 border-t border-[#262626] text-sm sm:text-base font-black text-white">
            <span>Total Paid</span>
            <span className="text-[#FF5A00] text-lg font-black tracking-tight">
              £{Number(order.total_amount || 0).toFixed(2)}
            </span>
          </div>
        </div>
      </div>

      {/* ========================================================
          6. ACTION BUTTONS & NAVIGATION
      ======================================================== */}
      <div className="flex flex-col sm:flex-row items-center gap-3 pt-2">
        {isPaid ? (
          <>
            <Link
              to="/order"
              className="w-full sm:flex-1 h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Order More Food</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/orders"
              className="w-full sm:flex-1 h-12 bg-[#181818] hover:bg-[#222222] border border-[#333333] text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>View My Orders</span>
            </Link>
          </>
        ) : isCancelled || isFailed ? (
          <>
            <Link
              to="/checkout"
              className="w-full sm:flex-1 h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Return to Checkout</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
            <Link
              to="/order"
              className="w-full sm:flex-1 h-12 bg-[#181818] hover:bg-[#222222] border border-[#333333] text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Back to Menu</span>
            </Link>
          </>
        ) : (
          <>
            <button
              type="button"
              onClick={() => fetchOrderDetails(undefined, true)}
              disabled={refreshing}
              className="w-full sm:flex-1 h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white font-extrabold text-xs uppercase tracking-wider rounded-xl transition-all shadow-lg shadow-[#FF5A00]/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              <span>Refresh Status</span>
            </button>
            <Link
              to="/order"
              className="w-full sm:flex-1 h-12 bg-[#181818] hover:bg-[#222222] border border-[#333333] text-white font-bold text-xs uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Back to Menu</span>
            </Link>
          </>
        )}
      </div>

      {/* ========================================================
          7. SUPPORT & CONTACT HELP CARD
      ======================================================== */}
      <div className="bg-[#121212] border border-[#242424] p-4 sm:p-5 rounded-2xl flex flex-col sm:flex-row items-center justify-around gap-3 text-xs text-[#A1A1AA]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#1C1C1C] border border-[#2C2C2C] flex items-center justify-center text-[#FF5A00]">
            <Phone className="w-4 h-4" />
          </div>
          <div className="text-left">
            <p className="text-[10px] text-[#71717A] font-bold uppercase">Need Assistance?</p>
            <a href="tel:07417521128" className="font-extrabold text-white hover:text-[#FF5A00] transition-colors">
              07417 521128
            </a>
          </div>
        </div>

        <div className="w-full sm:w-[1px] h-[1px] sm:h-8 bg-[#242424]" />

        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-[#1C1C1C] border border-[#2C2C2C] flex items-center justify-center text-[#FF5A00]">
            <Mail className="w-4 h-4" />
          </div>
          <div className="text-left">
            <p className="text-[10px] text-[#71717A] font-bold uppercase">Email Support</p>
            <a href="mailto:hellofoodychefs@gmail.com" className="font-extrabold text-white hover:text-[#FF5A00] transition-colors">
              hellofoodychefs@gmail.com
            </a>
          </div>
        </div>
      </div>
    </div>
  );
};
