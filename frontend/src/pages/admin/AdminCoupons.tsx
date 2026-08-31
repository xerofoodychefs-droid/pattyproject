import React, { useEffect, useState } from 'react';
import { Search, Plus, Trash2, RefreshCw, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';
import { AdminCreateCouponModal } from './AdminCreateCouponModal';

interface CouponItem {
  id: string;
  code: string;
  name: string;
  coupon_type: string;
  discount_value: number;
  min_order_value: number;
  usage_limit: number;
  used_count: number;
  is_active: boolean;
  created_at?: string;
}

export const AdminCoupons: React.FC = () => {
  const [coupons, setCoupons] = useState<CouponItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchCoupons = async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await api.get('/promotions/coupons');
      setCoupons(Array.isArray(data) ? data : []);
    } catch (err: any) {
      console.error('Failed to fetch coupons:', err);
      setError(err?.detail || err?.message || 'Failed to fetch coupons. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCoupons();
  }, []);

  const handleDelete = async (id: string, code: string) => {
    if (!window.confirm(`Are you sure you want to delete coupon "${code}"?`)) return;
    setDeletingId(id);
    try {
      await api.delete(`/promotions/coupons/${id}`);
      fetchCoupons();
    } catch (err) {
      alert('Failed to delete coupon.');
    } finally {
      setDeletingId(null);
    }
  };

  const filteredCoupons = coupons.filter(c => 
    c.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 w-full max-w-[1680px] mx-auto space-y-6 text-[#F5F5F5]">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">Coupons & Offers</h1>
          <p className="text-sm text-[#A1A1AA] font-normal mt-1">Create, manage and track all discounts and offers</p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={fetchCoupons}
            className="w-10 h-10 bg-[#151515] border border-[#242424] hover:border-[#333333] rounded-lg text-[#A1A1AA] hover:text-[#F5F5F5] flex items-center justify-center transition-colors cursor-pointer"
            title="Refresh Coupons"
            aria-label="Refresh coupons"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="h-10 px-4 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Coupon</span>
          </button>
        </div>
      </div>

      {/* Toolbar & Search */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0D0D0D] border border-[#242424] p-3 rounded-lg">
        <div className="relative w-64 sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-3 text-[#71717A]" />
          <input
            type="text"
            placeholder="Search by coupon code or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg py-2 pl-9 pr-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-xl flex items-center justify-between text-red-300 text-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
          <button
            onClick={fetchCoupons}
            className="px-3 py-1 bg-red-900/60 hover:bg-red-800 border border-red-700 rounded text-white text-xs font-semibold transition-colors cursor-pointer"
          >
            Retry
          </button>
        </div>
      )}

      {/* Coupons Data Table */}
      <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
              <tr>
                <th className="px-5 py-3.5">Coupon Code</th>
                <th className="px-5 py-3.5">Coupon Name</th>
                <th className="px-5 py-3.5">Type</th>
                <th className="px-5 py-3.5">Discount</th>
                <th className="px-5 py-3.5 text-right">Min. Order</th>
                <th className="px-5 py-3.5">Usage</th>
                <th className="px-5 py-3.5 text-center">Status</th>
                <th className="px-5 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                    <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-28" /></td>
                    <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                    <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-16" /></td>
                    <td className="px-5 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-12 ml-auto" /></td>
                    <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-28" /></td>
                    <td className="px-5 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-14 mx-auto" /></td>
                    <td className="px-5 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-8 ml-auto" /></td>
                  </tr>
                ))
              ) : filteredCoupons.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center text-[#71717A]">
                    No coupons found. Click "Create Coupon" to add one!
                  </td>
                </tr>
              ) : (
                filteredCoupons.map((c) => (
                  <tr key={c.id} className="hover:bg-[#121212] transition-colors h-14">
                    <td className="px-5 py-3">
                      <span className="px-2.5 py-1 bg-[#151515] text-[#F5F5F5] border border-[#242424] rounded text-xs font-mono font-semibold">
                        {c.code}
                      </span>
                    </td>
                    <td className="px-5 py-3 font-semibold text-[#F5F5F5]">{c.name}</td>
                    <td className="px-5 py-3 text-[#A1A1AA]">
                      {c.coupon_type === 'PERCENTAGE' ? 'Percentage' : c.coupon_type === 'FIXED_AMOUNT' ? 'Fixed Amount' : 'Free Shipping'}
                    </td>
                    <td className="px-5 py-3 font-semibold text-[#FF5A00]">
                      {c.coupon_type === 'PERCENTAGE' ? `${c.discount_value}% OFF` : c.coupon_type === 'FIXED_AMOUNT' ? `£${c.discount_value.toFixed(2)} OFF` : 'Free Delivery'}
                    </td>
                    <td className="px-5 py-3 text-right font-semibold text-[#F5F5F5]">£{c.min_order_value.toFixed(2)}</td>
                    <td className="px-5 py-3">
                      <div className="w-28 space-y-1">
                        <div className="flex justify-between text-[10px] text-[#A1A1AA]">
                          <span>{c.used_count} used</span>
                          <span>{c.usage_limit}</span>
                        </div>
                        <div className="w-full bg-[#151515] border border-[#242424] h-1.5 rounded-full overflow-hidden">
                          <div
                            className="bg-[#FF5A00] h-full rounded-full"
                            style={{ width: `${Math.min(100, (c.used_count / (c.usage_limit || 1)) * 100)}%` }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-center">
                      <span
                        className={`px-2.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${
                          c.is_active
                            ? 'bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/30'
                            : 'bg-[#151515] text-[#71717A] border-[#242424]'
                        }`}
                      >
                        {c.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={() => handleDelete(c.id, c.code)}
                        disabled={deletingId === c.id}
                        className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] text-[#71717A] hover:text-[#EF4444] hover:border-[#EF4444]/40 hover:bg-[#EF4444]/10 inline-flex items-center justify-center transition-colors cursor-pointer disabled:opacity-50"
                        title="Delete Coupon"
                        aria-label="Delete coupon"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showCreateModal && (
        <AdminCreateCouponModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={fetchCoupons}
        />
      )}
    </div>
  );
};
