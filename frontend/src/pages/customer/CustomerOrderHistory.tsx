import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Search, SlidersHorizontal, ChevronRight, Package, X, AlertCircle } from 'lucide-react';
import { api } from '../../api/client';
import { useAuthStore } from '../../store/authStore';

interface OrderItemData {
  id: string;
  product_name: string;
  quantity: number;
  unit_price: number;
  total_price: number;
}

interface OrderData {
  id: string;
  order_number: string;
  created_at: string;

  status: string;
  order_type: string;
  total_amount: number;
  subtotal: number;
  delivery_fee: number;
  service_fee: number;
  discount_amount: number;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  delivery_address?: any;
  items: OrderItemData[];
}

export const CustomerOrderHistory: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const [orders, setOrders] = useState<OrderData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Search & Filter State matching Screenshot
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState<'ALL' | 'COMPLETED' | 'CANCELLED' | 'REFUNDED'>('ALL');
  const [selectedOrder, setSelectedOrder] = useState<OrderData | null>(null);

  const fetchMyOrders = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<OrderData[]>('/orders/my-orders');
      setOrders(data);
    } catch (err: any) {
      setError(err?.message || 'Failed to load order history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) {
      navigate('/login');
      return;
    }
    fetchMyOrders();
  }, [user, navigate, fetchMyOrders]);

  // Filter Orders based on Tab and Search query
  const filteredOrders = orders.filter((order) => {
    // Search query matching order number or item name
    const matchesSearch =
      order.order_number.toLowerCase().includes(searchQuery.toLowerCase()) ||
      order.items?.some((item) => item.product_name.toLowerCase().includes(searchQuery.toLowerCase()));

    if (!matchesSearch) return false;

    const statusUpper = order.status.toUpperCase();

    if (activeTab === 'COMPLETED') {
      return statusUpper === 'DELIVERED' || statusUpper === 'COMPLETED' || statusUpper === 'PAID';
    }
    if (activeTab === 'CANCELLED') {
      return statusUpper === 'CANCELLED' || statusUpper === 'FAILED';
    }
    if (activeTab === 'REFUNDED') {
      return statusUpper === 'REFUNDED';
    }

    return true; // ALL tab
  });

  const getStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'DELIVERED' || s === 'COMPLETED' || s === 'PAID') {
      return (
        <span className="bg-[#10B981]/20 text-[#34D399] text-[11px] font-extrabold px-2.5 py-0.5 rounded-md uppercase tracking-wider">
          Delivered
        </span>
      );
    }
    if (s === 'CANCELLED' || s === 'FAILED') {
      return (
        <span className="bg-[#EF4444]/20 text-[#FCA5A5] text-[11px] font-extrabold px-2.5 py-0.5 rounded-md uppercase tracking-wider">
          Cancelled
        </span>
      );
    }
    if (s === 'REFUNDED') {
      return (
        <span className="bg-[#333333] text-[#9CA3AF] text-[11px] font-extrabold px-2.5 py-0.5 rounded-md uppercase tracking-wider">
          Refunded
        </span>
      );
    }
    return (
      <span className="bg-[#FF5500]/20 text-[#FF5500] text-[11px] font-extrabold px-2.5 py-0.5 rounded-md uppercase tracking-wider">
        {status}
      </span>
    );
  };

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      const dateStr = date.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
      const timeStr = date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: true });
      return `${dateStr} • ${timeStr}`;
    } catch {
      return isoString;
    }
  };

  const formatShortDate = (isoString: string) => {
    try {
      return new Date(isoString).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="w-full max-w-[1400px] mx-auto px-4 sm:px-10 lg:px-12 py-6 sm:py-10 pb-36 text-white min-h-[85vh]">
      {/* Title & Subtitle matching Reference Screenshot */}
      <div className="mb-8">
        <h1 className="text-3xl font-extrabold tracking-tight text-white">Order History</h1>
        <p className="text-sm text-[#9CA3AF] mt-1 font-medium">Track and view all your past orders</p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-[#2A1215] border border-[#EF4444]/40 rounded-xl flex items-center gap-3 text-xs text-[#FCA5A5]">
          <AlertCircle className="w-4 h-4 text-[#EF4444] shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search & Filter Controls matching Reference Screenshot */}
      <div className="flex flex-col sm:flex-row items-center gap-4 mb-8">
        {/* Search Bar Input */}
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-[#9CA3AF] absolute left-4 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search by order ID or item"
            className="w-full bg-[#121212] border border-[#222222] focus:border-[#FF5500] rounded-xl py-3 pl-11 pr-4 text-xs text-white placeholder-[#6B7280] focus:outline-none transition-colors"
          />
        </div>

        {/* Filter Button matching Reference Screenshot */}
        <button
          onClick={() => {}}
          className="flex items-center gap-2 border border-[#FF5500] text-[#FF5500] hover:bg-[#FF5500]/10 px-5 py-3 rounded-xl text-xs font-bold transition-all cursor-pointer shrink-0 self-stretch sm:self-auto justify-center"
        >
          <SlidersHorizontal className="w-4 h-4" />
          <span>Filter</span>
        </button>
      </div>

      {/* Category Tabs matching Reference Screenshot */}
      <div className="flex items-center gap-6 border-b border-[#1C1C1C] mb-8 overflow-x-auto">
        {[
          { key: 'ALL', label: 'All Orders' },
          { key: 'COMPLETED', label: 'Completed' },
          { key: 'CANCELLED', label: 'Cancelled' },
          { key: 'REFUNDED', label: 'Refunded' },
        ].map((tab) => {
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`pb-3 text-xs font-bold transition-colors relative cursor-pointer shrink-0 ${
                isActive ? 'text-white' : 'text-[#9CA3AF] hover:text-white'
              }`}
            >
              <span>{tab.label}</span>
              {isActive && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF5500]" />}
            </button>
          );
        })}
      </div>

      {/* Orders List / Skeleton / Empty state */}
      {loading ? (
        <div className="space-y-4 animate-pulse">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="h-28 bg-[#121212] border border-[#222222] rounded-2xl p-5" />
          ))}
        </div>
      ) : filteredOrders.length === 0 ? (
        <div className="bg-[#121212] border border-[#222222] rounded-2xl p-12 text-center max-w-md mx-auto my-6">
          <div className="w-16 h-16 bg-[#1A1A1A] rounded-full flex items-center justify-center mx-auto mb-4 border border-[#282828]">
            <Package className="w-8 h-8 text-[#FF5500]" />
          </div>
          <h3 className="text-lg font-bold text-white mb-2">No Orders Found</h3>
          <p className="text-xs text-[#9CA3AF] mb-6">
            You don't have any past orders under this filter yet. Explore our delicious menu and place an order!
          </p>
          <Link
            to="/menu"
            className="inline-block bg-[#FF5500] hover:bg-[#FF6611] text-white text-xs font-bold px-6 py-2.5 rounded-xl transition-all"
          >
            Explore Menu
          </Link>
        </div>
      ) : (
        /* Order Cards List matching Reference Screenshot */
        <div className="space-y-4">
          {filteredOrders.map((order) => {
            const itemCount = order.items?.reduce((sum, item) => sum + item.quantity, 0) || 1;
            const displayImg = '/herobackground.webp';

            return (
              <div
                key={order.id}
                onClick={() => setSelectedOrder(order)}
                className="bg-[#121212] border border-[#222222] hover:border-[#FF5500]/50 rounded-2xl p-5 sm:p-6 transition-all cursor-pointer flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group"
              >
                {/* Left Side: Product Thumbnail & Order Details */}
                <div className="flex items-start gap-4 flex-1 min-w-0">
                  <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-2xl bg-[#1A1A1A] border border-[#282828] overflow-hidden shrink-0">
                    <img
                      src={displayImg}
                      alt={order.order_number}
                      className="w-full h-full object-cover select-none group-hover:scale-105 transition-transform"
                    />
                  </div>

                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-extrabold text-white mb-1 group-hover:text-[#FF5500] transition-colors">
                      Order {order.order_number}
                    </h3>
                    <p className="text-xs text-[#9CA3AF] mb-0.5">{formatDate(order.created_at)}</p>
                    <p className="text-xs text-[#9CA3AF] mb-3">
                      {itemCount} {itemCount === 1 ? 'Item' : 'Items'}
                    </p>

                    {/* View Details Button matching Reference Screenshot */}
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedOrder(order);
                      }}
                      className="border border-[#FF5500] text-[#FF5500] hover:bg-[#FF5500]/10 text-xs font-extrabold px-3.5 py-1 rounded-lg transition-colors cursor-pointer"
                    >
                      View Details
                    </button>
                  </div>
                </div>

                {/* Right Side: Total Price, Status Badge, Subtext & Chevron */}
                <div className="flex items-center justify-between sm:justify-end gap-5 w-full sm:w-auto pt-3 sm:pt-0 border-t sm:border-t-0 border-[#1C1C1C]">
                  <div className="text-left sm:text-right">
                    <p className="text-base font-black text-white mb-1">£{order.total_amount.toFixed(2)}</p>
                    <div className="mb-1">{getStatusBadge(order.status)}</div>
                    <p className="text-[11px] text-[#9CA3AF]">
                      {order.status.toUpperCase() === 'DELIVERED' || order.status.toUpperCase() === 'COMPLETED'
                        ? `Delivered on ${formatShortDate(order.created_at)}`
                        : order.status.toUpperCase() === 'CANCELLED'
                        ? `Cancelled on ${formatShortDate(order.created_at)}`
                        : order.status.toUpperCase() === 'REFUNDED'
                        ? `Refunded on ${formatShortDate(order.created_at)}`
                        : `Order Placed`}
                    </p>
                  </div>

                  <ChevronRight className="w-5 h-5 text-[#9CA3AF] group-hover:text-white transition-colors shrink-0" />
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Order Details Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#121212] border border-[#282828] rounded-2xl p-6 sm:p-8 w-full max-w-lg shadow-2xl animate-fadeIn relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setSelectedOrder(null)}
              className="absolute top-5 right-5 text-[#9CA3AF] hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-xl font-extrabold text-white">Order {selectedOrder.order_number}</h3>
              {getStatusBadge(selectedOrder.status)}
            </div>
            <p className="text-xs text-[#9CA3AF] mb-6">{formatDate(selectedOrder.created_at)}</p>

            {/* Order Items Breakdown */}
            <div className="space-y-4 mb-6">
              <h4 className="text-xs font-extrabold uppercase tracking-wider text-[#9CA3AF] border-b border-[#222222] pb-2">
                Ordered Items
              </h4>

              <div className="divide-y divide-[#1C1C1C]">
                {selectedOrder.items?.map((item) => (
                  <div key={item.id} className="py-2.5 flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-white">{item.product_name}</p>
                      <p className="text-[11px] text-[#9CA3AF]">Qty: {item.quantity} × £{item.unit_price.toFixed(2)}</p>
                    </div>
                    <span className="font-mono font-bold text-white">£{item.total_price.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Pricing Summary */}
            <div className="bg-[#181818] border border-[#282828] rounded-xl p-4 space-y-2 text-xs mb-6">
              <div className="flex justify-between text-[#9CA3AF]">
                <span>Subtotal</span>
                <span className="text-white font-mono">£{selectedOrder.subtotal?.toFixed(2) || selectedOrder.total_amount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-[#9CA3AF]">
                <span>Delivery Fee</span>
                <span className="text-white font-mono">£{selectedOrder.delivery_fee?.toFixed(2) || '0.00'}</span>
              </div>
              <div className="flex justify-between text-white font-bold text-sm pt-2 border-t border-[#282828]">
                <span>Total Amount Paid</span>
                <span className="text-[#FF5500] font-mono">£{selectedOrder.total_amount.toFixed(2)}</span>
              </div>
            </div>

            {/* Close Button */}
            <button
              onClick={() => setSelectedOrder(null)}
              className="w-full bg-[#FF5500] hover:bg-[#FF6611] text-white text-xs font-bold py-3 rounded-xl transition-all shadow-lg shadow-[#FF5500]/20"
            >
              Close Details
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
