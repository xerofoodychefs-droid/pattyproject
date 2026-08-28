import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Truck, ShoppingBag, MapPin, Clock, Lock, CheckCircle2, Building2, Plus, Star, ShieldCheck, Check, AlertTriangle, ChevronDown } from 'lucide-react';
import { useCartStore } from '../../store/cartStore';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';
import { CustomerAddress } from '../../types/address';
import { CustomerCard } from '../../types/card';
import { loadSquareSdk } from '../../utils/squarePayments';

// ==========================================
// 1. ISOLATED SQUARE CARD PAYMENT COMPONENT
// ==========================================
interface SquareCardSectionProps {
  payments: any;
  onCardReady: (ready: boolean) => void;
  onCardInstance: (card: any) => void;
}

const SquareCardSection: React.FC<SquareCardSectionProps> = ({
  payments,
  onCardReady,
  onCardInstance,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cardRef = useRef<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!payments) return;
    let isMounted = true;

    const initCard = async () => {
      setLoading(true);
      setError(null);

      // Clean up previous instance
      if (cardRef.current) {
        try {
          await cardRef.current.destroy();
        } catch {}
        cardRef.current = null;
        onCardInstance(null);
        onCardReady(false);
      }

      try {
        console.info('[Square Card] Initializing Card component...');
        const cardInstance = await payments.card();
        console.info('[Square Card] Card component created successfully');

        if (!isMounted || !cardInstance) return;

        if (containerRef.current) {
          console.info('[Square Card] Attaching Card to DOM container...');
          containerRef.current.innerHTML = '';
          await cardInstance.attach(containerRef.current);
          console.info('[Square Card] Card successfully attached to DOM');

          if (isMounted) {
            cardRef.current = cardInstance;
            onCardInstance(cardInstance);
            onCardReady(true);
            setLoading(false);
          }
        }
      } catch (err: any) {
        console.error('[Square Card] Initialization/Attachment error:', err);
        if (isMounted) {
          setError(err?.message || 'Failed to initialize secure card input.');
          onCardReady(false);
          setLoading(false);
        }
      }
    };

    initCard();

    return () => {
      isMounted = false;
      if (cardRef.current) {
        try {
          cardRef.current.destroy();
        } catch {}
        cardRef.current = null;
      }
      onCardInstance(null);
      onCardReady(false);
    };
  }, [payments]);

  return (
    <div className="p-4 rounded-xl border border-[#242424] bg-[#121212] space-y-3.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-xs text-[#F5F5F5]">Credit / Debit Card</span>
        <div className="flex items-center gap-1.5">
          {/* VISA Badge */}
          <div className="h-5 px-1.5 bg-[#1A1F71] rounded flex items-center justify-center shadow-xs">
            <span className="text-[10px] font-black italic tracking-tighter text-white">VISA</span>
          </div>
          {/* Mastercard Badge */}
          <div className="h-5 px-1.5 bg-[#222222] border border-[#333333] rounded flex items-center justify-center shadow-xs">
            <div className="flex -space-x-1 items-center">
              <div className="w-2.5 h-2.5 rounded-full bg-[#EB001B]" />
              <div className="w-2.5 h-2.5 rounded-full bg-[#F79E1B] opacity-90" />
            </div>
          </div>
          {/* AMEX Badge */}
          <div className="h-5 px-1.5 bg-[#006FCF] rounded flex items-center justify-center shadow-xs">
            <span className="text-[9px] font-bold text-white tracking-tight">AMEX</span>
          </div>
        </div>
      </div>

      {error ? (
        <div className="p-3 bg-[#241209] border border-[#EF4444]/40 rounded-lg text-xs text-[#EF4444] flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : (
        <div className="relative min-h-[90px] w-full">
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-[#121212] rounded-lg text-xs text-[#A1A1AA] gap-2 z-10">
              <div className="w-4 h-4 border-2 border-[#FF5A00] border-t-transparent rounded-full animate-spin" />
              <span>Loading secure card inputs...</span>
            </div>
          )}
          <div
            id="square-card-container"
            ref={containerRef}
            className="w-full"
          />
        </div>
      )}
    </div>
  );
};

// ==========================================
// 2. ISOLATED DIGITAL WALLETS COMPONENT
// ==========================================
interface SquareDigitalWalletsSectionProps {
  payments: any;
  total: number;
  loading: boolean;
  paymentLoading: boolean;
  activePaymentMethod: 'CARD' | 'GOOGLE_PAY' | 'APPLE_PAY' | null;
  onGooglePayPayment: (gpayInstance: any) => void;
  onApplePayPayment: (apayInstance: any) => void;
}

const SquareDigitalWalletsSection: React.FC<SquareDigitalWalletsSectionProps> = ({
  payments,
  total,
  loading,
  paymentLoading,
  activePaymentMethod,
  onGooglePayPayment,
  onApplePayPayment,
}) => {
  const [googlePayAvailable, setGooglePayAvailable] = useState<boolean>(false);
  const [applePayAvailable, setApplePayAvailable] = useState<boolean>(false);
  const googlePayRef = useRef<any>(null);
  const applePayRef = useRef<any>(null);
  const paymentRequestRef = useRef<any>(null);
  const googlePayContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!payments) return;
    let isMounted = true;

    const initWallets = async () => {
      try {
        const formattedTotal = (total > 0 ? total : 0.01).toFixed(2);
        const req = payments.paymentRequest({
          countryCode: 'GB',
          currencyCode: 'GBP',
          total: {
            amount: formattedTotal,
            label: 'Patty Project',
          },
        });
        paymentRequestRef.current = req;

        // Check Google Pay
        try {
          const gpay = await payments.googlePay(req);
          if (isMounted && gpay) {
            googlePayRef.current = gpay;
            setGooglePayAvailable(true);
          }
        } catch {
          if (isMounted) setGooglePayAvailable(false);
        }

        // Check Apple Pay
        try {
          const apay = await payments.applePay(req);
          if (isMounted && apay) {
            applePayRef.current = apay;
            setApplePayAvailable(true);
          }
        } catch {
          if (isMounted) setApplePayAvailable(false);
        }
      } catch (err) {
        console.warn('[Square Wallets] Init notice:', err);
      }
    };

    initWallets();

    return () => {
      isMounted = false;
      if (googlePayRef.current) {
        try {
          googlePayRef.current.destroy();
        } catch {}
        googlePayRef.current = null;
      }
      applePayRef.current = null;
      paymentRequestRef.current = null;
      setGooglePayAvailable(false);
      setApplePayAvailable(false);
    };
  }, [payments]);

  // Update total in payment request dynamically when total changes
  useEffect(() => {
    if (paymentRequestRef.current && typeof paymentRequestRef.current.update === 'function') {
      try {
        const formattedTotal = (total > 0 ? total : 0.01).toFixed(2);
        paymentRequestRef.current.update({
          total: {
            amount: formattedTotal,
            label: 'Patty Project',
          },
        });
      } catch {}
    }
  }, [total]);

  // Mount Google Pay button when available
  useEffect(() => {
    if (googlePayAvailable && googlePayRef.current && googlePayContainerRef.current) {
      googlePayContainerRef.current.innerHTML = '';
      googlePayRef.current
        .attach(googlePayContainerRef.current, {
          buttonSizeMode: 'fill',
          buttonColor: 'black',
          buttonType: 'buy',
        })
        .catch((err: any) => {
          console.warn('[Square Google Pay] attach notice:', err);
        });
    }
  }, [googlePayAvailable]);

  if (!googlePayAvailable && !applePayAvailable) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div className="w-full">
        {/* Apple Pay Button */}
        {applePayAvailable && (
          <button
            type="button"
            id="apple-pay-button"
            onClick={() => onApplePayPayment(applePayRef.current)}
            disabled={loading || paymentLoading}
            className="w-full h-11 bg-black hover:bg-[#1A1A1A] border border-[#333333] rounded-lg text-white font-medium flex items-center justify-center gap-2 cursor-pointer shadow-md transition-all disabled:opacity-50 disabled:cursor-not-allowed mb-2.5"
            aria-label="Pay with Apple Pay"
          >
            {activePaymentMethod === 'APPLE_PAY' && paymentLoading ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
            ) : (
              <>
                <svg className="h-5 w-auto fill-current" viewBox="0 0 170 85" xmlns="http://www.w3.org/2000/svg">
                  <path d="M150.37 39.26c-.08-11.66 9.53-17.27 9.97-17.55-5.43-7.94-13.88-9.03-16.89-9.15-7.19-.73-14.04 4.24-17.69 4.24-3.65 0-9.29-4.14-15.29-4.03-7.88.12-15.15 4.58-19.2 11.62-8.18 14.19-2.09 35.19 5.86 46.68 3.89 5.62 8.53 11.93 14.62 11.7 5.86-.23 8.08-3.79 15.17-3.79 7.09 0 9.08 3.79 15.25 3.67 6.28-.12 10.26-5.69 14.12-11.34 4.47-6.53 6.31-12.85 6.42-13.18-.14-.06-12.25-4.7-12.34-18.49zM138.83 17.5c3.24-3.93 5.43-9.39 4.83-14.86-4.68.19-10.35 3.12-13.7 7.05-2.93 3.4-5.5 8.94-4.81 14.28 5.23.41 10.45-2.54 13.68-6.47z" />
                  <path d="M30.43 14.47h8.86v56.88h-8.86V14.47zM64.67 36.33h8.55v35.02h-8.55v-4.88c-2.48 3.58-6.84 5.65-11.75 5.65-8.86 0-16.14-7.23-16.14-18.06 0-10.88 7.28-18.11 16.14-18.11 4.91 0 9.27 2.07 11.75 5.65v-5.27zm-11.54 27.59c5.33 0 9.94-4.24 9.94-10.82 0-6.53-4.61-10.82-9.94-10.82-5.38 0-9.94 4.29-9.94 10.82 0 6.58 4.56 10.82 9.94 10.82zM102.32 36.33h8.55v35.02h-8.55v-4.88c-2.48 3.58-6.84 5.65-11.75 5.65-8.86 0-16.14-7.23-16.14-18.06 0-10.88 7.28-18.11 16.14-18.11 4.91 0 9.27 2.07 11.75 5.65v-5.27zm-11.54 27.59c5.33 0 9.94-4.24 9.94-10.82 0-6.53-4.61-10.82-9.94-10.82-5.38 0-9.94 4.29-9.94 10.82 0 6.58 4.56 10.82 9.94 10.82z" />
                </svg>
                <span className="text-xs font-semibold">Pay</span>
              </>
            )}
          </button>
        )}

        {/* Google Pay Button Mounted Target */}
        {googlePayAvailable && (
          <div
            id="square-google-pay-button"
            ref={googlePayContainerRef}
            onClick={() => onGooglePayPayment(googlePayRef.current)}
            className="w-full h-11 cursor-pointer overflow-hidden rounded-lg shadow-sm"
          />
        )}
      </div>

      <div className="relative flex py-1.5 items-center">
        <div className="flex-grow border-t border-[#242424]" />
        <span className="flex-shrink mx-3 text-[11px] uppercase tracking-wider font-semibold text-[#71717A]">
          Or Pay with Card
        </span>
        <div className="flex-grow border-t border-[#242424]" />
      </div>
    </div>
  );
};

// ==========================================
// 3. MAIN CUSTOMER CHECKOUT COMPONENT
// ==========================================
export const CustomerCheckout: React.FC = () => {
  const [step, setStep] = useState<1 | 2>(1);
  const {
    items,
    orderType,
    setOrderType,
    selectedBranch,
    nearestBranchForCollection,
    isDeliveryEligible,
    deliveryDistanceMiles,
    userCoords,
    getTotal,
    getSubtotal,
    getDeliveryFee,
    getServiceFee,
    couponCode,
    discountAmount,
    clearCart
  } = useCartStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const [customerName, setCustomerName] = useState(user?.full_name || '');
  const [customerEmail, setCustomerEmail] = useState(user?.email || '');
  const [phoneDigits, setPhoneDigits] = useState('');

  const [doorNumber, setDoorNumber] = useState('');
  const [addressLine1, setAddressLine1] = useState('');
  const [addressLine2, setAddressLine2] = useState('');
  const [city, setCity] = useState('London');
  const [postcode, setPostcode] = useState('');
  const [country, setCountry] = useState('United Kingdom');
  const [instructions, setInstructions] = useState('');
  const [deliveryTime, setDeliveryTime] = useState('As soon as possible (20 - 30 mins)');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Saved Addresses State for Logged-In Loyalty Customers
  const [savedAddresses, setSavedAddresses] = useState<CustomerAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);

  // Saved Cards State for Logged-In Loyalty Customers
  const [savedCards, setSavedCards] = useState<CustomerCard[]>([]);
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null);

  // Loyalty Points State
  const [loyaltyData, setLoyaltyData] = useState<any>(null);
  const [redeemPoints, setRedeemPoints] = useState<number>(0);

  // Square Payment Gateway State
  const [paymentConfig, setPaymentConfig] = useState<{
    provider: string;
    application_id?: string;
    location_id?: string;
    environment?: string;
  } | null>(null);

  const [squarePayments, setSquarePayments] = useState<any>(null);
  const cardInstanceRef = useRef<any>(null);
  const [squareCardReady, setSquareCardReady] = useState<boolean>(false);
  const [paymentLoading, setPaymentLoading] = useState<boolean>(false);
  const [activePaymentMethod, setActivePaymentMethod] = useState<'CARD' | 'GOOGLE_PAY' | 'APPLE_PAY' | null>(null);

  useEffect(() => {
    // Fetch public payment configuration
    api.get<any>('/payments/config')
      .then((cfg) => {
        if (cfg) setPaymentConfig(cfg);
      })
      .catch(() => {});

    // Populate user profile details into input fields
    if (user) {
      if (user.full_name) setCustomerName((prev) => prev || user.full_name);
      if (user.email) setCustomerEmail((prev) => prev || user.email);
      if (user.phone) {
        const cleanPhone = user.phone.replace(/\D/g, '');
        if (cleanPhone) setPhoneDigits((prev) => prev || cleanPhone.slice(-11));
      }
    } else {
      const rawUser = localStorage.getItem('patty_user');
      if (rawUser) {
        try {
          const parsed = JSON.parse(rawUser);
          if (parsed?.full_name) setCustomerName((prev) => prev || parsed.full_name);
          if (parsed?.email) setCustomerEmail((prev) => prev || parsed.email);
          if (parsed?.phone) {
            const cleanPhone = parsed.phone.replace(/\D/g, '');
            if (cleanPhone) setPhoneDigits((prev) => prev || cleanPhone.slice(-11));
          }
        } catch {}
      }
    }

    const token = localStorage.getItem('patty_token');
    if (token || user) {
      api.get<any>('/auth/me')
        .then((userData) => {
          if (userData) {
            if (userData.full_name) setCustomerName((prev) => prev || userData.full_name);
            if (userData.email) setCustomerEmail((prev) => prev || userData.email);
            if (userData.phone) {
              const cleanPhone = userData.phone.replace(/\D/g, '');
              if (cleanPhone) setPhoneDigits((prev) => prev || cleanPhone.slice(-11));
            }
          }
        })
        .catch(() => {});

      api.get<CustomerAddress[]>('/addresses')
        .then((addrs) => {
          setSavedAddresses(addrs);
          if (addrs && addrs.length > 0) {
            const defaultAddr = addrs.find((a) => a.is_default) || addrs[0];
            selectSavedAddress(defaultAddr);
          }
        })
        .catch(() => {});

      api.get<CustomerCard[]>('/payment-methods/cards')
        .then((cardsList) => {
          setSavedCards(cardsList);
          if (cardsList && cardsList.length > 0) {
            const defaultCard = cardsList.find((c) => c.is_default) || cardsList[0];
            setSelectedCardId(defaultCard.id);
          }
        })
        .catch(() => {});

      api.get<any>('/loyalty/balance')
        .then((res) => {
          setLoyaltyData(res);
        })
        .catch(() => {});
    }
  }, [user]);

  const selectSavedAddress = (addr: CustomerAddress) => {
    setSelectedAddressId(addr.id);
    setAddressLine1(addr.address_line1 || '');
    setAddressLine2(addr.address_line2 || '');
    setCity(addr.city || 'London');
    setPostcode(addr.postcode || '');
    if (addr.phone) {
      const cleanPhone = addr.phone.replace(/\D/g, '');
      if (cleanPhone.length >= 11) {
        setPhoneDigits(cleanPhone.slice(-11));
      }
    }
  };

  const subtotal = getSubtotal();
  const delivery = getDeliveryFee();
  const loyaltyDiscount = redeemPoints > 0 ? redeemPoints / 1000 : 0;
  const effectiveDiscount = Math.min(subtotal, discountAmount + loyaltyDiscount);
  const total = Math.max(0, subtotal - effectiveDiscount + delivery + getServiceFee());

  // Initialize Square payments client singleton when in Step 2
  useEffect(() => {
    if (step !== 2 || !paymentConfig || paymentConfig.provider !== 'square') {
      setSquarePayments(null);
      return;
    }
    if (!paymentConfig.application_id || !paymentConfig.location_id) {
      return;
    }

    let isMounted = true;
    const appId = paymentConfig.application_id;
    const locId = paymentConfig.location_id;
    const isSandbox = paymentConfig.environment === 'sandbox' || appId.startsWith('sandbox-');

    loadSquareSdk(isSandbox)
      .then((Square) => {
        if (isMounted && Square) {
          const payments = Square.payments(appId, locId);
          setSquarePayments(payments);
        }
      })
      .catch((err) => {
        console.error('[Square SDK] Load failed:', err);
      });

    return () => {
      isMounted = false;
      setSquarePayments(null);
    };
  }, [step, paymentConfig?.application_id, paymentConfig?.location_id, paymentConfig?.provider, paymentConfig?.environment]);

  const handleContinueToPayment = () => {
    setError('');
    if (!customerName.trim()) {
      setError('Full Name is mandatory.');
      return;
    }
    if (!customerEmail.trim()) {
      setError('Email address is mandatory.');
      return;
    }
    if (orderType === 'DELIVERY') {
      if (!addressLine1.trim()) {
        setError('Address line 1 is mandatory (*).');
        return;
      }
      if (!postcode.trim()) {
        setError('Post code is mandatory (*).');
        return;
      }
    }
    if (phoneDigits.length !== 11) {
      setError('Phone number is mandatory (*) and must contain exactly 11 digits (e.g. 07123456789).');
      return;
    }
    setStep(2);
  };

  const submitOrderAndCharge = async (
    methodType: 'CARD' | 'GOOGLE_PAY' | 'APPLE_PAY',
    sourceId: string | undefined
  ) => {
    setError('');
    if (items.length === 0) {
      setError('Your cart is empty. Please add items before checking out.');
      return;
    }
    if (!selectedBranch) {
      setError('Please select a branch before checking out.');
      return;
    }

    const outOfStockItem = items.find(
      (i) => i.product.is_available === false || (i.product.stock_quantity !== undefined && i.product.stock_quantity <= 0)
    );
    if (outOfStockItem) {
      setError(`'${outOfStockItem.product.name}' is currently out of stock at ${selectedBranch.name}. Please remove it from your cart before proceeding.`);
      return;
    }

    setLoading(true);
    setPaymentLoading(true);
    setActivePaymentMethod(methodType);

    try {
      // Step 1: Create Order
      const fullPhone = `+44 ${phoneDigits}`;
      const orderPayload = {
        branch_id: selectedBranch.id,
        order_type: orderType,
        customer_name: customerName,
        customer_email: customerEmail,
        customer_phone: fullPhone,
        delivery_address: orderType === 'DELIVERY' ? {
          door_number: doorNumber,
          address_line1: addressLine1,
          address_line2: addressLine2,
          city: city || 'London',
          postcode,
          country: country || 'United Kingdom',
          latitude: userCoords?.lat ?? null,
          longitude: userCoords?.lng ?? null
        } : null,
        delivery_instructions: instructions,
        latitude: userCoords?.lat ?? null,
        longitude: userCoords?.lng ?? null,
        coupon_code: couponCode || undefined,
        redeem_points: redeemPoints > 0 ? redeemPoints : undefined,
        items: items.map((i) => ({
          product_id: i.product.id,
          quantity: i.quantity,
          selected_modifiers: (i.selectedModifiers || []).map((m) => ({ name: m.price ? m.name : m.name, price: m.price }))
        }))
      };

      const newOrder: any = await api.post('/orders', orderPayload);

      // Step 2: Create / Process Payment Session with strict method type and stable idempotency key
      const idempotencyKey = `idemp_${newOrder.id}`;
      const sessionRes: any = await api.post(
        '/payments/create-session',
        {
          order_id: newOrder.id,
          payment_method_type: methodType,
          source_id: sourceId
        },
        {
          headers: {
            'Idempotency-Key': idempotencyKey
          }
        }
      );

      if (sessionRes && sessionRes.status === 'PAID') {
        clearCart();
        navigate(`/order-confirmation/${newOrder.order_number}`);
      } else if (sessionRes && sessionRes.transaction_id && sessionRes.provider === 'MOCK') {
        navigate(`/mock-checkout/${sessionRes.transaction_id}`);
      } else if (sessionRes && sessionRes.payment_url) {
        navigate(sessionRes.payment_url);
      } else {
        clearCart();
        navigate(`/order-confirmation/${newOrder.order_number}`);
      }
    } catch (err: any) {
      const detailObj = err?.detail || err?.data?.detail;
      const rawMsg =
        (typeof detailObj === 'string' ? detailObj : '') ||
        (typeof detailObj === 'object' && detailObj !== null ? (detailObj.message || detailObj.error || detailObj.msg) : '') ||
        err?.message ||
        'Payment initiation failed. Please try again.';

      if (typeof rawMsg === 'string' && (rawMsg.includes('2 MILES') || rawMsg.includes('RADIUS') || rawMsg.includes('DELIVERY_OUTSIDE_RADIUS'))) {
        setError('WE PROVIDE DELIVERY UP TO 2 MILES ONLY. Please choose Collection or enter an address within 2 miles.');
      } else {
        setError(rawMsg);
      }
    } finally {
      setLoading(false);
      setPaymentLoading(false);
      setActivePaymentMethod(null);
    }
  };

  // 1. CARD PAYMENT HANDLER
  const handleCardPayment = async () => {
    if (loading || paymentLoading) return;
    setError('');

    if (paymentConfig?.provider === 'square') {
      if (!cardInstanceRef.current || !squareCardReady) {
        setError('Card payment inputs are still loading. Please wait a moment.');
        return;
      }
      setPaymentLoading(true);
      setActivePaymentMethod('CARD');
      try {
        const tokenResult = await cardInstanceRef.current.tokenize();
        if (tokenResult.status !== 'OK') {
          const firstErr = tokenResult.errors?.[0]?.message || 'Card payment could not be completed. Please check your card details and try again.';
          setError(firstErr);
          setPaymentLoading(false);
          setActivePaymentMethod(null);
          return;
        }
        await submitOrderAndCharge('CARD', tokenResult.token);
      } catch (err: any) {
        setError(err?.message || 'Card payment could not be completed. Please check your card details and try again.');
        setPaymentLoading(false);
        setActivePaymentMethod(null);
      }
    } else {
      await submitOrderAndCharge('CARD', undefined);
    }
  };

  // 2. GOOGLE PAY HANDLER
  const handleGooglePayPayment = async (gpayInstance: any) => {
    if (loading || paymentLoading) return;
    if (!gpayInstance) {
      setError('Google Pay is not available.');
      return;
    }
    setError('');
    setPaymentLoading(true);
    setActivePaymentMethod('GOOGLE_PAY');
    try {
      const tokenResult = await gpayInstance.tokenize();
      if (tokenResult.status !== 'OK') {
        const firstErr = tokenResult.errors?.[0]?.message || 'Google Pay payment could not be completed. Please try again.';
        setError(firstErr);
        setPaymentLoading(false);
        setActivePaymentMethod(null);
        return;
      }
      await submitOrderAndCharge('GOOGLE_PAY', tokenResult.token);
    } catch (err: any) {
      setError(err?.message || 'Google Pay payment failed. Please try again.');
      setPaymentLoading(false);
      setActivePaymentMethod(null);
    }
  };

  // 3. APPLE PAY HANDLER
  const handleApplePayPayment = async (apayInstance: any) => {
    if (loading || paymentLoading) return;
    if (!apayInstance) {
      setError('Apple Pay is not available.');
      return;
    }
    setError('');
    setPaymentLoading(true);
    setActivePaymentMethod('APPLE_PAY');
    try {
      const tokenResult = await apayInstance.tokenize();
      if (tokenResult.status !== 'OK') {
        const firstErr = tokenResult.errors?.[0]?.message || 'Apple Pay payment could not be completed. Please try again.';
        setError(firstErr);
        setPaymentLoading(false);
        setActivePaymentMethod(null);
        return;
      }
      await submitOrderAndCharge('APPLE_PAY', tokenResult.token);
    } catch (err: any) {
      setError(err?.message || 'Apple Pay payment failed. Please try again.');
      setPaymentLoading(false);
      setActivePaymentMethod(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 md:py-12">
      {/* STEPS BREADCRUMBS */}
      <div className="flex items-center gap-2 text-sm text-[#A1A1AA] mb-8 overflow-x-auto pb-2">
        <button
          type="button"
          onClick={() => setStep(1)}
          className={`flex items-center gap-2 cursor-pointer font-medium ${
            step >= 1 ? 'text-[#F5F5F5]' : 'text-[#71717A]'
          }`}
        >
          <div
            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
              step > 1
                ? 'bg-[#22C55E] text-black'
                : step === 1
                ? 'bg-[#FF5A00] text-white'
                : 'bg-[#1C1C1C] text-[#71717A]'
            }`}
          >
            {step > 1 ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : '1'}
          </div>
          <span>Delivery</span>
        </button>

        <div className="w-8 h-[1px] bg-[#242424]" />

        <div
          className={`flex items-center gap-2 font-medium ${
            step >= 2 ? 'text-[#F5F5F5]' : 'text-[#71717A]'
          }`}
        >
          <div
            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold ${
              step === 2
                ? 'bg-[#FF5A00] text-white'
                : 'bg-[#1C1C1C] text-[#71717A]'
            }`}
          >
            2
          </div>
          <span>Payment</span>
        </div>

        <div className="w-8 h-[1px] bg-[#242424]" />

        <div className="flex items-center gap-2 text-[#71717A] font-medium">
          <div className="w-6 h-6 rounded-full bg-[#1C1C1C] flex items-center justify-center text-xs font-semibold">
            3
          </div>
          <span>Confirmation</span>
        </div>
      </div>

      <h1 className="text-2xl sm:text-3xl font-extrabold text-[#F5F5F5] tracking-tight mb-8">
        Checkout
      </h1>

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-[#241209] border border-[#FF5A00]/40 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[#FF5A00] shrink-0 mt-0.5" />
          <div className="text-sm text-[#F5F5F5]">{error}</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* LEFT COLUMN: Steps Form */}
        <div className="lg:col-span-7 space-y-6">
          {step === 1 ? (
            /* STEP 1: DELIVERY / COLLECTION DETAILS */
            <>
              {/* Order Type Toggle */}
              <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-5 sm:p-6 space-y-4">
                <h2 className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">
                  Order Type
                </h2>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setOrderType('DELIVERY')}
                    className={`py-3 px-4 rounded-lg border text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer transition-all ${
                      orderType === 'DELIVERY'
                        ? 'bg-[#FF5A00] border-[#FF5A00] text-white shadow-md'
                        : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                    }`}
                  >
                    <Truck className="w-4 h-4" />
                    <span>Delivery</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setOrderType('COLLECTION')}
                    className={`py-3 px-4 rounded-lg border text-sm font-semibold flex items-center justify-center gap-2 cursor-pointer transition-all ${
                      orderType === 'COLLECTION'
                        ? 'bg-[#FF5A00] border-[#FF5A00] text-white shadow-md'
                        : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                    }`}
                  >
                    <ShoppingBag className="w-4 h-4" />
                    <span>Collection</span>
                  </button>
                </div>
              </div>

              {/* Contact Information */}
              <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-5 sm:p-6 space-y-4">
                <h2 className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">
                  Contact Information
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                      Full Name *
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. John Doe"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                      Email Address *
                    </label>
                    <input
                      type="email"
                      required
                      placeholder="e.g. john@example.com"
                      value={customerEmail}
                      onChange={(e) => setCustomerEmail(e.target.value)}
                      className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                    />
                  </div>

                  <div className="sm:col-span-2">
                    <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                      Phone Number * (11 digits)
                    </label>
                    <div className="flex items-center">
                      <div className="bg-[#151515] border border-[#242424] border-r-0 rounded-l-lg px-3 py-2.5 text-xs text-[#A1A1AA] font-mono shrink-0">
                        +44
                      </div>
                      <input
                        type="tel"
                        required
                        maxLength={11}
                        placeholder="07123456789"
                        value={phoneDigits}
                        onChange={(e) => setPhoneDigits(e.target.value.replace(/\D/g, ''))}
                        className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-r-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Delivery Address (if Delivery) */}
              {orderType === 'DELIVERY' && (
                <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-5 sm:p-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">
                      Delivery Address
                    </h2>
                    {user && (
                      <Link
                        to="/addresses"
                        className="text-xs text-[#FF5A00] hover:underline"
                      >
                        Manage Addresses
                      </Link>
                    )}
                  </div>

                  {/* Saved addresses selector */}
                  {user && savedAddresses.length > 0 && (
                    <div className="space-y-2 mb-4">
                      <label className="text-xs font-medium text-[#A1A1AA]">
                        Choose from saved addresses:
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {savedAddresses.map((addr) => (
                          <button
                            type="button"
                            key={addr.id}
                            onClick={() => selectSavedAddress(addr)}
                            className={`p-3 rounded-lg border text-left text-xs transition-all cursor-pointer ${
                              selectedAddressId === addr.id
                                ? 'bg-[#241209] border-[#6B2A0D] text-[#F5F5F5]'
                                : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                            }`}
                          >
                            <p className="font-semibold text-[#F5F5F5]">
                              {addr.address_line1}
                            </p>
                            <p className="text-[11px] text-[#71717A]">{addr.postcode}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                        Door / Flat / Building (Optional)
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Flat 4B"
                        value={doorNumber}
                        onChange={(e) => setDoorNumber(e.target.value)}
                        className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                        Postcode *
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. N9 9HF"
                        value={postcode}
                        onChange={(e) => setPostcode(e.target.value)}
                        className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                        Address Line 1 *
                      </label>
                      <input
                        type="text"
                        required
                        placeholder="e.g. 4 Market Parade, Hertford Road"
                        value={addressLine1}
                        onChange={(e) => setAddressLine1(e.target.value)}
                        className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none"
                      />
                    </div>

                    <div className="sm:col-span-2">
                      <label className="block text-xs font-medium text-[#A1A1AA] mb-1.5">
                        Delivery Instructions (Optional)
                      </label>
                      <input
                        type="text"
                        placeholder="e.g. Ring buzzer 4, leave by door"
                        value={instructions}
                        onChange={(e) => setInstructions(e.target.value)}
                        className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3.5 py-2.5 text-sm text-[#F5F5F5] placeholder-[#71717A] focus:outline-none"
                      />
                    </div>
                  </div>
                </div>
              )}

              <button
                type="button"
                onClick={handleContinueToPayment}
                className="w-full h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-sm font-semibold rounded-lg shadow-lg shadow-[#FF5A00]/20 transition-all cursor-pointer flex items-center justify-center gap-2"
              >
                <span>Continue to Payment</span>
                <span>•</span>
                <span>£{total.toFixed(2)}</span>
              </button>
            </>
          ) : (
            /* STEP 2: PAYMENT METHOD */
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-5 sm:p-6 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-[#1C1C1C]">
                <h2 className="text-xs font-bold text-[#F5F5F5] uppercase tracking-wider flex items-center gap-2">
                  <Lock className="w-4 h-4 text-[#FF5A00]" />
                  <span>Payment Details</span>
                </h2>
                <span className="bg-[#0D2818] border border-[#22C55E]/40 text-[#22C55E] text-[10px] font-semibold uppercase px-2.5 py-1 rounded flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#22C55E]" />
                  256-Bit SSL Encrypted
                </span>
              </div>

              {paymentConfig?.provider === 'square' ? (
                <div className="space-y-4">
                  {/* 1. DIGITAL WALLETS (Apple Pay & Google Pay) */}
                  <SquareDigitalWalletsSection
                    payments={squarePayments}
                    total={total}
                    loading={loading}
                    paymentLoading={paymentLoading}
                    activePaymentMethod={activePaymentMethod}
                    onGooglePayPayment={handleGooglePayPayment}
                    onApplePayPayment={handleApplePayPayment}
                  />

                  {/* 2. SQUARE CARD PAYMENT FORM */}
                  <SquareCardSection
                    payments={squarePayments}
                    onCardReady={setSquareCardReady}
                    onCardInstance={(card) => {
                      cardInstanceRef.current = card;
                    }}
                  />
                </div>
              ) : (
                <div className="p-4 rounded-lg border border-[#6B2A0D] bg-[#241209] flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-[#FF5A00]/10 border border-[#FF5A00]/30 flex items-center justify-center text-[#FF5A00]">
                      <Building2 className="w-4.5 h-4.5" />
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-[#F5F5F5]">Patty Secure Checkout</p>
                      <p className="text-xs text-[#A1A1AA]">Pay securely via our payment gateway</p>
                    </div>
                  </div>
                  <input type="radio" checked readOnly className="w-4 h-4 accent-[#FF5A00]" />
                </div>
              )}

              {/* Saved Cards Selector for Logged-In Loyalty Customers */}
              {user && savedCards.length > 0 && (
                <div className="space-y-2.5 pt-1">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-semibold text-[#FF5A00]">
                      Saved Payment Cards
                    </label>
                    <Link
                      to="/payment-methods"
                      className="text-xs text-[#A1A1AA] hover:text-[#F5F5F5] underline transition-colors"
                    >
                      Manage Cards
                    </Link>
                  </div>

                  <div className="space-y-2">
                    {savedCards.map((card) => {
                      const isSelected = selectedCardId === card.id;
                      return (
                        <div
                          key={card.id}
                          onClick={() => setSelectedCardId(card.id)}
                          className={`p-3 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                            isSelected
                              ? 'bg-[#241209] border-[#6B2A0D] text-[#F5F5F5]'
                              : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded bg-[#151515] border border-[#242424] flex items-center justify-center font-bold text-[10px] text-[#F5F5F5] shrink-0">
                              {card.card_brand.slice(0, 4)}
                            </div>
                            <div>
                              <p className="font-semibold text-xs text-[#F5F5F5]">{card.card_brand}</p>
                              <p className="text-xs font-mono text-[#A1A1AA]">
                                •••• •••• •••• {card.last4}
                              </p>
                            </div>
                          </div>

                          <div className={`w-4 h-4 rounded-full border flex items-center justify-center ${
                            isSelected ? 'border-[#FF5A00]' : 'border-[#242424]'
                          }`}>
                            {isSelected && <div className="w-2 h-2 rounded-full bg-[#FF5A00]" />}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Loyalty Points Redemption Selector for Logged-In Customers */}
              {user && loyaltyData && loyaltyData.available_points >= 4000 && (
                <div className="p-4 rounded-xl border border-[#B44810]/30 bg-[#160B04]/50 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Star className="w-4 h-4 text-[#FF5A00] fill-[#FF5A00]" />
                      <span className="text-xs font-semibold text-white">Redeem Patty Points</span>
                    </div>
                    <span className="text-xs font-bold text-[#FF5A00]">
                      {loyaltyData.available_points.toLocaleString()} PTS Available
                    </span>
                  </div>
                  <p className="text-[11px] text-[#A1A1AA]">
                    Redeem your rewards in whole £1 increments (1,000 pts = £1 discount).
                  </p>
                  <div className="relative">
                    <select
                      value={redeemPoints}
                      onChange={(e) => setRedeemPoints(Number(e.target.value))}
                      className="w-full h-11 bg-[#121212] border border-[#2E2E2E] focus:border-[#FF5A00] rounded-lg px-3.5 text-xs text-[#F5F5F5] focus:outline-none appearance-none cursor-pointer pr-10"
                    >
                      <option value={0}>Do not use points (£0.00)</option>
                      {(loyaltyData.redeemable_increments || [4000])
                        .filter((pts: number) => pts / 1000 <= subtotal)
                        .map((pts: number) => (
                          <option key={pts} value={pts}>
                            Redeem {pts.toLocaleString()} Points (-£{(pts / 1000).toFixed(2)})
                          </option>
                        ))}
                    </select>
                    <ChevronDown className="w-4 h-4 text-[#71717A] absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2 text-xs text-[#22C55E] font-medium pt-1">
                <CheckCircle2 className="w-4 h-4" />
                <span>All payments are secure and encrypted</span>
              </div>

              {/* Card Pay Securely CTA Button (Exclusively processes Card) */}
              <button
                type="button"
                onClick={handleCardPayment}
                disabled={loading || paymentLoading || (paymentConfig?.provider === 'square' && !squareCardReady)}
                className="w-full h-12 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-sm font-bold rounded-xl shadow-lg shadow-[#FF5A00]/20 transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#FF5A00]/50 active:scale-[0.99]"
              >
                <Lock className="w-4 h-4" />
                <span>
                  {activePaymentMethod === 'CARD' && paymentLoading
                    ? 'Processing Card Payment...'
                    : `Pay Securely with Card • £${total.toFixed(2)}`}
                </span>
              </button>

              {/* Security Footer Note matching Reference Image */}
              <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#71717A] pt-1">
                <ShieldCheck className="w-3.5 h-3.5 text-[#71717A]" />
                <span>Your payment details are never stored on our servers.</span>
              </div>

              <button
                type="button"
                onClick={() => setStep(1)}
                disabled={loading || paymentLoading}
                className="w-full text-xs text-[#71717A] hover:text-[#A1A1AA] text-center pt-0.5 cursor-pointer transition-colors disabled:opacity-50"
              >
                ← Back to Delivery
              </button>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Your Order Side Panel (Sticky) */}
        <div className="lg:col-span-5 space-y-5 sticky top-24">
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-6 space-y-4">
            {/* Header with Edit Cart link */}
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-[#F5F5F5]">
                Your Order
              </h2>
              <Link
                to="/cart"
                className="text-xs font-semibold text-[#FF5A00] hover:underline"
              >
                Edit Cart
              </Link>
            </div>

            {/* Cart Items List */}
            <div className="divide-y divide-[#1C1C1C] max-h-72 overflow-y-auto pr-1">
              {items.map((item, idx) => {
                const itemUnitTotal =
                  item.product.base_price +
                  (item.selectedModifiers || []).reduce((acc, m) => acc + (m.price || 0), 0);
                const itemLineTotal = itemUnitTotal * item.quantity;

                return (
                  <div key={`${item.product.id}-${idx}`} className="py-3 flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      {item.product.image_url ? (
                        <img
                          src={item.product.image_url}
                          alt={item.product.name}
                          className="w-10 h-10 rounded-lg object-cover bg-[#151515] shrink-0"
                        />
                      ) : (
                        <div className="w-10 h-10 rounded-lg bg-[#151515] border border-[#242424] flex items-center justify-center text-[#71717A] shrink-0">
                          <ShoppingBag className="w-4 h-4" />
                        </div>
                      )}
                      <div>
                        <p className="text-xs font-semibold text-[#F5F5F5] leading-tight">
                          {item.product.name}
                        </p>
                        {item.selectedModifiers && item.selectedModifiers.length > 0 ? (
                          <p className="text-[11px] text-[#71717A] mt-0.5 leading-snug">
                            {item.selectedModifiers.map((m) => m.name).join(', ')}
                          </p>
                        ) : (
                          <p className="text-[11px] text-[#71717A] mt-0.5">No Add-ons</p>
                        )}
                      </div>
                    </div>

                    <div className="text-right shrink-0">
                      <span className="text-[11px] text-[#71717A] mr-1.5 font-mono">
                        x{item.quantity}
                      </span>
                      <span className="text-xs font-semibold text-[#F5F5F5] font-mono">
                        £{itemLineTotal.toFixed(2)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Order Totals Calculation Breakdown */}
            <div className="border-t border-[#1C1C1C] pt-3.5 space-y-2 text-xs">
              <div className="flex justify-between text-[#A1A1AA]">
                <span>Subtotal</span>
                <span className="font-mono text-[#F5F5F5]">£{subtotal.toFixed(2)}</span>
              </div>

              {orderType === 'DELIVERY' && (
                <div className="flex justify-between text-[#A1A1AA]">
                  <span>Delivery fee</span>
                  <span className="font-mono text-[#F5F5F5]">
                    {delivery === 0 ? 'FREE' : `£${delivery.toFixed(2)}`}
                  </span>
                </div>
              )}

              <div className="flex justify-between text-[#A1A1AA]">
                <span>Service fee</span>
                <span className="font-mono text-[#F5F5F5]">
                  £{getServiceFee().toFixed(2)}
                </span>
              </div>

              {discountAmount > 0 && (
                <div className="flex justify-between text-[#22C55E]">
                  <span>Coupon Discount ({couponCode})</span>
                  <span className="font-mono">-£{discountAmount.toFixed(2)}</span>
                </div>
              )}

              {redeemPoints > 0 && (
                <div className="flex justify-between text-[#FF5A00]">
                  <span>Patty Points Redeemed ({redeemPoints.toLocaleString()} pts)</span>
                  <span className="font-mono">-£{loyaltyDiscount.toFixed(2)}</span>
                </div>
              )}

              <div className="border-t border-[#242424] pt-3 flex justify-between items-baseline">
                <span className="text-sm font-bold text-[#F5F5F5]">Total</span>
                <span className="text-xl font-black text-[#FF5A00] font-mono">
                  £{total.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Loyalty Points Earning Banner */}
            <div className="bg-[#151515] border border-[#242424] rounded-lg p-2.5 flex items-center justify-center gap-1.5 text-xs text-[#F5F5F5]">
              <Star className="w-3.5 h-3.5 text-[#FF5A00] fill-[#FF5A00]" />
              <span>
                Earn{' '}
                <strong className="text-[#FF5A00] font-mono">
                  {Math.round(total * 100)}
                </strong>{' '}
                Patty Points on this order
              </span>
            </div>

            <div className="flex items-center justify-center gap-1.5 text-[11px] text-[#71717A] pt-1">
              <ShieldCheck className="w-3.5 h-3.5 text-[#71717A]" />
              <span>Encrypted 256-bit SSL secure checkout</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
