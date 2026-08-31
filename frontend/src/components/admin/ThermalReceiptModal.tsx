import React, { useEffect, useRef } from 'react';
import { X, Printer } from 'lucide-react';
import { Order } from '../../types';

interface ThermalReceiptModalProps {
  order: Order;
  isOpen: boolean;
  onClose: () => void;
  autoPrint?: boolean;
}

export const ThermalReceiptModal: React.FC<ThermalReceiptModalProps> = ({
  order,
  isOpen,
  onClose,
  autoPrint = false,
}) => {
  const hasTriggeredPrintRef = useRef(false);

  useEffect(() => {
    if (isOpen && autoPrint && order && !hasTriggeredPrintRef.current) {
      hasTriggeredPrintRef.current = true;
      const timer = setTimeout(() => {
        try {
          window.print();
        } catch (err) {
          console.warn('Auto-print invocation failed:', err);
        }
      }, 200);
      return () => clearTimeout(timer);
    }
    if (!isOpen) {
      hasTriggeredPrintRef.current = false;
    }
  }, [isOpen, autoPrint, order]);

  if (!isOpen || !order) return null;

  const subtotalVal = Number(order.subtotal || 0);
  const discountVal = Number(order.discount_amount || 0);
  const vatVal = Number(order.vat_amount || 0);
  const grossVal = Math.max(0, Number((subtotalVal - discountVal).toFixed(2)));
  const netVal = Math.max(0, Number((grossVal - vatVal).toFixed(2)));
  const totalVal = Number(order.total_amount || 0);
  const totalItemsCount = (order.items || []).reduce((acc, it) => acc + (it.quantity || 1), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 text-black">
      <div className="thermal-receipt-80mm bg-white rounded-lg max-w-md w-full p-6 shadow-2xl space-y-4 font-mono text-xs text-left relative max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center border-b border-black pb-2">
          <div className="text-left">
            <h3 className="font-extrabold text-sm tracking-wider uppercase">PATTY PROJECT UK</h3>
            <p className="text-[10px] text-zinc-600">Order: {order.order_number}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
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
              <div key={idx} className="flex justify-between items-start gap-2">
                <span className="break-words pr-2 flex-1">
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
            onClick={onClose}
            className="py-2 px-4 border border-zinc-400 rounded font-semibold hover:bg-zinc-100 cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
