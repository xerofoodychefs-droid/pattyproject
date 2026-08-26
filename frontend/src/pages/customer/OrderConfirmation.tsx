import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { CheckCircle2, Clock, MapPin, CreditCard, Phone, Mail, AlertTriangle, ArrowRight, ShoppingBag, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { Order } from '../../types';

export const OrderConfirmation: React.FC = () => {
  const { orderNumber } = useParams<{ orderNumber: string }>();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (orderNumber) {
      setLoading(true);
      setError('');
      api.get<Order>(`/orders/${encodeURIComponent(orderNumber)}`)
        .then((ord) => {
          setOrder(ord);
        })
        .catch((err) => {
          setError(err?.message || 'Could not load order confirmation details.');
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [orderNumber]);

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 text-center space-y-4">
        <Loader2 className="w-10 h-10 text-[#FF5A00] animate-spin mx-auto" />
        <p className="text-sm text-[#A1A1AA]">Retrieving authoritative order details...</p>
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-16 text-center space-y-6">
        <div className="w-16 h-16 bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/30 rounded-full flex items-center justify-center mx-auto">
          <AlertTriangle className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h1 className="text-2xl font-bold text-white">Order Not Found</h1>
          <p className="text-sm text-[#A1A1AA]">{error || `We could not find order ${orderNumber}.`}</p>
        </div>
        <Link
          to="/menu"
          className="inline-block bg-[#FF5A00] hover:bg-[#E84F00] text-white px-6 py-3 rounded-xl font-bold text-xs uppercase tracking-wider transition-colors shadow-lg shadow-[#FF5A00]/20"
        >
          Return to Menu
        </Link>
      </div>
    );
  }

  const isPaid = order.payment_status === 'PAID' || ['INCOMING', 'ACCEPTED', 'PREPARING', 'READY', 'OUT_FOR_DELIVERY', 'DELIVERED', 'COLLECTED'].includes(order.status);

  return (
    <div className="max-w-2xl mx-auto px-4 py-12 pb-24 space-y-8 text-center">
      {/* Status Heading */}
      {isPaid ? (
        <div className="space-y-3">
          <div className="w-16 h-16 bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/30 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-[#10B981]/10">
            <CheckCircle2 className="w-10 h-10" />
          </div>
          <h1 className="text-3xl font-extrabold text-white">Thank You!</h1>
          <p className="text-base font-bold text-[#FF5A00]">Your order has been placed.</p>
          <p className="text-xs text-[#9CA3AF]">
            Your order <strong className="text-white">{order.order_number}</strong> has been confirmed and received by the kitchen.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="w-16 h-16 bg-[#EAB308]/10 text-[#EAB308] border border-[#EAB308]/30 rounded-full flex items-center justify-center mx-auto shadow-lg shadow-[#EAB308]/10">
            <Clock className="w-10 h-10" />
          </div>
          <h1 className="text-3xl font-extrabold text-white">Payment Awaiting Confirmation</h1>
          <p className="text-base font-bold text-[#EAB308]">Payment is currently {order.payment_status || 'PENDING'}</p>
          <p className="text-xs text-[#9CA3AF]">
            Your order <strong className="text-white">{order.order_number}</strong> has been created, but payment has not been completed.
          </p>
        </div>
      )}

      {/* Metrics Card Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-[#121212] border border-[#262626] p-4 rounded-2xl shadow-xl text-xs text-left">
        <div className="space-y-1">
          <p className="text-[10px] text-[#6B7280] uppercase font-bold">Order Number</p>
          <p className="font-bold text-[#FF5A00]">{order.order_number}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] text-[#6B7280] uppercase font-bold">Fulfillment</p>
          <p className="font-bold text-white">{order.order_type}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] text-[#6B7280] uppercase font-bold">Total Amount</p>
          <p className="font-bold text-white">£{Number(order.total_amount || 0).toFixed(2)}</p>
        </div>
        <div className="space-y-1">
          <p className="text-[10px] text-[#6B7280] uppercase font-bold">Payment Status</p>
          <p className={`font-bold ${isPaid ? 'text-[#10B981]' : 'text-[#EAB308]'}`}>
            {order.payment_status || 'PENDING'}
          </p>
        </div>
      </div>

      {/* Pending Payment Action */}
      {!isPaid && (
        <div className="p-4 bg-[#241209] border border-[#6B2A0D] rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3 text-left">
          <div>
            <p className="text-xs font-bold text-[#FF5A00] uppercase tracking-wider">Complete Your Payment</p>
            <p className="text-xs text-[#A1A1AA]">Finish paying to send your order directly to the kitchen.</p>
          </div>
          <Link
            to={order.payment_transaction_id ? `/mock-checkout/${order.payment_transaction_id}` : '/checkout'}
            className="px-4 py-2 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-2 whitespace-nowrap shadow-md"
          >
            <span>Complete Payment</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* Support Contact Footer Card */}
      <div className="bg-[#121212] border border-[#262626] p-4 rounded-2xl flex items-center justify-around text-xs text-[#9CA3AF]">
        <div className="flex items-center gap-2">
          <Phone className="w-4 h-4 text-[#FF5A00]" />
          <div className="text-left">
            <p className="text-[10px] text-[#6B7280]">Need help?</p>
            <p className="font-bold text-white">07417 521128</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Mail className="w-4 h-4 text-[#FF5A00]" />
          <div className="text-left">
            <p className="text-[10px] text-[#6B7280]">Email support</p>
            <p className="font-bold text-white">hellofoodychefs@gmail.com</p>
          </div>
        </div>
      </div>

      <Link
        to="/menu"
        className="inline-block bg-[#FF5A00] hover:bg-[#E84F00] text-white px-8 py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider shadow-lg shadow-[#FF5A00]/25 transition-colors"
      >
        BACK TO MENU
      </Link>
    </div>
  );
};

