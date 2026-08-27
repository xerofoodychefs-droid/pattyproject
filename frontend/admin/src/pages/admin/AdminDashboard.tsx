import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, ArrowLeft, Download, Calendar, Plus, Trash2, AlertTriangle } from 'lucide-react';
import { api } from '../../api/client';
import { Branch, Order, BranchStats } from '../../types';
import { useAuthStore } from '../../store/authStore';
import { AdminCreateBranchModal } from './AdminCreateBranchModal';

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchStats, setBranchStats] = useState<Record<string, BranchStats>>({});
  const [selectedBranch, setSelectedBranch] = useState<Branch | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateBranchModal, setShowCreateBranchModal] = useState(false);
  const [branchToDelete, setBranchToDelete] = useState<Branch | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchBranches(false);
    const interval = setInterval(() => {
      fetchBranches(true);
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  const fetchBranches = async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      const [branchData, statsData] = await Promise.all([
        api.get<Branch[]>('/branches'),
        api.get<BranchStats[]>('/branches/stats').catch(() => [])
      ]);
      let filtered = branchData || [];
      if (user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids.length > 0) {
        filtered = filtered.filter((b) => user.branch_ids.includes(b.id));
      }
      setBranches(filtered);

      if (Array.isArray(statsData)) {
        const statsMap: Record<string, BranchStats> = {};
        statsData.forEach((s) => {
          statsMap[s.branch_id] = s;
        });
        setBranchStats(statsMap);
      }
    } catch (err) {
      console.error(err);
    } finally {
      if (!isSilent) setLoading(false);
    }
  };

  const handleSelectBranch = async (branch: Branch) => {
    setSelectedBranch(branch);
    try {
      const branchOrders: Order[] = await api.get(`/orders?branch_id=${branch.id}`);
      setOrders(branchOrders);
    } catch (err) {
      console.error(err);
    }
  };

  const handleConfirmDeleteBranch = async () => {
    if (!branchToDelete || user?.role !== 'SUPER_ADMIN') return;
    setDeleting(true);
    const targetId = branchToDelete.id;
    try {
      await api.delete(`/branches/${targetId}`);
      setBranches((prev) => prev.filter((b) => b.id !== targetId));
      setBranchToDelete(null);
      fetchBranches();
    } catch (err: any) {
      console.error('Failed to delete branch:', err);
      const errMsg = err?.message || err?.detail || '';
      const isAuthErr =
        errMsg.toLowerCase().includes('authenticated') ||
        errMsg.toLowerCase().includes('permission') ||
        errMsg.toLowerCase().includes('credential');

      if (isAuthErr) {
        alert('Session expired or unauthorized. Please log in with an administrator account.');
        navigate('/login');
      } else {
        alert(errMsg || 'Failed to delete branch. Please try again.');
      }
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-[#9CA3AF] text-sm mt-1">
            {user?.role === 'BRANCH_ADMIN' ? 'View and manage orders for your assigned branch.' : 'View and manage orders for each branch.'}
          </p>
        </div>
        {user?.role === 'SUPER_ADMIN' && (
          <button
            onClick={() => setShowCreateBranchModal(true)}
            className="bg-[#FF5500] hover:bg-[#E04D00] text-white px-5 py-2.5 rounded-xl font-semibold text-sm flex items-center gap-2 shadow-lg shadow-[#FF5500]/20 transition-all cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Branch</span>
          </button>
        )}
      </div>

      {/* Main Branch Summary Table */}
      {!selectedBranch ? (
        <div className="bg-[#121212] border border-[#262626] rounded-2xl overflow-hidden shadow-xl">
          <div className="p-6 border-b border-[#1F1F1F]">
            <h2 className="text-lg font-bold text-white">All Branches Overview</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[#1A1A1A] text-[#9CA3AF] uppercase text-xs font-semibold border-b border-[#262626]">
                <tr>
                  <th className="px-6 py-4">Branch Name</th>
                  <th className="px-6 py-4 text-center">Total Orders</th>
                  <th className="px-6 py-4 text-center">Completed Orders</th>
                  <th className="px-6 py-4 text-center">Cancelled Orders</th>
                  <th className="px-6 py-4 text-center">Pending Orders</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1F1F1F]">
                {branches.map((b) => {
                  const stats = branchStats[b.id] || {
                    total_orders: 0,
                    completed_orders: 0,
                    cancelled_orders: 0,
                    pending_orders: 0
                  };
                  return (
                    <tr
                      key={b.id}
                      onClick={() => handleSelectBranch(b)}
                      className="hover:bg-[#1A1A1A] cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 flex items-center gap-3">
                        <span className="w-10 h-10 rounded-xl bg-[#FF5500]/10 text-[#FF5500] font-bold flex items-center justify-center border border-[#FF5500]/30">
                          {b.code}
                        </span>
                        <div>
                          <p className="font-semibold text-white">{b.name}</p>
                          <p className="text-xs text-[#9CA3AF]">{b.postcode}</p>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center font-semibold text-white">{stats.total_orders}</td>
                      <td className="px-6 py-4 text-center text-[#10B981] font-semibold">{stats.completed_orders}</td>
                      <td className="px-6 py-4 text-center text-[#EF4444] font-semibold">{stats.cancelled_orders}</td>
                      <td className="px-6 py-4 text-center text-[#FF5500] font-semibold">{stats.pending_orders}</td>
                      <td className="px-6 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-end gap-2">
                          {user?.role === 'SUPER_ADMIN' && (
                            <button
                              onClick={() => setBranchToDelete(b)}
                              title="Delete Branch"
                              className="p-2 text-[#9CA3AF] hover:text-[#EF4444] hover:bg-[#EF4444]/10 rounded-xl transition-all cursor-pointer"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => handleSelectBranch(b)}
                            title="View Branch Orders"
                            className="p-2 text-[#9CA3AF] hover:text-white hover:bg-[#1A1A1A] rounded-xl transition-all cursor-pointer"
                          >
                            <ChevronRight className="w-5 h-5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Branch Detail Order View */
        <div className="space-y-6">
          <button
            onClick={() => setSelectedBranch(null)}
            className="flex items-center gap-2 text-[#9CA3AF] hover:text-white transition-colors text-sm font-medium"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back to Branches</span>
          </button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="w-12 h-12 rounded-xl bg-[#FF5500]/10 text-[#FF5500] font-bold text-lg flex items-center justify-center border border-[#FF5500]/30">
                {selectedBranch.code}
              </span>
              <div>
                <h2 className="text-2xl font-bold text-white">{selectedBranch.name}</h2>
                <p className="text-[#9CA3AF] text-sm">{orders.length} Total {orders.length === 1 ? 'Order' : 'Orders'}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button className="bg-[#1A1A1A] border border-[#262626] text-[#9CA3AF] hover:text-white px-4 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                <span>6 May 2025 - 6 May 2025</span>
              </button>
              <button className="bg-[#1A1A1A] border border-[#262626] text-[#9CA3AF] hover:text-white px-4 py-2.5 rounded-xl text-sm font-medium flex items-center gap-2">
                <Download className="w-4 h-4" />
                <span>Export</span>
              </button>
            </div>
          </div>

          {/* Orders Table */}
          <div className="bg-[#121212] border border-[#262626] rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[#1A1A1A] text-[#9CA3AF] uppercase text-xs font-semibold border-b border-[#262626]">
                  <tr>
                    <th className="px-6 py-4">Order ID</th>
                    <th className="px-6 py-4">Customer</th>
                    <th className="px-6 py-4">Items</th>
                    <th className="px-6 py-4">Amount</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Ordered On</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1F1F1F]">
                  {orders.length > 0 ? (
                    orders.map((o) => (
                      <tr key={o.id} className="hover:bg-[#1A1A1A] transition-colors">
                        <td className="px-6 py-4 font-bold text-[#FF5500]">{o.order_number}</td>
                        <td className="px-6 py-4 text-white font-medium">{o.customer_name}</td>
                        <td className="px-6 py-4 text-[#9CA3AF]">
                          {o.items.map((i) => `${i.product_name} (${i.quantity})`).join(', ') || 'Classic Beef Burger, French Fries'}
                        </td>
                        <td className="px-6 py-4 font-semibold text-white">£{o.total_amount.toFixed(2)}</td>
                        <td className="px-6 py-4">
                          <span
                            className={`px-2.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${
                              o.status === 'INCOMING'
                                ? 'bg-[#FF5A00]/15 text-[#FF5A00] border-[#FF5A00]/40'
                                : o.status === 'ACCEPTED'
                                ? 'bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40'
                                : o.status === 'PREPARING'
                                ? 'bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/40'
                                : o.status === 'READY'
                                ? 'bg-[#10B981]/15 text-[#10B981] border-[#10B981]/40'
                                : o.status === 'DELIVERED'
                                ? 'bg-[#22C55E]/15 text-[#22C55E] border-[#22C55E]/40'
                                : 'bg-[#151515] text-[#A1A1AA] border-[#242424]'
                            }`}
                          >
                            {o.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-[#9CA3AF]">{o.created_at ? new Date(o.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '10:15 AM'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-[#6B7280]">
                        No orders recorded for this branch yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {showCreateBranchModal && (
        <AdminCreateBranchModal
          onClose={() => setShowCreateBranchModal(false)}
          onSuccess={() => {
            fetchBranches();
            setShowCreateBranchModal(false);
          }}
        />
      )}

      {/* Delete Branch Confirmation Dialog Box */}
      {branchToDelete && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121212] border border-[#262626] rounded-2xl w-full max-w-md shadow-2xl p-6 relative">
            <div className="flex items-center gap-3 text-[#EF4444] mb-4">
              <div className="p-3 bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-xl">
                <AlertTriangle className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Delete Branch</h3>
                <p className="text-xs text-[#9CA3AF]">Confirm branch deletion</p>
              </div>
            </div>

            <p className="text-sm text-[#D1D5DB] leading-relaxed mb-6">
              Are you sure you want to delete <strong className="text-white">{branchToDelete.name}</strong> ({branchToDelete.code})? This will permanently remove the branch.
            </p>

            <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#262626]">
              <button
                onClick={() => setBranchToDelete(null)}
                disabled={deleting}
                className="px-4 py-2 bg-[#1A1A1A] hover:bg-[#262626] text-white rounded-xl text-xs font-semibold cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeleteBranch}
                disabled={deleting}
                className="px-5 py-2 bg-[#EF4444] hover:bg-[#DC2626] text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-[#EF4444]/20 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Trash2 className="w-4 h-4" />
                <span>{deleting ? 'Deleting...' : 'Delete Branch'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
