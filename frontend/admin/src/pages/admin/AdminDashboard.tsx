import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronRight,
  ArrowLeft,
  Download,
  Calendar,
  Plus,
  Trash2,
  AlertTriangle,
  ExternalLink,
  Search,
  Filter,
  ShoppingBag,
  Bike,
  Eye,
  Clock,
  CheckCircle2,
  XCircle,
  TrendingUp,
  RefreshCw
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
  const [selectedOrderForModal, setSelectedOrderForModal] = useState<Order | null>(null);

  // Filters for selected branch orders
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED'>('ALL');
  const [typeFilter, setTypeFilter] = useState<'ALL' | 'DELIVERY' | 'COLLECTION'>('ALL');
  const [dateFilter, setDateFilter] = useState<'ALL' | 'TODAY' | 'WEEK'>('ALL');

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
    setOrdersLoading(true);
    setSearchTerm('');
    setStatusFilter('ALL');
    setTypeFilter('ALL');
    setDateFilter('ALL');
    try {
      const branchOrders: Order[] = await api.get(`/orders?branch_id=${branch.id}`);
      setOrders(branchOrders || []);
    } catch (err) {
      console.error(err);
      setOrders([]);
    } finally {
      setOrdersLoading(false);
    }
  };

  const refreshBranchOrders = async () => {
    if (!selectedBranch) return;
    setOrdersLoading(true);
    try {
      const branchOrders: Order[] = await api.get(`/orders?branch_id=${selectedBranch.id}`);
      setOrders(branchOrders || []);
      // also refresh stats in background
      fetchBranches(true);
    } catch (err) {
      console.error(err);
    } finally {
      setOrdersLoading(false);
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

  // Branch detailed stats calculations
  const branchMetrics = useMemo(() => {
    const totalOrders = orders.length;
    let completedCount = 0;
    let activeCount = 0;
    let cancelledCount = 0;
    let totalRevenue = 0;

    orders.forEach((o) => {
      const status = (o.status || '').toUpperCase();
      if (['DELIVERED', 'COMPLETED'].includes(status)) {
        completedCount++;
        totalRevenue += Number(o.total_amount || 0);
      } else if (['CANCELLED', 'REFUNDED', 'REJECTED', 'REFUND_PENDING'].includes(status)) {
        cancelledCount++;
      } else {
        activeCount++;
        if (o.payment_status === 'PAID') {
          totalRevenue += Number(o.total_amount || 0);
        }
      }
    });

    return {
      totalOrders,
      completedCount,
      activeCount,
      cancelledCount,
      totalRevenue
    };
  }, [orders]);

  // Filtered orders list
  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      // Search term
      if (searchTerm.trim()) {
        const query = searchTerm.toLowerCase();
        const matchNumber = (o.order_number || '').toLowerCase().includes(query);
        const matchCustomer = (o.customer_name || '').toLowerCase().includes(query);
        const matchPhone = (o.customer_phone || '').toLowerCase().includes(query);
        const matchItems = (o.items || []).some((item) =>
          (item.product_name || '').toLowerCase().includes(query)
        );
        if (!matchNumber && !matchCustomer && !matchPhone && !matchItems) {
          return false;
        }
      }

      // Status filter
      const status = (o.status || '').toUpperCase();
      if (statusFilter === 'ACTIVE') {
        if (['DELIVERED', 'COMPLETED', 'CANCELLED', 'REFUNDED', 'REJECTED'].includes(status)) {
          return false;
        }
      } else if (statusFilter === 'COMPLETED') {
        if (!['DELIVERED', 'COMPLETED'].includes(status)) {
          return false;
        }
      } else if (statusFilter === 'CANCELLED') {
        if (!['CANCELLED', 'REFUNDED', 'REJECTED', 'REFUND_PENDING'].includes(status)) {
          return false;
        }
      }

      // Order type filter
      if (typeFilter !== 'ALL') {
        if (o.order_type !== typeFilter) {
          return false;
        }
      }

      // Date filter
      if (dateFilter !== 'ALL' && o.created_at) {
        const orderDate = new Date(o.created_at);
        const now = new Date();
        if (dateFilter === 'TODAY') {
          const isToday =
            orderDate.getDate() === now.getDate() &&
            orderDate.getMonth() === now.getMonth() &&
            orderDate.getFullYear() === now.getFullYear();
          if (!isToday) return false;
        } else if (dateFilter === 'WEEK') {
          const oneWeekAgo = new Date();
          oneWeekAgo.setDate(now.getDate() - 7);
          if (orderDate < oneWeekAgo) return false;
        }
      }

      return true;
    });
  }, [orders, searchTerm, statusFilter, typeFilter, dateFilter]);

  // CSV Export handler
  const handleExportCSV = () => {
    if (!selectedBranch || filteredOrders.length === 0) {
      alert('No orders available to export.');
      return;
    }

    const headers = [
      'Order Number',
      'Customer Name',
      'Phone',
      'Email',
      'Order Type',
      'Status',
      'Payment Status',
      'Total Amount (£)',
      'Created At',
      'Items Summary'
    ];

    const rows = filteredOrders.map((o) => [
      `"${o.order_number || ''}"`,
      `"${o.customer_name || ''}"`,
      `"${o.customer_phone || ''}"`,
      `"${o.customer_email || ''}"`,
      `"${o.order_type || ''}"`,
      `"${o.status || ''}"`,
      `"${o.payment_status || ''}"`,
      `"${Number(o.total_amount || 0).toFixed(2)}"`,
      `"${o.created_at ? new Date(o.created_at).toLocaleString('en-GB') : ''}"`,
      `"${(o.items || []).map((i) => `${i.product_name} (x${i.quantity})`).join('; ')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `orders_${selectedBranch.code}_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="w-full max-w-[1280px] mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 text-[#F5F5F5]">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#F5F5F5] tracking-tight">Dashboard</h1>
          <p className="text-xs sm:text-sm text-[#A1A1AA] font-normal mt-1">
            {user?.role === 'BRANCH_ADMIN'
              ? 'View and manage orders for your assigned branch.'
              : 'View branch operational statistics and live order logs.'}
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
              <p className="text-xs text-[#71717A] mt-0.5">Click on any branch to view full order history and live details</p>
            </div>
            <span className="px-2.5 py-1 rounded-full bg-[#181818] border border-[#262626] text-xs text-[#A1A1AA] font-medium">
              {branches.length} {branches.length === 1 ? 'Location' : 'Locations'} Total
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="bg-[#141414] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
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
                      <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-36" /></td>
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
                        className="hover:bg-[#151515] cursor-pointer transition-colors group"
                      >
                        <td className="px-5 py-3.5">
                          <div className="flex items-center gap-3">
                            <span className="w-9 h-9 rounded-lg bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-bold text-xs flex items-center justify-center shrink-0 group-hover:scale-105 transition-transform">
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
                        <td className="px-5 py-3.5 text-center font-bold text-sm text-[#F5F5F5]">
                          {stats.total_orders}
                        </td>
                        <td className="px-5 py-3.5 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold text-[#22C55E] bg-[#22C55E]/10 border border-[#22C55E]/20">
                            {stats.completed_orders}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold text-[#EF4444] bg-[#EF4444]/10 border border-[#EF4444]/20">
                            {stats.cancelled_orders}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-center">
                          <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md text-xs font-semibold text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/20">
                            {stats.pending_orders}
                          </span>
                        </td>
                        <td className="px-5 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                          <div className="flex items-center justify-end gap-2">
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
                              className="h-8 px-2.5 rounded-lg bg-[#151515] border border-[#242424] text-[#A1A1AA] hover:text-[#F5F5F5] hover:border-[#FF5A00]/50 hover:bg-[#FF5A00]/10 flex items-center gap-1 text-xs font-medium transition-all cursor-pointer"
                            >
                              <span>View</span>
                              <ChevronRight className="w-3.5 h-3.5 text-[#FF5A00]" />
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
        /* Detailed Branch Order View */
        <div className="space-y-6 animate-in fade-in duration-200">
          {/* Top Bar with Navigation & Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0D0D0D] border border-[#242424] rounded-xl p-5 shadow-sm">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSelectedBranch(null)}
                className="w-9 h-9 rounded-lg bg-[#181818] border border-[#2B2B2B] hover:border-[#FF5A00]/50 hover:text-[#FF5A00] text-[#A1A1AA] flex items-center justify-center transition-colors cursor-pointer shrink-0"
                title="Back to All Branches"
                aria-label="Back to All Branches"
              >
                <ArrowLeft className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-3">
                <span className="w-10 h-10 rounded-lg bg-[#241209] border border-[#6B2A0D] text-[#FF5A00] font-bold text-sm flex items-center justify-center shrink-0">
                  {selectedBranch.code}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg sm:text-xl font-bold text-[#F5F5F5]">{selectedBranch.name}</h2>
                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#181818] text-[#A1A1AA] border border-[#262626]">
                      {selectedBranch.postcode}
                    </span>
                  </div>
                  <p className="text-[#71717A] text-xs mt-0.5">
                    {orders.length} {orders.length === 1 ? 'order' : 'orders'} total in branch records
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2.5 self-end sm:self-auto">
              <button
                onClick={refreshBranchOrders}
                disabled={ordersLoading}
                title="Refresh Orders"
                className="h-9 px-3 bg-[#151515] border border-[#242424] hover:border-[#383838] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-[#FF5A00] ${ordersLoading ? 'animate-spin' : ''}`} />
                <span className="hidden sm:inline">Refresh</span>
              </button>

              <button
                onClick={() => navigate('/admin/orders')}
                className="h-9 px-3.5 bg-[#FF5A00]/10 border border-[#FF5A00]/30 hover:bg-[#FF5A00]/20 text-[#FF5A00] rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                <span>Live Kitchen Board</span>
              </button>

              <button
                onClick={handleExportCSV}
                className="h-9 px-3.5 bg-[#151515] border border-[#242424] hover:border-[#383838] text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-[#FF5A00]" />
                <span>Export CSV</span>
              </button>
            </div>
          </div>

          {/* Metric Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-4 space-y-1">
              <p className="text-xs text-[#71717A] font-medium">Total Orders</p>
              <p className="text-xl sm:text-2xl font-bold text-[#F5F5F5]">{branchMetrics.totalOrders}</p>
            </div>
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-4 space-y-1">
              <p className="text-xs text-[#71717A] font-medium flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3 text-[#22C55E]" />
                <span>Completed</span>
              </p>
              <p className="text-xl sm:text-2xl font-bold text-[#22C55E]">{branchMetrics.completedCount}</p>
            </div>
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-4 space-y-1">
              <p className="text-xs text-[#71717A] font-medium flex items-center gap-1">
                <Clock className="w-3 h-3 text-[#F59E0B]" />
                <span>In Progress</span>
              </p>
              <p className="text-xl sm:text-2xl font-bold text-[#F59E0B]">{branchMetrics.activeCount}</p>
            </div>
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-4 space-y-1">
              <p className="text-xs text-[#71717A] font-medium flex items-center gap-1">
                <TrendingUp className="w-3 h-3 text-[#FF5A00]" />
                <span>Branch Revenue</span>
              </p>
              <p className="text-xl sm:text-2xl font-bold text-[#FF5A00]">£{branchMetrics.totalRevenue.toFixed(2)}</p>
            </div>
          </div>

          {/* Search & Filter Bar */}
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-4 space-y-3">
            <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
              {/* Search input */}
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-[#71717A] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by order #, customer name, phone, item..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full h-9 pl-9 pr-4 bg-[#141414] border border-[#242424] rounded-lg text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none focus:border-[#FF5A00] transition-colors"
                />
              </div>

              {/* Filters */}
              <div className="flex flex-wrap items-center gap-2">
                {/* Date Filter */}
                <div className="flex items-center rounded-lg bg-[#141414] border border-[#242424] p-0.5 text-xs">
                  <button
                    onClick={() => setDateFilter('ALL')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${dateFilter === 'ALL' ? 'bg-[#FF5A00] text-white font-semibold' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'}`}
                  >
                    All Time
                  </button>
                  <button
                    onClick={() => setDateFilter('TODAY')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${dateFilter === 'TODAY' ? 'bg-[#FF5A00] text-white font-semibold' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'}`}
                  >
                    Today
                  </button>
                  <button
                    onClick={() => setDateFilter('WEEK')}
                    className={`px-2.5 py-1 rounded-md transition-colors ${dateFilter === 'WEEK' ? 'bg-[#FF5A00] text-white font-semibold' : 'text-[#A1A1AA] hover:text-[#F5F5F5]'}`}
                  >
                    7 Days
                  </button>
                </div>

                {/* Type Filter */}
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as any)}
                  className="h-9 px-3 bg-[#141414] border border-[#242424] rounded-lg text-xs text-[#F5F5F5] focus:outline-none focus:border-[#FF5A00] transition-colors cursor-pointer"
                >
                  <option value="ALL">All Types</option>
                  <option value="DELIVERY">Delivery</option>
                  <option value="COLLECTION">Collection</option>
                </select>
              </div>
            </div>

            {/* Status Tabs */}
            <div className="flex items-center gap-1.5 border-t border-[#1C1C1C] pt-3 overflow-x-auto">
              <button
                onClick={() => setStatusFilter('ALL')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                  statusFilter === 'ALL'
                    ? 'bg-[#241209] text-[#FF5A00] border border-[#6B2A0D]'
                    : 'text-[#71717A] hover:text-[#A1A1AA] bg-[#141414]'
                }`}
              >
                All Orders ({orders.length})
              </button>
              <button
                onClick={() => setStatusFilter('ACTIVE')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                  statusFilter === 'ACTIVE'
                    ? 'bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30'
                    : 'text-[#71717A] hover:text-[#A1A1AA] bg-[#141414]'
                }`}
              >
                In Progress ({branchMetrics.activeCount})
              </button>
              <button
                onClick={() => setStatusFilter('COMPLETED')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                  statusFilter === 'COMPLETED'
                    ? 'bg-[#22C55E]/15 text-[#22C55E] border border-[#22C55E]/30'
                    : 'text-[#71717A] hover:text-[#A1A1AA] bg-[#141414]'
                }`}
              >
                Completed ({branchMetrics.completedCount})
              </button>
              <button
                onClick={() => setStatusFilter('CANCELLED')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                  statusFilter === 'CANCELLED'
                    ? 'bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/30'
                    : 'text-[#71717A] hover:text-[#A1A1AA] bg-[#141414]'
                }`}
              >
                Cancelled ({branchMetrics.cancelledCount})
              </button>
            </div>
          </div>

          {/* Orders Table */}
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="bg-[#141414] text-[#A1A1AA] uppercase text-[11px] font-semibold border-b border-[#1C1C1C]">
                  <tr>
                    <th className="px-5 py-3.5">Order ID</th>
                    <th className="px-5 py-3.5">Customer</th>
                    <th className="px-5 py-3.5">Type</th>
                    <th className="px-5 py-3.5">Items</th>
                    <th className="px-5 py-3.5">Amount & Payment</th>
                    <th className="px-5 py-3.5">Status</th>
                    <th className="px-5 py-3.5">Ordered On</th>
                    <th className="px-5 py-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1C1C1C] bg-[#0D0D0D]">
                  {ordersLoading ? (
                    [...Array(4)].map((_, i) => (
                      <tr key={i} className="animate-pulse">
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-28" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-16" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-48" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-20" /></td>
                        <td className="px-5 py-4"><div className="h-4 bg-[#151515] rounded w-24" /></td>
                        <td className="px-5 py-4 text-right"><div className="h-4 bg-[#151515] rounded w-12 ml-auto" /></td>
                      </tr>
                    ))
                  ) : filteredOrders.length > 0 ? (
                    filteredOrders.map((o) => {
                      const itemsSummary = (o.items || [])
                        .map((i) => `${i.product_name || 'Item'} (x${i.quantity || 1})`)
                        .join(', ');

                      return (
                        <tr
                          key={o.id}
                          onClick={() => setSelectedOrderForModal(o)}
                          className="hover:bg-[#141414] transition-colors cursor-pointer group"
                        >
                          <td className="px-5 py-3.5 font-bold text-sm text-[#FF5A00]">
                            {o.order_number}
                          </td>
                          <td className="px-5 py-3.5">
                            <p className="font-semibold text-[#F5F5F5]">{o.customer_name || 'Customer'}</p>
                            <p className="text-[11px] text-[#71717A]">{o.customer_phone || 'No phone'}</p>
                          </td>
                          <td className="px-5 py-3.5">
                            {o.order_type === 'DELIVERY' ? (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#3B82F6]/10 text-[#3B82F6] border border-[#3B82F6]/20">
                                <Bike className="w-3 h-3" />
                                <span>DELIVERY</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#A855F7]/10 text-[#A855F7] border border-[#A855F7]/20">
                                <ShoppingBag className="w-3 h-3" />
                                <span>COLLECTION</span>
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-3.5 max-w-xs">
                            <p className="text-[#A1A1AA] text-xs truncate" title={itemsSummary}>
                              {itemsSummary || 'No items listed'}
                            </p>
                          </td>
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-[#F5F5F5]">
                                £{Number(o.total_amount || 0).toFixed(2)}
                              </span>
                              <span
                                className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${
                                  o.payment_status === 'PAID'
                                    ? 'bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/30'
                                    : o.payment_status === 'FAILED'
                                    ? 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/30'
                                    : 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/30'
                                }`}
                              >
                                {o.payment_status || 'PENDING'}
                              </span>
                            </div>
                          </td>
                          <td className="px-5 py-3.5">
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider border ${
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
                                  : o.status === 'CANCELLED' || o.status === 'REFUNDED'
                                  ? 'bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/40'
                                  : 'bg-[#181818] text-[#A1A1AA] border-[#2B2B2B]'
                              }`}
                            >
                              {o.status}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-[#71717A] text-[11px] whitespace-nowrap">
                            {o.created_at
                              ? new Date(o.created_at).toLocaleString('en-GB', {
                                  day: '2-digit',
                                  month: 'short',
                                  hour: '2-digit',
                                  minute: '2-digit'
                                })
                              : '—'}
                          </td>
                          <td className="px-5 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => setSelectedOrderForModal(o)}
                              title="View Order Details"
                              className="h-7 px-2.5 rounded-md bg-[#181818] hover:bg-[#FF5A00]/15 border border-[#2B2B2B] hover:border-[#FF5A00]/50 text-[#A1A1AA] hover:text-[#FF5A00] inline-flex items-center gap-1 text-[11px] font-medium transition-colors cursor-pointer"
                            >
                              <Eye className="w-3 h-3" />
                              <span>Details</span>
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  ) : (
                    <tr>
                      <td colSpan={8} className="px-5 py-12 text-center text-[#71717A]">
                        {searchTerm || statusFilter !== 'ALL' || typeFilter !== 'ALL' || dateFilter !== 'ALL'
                          ? 'No orders match your filter criteria.'
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

      {/* Order Details Modal */}
      {selectedOrderForModal && (
        <AdminOrderDetailsModal
          order={selectedOrderForModal}
          onClose={() => setSelectedOrderForModal(null)}
          onUpdateStatus={() => {
            refreshBranchOrders();
            setSelectedOrderForModal(null);
          }}
        />
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
