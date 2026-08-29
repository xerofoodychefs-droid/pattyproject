import React, { useState, useEffect } from 'react';
import { X, Ticket, Plus } from 'lucide-react';
import { api } from '../../api/client';

interface AdminCreateCouponModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export const AdminCreateCouponModal: React.FC<AdminCreateCouponModalProps> = ({ onClose, onSuccess }) => {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [couponType, setCouponType] = useState<'PERCENTAGE' | 'FIXED_AMOUNT' | 'FREE_SHIPPING'>('PERCENTAGE');
  const [discountValue, setDiscountValue] = useState<string>('10');
  const [minOrderValue, setMinOrderValue] = useState<string>('15');
  const [usageLimit, setUsageLimit] = useState<string>('1000');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!code.trim()) {
      setError('Coupon code is required.');
      return;
    }
    if (!name.trim()) {
      setError('Coupon name is required.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/promotions/coupons', {
        code: code.trim().toUpperCase(),
        name: name.trim(),
        coupon_type: couponType,
        discount_value: couponType === 'FREE_SHIPPING' ? 0.0 : parseFloat(discountValue) || 0.0,
        min_order_value: parseFloat(minOrderValue) || 0.0,
        usage_limit: parseInt(usageLimit) || 1000,
        is_active: true
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create coupon. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal-container bg-[#0D0D0D] border border-[#242424] rounded-xl max-w-md shadow-2xl p-4 sm:p-6 relative text-[#F5F5F5] space-y-4">
        
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#1C1C1C] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] flex items-center justify-center text-[#FF5A00] shrink-0">
              <Ticket className="w-4.5 h-4.5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">Create Coupon</h2>
              <p className="text-xs text-[#A1A1AA]">Add a new promo code or discount offer</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="p-1 text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg transition-colors cursor-pointer shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/20 text-[#EF4444] rounded-lg text-xs font-medium shrink-0">
            {error}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 overflow-y-auto pr-1 space-y-3.5">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                  Coupon Code *
                </label>
                <input
                  type="text"
                  placeholder="e.g. SUMMER20"
                  value={code}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] uppercase font-mono font-semibold focus:outline-none transition-colors"
                  required
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                  Coupon Name *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Summer Special"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] focus:outline-none transition-colors"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                Discount Type *
              </label>
              <select
                value={couponType}
                onChange={(e: any) => setCouponType(e.target.value)}
                className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] focus:outline-none transition-colors"
              >
                <option value="PERCENTAGE">Percentage (% OFF)</option>
                <option value="FIXED_AMOUNT">Fixed Amount (£ OFF)</option>
                <option value="FREE_SHIPPING">Free Shipping</option>
              </select>
            </div>

            {couponType !== 'FREE_SHIPPING' && (
              <div>
                <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                  Discount Value * {couponType === 'PERCENTAGE' ? '(%)' : '(£)'}
                </label>
                <input
                  type="number"
                  step="0.01"
                  placeholder={couponType === 'PERCENTAGE' ? 'e.g. 20' : 'e.g. 5.00'}
                  value={discountValue}
                  onChange={(e) => setDiscountValue(e.target.value)}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] focus:outline-none transition-colors"
                  required
                />
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                  Min. Order Value (£)
                </label>
                <input
                  type="number"
                  step="0.01"
                  placeholder="e.g. 15.00"
                  value={minOrderValue}
                  onChange={(e) => setMinOrderValue(e.target.value)}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] focus:outline-none transition-colors"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-[#A1A1AA] uppercase mb-1">
                  Usage Limit
                </label>
                <input
                  type="number"
                  placeholder="e.g. 1000"
                  value={usageLimit}
                  onChange={(e) => setUsageLimit(e.target.value)}
                  className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 text-xs text-[#F5F5F5] focus:outline-none transition-colors"
                />
              </div>
            </div>
          </div>

          <div className="pt-4 mt-4 flex flex-wrap items-center justify-end gap-2.5 border-t border-[#1C1C1C] shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-4 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="h-9 px-4 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{loading ? 'Creating...' : 'Create Coupon'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
