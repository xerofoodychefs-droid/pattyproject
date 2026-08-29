import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronRight,
  ArrowLeft,
  Download,
  Plus,
  Trash2,
  AlertTriangle,
  Search,
  Truck,
  ShoppingBag,
  Eye,
  CheckCircle2,
  Clock,
  XCircle,
  TrendingUp
} from 'lucide-react';
import { api } from '../../api/client';
import { Branch, Order, BranchStats } from '../../types';
import { useAuthStore } from '../../store/authStore';
import { AdminCreateBranchModal } from './AdminCreateBranchModal';
import { AdminOrderDetailsModal } from './AdminOrderDetailsModal';

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchStats, setBranchStats] = useState<Record<string, BranchStats>>({});
  const [selectedBranch, setSelectedBranch] = useState<Branch | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showCreateBranchModal, setShowCreateBranchModal] = useState(false);
  const [branchToDelete, setBranchToDelete] = useState<Branch | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Order Details Modal & Filters
  const [selectedOrderForModal, setSelectedOrderForModal] = useState<Order | null>(null);
  const [orderSearchQuery, setOrderSearchQuery] = useState('');
  const [orderStatusFilter, setOrderStatusFilter] = useState<string>('ALL');

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
      const timestamp = Date.now();
      const [branchData, statsData] = await Promise.all([
        api.get<Branch[]>(`/branches?_t=${timestamp}`),
        api.get<BranchStats[]>(`/branches/stats?_t=${timestamp}`).catch((err) => {
          console.warn('[AdminDashboard] /branches/stats fetch failed:', err?.message || err);
          return [];
        })
      ]);
      let filtered = branchData || [];
      if (user?.role === 'BRANCH_ADMIN') {
        const allowedIds = user.branch_ids || [];
        filtered = filtered.filter((b) => allowedIds.includes(b.id));
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

  const fetchBranchOrders = async (branchId: string) => {
    setOrdersLoading(true);
    try {
      const branchOrders: Order[] = await api.get(`/orders?branch_id=${branchId}&_t=${Date.now()}`);
      setOrders(branchOrders || []);
    } catch (err) {
      console.error('Failed to fetch branch orders:', err);
    } finally {
      setOrdersLoading(false);
    }
  };

  const handleSelectBranch = async (branch: Branch) => {
    setSelectedBranch(branch);
    setOrderSearchQuery('');
    setOrderStatusFilter('ALL');
    await fetchBranchOrders(branch.id);
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
        navigate('/admin');
      } else {
        alert(errMsg || 'Failed to delete branch. Please try again.');
      }
    } finally {
      setDeleting(false);
    }
  };

  // Export branch orders to CSV
  const handleExportCSV = () => {
    if (!selectedBranch || orders.length === 0) return;

    const headers = ['Order Number', 'Date', 'Customer Name', 'Phone', 'Type', 'Status', 'Payment Status', 'Total Amount (£)', 'Items'];
    const rows = orders.map((o) => [
      o.order_number,
      o.created_at ? new Date(o.created_at).toLocaleString() : '',
      `"${o.customer_name || ''}"`,
      `"${o.customer_phone || ''}"`,
      o.order_type,
      o.status,
      o.payment_status || 'PENDING',
      o.total_amount.toFixed(2),
      `"${(o.items || []).map((i) => `${i.product_name} x${i.quantity}`).join('; ')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${selectedBranch.name.replace(/\s+/g, '_')}_Orders_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Filtered orders for the selected branch
  const filteredOrders = orders.filter((o) => {
    const matchesSearch =
      !orderSearchQuery ||
      o.order_number.toLowerCase().includes(orderSearchQuery.toLowerCase()) ||
      o.customer_name.toLowerCase().includes(orderSearchQuery.toLowerCase()) ||
      (o.customer_phone && o.customer_phone.includes(orderSearchQuery));

    const matchesStatus = orderStatusFilter === 'ALL' || o.status === orderStatusFilter;

    return matchesSearch && matchesStatus;
  });

  return (
    <div className="w-full max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 text-[#F5F5F5]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F5F5F5] tracking-tight">Dashboard</h1>
          <p className="text-xs sm:text-sm text-[#A1A1AA] font-normal mt-1">
            {user?.role === 'BRANCH_ADMIN' ? 'View and manage live orders for your assigned branch.' : 'Overview performance and manage orders across all branch locations.'}
          </p>
        </div>
        {user?.role === 'SUPER_ADMIN' && !selectedBranch && (
          <button
            onClick={() => setShowCreateBranchModal(true)}
            className="h-10 px-4 bg-[#FF5A00] hover:bg-[#E84F00] text-white rounded-lg text-xs font-semibold flex items-center gap-2 shadow-sm transition-colors cursor-pointer self-start sm:self-auto"
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
            <div>
              <h2 className="text-base font-semibold text-[#F5F5F5]">All Branches Overview</h2>
              <p className="text-xs text-[#71717A] mt-0.5">Click any branch to view detailed orders and order management</p>
            </div>
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => fetchBranches(false)}
                className="h-8 px-3 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <TrendingUp className={`w-3.5 h-3.5 text-[#FF5A00] ${loading ? 'animate-spin' : ''}`} />
                <span>Refresh Stats</span>
              </button>
              <span className="text-xs text-[#A1A1AA] bg-[#171717] px-3 py-1.5 rounded-lg border border-[#242424] font-medium">
                {branches.length} {branches.length === 1 ? 'Location' : 'Locations'} Total
              </span>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse table-fixed min-w-[760px]">
              <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                <tr>
                  <th className="w-[30%] px-5 py-3.5">Branch Name</th>
                  <th className="w-[14%] px-5 py-3.5 text-center">Total Orders</th>
                  <th className="w-[14%] px-5 py-3.5 text-center">Completed Orders</th>
                  <th className="w-[14%] px-5 py-3.5 text-center">Cancelled Orders</th>
                  <th className="w-[14%] px-5 py-3.5 text-center">Pending Orders</th>
                  <th className="w-[14%] px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                {loading ? (
                  [...Array(3)].map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-36" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded-full w-14 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded-full w-14 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded-full w-14 mx-auto" /></td>
                      <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded-full w-14 mx-auto" /></td>
                      <td className="px-5 py-4 text-right"><div className="h-7 bg-[#151515] rounded w-16 ml-auto" /></td>
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
                        className="hover:bg-[#141414] cursor-pointer transition-colors group"
                      >
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-3">
                            <span className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-bold text-xs flex items-center justify-center shrink-0 shadow-sm">
                              {b.code}
                            </span>
                            <div className="min-w-0">
                              <p className="font-semibold text-sm text-[#F5F5F5] group-hover:text-[#FF5A00] transition-colors truncate">
                                {b.name}
                              </p>
                              <p className="text-xs text-[#71717A] truncate">
                                {b.address_line1 ? `${b.address_line1}, ` : ''}{b.postcode}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-5 py-4 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold bg-[#1C1C1C] text-[#F5F5F5] border border-[#2A2A2A] min-w-[48px]">
                            {stats.total_orders}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30 min-w-[48px]">
                            {stats.completed_orders}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/30 min-w-[48px]">
                            {stats.cancelled_orders}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold bg-[#F59E0B]/10 text-[#F59E0B] border border-[#F59E0B]/30 min-w-[48px]">
                            {stats.pending_orders}
                          </span>
                        </td>
                        <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
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
                              className="h-8 px-2.5 rounded-lg bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#FF5A00] hover:border-[#FF5A00]/40 flex items-center gap-1 text-xs font-medium transition-colors cursor-pointer"
                            >
                              <span>View</span>
                              <ChevronRight className="w-3.5 h-3.5" />
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
          {/* Back Navigation & Branch Info Card */}
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-5 space-y-4">
            <button
              onClick={() => setSelectedBranch(null)}
              className="inline-flex items-center gap-1.5 text-[#A1A1AA] hover:text-[#F5F5F5] transition-colors text-xs font-semibold cursor-pointer pb-2 border-b border-[#1C1C1C] w-full"
            >
              <ArrowLeft className="w-4 h-4 text-[#FF5A00]" />
              <span>Back to All Branches</span>
            </button>

            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pt-1">
              <div className="flex items-center gap-3.5">
                <span className="w-12 h-12 rounded-xl bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-bold text-base flex items-center justify-center shrink-0 shadow-sm">
                  {selectedBranch.code}
                </span>
                <div>
                  <h2 className="text-xl font-bold text-[#F5F5F5] flex items-center gap-2">
                    <span>{selectedBranch.name}</span>
                    <span className="text-xs font-normal text-[#A1A1AA] px-2 py-0.5 bg-[#171717] border border-[#242424] rounded-full">
                      {selectedBranch.postcode}
                    </span>
                  </h2>
                  <p className="text-[#71717A] text-xs mt-0.5">
                    {selectedBranch.address_line1}, {selectedBranch.city || 'London'} • Phone: {selectedBranch.phone || '020 7946 0000'}
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2.5 self-start md:self-auto">
                <button
                  onClick={() => fetchBranchOrders(selectedBranch.id)}
                  className="h-9 px-3.5 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <TrendingUp className="w-3.5 h-3.5 text-[#FF5A00]" />
                  <span>Refresh</span>
                </button>
                <button
                  onClick={handleExportCSV}
                  disabled={orders.length === 0}
                  className="h-9 px-3.5 bg-[#151515] border border-[#242424] hover:border-[#333333] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Download className="w-3.5 h-3.5 text-[#FF5A00]" />
                  <span>Export CSV</span>
                </button>
              </div>
            </div>

            {/* Quick Stats Pill Summary */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <div className="bg-[#141414] border border-[#1F1F1F] rounded-lg p-3">
                <p className="text-[11px] text-[#71717A] uppercase font-semibold">Total Orders</p>
                <p className="text-lg font-bold text-[#F5F5F5] mt-0.5">{orders.length}</p>
              </div>
              <div className="bg-[#141414] border border-[#1F1F1F] rounded-lg p-3">
                <p className="text-[11px] text-[#22C55E] uppercase font-semibold">Completed</p>
                <p className="text-lg font-bold text-[#22C55E] mt-0.5">
                  {orders.filter((o) => o.status === 'DELIVERED' || o.status === 'READY').length}
                </p>
              </div>
              <div className="bg-[#141414] border border-[#1F1F1F] rounded-lg p-3">
                <p className="text-[11px] text-[#F59E0B] uppercase font-semibold">In Progress</p>
                <p className="text-lg font-bold text-[#F59E0B] mt-0.5">
                  {orders.filter((o) => ['INCOMING', 'ACCEPTED', 'PREPARING'].includes(o.status)).length}
                </p>
              </div>
              <div className="bg-[#141414] border border-[#1F1F1F] rounded-lg p-3">
                <p className="text-[11px] text-[#EF4444] uppercase font-semibold">Cancelled</p>
                <p className="text-lg font-bold text-[#EF4444] mt-0.5">
                  {orders.filter((o) => o.status === 'CANCELLED').length}
                </p>
              </div>
            </div>
          </div>

          {/* Search and Filters */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-[#0D0D0D] border border-[#242424] rounded-xl p-3.5">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
              <input
                type="text"
                value={orderSearchQuery}
                onChange={(e) => setOrderSearchQuery(e.target.value)}
                placeholder="Search by order #, customer name or phone..."
                className="w-full bg-[#141414] border border-[#242424] focus:border-[#FF5A00] rounded-lg pl-9 pr-4 py-2 text-xs text-[#F5F5F5] placeholder-[#71717A] outline-none transition-colors"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={orderStatusFilter}
                onChange={(e) => setOrderStatusFilter(e.target.value)}
                className="bg-[#141414] border border-[#242424] focus:border-[#FF5A00] rounded-lg px-3 py-2 text-xs text-[#F5F5F5] outline-none transition-colors cursor-pointer"
              >
                <option value="ALL">All Statuses ({orders.length})</option>
                <option value="INCOMING">Incoming</option>
                <option value="ACCEPTED">Accepted</option>
                <option value="PREPARING">Preparing</option>
                <option value="READY">Ready</option>
                <option value="DELIVERED">Delivered</option>
                <option value="CANCELLED">Cancelled</option>
              </select>
            </div>
          </div>

          {/* Orders Table */}
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse table-fixed min-w-[840px]">
                <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                  <tr>
                    <th className="w-[14%] px-5 py-3.5">Order ID</th>
                    <th className="w-[18%] px-5 py-3.5">Customer</th>
                    <th className="w-[12%] px-5 py-3.5 text-center">Type</th>
                    <th className="w-[24%] px-5 py-3.5">Items Summary</th>
                    <th className="w-[10%] px-5 py-3.5 text-right">Amount</th>
                    <th className="w-[12%] px-5 py-3.5 text-center">Status</th>
                    <th className="w-[10%] px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                  {ordersLoading ? (
                    [...Array(4)].map((_, i) => (
                      <tr key={i} className="animate-pulse">
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-28" /></td>
                        <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded w-16 mx-auto" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-44" /></td>
                        <td className="px-5 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-12 ml-auto" /></td>
                        <td className="px-5 py-4 text-center"><div className="h-5 bg-[#151515] rounded w-20 mx-auto" /></td>
                        <td className="px-5 py-4 text-right"><div className="h-7 bg-[#151515] rounded w-14 ml-auto" /></td>
                      </tr>
                    ))
                  ) : filteredOrders.length > 0 ? (
                    filteredOrders.map((o) => {
                      const itemsSummary = (o.items || [])
                        .map((i) => `${i.product_name || 'Product'} (x${i.quantity})`)
                        .join(', ');

                      return (
                        <tr
                          key={o.id}
                          onClick={() => setSelectedOrderForModal(o)}
                          className="hover:bg-[#141414] cursor-pointer transition-colors group"
                        >
                          {/* Order Number */}
                          <td className="px-5 py-4 font-semibold text-[#FF5A00] group-hover:underline">
                            {o.order_number}
                            <p className="text-[10px] text-[#71717A] font-normal mt-0.5">
                              {o.created_at ? new Date(o.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                            </p>
                          </td>

                          {/* Customer */}
                          <td className="px-5 py-4">
                            <p className="text-[#F5F5F5] font-medium truncate">{o.customer_name || 'Guest'}</p>
                            <p className="text-[11px] text-[#71717A] truncate">{o.customer_phone || o.customer_email || 'No contact'}</p>
                          </td>

                          {/* Order Type */}
                          <td className="px-5 py-4 text-center">
                            <span
                              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border ${
                                o.order_type === 'DELIVERY'
                                  ? 'bg-[#3B82F6]/10 text-[#60A5FA] border-[#3B82F6]/30'
                                  : 'bg-[#F59E0B]/10 text-[#FBBF24] border-[#F59E0B]/30'
                              }`}
                            >
                              {o.order_type === 'DELIVERY' ? <Truck className="w-3 h-3" /> : <ShoppingBag className="w-3 h-3" />}
                              <span>{o.order_type}</span>
                            </span>
                          </td>

                          {/* Items */}
                          <td className="px-5 py-4 text-[#A1A1AA]">
                            <p className="truncate text-xs text-[#D4D4D8]" title={itemsSummary}>
                              {itemsSummary || 'No items listed'}
                            </p>
                            <p className="text-[10px] text-[#71717A]">
                              {(o.items || []).reduce((acc, curr) => acc + (curr.quantity || 1), 0)} {(o.items || []).reduce((acc, curr) => acc + (curr.quantity || 1), 0) === 1 ? 'item' : 'items'} total
                            </p>
                          </td>

                          {/* Amount */}
                          <td className="px-5 py-4 text-right font-semibold text-[#F5F5F5]">
                            £{o.total_amount.toFixed(2)}
                            {o.payment_status && (
                              <p className={`text-[10px] font-normal ${o.payment_status === 'PAID' ? 'text-[#22C55E]' : 'text-[#F59E0B]'}`}>
                                {o.payment_status}
                              </p>
                            )}
                          </td>

                          {/* Status */}
                          <td className="px-5 py-4 text-center">
                            <span
                              className={`inline-block px-2.5 py-1 rounded text-[10px] font-semibold uppercase tracking-wider border ${
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

                          {/* Action Button */}
                          <td className="px-5 py-4 text-right" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => setSelectedOrderForModal(o)}
                              title="View full order details"
                              className="h-8 px-2.5 rounded-lg bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#FF5A00] hover:border-[#FF5A00]/40 inline-flex items-center gap-1 text-xs font-medium transition-colors cursor-pointer"
                            >
                              <Eye className="w-3.5 h-3.5" />
                              <span>Details</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={7} className="px-5 py-12 text-center text-[#71717A]">
                        {orderSearchQuery || orderStatusFilter !== 'ALL'
                          ? 'No orders match the selected filters.'
                          : 'No orders recorded for this branch yet.'}
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

      {/* Order Details Modal */}
      {selectedOrderForModal && (
        <AdminOrderDetailsModal
          order={selectedOrderForModal}
          onClose={() => setSelectedOrderForModal(null)}
          onUpdateStatus={async () => {
            if (selectedBranch) {
              await fetchBranchOrders(selectedBranch.id);
            }
            fetchBranches(true);
            setSelectedOrderForModal(null);
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
