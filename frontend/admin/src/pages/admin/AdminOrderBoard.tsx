import React, { useEffect, useState, useCallback } from 'react';
import { Search, RefreshCw, Eye, Truck, ShoppingBag, ChefHat, ClipboardCheck, CheckCircle, ArrowRight, Inbox } from 'lucide-react';
import { api } from '../../api/client';
import { Order, Branch } from '../../types';
import { useAuthStore } from '../../store/authStore';
import { AdminOrderDetailsModal } from './AdminOrderDetailsModal';

export const AdminOrderBoard: React.FC = () => {
  const { user } = useAuthStore();
  const [orders, setOrders] = useState<Order[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [filterBranch, setFilterBranch] = useState(
    user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids[0] ? user.branch_ids[0] : 'ALL'
  );
  const [filterStatus, setFilterStatus] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [updatingOrderId, setUpdatingOrderId] = useState<string | null>(null);

  const fetchBranches = useCallback(async () => {
    try {
      const data: Branch[] = await api.get('/branches');
      let filtered = data || [];
      if (user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids.length > 0) {
        filtered = filtered.filter((b) => user.branch_ids.includes(b.id));
      }
      setBranches(filtered);
    } catch (err) {
      console.error('Failed to load branches', err);
    }
  }, [user]);

  const fetchOrders = useCallback(async (isSilent = false) => {
    if (!isSilent) setLoading(true);
    try {
      let url = '/orders';
      const params = [];
      if (user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids[0]) {
        params.push(`branch_id=${user.branch_ids[0]}`);
      } else if (filterBranch !== 'ALL') {
        params.push(`branch_id=${filterBranch}`);
      }
      if (filterStatus !== 'ALL') params.push(`status=${filterStatus}`);
      if (params.length) url += `?${params.join('&')}`;

      const data: Order[] = await api.get(url);
      if (Array.isArray(data)) {
        setOrders(data);
      }
    } catch (err) {
      console.error('Failed to load orders', err);
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [filterBranch, filterStatus, user]);

  useEffect(() => {
    fetchBranches();
  }, [fetchBranches]);

  useEffect(() => {
    fetchOrders(false);
    // Realtime authoritative polling synchronization every 5 seconds
    const interval = setInterval(() => {
      fetchOrders(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchOrders]);

  useEffect(() => {
    if (selectedOrder) {
      const currentInList = orders.find((o) => o.id === selectedOrder.id);
      if (currentInList && currentInList.status !== selectedOrder.status) {
        setSelectedOrder(currentInList);
      }
    }
  }, [orders, selectedOrder]);

  const handleQuickStatusChange = async (orderId: string, newStatus: string) => {
    setUpdatingOrderId(orderId);
    try {
      await api.patch(`/orders/${orderId}/status`, { status: newStatus });
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? { ...o, status: newStatus } : o))
      );
    } catch (err: any) {
      console.error('Failed to update status', err);
      const detailMsg =
        (typeof err?.detail === 'string' ? err.detail : '') ||
        (typeof err?.detail === 'object' && err.detail ? (err.detail.message || err.detail.error || err.detail.msg) : '') ||
        err?.message ||
        'Failed to update order status. Please try again.';
      alert(detailMsg);
    } finally {
      setUpdatingOrderId(null);
    }
  };

  const getNextStatus = (currentStatus: string) => {
    switch (currentStatus) {
      case 'INCOMING':
      case 'PENDING_PAYMENT':
      case 'PAID':
        return { label: 'Accept', status: 'ACCEPTED', color: 'bg-[#06B6D4] hover:bg-[#0891B2] text-white' };
      case 'ACCEPTED':
        return { label: 'Prepare', status: 'PREPARING', color: 'bg-[#F59E0B] hover:bg-[#D97706] text-black font-bold' };
      case 'PREPARING':
        return { label: 'Ready', status: 'READY', color: 'bg-[#10B981] hover:bg-[#059669] text-white' };
      case 'READY':
      case 'OUT_FOR_DELIVERY':
        return { label: 'Delivered', status: 'DELIVERED', color: 'bg-[#22C55E] hover:bg-[#16A34A] text-white' };
      default:
        return null;
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'INCOMING':
      case 'PENDING_PAYMENT':
        return 'bg-[#FF5A00]/15 text-[#FF5A00] border-[#FF5A00]/40';
      case 'ACCEPTED':
        return 'bg-[#06B6D4]/15 text-[#06B6D4] border-[#06B6D4]/40';
      case 'PREPARING':
        return 'bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/40';
      case 'READY':
        return 'bg-[#10B981]/15 text-[#10B981] border-[#10B981]/40';
      case 'OUT_FOR_DELIVERY':
        return 'bg-[#8B5CF6]/15 text-[#8B5CF6] border-[#8B5CF6]/40';
      case 'DELIVERED':
      case 'COLLECTED':
        return 'bg-[#22C55E]/15 text-[#22C55E] border-[#22C55E]/40';
      case 'CANCELLED':
      case 'REJECTED':
        return 'bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/40';
      default:
        return 'bg-[#241209] text-[#FF5A00] border-[#6B2A0D]';
    }
  };

  // Metrics count
  const incomingCount = orders.filter((o) => o.status === 'INCOMING' || o.status === 'PENDING_PAYMENT' || o.status === 'PAID').length;
  const acceptedCount = orders.filter((o) => o.status === 'ACCEPTED').length;
  const preparingCount = orders.filter((o) => o.status === 'PREPARING').length;
  const readyCount = orders.filter((o) => o.status === 'READY' || o.status === 'OUT_FOR_DELIVERY').length;
  const deliveredCount = orders.filter((o) => o.status === 'DELIVERED' || o.status === 'COLLECTED').length;

  // Filter local search
  const filteredOrders = orders.filter(
    (o) =>
      o.order_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.customer_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.customer_phone.includes(searchQuery)
  );

  return (
    <div className="w-full max-w-[1260px] mx-auto px-6 sm:px-8 py-8 space-y-6 text-[#F5F5F5]">
      {/* Header Bar & Top Toolbar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">Order Management</h1>
          <p className="text-sm text-[#A1A1AA] font-normal mt-1">
            Track and update orders through Incoming, Accepted, Preparing, Ready, and Delivered stages.
          </p>
        </div>

        {/* Top Controls Toolbar */}
        <div className="flex items-center gap-2.5">
          <div className="relative w-64 sm:w-72">
            <Search className="w-4 h-4 absolute left-3 top-3 text-[#71717A]" />
            <input
              type="text"
              placeholder="Search by order ID, customer..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] rounded-lg py-2 pl-9 pr-3.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
            />
          </div>

          <button
            onClick={() => fetchOrders(false)}
            className="h-10 px-3.5 bg-[#151515] border border-[#242424] hover:border-[#333333] rounded-lg text-xs font-medium text-[#A1A1AA] hover:text-[#F5F5F5] flex items-center gap-2 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-[#FF5A00]' : 'text-[#FF5A00]'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Operational Status Summary Cards (5 lifecycle stages) */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* Incoming Card */}
        <div
          onClick={() => setFilterStatus(filterStatus === 'INCOMING' ? 'ALL' : 'INCOMING')}
          className={`bg-[#0D0D0D] border p-3.5 rounded-xl flex items-center gap-3.5 shadow-sm cursor-pointer transition-all ${
            filterStatus === 'INCOMING' ? 'border-[#FF5A00] ring-1 ring-[#FF5A00]' : 'border-[#242424] hover:border-[#333]'
          }`}
        >
          <div className="w-9 h-9 rounded-lg bg-[#FF5A00]/15 border border-[#FF5A00]/30 flex items-center justify-center text-[#FF5A00] shrink-0">
            <Inbox className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-[#A1A1AA]">Incoming</p>
            <h3 className="text-xl font-bold text-[#FF5A00] leading-tight">{incomingCount}</h3>
          </div>
        </div>

        {/* Accepted Card */}
        <div
          onClick={() => setFilterStatus(filterStatus === 'ACCEPTED' ? 'ALL' : 'ACCEPTED')}
          className={`bg-[#0D0D0D] border p-3.5 rounded-xl flex items-center gap-3.5 shadow-sm cursor-pointer transition-all ${
            filterStatus === 'ACCEPTED' ? 'border-[#06B6D4] ring-1 ring-[#06B6D4]' : 'border-[#242424] hover:border-[#333]'
          }`}
        >
          <div className="w-9 h-9 rounded-lg bg-[#06B6D4]/15 border border-[#06B6D4]/30 flex items-center justify-center text-[#06B6D4] shrink-0">
            <ClipboardCheck className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-[#A1A1AA]">Accepted</p>
            <h3 className="text-xl font-bold text-[#06B6D4] leading-tight">{acceptedCount}</h3>
          </div>
        </div>

        {/* Preparing Card */}
        <div
          onClick={() => setFilterStatus(filterStatus === 'PREPARING' ? 'ALL' : 'PREPARING')}
          className={`bg-[#0D0D0D] border p-3.5 rounded-xl flex items-center gap-3.5 shadow-sm cursor-pointer transition-all ${
            filterStatus === 'PREPARING' ? 'border-[#F59E0B] ring-1 ring-[#F59E0B]' : 'border-[#242424] hover:border-[#333]'
          }`}
        >
          <div className="w-9 h-9 rounded-lg bg-[#F59E0B]/15 border border-[#F59E0B]/30 flex items-center justify-center text-[#F59E0B] shrink-0">
            <ChefHat className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-[#A1A1AA]">Preparing</p>
            <h3 className="text-xl font-bold text-[#F59E0B] leading-tight">{preparingCount}</h3>
          </div>
        </div>

        {/* Ready Card */}
        <div
          onClick={() => setFilterStatus(filterStatus === 'READY' ? 'ALL' : 'READY')}
          className={`bg-[#0D0D0D] border p-3.5 rounded-xl flex items-center gap-3.5 shadow-sm cursor-pointer transition-all ${
            filterStatus === 'READY' ? 'border-[#10B981] ring-1 ring-[#10B981]' : 'border-[#242424] hover:border-[#333]'
          }`}
        >
          <div className="w-9 h-9 rounded-lg bg-[#10B981]/15 border border-[#10B981]/30 flex items-center justify-center text-[#10B981] shrink-0">
            <ShoppingBag className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-[#A1A1AA]">Ready</p>
            <h3 className="text-xl font-bold text-[#10B981] leading-tight">{readyCount}</h3>
          </div>
        </div>

        {/* Delivered Card */}
        <div
          onClick={() => setFilterStatus(filterStatus === 'DELIVERED' ? 'ALL' : 'DELIVERED')}
          className={`bg-[#0D0D0D] border p-3.5 rounded-xl flex items-center gap-3.5 shadow-sm cursor-pointer transition-all ${
            filterStatus === 'DELIVERED' ? 'border-[#22C55E] ring-1 ring-[#22C55E]' : 'border-[#242424] hover:border-[#333]'
          }`}
        >
          <div className="w-9 h-9 rounded-lg bg-[#22C55E]/15 border border-[#22C55E]/30 flex items-center justify-center text-[#22C55E] shrink-0">
            <CheckCircle className="w-4.5 h-4.5" />
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-[#A1A1AA]">Delivered</p>
            <h3 className="text-xl font-bold text-[#22C55E] leading-tight">{deliveredCount}</h3>
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-[#0D0D0D] border border-[#242424] p-3.5 rounded-xl">
        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={filterBranch}
            onChange={(e) => setFilterBranch(e.target.value)}
            disabled={user?.role === 'BRANCH_ADMIN'}
            className="h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] text-[#F5F5F5] text-xs font-semibold px-3.5 rounded-lg focus:outline-none cursor-pointer transition-colors disabled:opacity-75 disabled:cursor-not-allowed"
          >
            {user?.role !== 'BRANCH_ADMIN' && <option value="ALL">All Branches</option>}
            {branches.map((b) => (
              <option key={b.id} value={b.id}>{b.name}</option>
            ))}
          </select>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="h-10 bg-[#151515] border border-[#242424] focus:border-[#FF5A00] text-[#F5F5F5] text-xs font-semibold px-3.5 rounded-lg focus:outline-none cursor-pointer transition-colors"
          >
            <option value="ALL">All Statuses</option>
            <option value="INCOMING">Incoming</option>
            <option value="ACCEPTED">Accepted</option>
            <option value="PREPARING">Preparing</option>
            <option value="READY">Ready</option>
            <option value="OUT_FOR_DELIVERY">Out for Delivery</option>
            <option value="DELIVERED">Delivered</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="text-xs text-[#A1A1AA]">
          Showing <span className="font-bold text-white">{filteredOrders.length}</span> orders
        </div>
      </div>

      {/* Orders Data Table */}
      <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="bg-[#171717] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
              <tr>
                <th className="px-4 py-3.5">Order ID</th>
                <th className="px-4 py-3.5">Customer</th>
                <th className="px-4 py-3.5">Type</th>
                <th className="px-4 py-3.5">Items</th>
                <th className="px-4 py-3.5 text-right">Amount</th>
                <th className="px-4 py-3.5 text-center">Payment</th>
                <th className="px-4 py-3.5">Time</th>
                <th className="px-4 py-3.5 text-center">Change Status</th>
                <th className="px-4 py-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
              {loading ? (
                [...Array(4)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                    <td className="px-4 py-4"><div className="h-4 bg-[#151515] rounded w-28" /></td>
                    <td className="px-4 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                    <td className="px-4 py-4"><div className="h-4 bg-[#151515] rounded w-16" /></td>
                    <td className="px-4 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-16 ml-auto" /></td>
                    <td className="px-4 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-12 mx-auto" /></td>
                    <td className="px-4 py-4"><div className="h-4 bg-[#151515] rounded w-16" /></td>
                    <td className="px-4 py-4 text-center"><div className="h-4 bg-[#151515] rounded w-24 mx-auto" /></td>
                    <td className="px-4 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-16 ml-auto" /></td>
                  </tr>
                ))
              ) : filteredOrders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-5 py-12 text-center text-[#71717A]">
                    No orders matching the active criteria.
                  </td>
                </tr>
              ) : (
                filteredOrders.map((o) => {
                  const nextAction = getNextStatus(o.status);
                  const isUpdating = updatingOrderId === o.id;

                  return (
                    <tr key={o.id} className="hover:bg-[#121212] transition-colors h-14">
                      <td className="px-4 py-3 font-bold text-[#FF5A00]">{o.order_number}</td>
                      <td className="px-4 py-3">
                        <p className="font-semibold text-[#F5F5F5]">{o.customer_name}</p>
                        <p className="text-[11px] text-[#71717A]">{o.customer_phone}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center gap-1.5 text-[#F5F5F5] font-medium">
                          {o.order_type === 'DELIVERY' ? <Truck className="w-3.5 h-3.5 text-[#FF5A00]" /> : <ShoppingBag className="w-3.5 h-3.5 text-[#06B6D4]" />}
                          <span>{o.order_type}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[#A1A1AA]">
                        {o.items.length > 0 ? `${o.items.length} items` : '1 item'}
                      </td>
                      <td className="px-4 py-3 text-right font-bold text-[#F5F5F5]">£{o.total_amount.toFixed(2)}</td>
                      <td className="px-4 py-3 text-center">
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30">
                          {o.payment_status || 'Paid'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[#A1A1AA]">
                        {o.created_at ? new Date(o.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Just now'}
                      </td>
                      
                      {/* Direct Inline Status Dropdown */}
                      <td className="px-4 py-3 text-center">
                        <select
                          value={o.status}
                          disabled={isUpdating}
                          onChange={(e) => handleQuickStatusChange(o.id, e.target.value)}
                          className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider border cursor-pointer focus:outline-none transition-all ${getStatusBadgeClass(o.status)}`}
                        >
                          <option value="INCOMING" className="bg-[#151515] text-[#FF5A00]">Incoming</option>
                          <option value="ACCEPTED" className="bg-[#151515] text-[#06B6D4]">Accepted</option>
                          <option value="PREPARING" className="bg-[#151515] text-[#F59E0B]">Preparing</option>
                          <option value="READY" className="bg-[#151515] text-[#10B981]">Ready</option>
                          <option value="OUT_FOR_DELIVERY" className="bg-[#151515] text-[#8B5CF6]">Out for Delivery</option>
                          <option value="DELIVERED" className="bg-[#151515] text-[#22C55E]">Delivered</option>
                          <option value="CANCELLED" className="bg-[#151515] text-[#EF4444]">Cancelled</option>
                        </select>
                      </td>

                      {/* Actions: Next Step Button + View Details */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {nextAction && (
                            <button
                              onClick={() => handleQuickStatusChange(o.id, nextAction.status)}
                              disabled={isUpdating}
                              className={`px-2.5 py-1 rounded-md text-[11px] font-bold transition-colors cursor-pointer flex items-center gap-1 shadow-sm ${nextAction.color}`}
                              title={`Advance status to ${nextAction.status}`}
                            >
                              <span>{nextAction.label}</span>
                              <ArrowRight className="w-3 h-3" />
                            </button>
                          )}

                          <button
                            onClick={() => setSelectedOrder(o)}
                            className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#F5F5F5] hover:border-[#333333] inline-flex items-center justify-center transition-colors cursor-pointer"
                            title="View Full Order Details"
                            aria-label="View order details"
                          >
                            <Eye className="w-4 h-4" />
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

      {/* Order Details Modal Trigger */}
      {selectedOrder && (
        <AdminOrderDetailsModal
          order={selectedOrder}
          onClose={() => setSelectedOrder(null)}
          onUpdateStatus={() => {
            fetchOrders();
            setSelectedOrder(null);
          }}
        />
      )}
    </div>
  );
};
