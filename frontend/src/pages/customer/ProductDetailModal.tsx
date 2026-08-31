import React, { useState, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { Share2, X, Check, Plus, Minus, ShoppingCart, Sliders, Utensils } from 'lucide-react';
import { Product, ProductModifier, ProductChoiceGroup, ProductChoiceOption, SelectedChoice } from '../../types';
import { useCartStore } from '../../store/cartStore';
import { useShopHoursStore, formatTime12h } from '../../store/shopHoursStore';

interface Props {
  product: Product;
  onClose: () => void;
}

export const ProductDetailModal: React.FC<Props> = ({ product, onClose }) => {
  const [selectedModifiers, setSelectedModifiers] = useState<ProductModifier[]>([]);
  const [selectedChoices, setSelectedChoices] = useState<SelectedChoice[]>([]);
  const [removedIngredients, setRemovedIngredients] = useState<string[]>([]);
  const [quantity, setQuantity] = useState<number>(1);
  const { items, addItem, setProductModalOpen } = useCartStore();
  const { isOpen, openingTime } = useShopHoursStore();

  const choiceGroups = useMemo(() => product.choice_groups || [], [product.choice_groups]);

  // Check if any required group is not satisfied
  const unsatisfiedGroup = useMemo(() => {
    return choiceGroups.find((grp) => {
      const count = selectedChoices.filter((c) => c.group_id === grp.id).length;
      return grp.is_required && count < grp.min_selections;
    });
  }, [choiceGroups, selectedChoices]);

  const isChoiceRequirementSatisfied = !unsatisfiedGroup;

  const toggleChoice = (grp: ProductChoiceGroup, opt: ProductChoiceOption) => {
    if (!opt.is_active) return;
    const currentForGroup = selectedChoices.filter((c) => c.group_id === grp.id);
    const isAlreadySelected = currentForGroup.some((c) => c.option_id === opt.id);

    if (isAlreadySelected) {
      setSelectedChoices(selectedChoices.filter((c) => !(c.group_id === grp.id && c.option_id === opt.id)));
    } else {
      if (grp.max_selections === 1) {
        const otherChoices = selectedChoices.filter((c) => c.group_id !== grp.id);
        setSelectedChoices([
          ...otherChoices,
          {
            group_id: grp.id,
            group_name: grp.name,
            option_id: opt.id,
            option_name: opt.name,
            price_delta: opt.price_delta || 0.0
          }
        ]);
      } else {
        if (currentForGroup.length >= grp.max_selections) {
          alert(`You can select up to ${grp.max_selections} items for ${grp.name}.`);
          return;
        }
        setSelectedChoices([
          ...selectedChoices,
          {
            group_id: grp.id,
            group_name: grp.name,
            option_id: opt.id,
            option_name: opt.name,
            price_delta: opt.price_delta || 0.0
          }
        ]);
      }
    }
  };

  // Reset selections when viewing a different product
  useEffect(() => {
    setSelectedModifiers([]);
    setSelectedChoices([]);
    setRemovedIngredients([]);
    setQuantity(1);
  }, [product.id]);

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

  // Scroll position capture, body scroll lock, Escape key listener, and modal open state in store
  useEffect(() => {
    const scrollY = window.scrollY || window.pageYOffset || document.documentElement.scrollTop || 0;
    const originalOverflow = document.body.style.overflow;
    const originalPaddingRight = document.body.style.paddingRight;

    // Calculate scrollbar width to avoid layout shift when scrollbar is hidden
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
    if (scrollbarWidth > 0) {
      document.body.style.paddingRight = `${scrollbarWidth}px`;
    }
    document.body.style.overflow = 'hidden';
    setProductModalOpen(true);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = originalOverflow;
      document.body.style.paddingRight = originalPaddingRight;
      setProductModalOpen(false);
      window.scrollTo({
        top: scrollY,
        behavior: 'instant' as ScrollBehavior,
      });
    };
  }, [setProductModalOpen, onClose]);

  // Modifiers configured by Admin for this specific product (no hardcoded fallbacks)
  const availableModifiers = useMemo(() => {
    if (!product.modifiers || !Array.isArray(product.modifiers)) {
      return [];
    }
    return product.modifiers.filter(
      (modifier) => modifier && modifier.is_active !== false
    );
  }, [product.modifiers]);

  const toggleModifier = (mod: ProductModifier & { is_out_of_stock?: boolean }) => {
    if (mod.is_out_of_stock) return;
    if (selectedModifiers.some((m) => m.id === mod.id)) {
      setSelectedModifiers(selectedModifiers.filter((m) => m.id !== mod.id));
    } else {
      setSelectedModifiers([...selectedModifiers, mod]);
    }
  };

  const modTotal = selectedModifiers.reduce((sum, m) => sum + m.price, 0);
  const choiceTotal = selectedChoices.reduce((sum, c) => sum + c.price_delta, 0);
  const unitPrice = product.base_price + modTotal + choiceTotal;
  const totalPrice = unitPrice * quantity;

  const isProductOutOfStock = product.is_out_of_stock === true || product.is_available === false || (product.stock_quantity !== undefined && product.stock_quantity <= 0);

  const handleAddToCart = () => {
    if (isProductOutOfStock || quantity < 1 || !isChoiceRequirementSatisfied) return;
    addItem(product, quantity, selectedModifiers, removedIngredients, selectedChoices);
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

  const modalContent = (
    <div
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-3 sm:p-4 md:p-6 overflow-hidden animate-in fade-in duration-150"
      role="dialog"
      aria-modal="true"
      aria-labelledby={`product-title-${product.id}`}
    >
      {/* Click Outside Backdrop Listener */}
      <div
        className="absolute inset-0 cursor-pointer"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Main Modal Surface */}
      <div
        onClick={(e) => e.stopPropagation()}
        className="bg-[#0D0D0D] text-[#F5F5F5] rounded-xl sm:rounded-2xl max-w-2xl lg:max-w-3xl w-full shadow-2xl overflow-hidden relative z-10 border border-[#242424] flex flex-col md:flex-row max-h-[calc(100dvh-1.5rem)] sm:max-h-[90vh] animate-in zoom-in-95 duration-150 overscroll-contain"
      >
        
        {/* LEFT COLUMN: Product Image & Details */}
        <div className="w-full md:w-1/2 flex flex-col justify-between border-b md:border-b-0 md:border-r border-[#242424] bg-[#0D0D0D] overflow-y-auto max-h-[35vh] sm:max-h-[40vh] md:max-h-none shrink-0 md:shrink overscroll-contain">
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
                <h2 id={`product-title-${product.id}`} className="text-lg sm:text-xl font-bold text-[#F5F5F5] leading-snug">
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
            {!isOpen ? (
              <button
                disabled
                className="h-12 bg-[#18181B] border border-red-900/50 text-[#A1A1AA] rounded-lg px-5 flex items-center justify-between font-semibold text-sm cursor-not-allowed w-full select-none"
              >
                <span className="text-white font-bold">£{totalPrice.toFixed(2)}</span>
                <span className="text-red-400 font-bold uppercase tracking-wider">
                  Shop Closed (Opens at {formatTime12h(openingTime)})
                </span>
              </button>
            ) : isProductOutOfStock ? (
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
                  disabled={!isChoiceRequirementSatisfied}
                  className={`flex-1 h-11 rounded-lg px-4 flex items-center justify-between font-semibold text-sm transition-all shadow-lg focus:outline-none ${
                    isChoiceRequirementSatisfied
                      ? 'bg-[#FF5A00] hover:bg-[#E84F00] active:scale-[0.99] text-white cursor-pointer focus:ring-2 focus:ring-[#FF5A00]/50'
                      : 'bg-[#242424] text-[#71717A] cursor-not-allowed border border-[#333333]'
                  }`}
                >
                  <span className="font-bold">£{totalPrice.toFixed(2)}</span>
                  <span>
                    {isChoiceRequirementSatisfied
                      ? `Add ${quantity} ${quantity === 1 ? 'piece' : 'pieces'} to cart`
                      : unsatisfiedGroup?.min_selections === unsatisfiedGroup?.max_selections
                      ? `Select ${unsatisfiedGroup?.min_selections} items to add`
                      : `Select ${unsatisfiedGroup?.name || 'choices'}`}
                  </span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT COLUMN: Customization Options List */}
        <div className="w-full md:w-1/2 flex flex-col bg-[#121212] overflow-hidden flex-1 min-h-0">
          
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
          <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-5 space-y-5 bg-[#121212] overscroll-contain">
            
            {/* 0. CHOICE GROUPS SECTION (e.g. Choose any 2, Choose your rasher) */}
            {choiceGroups.length > 0 && (
              <div className="space-y-5 pb-4 border-b border-[#242424]">
                {choiceGroups.map((grp) => {
                  const currentForGrp = selectedChoices.filter((c) => c.group_id === grp.id);
                  const count = currentForGrp.length;
                  const isSatisfied = !grp.is_required || count >= grp.min_selections;

                  return (
                    <div key={grp.id} className="space-y-2.5">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Utensils className="w-4 h-4 text-[#FF5A00]" />
                          <h4 className="font-bold text-xs text-[#F5F5F5] uppercase tracking-wider">
                            {grp.name}
                          </h4>
                          {grp.is_required && (
                            <span className="text-[10px] text-[#FF5A00] font-bold">*Required</span>
                          )}
                        </div>
                        <span
                          className={`text-[11px] px-2 py-0.5 rounded font-bold border ${
                            isSatisfied
                              ? 'bg-[#10B981]/15 text-[#34D399] border-[#10B981]/30'
                              : 'bg-[#FF5A00]/15 text-[#FF5A00] border-[#FF5A00]/30'
                          }`}
                        >
                          {grp.min_selections === grp.max_selections
                            ? `Selected: ${count} / ${grp.max_selections}`
                            : `Selected: ${count} (Max ${grp.max_selections})`}
                        </span>
                      </div>

                      <div className="space-y-2">
                        {grp.options.map((opt) => {
                          const isSelected = currentForGrp.some((c) => c.option_id === opt.id);
                          const isUnavailable = !opt.is_active;

                          return (
                            <div
                              key={opt.id}
                              onClick={() => toggleChoice(grp, opt)}
                              className={`border rounded-xl p-3 min-h-[50px] flex items-center justify-between transition-all select-none ${
                                isUnavailable
                                  ? 'border-[#242424] bg-[#151515]/50 opacity-40 cursor-not-allowed'
                                  : isSelected
                                  ? 'border-[#FF5A00] bg-[#FF5A00]/10 text-[#F5F5F5] cursor-pointer'
                                  : 'border-[#242424] bg-[#151515] hover:border-[#333333] hover:bg-[#181818] text-[#A1A1AA] cursor-pointer'
                              }`}
                            >
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
                                  <p className="text-sm font-medium text-[#F5F5F5]">
                                    {opt.name}
                                  </p>
                                  {isUnavailable && (
                                    <span className="text-[11px] font-semibold text-[#EF4444] block mt-0.5">
                                      UNAVAILABLE
                                    </span>
                                  )}
                                </div>
                              </div>

                              {!isUnavailable && opt.price_delta > 0 && (
                                <span className="text-xs font-semibold text-[#FF5A00] shrink-0">
                                  +£{opt.price_delta.toFixed(2)}
                                </span>
                              )}
                              {!isUnavailable && (!opt.price_delta || opt.price_delta === 0) && (
                                <span className="text-[11px] font-medium text-[#71717A] shrink-0">
                                  Included
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            
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

            {/* 2. ADD-ONS / MODIFIERS SECTION (Rendered ONLY if admin configured modifiers for this product) */}
            {availableModifiers.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-bold text-xs text-[#F5F5F5] uppercase tracking-wider">
                    Add Extras & Sides
                  </h4>
                </div>

                <div className="space-y-2">
                  {availableModifiers.map((mod) => {
                    const isSelected = selectedModifiers.some((m) => m.id === mod.id);
                    const isOutOfStock = (mod as any).is_out_of_stock;

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
            )}

            {/* Empty Customization State (When item has no choices, ingredients, or modifiers) */}
            {choiceGroups.length === 0 && ingredientOptions.length === 0 && availableModifiers.length === 0 && (
              <div className="py-12 px-4 text-center space-y-3">
                <div className="w-12 h-12 rounded-full bg-[#181818] border border-[#262626] flex items-center justify-center mx-auto text-[#FF5A00]">
                  <Check className="w-6 h-6 stroke-[2.5]" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-bold text-white">Signature Recipe</p>
                  <p className="text-xs text-[#71717A] max-w-xs mx-auto">
                    This item is prepared fresh to our signature recipe with no additional customization required.
                  </p>
                </div>
              </div>
            )}

          </div>

          {/* Mobile Bottom Action CTA Bar (Pinned at bottom) with Quantity Stepper */}
          <div className="md:hidden p-4 bg-[#0D0D0D] border-t border-[#242424] shrink-0 sticky bottom-0 z-30">
            {!isOpen ? (
              <button
                disabled
                className="h-12 bg-[#18181B] border border-red-900/50 text-[#A1A1AA] rounded-lg px-5 flex items-center justify-between font-semibold text-sm cursor-not-allowed w-full select-none"
              >
                <span className="text-white font-bold">£{totalPrice.toFixed(2)}</span>
                <span className="text-red-400 font-bold uppercase tracking-wider">
                  Shop Closed (Opens at {formatTime12h(openingTime)})
                </span>
              </button>
            ) : isProductOutOfStock ? (
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
                  disabled={!isChoiceRequirementSatisfied}
                  className={`flex-1 h-11 rounded-lg px-4 flex items-center justify-between font-semibold text-sm transition-all shadow-lg focus:outline-none ${
                    isChoiceRequirementSatisfied
                      ? 'bg-[#FF5A00] hover:bg-[#E84F00] active:scale-[0.99] text-white cursor-pointer focus:ring-2 focus:ring-[#FF5A00]/50'
                      : 'bg-[#242424] text-[#71717A] cursor-not-allowed border border-[#333333]'
                  }`}
                >
                  <span className="font-bold">£{totalPrice.toFixed(2)}</span>
                  <span>
                    {isChoiceRequirementSatisfied
                      ? `Add ${quantity} ${quantity === 1 ? 'pc' : 'pcs'}`
                      : unsatisfiedGroup?.min_selections === unsatisfiedGroup?.max_selections
                      ? `Select ${unsatisfiedGroup?.min_selections} items to add`
                      : `Select ${unsatisfiedGroup?.name || 'choices'}`}
                  </span>
                </button>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
};

export default ProductDetailModal;
