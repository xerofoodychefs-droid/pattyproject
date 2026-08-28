import React, { useState, useEffect, useMemo } from 'react';
import { Share2, X, Check, Plus, Minus, ShoppingCart, Sliders } from 'lucide-react';
import { Product, ProductModifier } from '../../types';
import { useCartStore } from '../../store/cartStore';

interface Props {
  product: Product;
  onClose: () => void;
}

export const ProductDetailModal: React.FC<Props> = ({ product, onClose }) => {
  const [selectedModifiers, setSelectedModifiers] = useState<ProductModifier[]>([]);
  const [removedIngredients, setRemovedIngredients] = useState<string[]>([]);
  const [quantity, setQuantity] = useState<number>(1);
  const { items, addItem, setProductModalOpen } = useCartStore();

  // Parse product ingredients list
  const ingredientOptions = useMemo(() => {
    if (!product.ingredients) return [];
    if (Array.isArray(product.ingredients)) return product.ingredients.filter(Boolean);
    if (typeof product.ingredients === 'string') {
      return (product.ingredients as string)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  }, [product.ingredients]);

  const toggleRemoveIngredient = (ing: string) => {
    if (removedIngredients.includes(ing)) {
      setRemovedIngredients(removedIngredients.filter((i) => i !== ing));
    } else {
      setRemovedIngredients([...removedIngredients, ing]);
    }
  };

  // Calculate how many pieces of this product are already in cart
  const inCartQuantity = items
    .filter((item) => item.product.id === product.id)
    .reduce((sum, item) => sum + item.quantity, 0);

  // Set modal open state in store on mount, reset on unmount
  useEffect(() => {
    setProductModalOpen(true);
    return () => {
      setProductModalOpen(false);
    };
  }, [setProductModalOpen]);

  // Fallback options list matching reference structure
  const availableModifiers: (ProductModifier & { is_out_of_stock?: boolean; is_veg?: boolean })[] =
    product.modifiers && product.modifiers.length > 0
      ? product.modifiers
      : [
          { id: 'mod-1', name: 'Coke Zero', price: 0.00, is_required: false, is_active: true, is_out_of_stock: true, is_veg: true },
          { id: 'mod-2', name: 'Coke', price: 1.50, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-3', name: 'Thums Up', price: 1.50, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-4', name: 'Lemon Flippinade', price: 2.00, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-5', name: 'Cranberry Flippinade', price: 2.00, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-6', name: 'Passionfruit Flippinade', price: 2.00, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-7', name: 'Fries', price: 2.50, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-8', name: 'Potato Wedges', price: 2.50, is_required: false, is_active: true, is_veg: true },
          { id: 'mod-9', name: 'Peri Fries', price: 2.80, is_required: false, is_active: true, is_veg: true },
        ];

  const toggleModifier = (mod: ProductModifier & { is_out_of_stock?: boolean }) => {
    if (mod.is_out_of_stock) return;
    if (selectedModifiers.some((m) => m.id === mod.id)) {
      setSelectedModifiers(selectedModifiers.filter((m) => m.id !== mod.id));
    } else {
      setSelectedModifiers([...selectedModifiers, mod]);
    }
  };

  const modTotal = selectedModifiers.reduce((sum, m) => sum + m.price, 0);
  const unitPrice = product.base_price + modTotal;
  const totalPrice = unitPrice * quantity;

  const isProductOutOfStock = product.is_available === false || (product.stock_quantity !== undefined && product.stock_quantity <= 0);

  const handleAddToCart = () => {
    if (isProductOutOfStock || quantity < 1) return;
    addItem(product, quantity, selectedModifiers, removedIngredients);
    onClose();
  };

  const isVegProduct =
    product.name.toLowerCase().includes('veg') ||
    product.name.toLowerCase().includes('cheese') ||
    product.name.toLowerCase().includes('halloumi') ||
    product.name.toLowerCase().includes('fries') ||
    product.name.toLowerCase().includes('drink') ||
    product.name.toLowerCase().includes('coke');

  const defaultImg = product.image_url || '/placeholder-burger.svg';

  return (
    <div className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 md:p-6 overflow-y-auto animate-in fade-in duration-150">
      {/* Click Outside Backdrop Listener */}
      <div className="fixed inset-0" onClick={onClose} />

      {/* Main Modal Surface */}
      <div className="bg-[#0D0D0D] text-[#F5F5F5] rounded-t-[12px] sm:rounded-[12px] max-w-2xl lg:max-w-3xl w-full shadow-2xl overflow-hidden relative z-10 border border-[#242424] flex flex-col md:flex-row max-h-[90vh] animate-in zoom-in-95 duration-150">
        
        {/* LEFT COLUMN: Product Image & Details */}
        <div className="w-full md:w-1/2 flex flex-col justify-between border-b md:border-b-0 md:border-r border-[#242424] bg-[#0D0D0D] overflow-y-auto">
          <div className="p-4 sm:p-5 space-y-3.5">
            
            {/* Top Action Header with Share & Close buttons */}
            <div className="flex items-center justify-between pb-1">
              {/* Dietary & Cart Status Badges */}
              <div className="flex items-center gap-2 flex-wrap">
                {isVegProduct && (
                  <div className="flex items-center gap-1.5 bg-[#22C55E]/10 border border-[#22C55E]/30 px-2 py-0.5 rounded-md">
                    <div className="w-2 h-2 rounded-full bg-[#22C55E]" />
                    <span className="text-[11px] text-[#22C55E] font-semibold">Veg</span>
                  </div>
                )}
                {inCartQuantity > 0 && (
                  <div className="flex items-center gap-1.5 bg-[#FF5A00]/15 border border-[#FF5A00]/40 text-[#FF5A00] text-[11px] font-bold px-2 py-0.5 rounded-md">
                    <ShoppingCart className="w-3 h-3" />
                    <span>{inCartQuantity} already in cart</span>
                  </div>
                )}
              </div>

              {/* Control Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (navigator.share) {
                      navigator.share({
                        title: product.name,
                        text: `Check out ${product.name} at Patty Project!`,
                        url: window.location.href,
                      }).catch(() => {});
                    } else {
                      navigator.clipboard.writeText(window.location.href);
                    }
                  }}
                  className="w-8 h-8 rounded-full bg-[#181818] border border-[#2A2A2A] text-[#A1A1AA] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
                  title="Share"
                  aria-label="Share"
                >
                  <Share2 className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={onClose}
                  className="w-8 h-8 rounded-full bg-[#181818] border border-[#2A2A2A] text-[#A1A1AA] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
                  title="Close"
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Product Image Frame */}
            <div className="w-full h-44 sm:h-52 rounded-xl overflow-hidden bg-[#151515] border border-[#242424] relative flex items-center justify-center">
              <img
                src={defaultImg}
                alt={product.name}
                onError={(e) => {
                  (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                }}
                className={`w-full h-full object-cover transition-transform duration-300 hover:scale-105 ${
                  isProductOutOfStock ? 'grayscale opacity-50' : ''
                }`}
              />
              {isProductOutOfStock && (
                <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                  <span className="bg-[#EF4444] text-white text-xs font-bold px-3 py-1 rounded uppercase tracking-wider">
                    Out of Stock
                  </span>
                </div>
              )}
            </div>

            {/* Product Info */}
            <div className="space-y-2 pt-1">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-lg sm:text-xl font-bold text-[#F5F5F5] leading-snug">
                  {product.name}
                </h2>
                <span className={`text-lg font-bold shrink-0 ${isProductOutOfStock ? 'text-[#71717A]' : 'text-[#FF5A00]'}`}>
                  £{product.base_price.toFixed(2)}
                </span>
              </div>

              {isProductOutOfStock && (
                <span className="inline-block bg-[#EF4444]/10 border border-[#EF4444]/25 text-[#EF4444] text-xs font-semibold px-2.5 py-1 rounded-md">
                  Currently unavailable at this branch
                </span>
              )}

              <p className="text-xs sm:text-sm text-[#A1A1AA] font-normal leading-relaxed">
                {product.short_description ||
                  product.full_description ||
                  'Made fresh to order with top-tier premium ingredients.'}
              </p>

              {product.allergens && (
                <p className="text-[11px] text-[#71717A] italic pt-1">
                  Allergens: {product.allergens}
                </p>
              )}
            </div>
          </div>

          {/* Desktop Bottom Action CTA Bar with Quantity Stepper */}
          <div className="hidden md:block p-5 bg-[#0D0D0D] border-t border-[#242424] shrink-0">
            {isProductOutOfStock ? (
              <button
                disabled
                className="h-12 bg-[#18181B] border border-[#27272A] text-[#71717A] rounded-lg px-5 flex items-center justify-between font-semibold text-sm cursor-not-allowed w-full select-none"
              >
                <span className="line-through opacity-70">£{totalPrice.toFixed(2)}</span>
                <span className="text-[#EF4444] font-bold uppercase tracking-wider">Out of Stock</span>
              </button>
            ) : (
              <div className="flex items-center gap-3">
                {/* Quantity Stepper */}
                <div className="flex items-center bg-[#151515] border border-[#2A2A2A] rounded-lg p-1">
                  <button
                    type="button"
                    onClick={() => setQuantity((prev) => Math.max(1, prev - 1))}
                    disabled={quantity <= 1}
                    className="w-9 h-9 rounded-md bg-[#202020] hover:bg-[#2A2A2A] active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed text-white flex items-center justify-center transition-all cursor-pointer"
                    title="Decrease quantity"
                    aria-label="Decrease quantity"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span className="font-bold text-sm min-w-[32px] text-center text-white select-none px-1">
                    {quantity}
                  </span>
                  <button
                    type="button"
                    onClick={() => setQuantity((prev) => prev + 1)}
                    className="w-9 h-9 rounded-md bg-[#202020] hover:bg-[#2A2A2A] active:scale-95 text-white flex items-center justify-center transition-all cursor-pointer"
                    title="Increase quantity"
                    aria-label="Increase quantity"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Add to Cart Button */}
                <button
                  onClick={handleAddToCart}
                  className="flex-1 h-11 bg-[#FF5A00] hover:bg-[#E84F00] active:scale-[0.99] text-white rounded-lg px-4 flex items-center justify-between font-semibold text-sm transition-all cursor-pointer shadow-lg focus:outline-none focus:ring-2 focus:ring-[#FF5A00]/50"
                >
                  <span className="font-bold">£{totalPrice.toFixed(2)}</span>
                  <span>Add {quantity} {quantity === 1 ? 'piece' : 'pieces'} to cart</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Customization Options List */}
        <div className="w-full md:w-1/2 flex flex-col bg-[#121212] overflow-hidden flex-1">
          
          {/* Customization Section Header */}
          <div className="p-4 sm:p-5 border-b border-[#242424] flex items-center justify-between bg-[#121212] sticky top-0 z-10 shrink-0">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-base text-[#F5F5F5]">
                  Customize Your Meal
                </h3>
                <span className="text-[11px] font-medium text-[#A1A1AA] bg-[#151515] border border-[#242424] px-2 py-0.5 rounded">
                  Optional
                </span>
              </div>
              <p className="text-xs text-[#71717A] mt-0.5">
                Remove unwanted ingredients or add delicious extras
              </p>
            </div>
          </div>

          {/* Scrollable Option Cards List */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5 bg-[#121212]">
            
            {/* 1. CUSTOMIZE / REMOVE INGREDIENTS SECTION */}
            {ingredientOptions.length > 0 && (
              <div className="space-y-3 pb-4 border-b border-[#242424]">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-[#FF5A00]" />
                    <h4 className="font-bold text-xs text-[#F5F5F5] uppercase tracking-wider">
                      Ingredients (Untick to Remove)
                    </h4>
                  </div>
                  {removedIngredients.length > 0 && (
                    <span className="text-[10px] bg-[#EF4444]/20 border border-[#EF4444]/30 text-[#FCA5A5] px-2 py-0.5 rounded font-bold">
                      {removedIngredients.length} Removed
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {ingredientOptions.map((ing) => {
                    const isRemoved = removedIngredients.includes(ing);
                    return (
                      <button
                        key={ing}
                        type="button"
                        onClick={() => toggleRemoveIngredient(ing)}
                        className={`p-2.5 rounded-xl border text-left flex items-center justify-between transition-all cursor-pointer select-none ${
                          isRemoved
                            ? 'border-[#EF4444]/40 bg-[#2A1215] text-[#FCA5A5]'
                            : 'border-[#262626] bg-[#171717] hover:border-[#3A3A3A] hover:bg-[#1E1E1E] text-[#F5F5F5]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5 min-w-0 flex-1">
                          <div
                            className={`w-4 h-4 rounded-md flex items-center justify-center border transition-colors shrink-0 ${
                              isRemoved
                                ? 'border-[#EF4444] bg-[#EF4444] text-white'
                                : 'border-[#22C55E] bg-[#22C55E]/20 text-[#22C55E]'
                            }`}
                          >
                            {isRemoved ? (
                              <X className="w-3 h-3 stroke-[3]" />
                            ) : (
                              <Check className="w-3 h-3 stroke-[3]" />
                            )}
                          </div>
                          <span className={`text-xs font-semibold truncate ${isRemoved ? 'line-through opacity-70' : ''}`}>
                            {ing}
                          </span>
                        </div>
                        {isRemoved && (
                          <span className="text-[9px] font-bold uppercase tracking-wider bg-[#EF4444] text-white px-1.5 py-0.5 rounded ml-1 shrink-0">
                            NO {ing}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 2. ADD-ONS / MODIFIERS SECTION */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-xs text-[#F5F5F5] uppercase tracking-wider">
                  Add Extras & Sides
                </h4>
              </div>

              <div className="space-y-2">
                {availableModifiers.map((mod) => {
                  const isSelected = selectedModifiers.some((m) => m.id === mod.id);
                  const isOutOfStock = mod.is_out_of_stock;

                  return (
                    <div
                      key={mod.id}
                      onClick={() => toggleModifier(mod)}
                      className={`border rounded-xl p-3 min-h-[50px] flex items-center justify-between transition-all select-none ${
                        isOutOfStock
                          ? 'border-[#242424] bg-[#151515]/50 opacity-40 cursor-not-allowed'
                          : isSelected
                          ? 'border-[#6B2A0D] bg-[#241209] text-[#F5F5F5] cursor-pointer'
                          : 'border-[#242424] bg-[#151515] hover:border-[#333333] hover:bg-[#181818] text-[#A1A1AA] cursor-pointer'
                      }`}
                    >
                      {/* Left Option Info */}
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors shrink-0 ${
                            isSelected
                              ? 'border-[#FF5A00] bg-[#FF5A00] text-white'
                              : 'border-[#242424] bg-[#0D0D0D]'
                          }`}
                        >
                          {isSelected && <Check className="w-3.5 h-3.5 stroke-[2.5]" />}
                        </div>

                        <div>
                          <p className={`text-sm font-medium ${isSelected ? 'text-[#F5F5F5]' : 'text-[#F5F5F5]'}`}>
                            {mod.name}
                          </p>
                          {isOutOfStock && (
                            <span className="text-[11px] font-semibold text-[#EF4444] block mt-0.5">
                              OUT OF STOCK
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Right Option Price */}
                      {!isOutOfStock && mod.price > 0 && (
                        <span className="text-xs font-semibold text-[#FF5A00] shrink-0">
                          +£{mod.price.toFixed(2)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

          </div>

          {/* Mobile Bottom Action CTA Bar (Pinned at bottom) with Quantity Stepper */}
          <div className="md:hidden p-4 bg-[#0D0D0D] border-t border-[#242424] shrink-0 sticky bottom-0 z-30">
            {isProductOutOfStock ? (
              <button
                disabled
                className="h-12 bg-[#18181B] border border-[#27272A] text-[#71717A] rounded-lg px-5 flex items-center justify-between font-semibold text-sm cursor-not-allowed w-full select-none"
              >
                <span className="line-through opacity-70">£{totalPrice.toFixed(2)}</span>
                <span className="text-[#EF4444] font-bold uppercase tracking-wider">Out of Stock</span>
              </button>
            ) : (
              <div className="flex items-center gap-2.5">
                {/* Quantity Stepper */}
                <div className="flex items-center bg-[#151515] border border-[#2A2A2A] rounded-lg p-1">
                  <button
                    type="button"
                    onClick={() => setQuantity((prev) => Math.max(1, prev - 1))}
                    disabled={quantity <= 1}
                    className="w-9 h-9 rounded-md bg-[#202020] hover:bg-[#2A2A2A] active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed text-white flex items-center justify-center transition-all cursor-pointer"
                    title="Decrease quantity"
                    aria-label="Decrease quantity"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span className="font-bold text-sm min-w-[28px] text-center text-white select-none px-1">
                    {quantity}
                  </span>
                  <button
                    type="button"
                    onClick={() => setQuantity((prev) => prev + 1)}
                    className="w-9 h-9 rounded-md bg-[#202020] hover:bg-[#2A2A2A] active:scale-95 text-white flex items-center justify-center transition-all cursor-pointer"
                    title="Increase quantity"
                    aria-label="Increase quantity"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Add to Cart Button */}
                <button
                  onClick={handleAddToCart}
                  className="flex-1 h-11 bg-[#FF5A00] hover:bg-[#E84F00] active:scale-[0.99] text-white rounded-lg px-4 flex items-center justify-between font-semibold text-sm transition-all cursor-pointer shadow-lg focus:outline-none focus:ring-2 focus:ring-[#FF5A00]/50"
                >
                  <span className="font-bold">£{totalPrice.toFixed(2)}</span>
                  <span>Add {quantity} {quantity === 1 ? 'pc' : 'pcs'}</span>
                </button>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default ProductDetailModal;
