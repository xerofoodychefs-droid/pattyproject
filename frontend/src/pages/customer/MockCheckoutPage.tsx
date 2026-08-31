import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ShieldAlert, CheckCircle2, XCircle, AlertTriangle, Clock, ArrowLeft, RefreshCw, Loader2 } from 'lucide-react';
import { api } from '../../api/client';
import { useCartStore } from '../../store/cartStore';


interface MockPaymentData {
  payment_id: string;
  transaction_id: string;
  order_id: string;
  order_number: string;
  customer_name: string;
  order_type: string;
  amount: number;
  currency: string;
  payment_status: string;
  order_status: string;
  created_at: string;
}

export const MockCheckoutPage: React.FC = () => {
  const { transactionId } = useParams<{ transactionId?: string }>();
  const [searchParams] = useSearchParams();
  const txId = transactionId || searchParams.get('transaction_id') || searchParams.get('tx_id') || '';

  const navigate = useNavigate();
  const { clearCart } = useCartStore();

  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [paymentData, setPaymentData] = useState<MockPaymentData | null>(null);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);

  const fetchPaymentDetails = useCallback(async () => {
    if (!txId) {
      setError('No transaction ID provided.');
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError('');
      const data: MockPaymentData = await api.get(`/payments/verify/${txId}`);
      setPaymentData(data);
    } catch (err: any) {
      const detailMsg =
        (typeof err?.detail === 'string' ? err.detail : '') ||
        (typeof err?.detail === 'object' && err.detail ? (err.detail.message || err.detail.error || err.detail.msg) : '') ||
        err?.message ||
        'Failed to load transaction details from development gateway.';
      setError(detailMsg);
    } finally {
      setLoading(false);
    }
  }, [txId]);

  useEffect(() => {
    fetchPaymentDetails();
  }, [fetchPaymentDetails]);

  const handleSimulatePayment = async (status: 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'PENDING') => {
    if (!paymentData) return;

    setActionLoading(true);
    setActionMessage(null);
    setError('');

    try {
      const payload = {
        order_id: paymentData.order_id,
        transaction_id: paymentData.transaction_id,
        status: status,
        amount: paymentData.amount,
        currency: paymentData.currency || 'GBP'
      };

      const res: any = await api.post('/payments/mock-simulate', payload);

      if (status === 'SUCCESS') {
        clearCart();
        setActionMessage({
          type: 'success',
          text: 'Payment successful! Redirecting to order confirmation...'
        });
        const targetIdentifier = paymentData.order_id || encodeURIComponent(paymentData.order_number || '');
        setTimeout(() => {
          navigate(`/order-confirmation/${targetIdentifier}`);
        }, 1200);
      } else if (status === 'FAILED') {
        setActionMessage({
          type: 'error',
          text: 'Simulated payment failure recorded. Payment status is now FAILED. Order remains unpaid.'
        });
        await fetchPaymentDetails();
      } else if (status === 'CANCELLED') {
        setActionMessage({
          type: 'warning',
          text: 'Simulated payment cancellation recorded. Payment status is now CANCELLED. Order remains unpaid.'
        });
        await fetchPaymentDetails();
      } else if (status === 'PENDING') {
        setActionMessage({
          type: 'info',
          text: 'Payment status remains PENDING. Order remains unpaid.'
        });
        await fetchPaymentDetails();
      }
    } catch (err: any) {
      const detailMsg =
        (typeof err?.detail === 'string' ? err.detail : '') ||
        (typeof err?.detail === 'object' && err.detail ? (err.detail.message || err.detail.error || err.detail.msg) : '') ||
        err?.message ||
        `Failed to simulate ${status} event on backend.`;
      setError(detailMsg);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRetryPayment = async () => {
    setActionLoading(true);
    setError('');
    setActionMessage(null);
    try {
      if (paymentData?.order_id) {
        const retryIdempotencyKey = `idemp_retry_${paymentData.order_id}_${Date.now()}`;
        const newSession: any = await api.post(
          '/payments/create-session',
          {
            order_id: paymentData.order_id,
            payment_method_type: 'CARD'
          },
          {
            headers: {
              'Idempotency-Key': retryIdempotencyKey
            }
          }
        );
        if (newSession && newSession.transaction_id) {
          navigate(`/mock-checkout/${newSession.transaction_id}`);
          return;
        }
      }
      await fetchPaymentDetails();
    } catch (err: any) {
      const detailMsg =
        (typeof err?.detail === 'string' ? err.detail : '') ||
        (typeof err?.detail === 'object' && err.detail ? (err.detail.message || err.detail.error || err.detail.msg) : '') ||
        err?.message ||
        'Failed to re-initiate payment session.';
      setError(detailMsg);
    } finally {
      setActionLoading(false);
    }
  };



  return (
    <div className="w-full max-w-3xl mx-auto px-4 py-8 pb-20 text-[#F5F5F5]">
      {/* Development Warning Header */}
      <div className="bg-[#18181B] border-2 border-[#EAB308] rounded-xl p-5 mb-8 shadow-lg">
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 rounded-lg bg-[#EAB308]/10 border border-[#EAB308]/30 flex items-center justify-center shrink-0 text-[#EAB308]">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-[#EAB308] text-black">
                Development Test Payment
              </span>
              <span className="text-xs text-[#A1A1AA]">Pluggable Mock Gateway</span>
            </div>
            <p className="text-sm text-[#D4D4D8] mt-2 leading-relaxed">
              This is an internal development mock payment screen used for end-to-end integration testing without connecting to live bank providers. This gateway is strictly blocked in production environments.
            </p>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center py-20 bg-[#121212] border border-[#27272A] rounded-xl">
          <Loader2 className="w-8 h-8 text-[#FF5A00] animate-spin mb-4" />
          <p className="text-sm text-[#A1A1AA]">Loading mock transaction details...</p>
        </div>
      ) : error ? (
        <div className="bg-[#18181B] border border-[#EF4444]/40 rounded-xl p-6 text-center">
          <XCircle className="w-10 h-10 text-[#EF4444] mx-auto mb-3" />
          <h2 className="text-lg font-bold text-white mb-2">Gateway Error</h2>
          <p className="text-sm text-[#EF4444] mb-6">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={fetchPaymentDetails}
              className="px-4 py-2 bg-[#27272A] hover:bg-[#3F3F46] text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <RefreshCw className="w-4 h-4" /> Retry
            </button>
            <button
              onClick={() => navigate('/checkout')}
              className="px-4 py-2 bg-[#FF5A00] hover:bg-[#EA580C] text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <ArrowLeft className="w-4 h-4" /> Return to Checkout
            </button>
          </div>
        </div>
      ) : paymentData ? (
        <div className="space-y-6">
          {/* Order & Payment Summary Card */}
          <div className="bg-[#121212] border border-[#27272A] rounded-xl p-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#27272A] mb-5">
              <div>
                <span className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">Order Reference</span>
                <h2 className="text-xl font-bold text-white mt-0.5">{paymentData.order_number}</h2>
              </div>
              <div className="text-right">
                <span className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider">Total Charge</span>
                <p className="text-2xl font-black text-[#FF5A00] mt-0.5">
                  £{paymentData.amount.toFixed(2)} <span className="text-xs font-normal text-[#A1A1AA]">{paymentData.currency}</span>
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div className="bg-[#18181B] p-3.5 rounded-lg border border-[#27272A]/70">
                <span className="text-xs text-[#71717A] block mb-1">Customer Name</span>
                <span className="font-semibold text-[#F4F4F5]">{paymentData.customer_name}</span>
              </div>
              <div className="bg-[#18181B] p-3.5 rounded-lg border border-[#27272A]/70">
                <span className="text-xs text-[#71717A] block mb-1">Order Type</span>
                <span className="font-semibold text-[#F4F4F5]">{paymentData.order_type}</span>
              </div>
              <div className="bg-[#18181B] p-3.5 rounded-lg border border-[#27272A]/70">
                <span className="text-xs text-[#71717A] block mb-1">Mock Transaction ID</span>
                <code className="text-xs font-mono text-[#38BDF8] break-all">{paymentData.transaction_id}</code>
              </div>
              <div className="bg-[#18181B] p-3.5 rounded-lg border border-[#27272A]/70">
                <span className="text-xs text-[#71717A] block mb-1">Current Payment Status</span>
                <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-bold ${
                  paymentData.payment_status === 'PAID'
                    ? 'bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30'
                    : paymentData.payment_status === 'FAILED'
                    ? 'bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/30'
                    : paymentData.payment_status === 'CANCELLED'
                    ? 'bg-[#A1A1AA]/10 text-[#A1A1AA] border border-[#A1A1AA]/30'
                    : 'bg-[#EAB308]/10 text-[#EAB308] border border-[#EAB308]/30'
                }`}>
                  {paymentData.payment_status}
                </span>
              </div>
            </div>
          </div>

          {/* Action Feedback Message */}
          {actionMessage && (
            <div className={`p-4 rounded-xl border flex items-start gap-3 ${
              actionMessage.type === 'success'
                ? 'bg-[#22C55E]/10 border-[#22C55E]/40 text-[#22C55E]'
                : actionMessage.type === 'error'
                ? 'bg-[#EF4444]/10 border-[#EF4444]/40 text-[#EF4444]'
                : actionMessage.type === 'warning'
                ? 'bg-[#F97316]/10 border-[#F97316]/40 text-[#F97316]'
                : 'bg-[#38BDF8]/10 border-[#38BDF8]/40 text-[#38BDF8]'
            }`}>
              {actionMessage.type === 'success' && <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />}
              {actionMessage.type === 'error' && <XCircle className="w-5 h-5 shrink-0 mt-0.5" />}
              {actionMessage.type === 'warning' && <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />}
              {actionMessage.type === 'info' && <Clock className="w-5 h-5 shrink-0 mt-0.5" />}
              <p className="text-sm leading-relaxed">{actionMessage.text}</p>
            </div>
          )}

          {/* Controlled Simulation Actions */}
          <div className="bg-[#121212] border border-[#27272A] rounded-xl p-6">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider mb-2">Simulate Payment Outcome</h3>
            <p className="text-xs text-[#A1A1AA] mb-5">
              Select an action below to test the full lifecycle transitions, webhooks, and order status updates.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
              {/* Simulate Success */}
              <button
                id="btn-simulate-success"
                disabled={actionLoading || paymentData.payment_status === 'PAID'}
                onClick={() => handleSimulatePayment('SUCCESS')}
                className="w-full p-4 bg-[#22C55E] hover:bg-[#16A34A] disabled:opacity-50 disabled:cursor-not-allowed text-black font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2.5 shadow-md"
              >
                <CheckCircle2 className="w-5 h-5" />
                <span>Simulate Successful Payment</span>
              </button>

              {/* Simulate Failure */}
              <button
                id="btn-simulate-failure"
                disabled={actionLoading || paymentData.payment_status === 'PAID'}
                onClick={() => handleSimulatePayment('FAILED')}
                className="w-full p-4 bg-[#EF4444] hover:bg-[#DC2626] disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2.5 shadow-md"
              >
                <XCircle className="w-5 h-5" />
                <span>Simulate Failed Payment</span>
              </button>

              {/* Simulate Cancellation */}
              <button
                id="btn-simulate-cancel"
                disabled={actionLoading || paymentData.payment_status === 'PAID'}
                onClick={() => handleSimulatePayment('CANCELLED')}
                className="w-full p-4 bg-[#27272A] hover:bg-[#3F3F46] disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2.5 border border-[#3F3F46]"
              >
                <AlertTriangle className="w-5 h-5 text-[#EAB308]" />
                <span>Simulate Cancelled Payment</span>
              </button>

              {/* Simulate Pending */}
              <button
                id="btn-simulate-pending"
                disabled={actionLoading || paymentData.payment_status === 'PAID'}
                onClick={() => handleSimulatePayment('PENDING')}
                className="w-full p-4 bg-[#18181B] hover:bg-[#27272A] disabled:opacity-50 disabled:cursor-not-allowed text-[#D4D4D8] font-bold text-sm rounded-xl transition-all flex items-center justify-center gap-2.5 border border-[#27272A]"
              >
                <Clock className="w-5 h-5 text-[#38BDF8]" />
                <span>Simulate Pending Payment</span>
              </button>
            </div>

            {(paymentData.payment_status === 'FAILED' || paymentData.payment_status === 'CANCELLED') && (
              <div className="mt-4 p-4 bg-[#241209] border border-[#6B2A0D] rounded-xl flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="text-left">
                  <p className="text-xs font-bold text-[#FF5A00] uppercase tracking-wider">Payment Not Completed</p>
                  <p className="text-xs text-[#A1A1AA]">You can re-initiate a payment attempt for this order without creating a duplicate.</p>
                </div>
                <button
                  onClick={handleRetryPayment}
                  disabled={actionLoading}
                  className="px-4 py-2 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-2 whitespace-nowrap shadow-md"
                >
                  <RefreshCw className="w-3.5 h-3.5" /> Re-try Payment
                </button>
              </div>
            )}


            {/* Back to Checkout */}
            <div className="mt-6 pt-5 border-t border-[#27272A] flex items-center justify-between">
              <button
                onClick={() => navigate('/checkout')}
                className="text-xs text-[#A1A1AA] hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <ArrowLeft className="w-3.5 h-3.5" /> Return to Customer Checkout
              </button>

              <button
                onClick={fetchPaymentDetails}
                className="text-xs text-[#A1A1AA] hover:text-white flex items-center gap-1.5 transition-colors"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Refresh Status
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};
