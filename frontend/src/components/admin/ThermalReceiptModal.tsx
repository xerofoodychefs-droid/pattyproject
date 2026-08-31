import React, { useEffect, useRef } from 'react';
import { X, Printer } from 'lucide-react';
import { Order } from '../../types';

interface ThermalReceiptModalProps {
  order: Order;
  isOpen: boolean;
  onClose: () => void;
  autoPrint?: boolean;
}

interface CustomizationCategories {
  addons: { label: string; price?: number }[];
  removals: string[];
  selections: { label: string; price?: number }[];
}

const parseCustomizations = (item: any): CustomizationCategories => {
  const addons: { label: string; price?: number }[] = [];
  const removals: string[] = [];
  const selections: { label: string; price?: number }[] = [];

  // 1. Process selected_modifiers (array of objects or strings)
  if (Array.isArray(item.selected_modifiers)) {
    for (const mod of item.selected_modifiers) {
      if (!mod) continue;
      if (typeof mod === 'string') {
        const trimmed = mod.trim();
        if (trimmed.startsWith('-') || trimmed.toLowerCase().startsWith('no ') || trimmed.toLowerCase().startsWith('without ')) {
          const clean = trimmed.replace(/^[-•\s]+/, '').replace(/^(no|without)\s+/i, '').trim();
          if (clean && !removals.includes(clean)) removals.push(clean);
        } else if (trimmed.includes(':')) {
          selections.push({ label: trimmed });
        } else {
          addons.push({ label: trimmed.replace(/^[+•\s]+/, '').trim() });
        }
      } else if (typeof mod === 'object') {
        const rawName = (mod.name || mod.option_name || '').trim();
        const price = typeof mod.price === 'number' && mod.price > 0 ? mod.price : undefined;

        if (mod.is_choice || mod.group_name || (rawName.includes(':') && !rawName.startsWith('-'))) {
          const group = mod.group_name || (rawName.includes(':') ? rawName.split(':')[0].trim() : '');
          const opt = mod.option_name || (rawName.includes(':') ? rawName.split(':')[1].trim() : rawName);
          const label = group ? `${group}: ${opt}` : opt;
          if (label && !selections.some(s => s.label === label)) {
            selections.push({ label, price });
          }
        } else if (rawName.startsWith('-') || rawName.toLowerCase().startsWith('no ') || rawName.toLowerCase().startsWith('without ') || mod.is_removal) {
          const clean = rawName.replace(/^[-•\s]+/, '').replace(/^(no|without)\s+/i, '').trim();
          if (clean && !removals.includes(clean)) removals.push(clean);
        } else if (rawName) {
          addons.push({ label: rawName.replace(/^[+•\s]+/, '').trim(), price });
        }
      }
    }
  }

  // 2. Process selected_choices (array of choice objects)
  if (Array.isArray(item.selected_choices)) {
    for (const ch of item.selected_choices) {
      if (!ch) continue;
      const group = (ch.group_name || '').trim();
      const opt = (ch.option_name || ch.name || '').trim();
      const label = group ? `${group}: ${opt}` : opt;
      const price = typeof ch.price_delta === 'number' && ch.price_delta > 0 ? ch.price_delta : undefined;
      if (label && !selections.some(s => s.label === label)) {
        selections.push({ label, price });
      }
    }
  }

  // 3. Process removed_ingredients (array of strings)
  if (Array.isArray(item.removed_ingredients)) {
    for (const rem of item.removed_ingredients) {
      if (typeof rem === 'string' && rem.trim()) {
        const clean = rem.trim().replace(/^[-•\s]+/, '').replace(/^(no|without)\s+/i, '').trim();
        if (clean && !removals.includes(clean)) {
          removals.push(clean);
        }
      }
    }
  }

  return { addons, removals, selections };
};

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

  // Address parsing
  const formatAddressLines = (): string[] => {
    if (order.order_type !== 'DELIVERY' || !order.delivery_address) return [];
    const addr = order.delivery_address;
    const lines: string[] = [];
    if (typeof addr === 'string') {
      return addr.split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
    }
    if (typeof addr === 'object' && addr !== null) {
      if (addr.address_line1) lines.push(String(addr.address_line1).trim());
      if (addr.address_line2) lines.push(String(addr.address_line2).trim());
      if (addr.city) lines.push(String(addr.city).trim());
      const postAndCountry = [addr.postcode, addr.country || 'United Kingdom'].filter(Boolean).map(s => String(s).trim()).join(', ');
      if (postAndCountry) lines.push(postAndCountry);
      if (lines.length === 0 && addr.formatted_address) {
        return String(addr.formatted_address).split(/[\n,]+/).map(s => s.trim()).filter(Boolean);
      }
    }
    return lines;
  };

  const addressLines = formatAddressLines();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 text-black">
      <div className="thermal-receipt-80mm bg-white rounded-lg max-w-md w-full p-5 shadow-2xl font-mono text-xs text-left relative max-h-[90vh] overflow-y-auto">
        {/* Close Button (Screen Only) */}
        <div className="flex justify-end print:hidden mb-1">
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-zinc-200 rounded text-black cursor-pointer"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* 1. Centered Monochrome Logo */}
        <div className="flex justify-center mb-1">
          <img
            src="/logo.png"
            alt="Patty Project"
            className="w-16 h-16 object-contain filter grayscale contrast-200"
          />
        </div>

        {/* 2. Header: PATTY PROJECT (no UK) and Order Number */}
        <div className="text-center space-y-0.5">
          <h2 className="font-extrabold text-base tracking-wider uppercase">PATTY PROJECT</h2>
          <p className="text-xs font-semibold">Order: {order.order_number}</p>
        </div>

        <div className="border-b border-dashed border-zinc-400 my-2" />

        {/* 3. Customer Information */}
        {(order.customer_name || order.customer_phone) && (
          <>
            <div className="space-y-1 text-xs">
              <div className="font-bold tracking-wide uppercase text-[11px]">CUSTOMER</div>
              {order.customer_name && (
                <div className="flex gap-2">
                  <span className="w-12 text-zinc-700">Name</span>
                  <span>: {order.customer_name}</span>
                </div>
              )}
              {order.customer_phone && (
                <div className="flex gap-2">
                  <span className="w-12 text-zinc-700">Phone</span>
                  <span>: {order.customer_phone}</span>
                </div>
              )}
            </div>
            <div className="border-b border-dashed border-zinc-400 my-2" />
          </>
        )}

        {/* 4. Delivery Address or Order Type */}
        {addressLines.length > 0 ? (
          <>
            <div className="space-y-0.5 text-xs">
              <div className="font-bold tracking-wide uppercase text-[11px]">DELIVERY ADDRESS</div>
              {addressLines.map((line, lIdx) => (
                <div key={lIdx} className="break-words leading-tight">{line}</div>
              ))}
            </div>
            <div className="border-b border-dashed border-zinc-400 my-2" />
          </>
        ) : order.order_type === 'COLLECTION' ? (
          <>
            <div className="space-y-0.5 text-xs">
              <div className="font-bold tracking-wide uppercase text-[11px]">ORDER TYPE</div>
              <div className="font-semibold">COLLECTION</div>
              {order.collection_slot_time && (
                <div className="text-[11px] text-zinc-700">Slot: {new Date(order.collection_slot_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
              )}
            </div>
            <div className="border-b border-dashed border-zinc-400 my-2" />
          </>
        ) : null}

        {/* 5. Bill Title & Table Header */}
        <div className="text-center font-bold tracking-widest text-sm py-0.5">
          BILL
        </div>

        <div className="border-b border-dashed border-zinc-400 my-1" />

        <div className="flex justify-between items-center text-[11px] font-bold pb-0.5">
          <div className="flex gap-2">
            <span className="w-5">QTY</span>
            <span>ITEM & DETAILS</span>
          </div>
          <span>PRICE</span>
        </div>

        <div className="border-b border-dashed border-zinc-400 mb-2" />

        {/* 6. Items, Customizations, Add-ons, Removals, Selections */}
        <div className="space-y-2 py-0.5">
          {order.items && order.items.length > 0 ? (
            order.items.map((item, idx) => {
              const { addons, removals, selections } = parseCustomizations(item);
              const hasCustomizations = addons.length > 0 || removals.length > 0 || selections.length > 0;

              return (
                <div key={idx} className="space-y-1">
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex gap-2 flex-1 items-start">
                      <span className="font-bold w-5 shrink-0">{item.quantity}</span>
                      <span className="font-bold break-words flex-1 leading-snug">{item.product_name}</span>
                    </div>
                    <span className="font-bold shrink-0">
                      £{Number(item.total_price || 0).toFixed(2)}
                    </span>
                  </div>

                  {hasCustomizations && (
                    <div className="pl-7 text-[11px] space-y-1 leading-tight text-zinc-800">
                      {addons.length > 0 && (
                        <div>
                          <div className="font-semibold">• Add-ons:</div>
                          <div className="pl-3 space-y-0.5">
                            {addons.map((a, aIdx) => (
                              <div key={aIdx} className="flex justify-between">
                                <span>- {a.label}</span>
                                {a.price !== undefined && (
                                  <span>£{Number(a.price).toFixed(2)}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {removals.length > 0 && (
                        <div>
                          <div className="font-semibold">• Removals:</div>
                          <div className="pl-3 space-y-0.5">
                            {removals.map((r, rIdx) => (
                              <div key={rIdx}>- {r}</div>
                            ))}
                          </div>
                        </div>
                      )}

                      {selections.length > 0 && (
                        <div>
                          <div className="font-semibold">• Selections / Options:</div>
                          <div className="pl-3 space-y-0.5">
                            {selections.map((s, sIdx) => (
                              <div key={sIdx} className="flex justify-between">
                                <span>- {s.label}</span>
                                {s.price !== undefined && (
                                  <span>£{Number(s.price).toFixed(2)}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="flex justify-between items-start gap-2">
              <div className="flex gap-2 flex-1">
                <span className="font-bold w-5">1</span>
                <span className="font-bold">Standard Order</span>
              </div>
              <span className="font-bold">£{subtotalVal.toFixed(2)}</span>
            </div>
          )}
        </div>

        {/* 7. Totals & Discount */}
        <div className="border-t border-dashed border-zinc-400 pt-1.5 flex justify-between font-bold text-xs">
          <span>{totalItemsCount} ITEM(S)</span>
          <span>£{subtotalVal.toFixed(2)}</span>
        </div>

        {discountVal > 0 && (
          <div className="flex justify-between text-xs text-zinc-800 pt-0.5">
            <span>DISCOUNT {order.coupon_code ? `(${order.coupon_code})` : ''}</span>
            <span>-£{discountVal.toFixed(2)}</span>
          </div>
        )}

        <div className="border-t border-dashed border-zinc-400 my-1.5" />

        <div className="flex justify-between font-extrabold text-sm py-0.5">
          <span>AMOUNT DUE</span>
          <span>£{totalVal.toFixed(2)}</span>
        </div>

        <div className="border-b border-dashed border-zinc-400 my-1.5" />

        {/* 8. 4-Column VAT Breakdown */}
        <div className="space-y-1">
          <div className="grid grid-cols-4 font-bold text-[11px] pb-0.5">
            <span>Rate</span>
            <span className="text-right">Net</span>
            <span className="text-right">Tax</span>
            <span className="text-right">Gross</span>
          </div>
          <div className="border-b border-dashed border-zinc-300" />
          <div className="grid grid-cols-4 text-[11px]">
            <span>20%</span>
            <span className="text-right">£{netVal.toFixed(2)}</span>
            <span className="text-right">£{vatVal.toFixed(2)}</span>
            <span className="text-right">£{grossVal.toFixed(2)}</span>
          </div>
        </div>

        <div className="border-b border-dashed border-zinc-400 my-2" />

        {/* 9. Legal Notice */}
        <div className="text-center text-[10px]">
          <p className="font-semibold">Tax are included in the Gross amount!</p>
        </div>

        <div className="border-b border-dashed border-zinc-400 my-2" />

        <div className="text-center text-[11px] font-bold tracking-wider">
          VAT NO: 525 5772 74
        </div>

        <div className="border-b border-dashed border-zinc-400 my-2" />

        {/* 10. Receipt Thank You Footer */}
        <div className="text-center text-[11px] space-y-0.5 text-zinc-800">
          <p>Thank you for your order!</p>
          <p>We hope to serve you again.</p>
        </div>

        <div className="border-b border-dashed border-zinc-400 mt-2 mb-3" />

        {/* Action Buttons (Print / Close) */}
        <div className="pt-1 flex gap-2 print:hidden">
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
