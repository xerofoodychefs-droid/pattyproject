import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronRight, ArrowLeft, Download, Calendar, Plus, Trash2, AlertTriangle, ExternalLink } from 'lucide-react';
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
        api.get<BranchStats[]>('/branches/stats').catch((err) => {
          console.warn('[AdminDashboard] /branches/stats fetch failed:', err?.message || err);
          return [];
        })
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
        navigate('/admin/login');
      } else {
        alert(errMsg || 'Failed to delete branch. Please try again.');
      }
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="w-full max-w-[1220px] mx-auto px-6 sm:px-8 py-8 space-y-6 text-[#F5F5F5]">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">Dashboard</h1>
          <p className="text-sm text-[#A1A1AA] font-normal mt-1">
            {user?.role === 'BRANCH_ADMIN' ? 'View and manage orders for your assigned branch.' : 'View and manage orders for each branch.'}
          </p>
        </div>
        {user?.role === 'SUPER_ADMIN' && (
          <button
            onClick={() => setShowCreateBranchModal(true)}
            className="h-10 px-4 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-sm transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Create Branch</span>
          </button>
        )}
      </div>

      {/* Main Branch Summary Table */}
      {!selectedBranch ? (
        <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
          <div className="p-5 border-b border-[#1C1C1C] flex items-center justify-between">
            <h2 className="text-base font-semibold text-[#F5F5F5]">All Branches Overview</h2>
            <span className="text-xs text-[#71717A] font-medium">{branches.length} Locations Total</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                <tr>
                  <th className="px-5 py-3.5">Branch Name</th>
                  <th className="px-5 py-3.5 text-center">Total Orders</th>
                  <th className="px-5 py-3.5 text-center">Completed Orders</th>
                  <th className="px-5 py-3.5 text-center">Cancelled Orders</th>
                  <th className="px-5 py-3.5 text-center">Pending Orders</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                {loading ? (
                  [...Array(3)].map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-32" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-12 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-12 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-12 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-12 mx-auto" /></td>
                      <td className="px-5 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-16 ml-auto" /></td>
                    </tr>
                  ))
                ) : branches.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-12 text-center text-[#71717A]">
                      No branches found. Click "Create Branch" to add your first outlet.
                    </td>
                  </tr>
                ) : (
                  branches.map((b) => {
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
                        className="hover:bg-[#121212] cursor-pointer transition-colors h-14"
                      >
                        <td className="px-5 py-3 flex items-center gap-3">
                          <span className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-semibold text-xs flex items-center justify-center shrink-0">
                            {b.code}
                          </span>
                          <div className="min-w-0">
                            <p className="font-semibold text-sm text-[#F5F5F5] truncate">{b.name}</p>
                            <p className="text-xs text-[#71717A] truncate">{b.address_line1}, {b.postcode}</p>
                          </div>
                        </td>
                        <td className="px-5 py-3 text-center font-semibold text-[#F5F5F5]">{stats.total_orders}</td>
                        <td className="px-5 py-3 text-center text-[#22C55E] font-semibold">{stats.completed_orders}</td>
                        <td className="px-5 py-3 text-center text-[#EF4444] font-semibold">{stats.cancelled_orders}</td>
                        <td className="px-5 py-3 text-center text-[#F59E0B] font-semibold">{stats.pending_orders}</td>
                        <td className="px-5 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-1.5">
                            {user?.role === 'SUPER_ADMIN' && (
                              <button
                                onClick={() => setBranchToDelete(b)}
                                title="Delete Branch"
                                aria-label="Delete branch"
                                className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] text-[#71717A] hover:text-[#EF4444] hover:border-[#EF4444]/40 hover:bg-[#EF4444]/10 flex items-center justify-center transition-colors cursor-pointer"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            )}
                            <button
                              onClick={() => handleSelectBranch(b)}
                              title="View Branch Orders"
                              aria-label="View branch orders"
                              className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#F5F5F5] hover:border-[#333333] flex items-center justify-center transition-colors cursor-pointer"
                            >
                              <ChevronRight className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Branch Detail Order View */
        <div className="space-y-6">
          <button
            onClick={() => setSelectedBranch(null)}
            className="flex items-center gap-1.5 text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors text-xs font-medium cursor-pointer"
          >
            <ArrowLeft className="w-4 h-4 text-[#FF5A00]" />
            <span>Back to All Branches</span>
          </button>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3.5">
              <span className="w-10 h-10 rounded-lg bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-bold text-sm flex items-center justify-center shrink-0">
                {selectedBranch.code}
              </span>
              <div>
                <h2 className="text-xl font-bold text-[#F5F5F5]">{selectedBranch.name}</h2>
                <p className="text-[#A1A1AA] text-xs">{orders.length} Total {orders.length === 1 ? 'Order' : 'Orders'} Recorded</p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              <button className="h-9 px-3.5 bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-2 transition-colors">
                <Calendar className="w-3.5 h-3.5 text-[#FF5A00]" />
                <span>Today</span>
              </button>
              <button className="h-9 px-3.5 bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-2 transition-colors">
                <Download className="w-3.5 h-3.5 text-[#FF5A00]" />
                <span>Export</span>
              </button>
            </div>
          </div>

          {/* Orders Table */}
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                  <tr>
                    <th className="px-5 py-3.5">Order ID</th>
                    <th className="px-5 py-3.5">Customer</th>
                    <th className="px-5 py-3.5">Items</th>
                    <th className="px-5 py-3.5">Amount</th>
                    <th className="px-5 py-3.5">Status</th>
                    <th className="px-5 py-3.5 text-right">Ordered On</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                  {orders.length > 0 ? (
                    orders.map((o) => (
                      <tr key={o.id} className="hover:bg-[#121212] transition-colors h-14">
                        <td className="px-5 py-3 font-semibold text-[#FF5A00]">{o.order_number}</td>
                        <td className="px-5 py-3 text-[#F5F5F5] font-medium">{o.customer_name}</td>
                        <td className="px-5 py-3 text-[#A1A1AA] max-w-xs truncate">
                          {o.items.map((i) => `${i.product_name} (x${i.quantity})`).join(', ') || 'Classic Beef Burger, French Fries'}
                        </td>
                        <td className="px-5 py-3 font-semibold text-[#F5F5F5]">£{o.total_amount.toFixed(2)}</td>
                        <td className="px-5 py-3">
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
                        <td className="px-5 py-3 text-right text-[#71717A]">{o.created_at ? new Date(o.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '10:15 AM'}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={6} className="px-5 py-12 text-center text-[#71717A]">
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

      {/* Create Branch Modal */}
      {showCreateBranchModal && (
        <AdminCreateBranchModal
          onClose={() => setShowCreateBranchModal(false)}
          onSuccess={() => {
            fetchBranches();
            setShowCreateBranchModal(false);
          }}
        />
      )}

      {/* Delete Branch Dialog */}
      {branchToDelete && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl w-full max-w-md shadow-2xl p-6 relative text-[#F5F5F5] space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-[#EF4444]/10 border border-[#EF4444]/30 flex items-center justify-center text-[#EF4444] shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-semibold text-[#F5F5F5]">Delete Branch</h3>
                <p className="text-xs text-[#A1A1AA]">Confirm branch deletion</p>
              </div>
            </div>

            <p className="text-xs text-[#A1A1AA] leading-relaxed">
              Are you sure you want to delete <strong className="text-[#F5F5F5]">{branchToDelete.name}</strong> ({branchToDelete.code})? This will permanently remove the branch.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-[#1C1C1C]">
              <button
                onClick={() => setBranchToDelete(null)}
                disabled={deleting}
                className="h-9 px-4 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDeleteBranch}
                disabled={deleting}
                className="h-9 px-4 bg-[#EF4444] hover:bg-[#DC2626] text-white rounded-lg text-xs font-semibold transition-colors shadow-sm flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{deleting ? 'Deleting...' : 'Delete Branch'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
