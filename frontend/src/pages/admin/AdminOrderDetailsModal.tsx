import React, { useState, useEffect } from 'react';
import { X, User, MapPin, CreditCard, ShoppingBag, AlertTriangle, Printer } from 'lucide-react';
import { Order } from '../../types';
import { api } from '../../api/client';

interface Props {
  order: Order;
  onClose: () => void;
  onUpdateStatus: () => void;
}

export const AdminOrderDetailsModal: React.FC<Props> = ({ order, onClose, onUpdateStatus }) => {
  const [selectedStatus, setSelectedStatus] = useState(order.status);
  const [loading, setLoading] = useState(false);
  const [showReceiptModal, setShowReceiptModal] = useState(false);

  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

  const handleUpdateStatus = async () => {
    setLoading(true);
    try {
      await api.patch(`/orders/${order.id}/status`, { status: selectedStatus });
      onUpdateStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelOrder = async () => {
    if (!window.confirm('Are you sure you want to cancel this order?')) return;
    setLoading(true);
    try {
      await api.patch(`/orders/${order.id}/status`, { status: 'CANCELLED', notes: 'Order cancelled by Admin' });
      onUpdateStatus();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="admin-modal-overlay">
      <div className="admin-modal-container bg-[#0D0D0D] border border-[#242424] rounded-xl max-w-4xl shadow-2xl p-4 sm:p-6 relative text-[#F5F5F5] flex flex-col space-y-4">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 border-b border-[#1C1C1C] shrink-0">
          <div className="flex items-center gap-3">
            <h2 className="text-base sm:text-lg font-bold text-[#F5F5F5]">Order Details <span className="text-[#FF5A00]">{order.order_number}</span></h2>
            <span className="px-2.5 py-0.5 bg-[#241209] text-[#FF5A00] border border-[#6B2A0D] rounded text-[10px] font-semibold uppercase tracking-wider">
              {order.status}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowReceiptModal(true)}
              className="px-2.5 py-1 bg-[#1C1C1C] hover:bg-[#252525] border border-[#333333] text-[#F5F5F5] rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5 text-[#FF5A00]" />
              <span>Print Bill</span>
            </button>
            <button
              onClick={onClose}
              aria-label="Close modal"
              className="p-1 text-[#A1A1AA] hover:text-[#F5F5F5] rounded-lg transition-colors cursor-pointer shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-5 pr-1">

        {/* Top Info Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* Card 1: Order Info */}
          <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-2 text-xs">
            <div className="flex items-center gap-2 text-[#FF5A00] font-semibold mb-2">
              <ShoppingBag className="w-4 h-4" />
              <span>Order Information</span>
            </div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Order ID</span><span className="text-[#F5F5F5] font-semibold">{order.order_number}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Order Type</span><span className="text-[#F5F5F5]">{order.order_type}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Payment Method</span><span className="text-[#F5F5F5]">{order.payment_method}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Payment Status</span><span className="text-[#22C55E] font-semibold">{order.payment_status}</span></div>
            <div className="flex justify-between font-semibold pt-2 border-t border-[#242424]"><span className="text-[#F5F5F5]">Total Amount</span><span className="text-[#FF5A00] text-sm font-bold">£{order.total_amount.toFixed(2)}</span></div>
          </div>

          {/* Card 2: Customer Info */}
          <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-2 text-xs">
            <div className="flex items-center gap-2 text-[#FF5A00] font-semibold mb-2">
              <User className="w-4 h-4" />
              <span>Customer Information</span>
            </div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Name</span><span className="text-[#F5F5F5] font-semibold">{order.customer_name || 'Guest Customer'}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Phone</span><span className="text-[#F5F5F5]">{order.customer_phone || 'No phone provided'}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Email</span><span className="text-[#F5F5F5] truncate max-w-[140px]" title={order.customer_email}>{order.customer_email || 'No email provided'}</span></div>
            <div className="flex justify-between"><span className="text-[#A1A1AA]">Points Earned</span><span className="text-[#FF5A00] font-semibold">+{order.points_earned ? order.points_earned.toLocaleString() : 0} pts</span></div>
            {order.points_redeemed ? (
              <div className="flex justify-between"><span className="text-[#A1A1AA]">Points Redeemed</span><span className="text-[#10B981] font-semibold">-{order.points_redeemed.toLocaleString()} pts</span></div>
            ) : null}
          </div>

          {/* Card 3: Delivery / Collection Details */}
          <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-2 text-xs">
            <div className="flex items-center gap-2 text-[#FF5A00] font-semibold mb-2">
              <MapPin className="w-4 h-4" />
              <span>{order.order_type === 'COLLECTION' ? 'Collection Details' : 'Delivery Address'}</span>
            </div>
            {order.order_type === 'COLLECTION' ? (
              <>
                <p className="text-[#F5F5F5] font-medium">Customer Collection at Branch</p>
                {order.collection_slot_time && (
                  <p className="text-[#A1A1AA]">Slot: {new Date(order.collection_slot_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</p>
                )}
              </>
            ) : (
              <>
                <p className="text-[#F5F5F5] font-medium">{order.delivery_address?.address_line1 || 'No address line 1'}</p>
                <p className="text-[#A1A1AA]">{[order.delivery_address?.city, order.delivery_address?.postcode].filter(Boolean).join(', ') || 'London, United Kingdom'}</p>
                <p className="text-xs text-[#FF5A00] mt-2 font-medium">Instructions: {order.delivery_instructions || 'None'}</p>
              </>
            )}
          </div>
        </div>

        {/* Bottom Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Ordered Items Table */}
          <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-3.5">
            <h3 className="text-xs font-semibold text-[#F5F5F5] uppercase tracking-wider">Ordered Items</h3>
            <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
              {order.items && order.items.length > 0 ? (
                order.items.map((item, idx) => (
                  <div key={idx} className="flex items-start justify-between text-xs pb-2.5 border-b border-[#242424] last:border-0">
                    <div>
                      <p className="font-semibold text-[#F5F5F5]">{item.product_name}</p>
                      <p className="text-[11px] text-[#71717A]">Qty: {item.quantity}</p>
                      {item.selected_modifiers && item.selected_modifiers.length > 0 && (
                        <div className="mt-1 space-y-0.5">
                          {item.selected_modifiers.map((mod: any, mIdx: number) => (
                            <p key={mIdx} className="text-[11px] text-[#FF5A00]/90">
                              • {mod.name}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                    <p className="font-semibold text-[#F5F5F5]">£{item.total_price.toFixed(2)}</p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-[#71717A] py-2">No item details recorded for this order.</p>
              )}
            </div>

            {(() => {
              const subtotalVal = Number(order.subtotal || 0);
              const discountVal = Number(order.discount_amount || 0);
              const vatVal = Number(order.vat_amount || 0);
              const grossVal = Math.max(0, Number((subtotalVal - discountVal).toFixed(2)));
              const netVal = Math.max(0, Number((grossVal - vatVal).toFixed(2)));
              const totalVal = Number(order.total_amount || 0);

              return (
                <div className="pt-3 border-t border-[#242424] space-y-1.5 text-xs text-[#A1A1AA]">
                  <div className="flex justify-between"><span>Subtotal</span><span>£{subtotalVal.toFixed(2)}</span></div>
                  {discountVal > 0 && (
                    <div className="flex justify-between text-[#10B981]">
                      <span>Discount {order.coupon_code ? `(${order.coupon_code})` : ''}</span>
                      <span>-£{discountVal.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between text-[#71717A]">
                    <span>Net Amount</span>
                    <span>£{netVal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-[#71717A]">
                    <span>VAT (20% Included)</span>
                    <span>£{vatVal.toFixed(2)}</span>
                  </div>
                  {Number(order.delivery_fee) > 0 && (
                    <div className="flex justify-between"><span>Delivery Fee</span><span>£{Number(order.delivery_fee).toFixed(2)}</span></div>
                  )}
                  {Number(order.service_fee) > 0 && (
                    <div className="flex justify-between"><span>Service Fee</span><span>£{Number(order.service_fee).toFixed(2)}</span></div>
                  )}
                  <div className="flex justify-between text-sm font-semibold text-[#F5F5F5] pt-2 border-t border-[#242424]">
                    <div>
                      <span>Total Amount</span>
                      <p className="text-[10px] font-normal text-[#71717A]">VAT included in gross • VAT NO: 525 5772 74</p>
                    </div>
                    <span className="text-[#FF5A00] font-bold text-base">£{totalVal.toFixed(2)}</span>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Payment & Status Control */}
          <div className="space-y-3.5">
            <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-2 text-xs">
              <h3 className="text-xs font-semibold text-[#F5F5F5] uppercase tracking-wider mb-2">Payment Details</h3>
              <div className="flex justify-between"><span className="text-[#A1A1AA]">Method</span><span className="text-[#F5F5F5] font-medium">Online Card VISA</span></div>
              <div className="flex justify-between"><span className="text-[#A1A1AA]">Transaction ID</span><span className="text-[#F5F5F5] font-mono">{order.payment_transaction_id || 'TXN4789632145'}</span></div>
              <div className="flex justify-between"><span className="text-[#A1A1AA]">Paid On</span><span className="text-[#F5F5F5]">6 May 2025, 10:23 AM</span></div>
            </div>

            {/* Update Order Status Controls */}
            <div className="bg-[#151515] border border-[#242424] p-4 rounded-lg space-y-3">
              <h3 className="text-xs font-semibold text-[#F5F5F5] uppercase tracking-wider">Update Order Status</h3>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="w-full h-10 bg-[#0D0D0D] border border-[#242424] focus:border-[#FF5A00] text-[#F5F5F5] text-xs font-semibold px-3 rounded-lg focus:outline-none transition-colors"
              >
                <option value="INCOMING">INCOMING (New Order)</option>
                <option value="ACCEPTED">ACCEPTED (Order Confirmed)</option>
                <option value="PREPARING">PREPARING (In Kitchen)</option>
                <option value="READY">READY (Packed / Waiting Dispatch)</option>
                <option value="OUT_FOR_DELIVERY">OUT FOR DELIVERY (With Driver)</option>
                <option value="DELIVERED">DELIVERED (Completed Delivery)</option>
                <option value="COLLECTED">COLLECTED (Customer Picked Up)</option>
                <option value="CANCELLED">CANCELLED</option>
              </select>

              <button
                onClick={handleUpdateStatus}
                disabled={loading}
                className="w-full h-10 bg-[#FF5A00] hover:bg-[#E84F00] text-white text-xs font-semibold rounded-lg transition-colors shadow-sm disabled:opacity-50 cursor-pointer"
              >
                {loading ? 'Updating...' : 'Save Selected Status'}
              </button>

              {/* One-Click Quick Workflow Action */}
              {selectedStatus === 'INCOMING' && (
                <button
                  onClick={async () => {
                    setSelectedStatus('ACCEPTED');
                    setLoading(true);
                    try {
                      await api.patch(`/orders/${order.id}/status`, { status: 'ACCEPTED' });
                      onUpdateStatus();
                    } finally { setLoading(false); }
                  }}
                  className="w-full h-10 bg-[#06B6D4] hover:bg-[#0891B2] text-white text-xs font-bold rounded-lg transition-colors shadow-sm cursor-pointer"
                >
                  ✓ Accept Order
                </button>
              )}

              {selectedStatus === 'ACCEPTED' && (
                <button
                  onClick={async () => {
                    setSelectedStatus('PREPARING');
                    setLoading(true);
                    try {
                      await api.patch(`/orders/${order.id}/status`, { status: 'PREPARING' });
                      onUpdateStatus();
                    } finally { setLoading(false); }
                  }}
                  className="w-full h-10 bg-[#F59E0B] hover:bg-[#D97706] text-black text-xs font-bold rounded-lg transition-colors shadow-sm cursor-pointer"
                >
                  🍳 Start Preparing
                </button>
              )}

              {selectedStatus === 'PREPARING' && (
                <button
                  onClick={async () => {
                    setSelectedStatus('READY');
                    setLoading(true);
                    try {
                      await api.patch(`/orders/${order.id}/status`, { status: 'READY' });
                      onUpdateStatus();
                    } finally { setLoading(false); }
                  }}
                  className="w-full h-10 bg-[#10B981] hover:bg-[#059669] text-white text-xs font-bold rounded-lg transition-colors shadow-sm cursor-pointer"
                >
                  📦 Mark Ready
                </button>
              )}

              {(selectedStatus === 'READY' || selectedStatus === 'OUT_FOR_DELIVERY') && (
                <button
                  onClick={async () => {
                    const finalStatus = order.order_type === 'COLLECTION' ? 'COLLECTED' : 'DELIVERED';
                    setSelectedStatus(finalStatus);
                    setLoading(true);
                    try {
                      await api.patch(`/orders/${order.id}/status`, { status: finalStatus });
                      onUpdateStatus();
                    } finally { setLoading(false); }
                  }}
                  className="w-full h-10 bg-[#22C55E] hover:bg-[#16A34A] text-white text-xs font-bold rounded-lg transition-colors shadow-sm cursor-pointer"
                >
                  🚚 Mark {order.order_type === 'COLLECTION' ? 'Collected' : 'Delivered'}
                </button>
              )}

              <button
                onClick={handleCancelOrder}
                className="w-full h-9 bg-[#EF4444]/10 border border-[#EF4444]/30 hover:bg-[#EF4444]/20 text-[#EF4444] text-xs font-semibold rounded-lg transition-colors flex items-center justify-center gap-2 cursor-pointer"
              >
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Cancel Order</span>
              </button>
            </div>

          </div>
        </div>
        </div>
      </div>

      {/* Printable Official Receipt Modal */}
      {showReceiptModal && (() => {
        const subtotalVal = Number(order.subtotal || 0);
        const discountVal = Number(order.discount_amount || 0);
        const vatVal = Number(order.vat_amount || 0);
        const grossVal = Math.max(0, Number((subtotalVal - discountVal).toFixed(2)));
        const netVal = Math.max(0, Number((grossVal - vatVal).toFixed(2)));
        const totalVal = Number(order.total_amount || 0);
        const totalItemsCount = (order.items || []).reduce((acc, it) => acc + (it.quantity || 1), 0);

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 text-black">
            <div className="bg-white rounded-lg max-w-md w-full p-6 shadow-2xl space-y-4 font-mono text-xs text-left relative max-h-[90vh] overflow-y-auto">
              <div className="flex justify-between items-center border-b border-black pb-2">
                <div className="text-left">
                  <h3 className="font-extrabold text-sm tracking-wider uppercase">PATTY PROJECT UK</h3>
                  <p className="text-[10px] text-zinc-600">Order: {order.order_number}</p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowReceiptModal(false)}
                  className="p-1 hover:bg-zinc-200 rounded text-black cursor-pointer print:hidden"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="text-center font-bold tracking-widest text-sm border-b border-dashed border-zinc-400 py-1">
                BILL
              </div>

              <div className="space-y-1.5 py-1">
                {order.items && order.items.length > 0 ? (
                  order.items.map((item, idx) => (
                    <div key={idx} className="flex justify-between items-start">
                      <span className="truncate max-w-[240px]">
                        {item.quantity}  {item.product_name}
                      </span>
                      <span className="font-semibold shrink-0">
                        £{Number(item.total_price || 0).toFixed(2)}
                      </span>
                    </div>
                  ))
                ) : (
                  <p>1  Standard Order  £{subtotalVal.toFixed(2)}</p>
                )}
              </div>

              <div className="border-t border-zinc-400 pt-1.5 flex justify-between font-bold">
                <span>{totalItemsCount}  ITEM(S)</span>
                <span>£{subtotalVal.toFixed(2)}</span>
              </div>

              {discountVal > 0 && (
                <div className="flex justify-between text-zinc-800">
                  <span>   Discount</span>
                  <span>-£{discountVal.toFixed(2)}</span>
                </div>
              )}

              <div className="border-t border-zinc-400 pt-1.5 flex justify-between font-extrabold text-sm">
                <span>   AMOUNT DUE</span>
                <span>£{totalVal.toFixed(2)}</span>
              </div>

              <div className="border-t border-dashed border-zinc-400 pt-3 space-y-1">
                <div className="grid grid-cols-4 font-bold text-[11px] pb-1 border-b border-zinc-300">
                  <span>Rate</span>
                  <span className="text-right">Net</span>
                  <span className="text-right">Tax</span>
                  <span className="text-right">Gross</span>
                </div>
                <div className="grid grid-cols-4 text-[11px]">
                  <span>20%</span>
                  <span className="text-right">£{netVal.toFixed(2)}</span>
                  <span className="text-right">£{vatVal.toFixed(2)}</span>
                  <span className="text-right">£{grossVal.toFixed(2)}</span>
                </div>
              </div>

              <div className="pt-2 text-center text-[10px] space-y-1 border-t border-zinc-300">
                <p className="font-semibold">Tax are included in the Gross amount!</p>
                <p className="font-bold tracking-wider">VAT NO: 525 5772 74</p>
              </div>

              <div className="pt-3 flex gap-2 print:hidden">
                <button
                  type="button"
                  onClick={() => window.print()}
                  className="flex-1 py-2 bg-black text-white rounded font-bold hover:bg-zinc-800 flex items-center justify-center gap-1.5 cursor-pointer"
                >
                  <Printer className="w-3.5 h-3.5" />
                  <span>Print</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowReceiptModal(false)}
                  className="py-2 px-4 border border-zinc-400 rounded font-semibold hover:bg-zinc-100 cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
