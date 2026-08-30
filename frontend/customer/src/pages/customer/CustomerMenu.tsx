import React, { useEffect, useState, useMemo } from 'react';
import {
  Plus,
  LayoutGrid,
  Beef,
  Drumstick,
  UtensilsCrossed,
  Flame,
  CupSoda,
  Sparkles,
} from 'lucide-react';
import { api } from '../../api/client';
import { Product, Category, Branch } from '../../types';
import { ProductDetailModal } from './ProductDetailModal';
import { useCartStore } from '../../store/cartStore';
import { useProductRealtime } from '../../hooks/useProductRealtime';

interface OfferCard {
  id: string;
  title: string;
  subtitle: string;
  badge: string;
  image_url: string;
  price?: number;
  code?: string;
  isCombo?: boolean;
}

const DEFAULT_OFFERS: OfferCard[] = [];

export const CustomerMenu: React.FC = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [offerCards, setOfferCards] = useState<OfferCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const { selectedBranch, setSelectedBranch } = useCartStore();

  // Realtime product availability subscription (Zero-refresh immediate update)
  useProductRealtime({
    onProductAvailabilityChange: (productId: string, isOutOfStock: boolean) => {
      const boolOutOfStock = Boolean(isOutOfStock);
      setProducts((prev) =>
        prev.map((p) => {
          if (p.id !== productId) return p;
          return {
            ...p,
            is_out_of_stock: boolOutOfStock,
            is_available: !boolOutOfStock,
            stock_quantity: boolOutOfStock ? 0 : (p.stock_quantity && p.stock_quantity > 0 ? p.stock_quantity : 100),
          };
        })
      );
      setSelectedProduct((prev) => {
        if (!prev || prev.id !== productId) return prev;
        return {
          ...prev,
          is_out_of_stock: boolOutOfStock,
          is_available: !boolOutOfStock,
          stock_quantity: boolOutOfStock ? 0 : (prev.stock_quantity && prev.stock_quantity > 0 ? prev.stock_quantity : 100),
        };
      });
    },
    onReconnect: () => {
      const currentBranch = useCartStore.getState().selectedBranch;
      const branchParam = currentBranch?.id ? `?branch_id=${currentBranch.id}&_t=${Date.now()}` : `?_t=${Date.now()}`;
      api.get<Product[]>(`/products${branchParam}`).then((data) => {
        if (data && Array.isArray(data)) {
          setProducts((prev) => {
            const map = new Map(data.map((item) => [item.id, item]));
            return prev.map((p) => {
              const updated = map.get(p.id);
              return updated ? { ...p, ...updated } : p;
            });
          });
        }
      }).catch(() => {});
    },
  });

  useEffect(() => {
    let isMounted = true;

    const loadAllMenuData = async () => {
      try {
        let currentBranch = useCartStore.getState().selectedBranch;
        const branchParam = currentBranch?.id ? `?branch_id=${currentBranch.id}` : '';

        // Concurrent high-speed data fetch (All 6 requests fully parallelized)
        const [branchData, catData, prodData, todayData, pageOffersData, comboData] = await Promise.all([
          api.get<Branch[]>('/branches').catch(() => []),
          api.get<Category[]>('/categories').catch(() => []),
          api.get<Product[]>(`/products${branchParam}`).catch(() => []),
          api.get<any>('/promotions/settings/todays-offers').catch(() => null),
          api.get<any>('/promotions/settings/offers-page').catch(() => null),
          api.get<any>('/promotions/settings/combo-deals').catch(() => null)
        ]);

        if (!isMounted) return;

        // Authoritative branch UUID reconciliation in background
        const activeBranches = (branchData || []).filter((b) => b.is_active !== false);
        if (activeBranches.length > 0) {
          useCartStore.getState().reconcileActiveBranches(activeBranches);
          if (!currentBranch) {
            currentBranch = activeBranches[0];
            setSelectedBranch(currentBranch, null, false, currentBranch);
          }
        }

        let currentCategories = Array.isArray(catData) ? [...catData] : [];
        let currentProducts = Array.isArray(prodData) ? [...prodData] : [];

        // Find or create Combo category
        let comboCategory = currentCategories.find(c => c.slug?.includes('combo') || c.name?.toLowerCase().includes('combo'));
        if (!comboCategory && comboData?.combos && comboData.combos.length > 0) {
          comboCategory = {
            id: 'category-combo-offers',
            name: 'Combo Offers',
            slug: 'combo-offers',
            display_order: 0
          };
          currentCategories.unshift(comboCategory);
        }

        // Merge active combo deals into menu products list
        if (comboData?.combos && Array.isArray(comboData.combos)) {
          const activeCombos = comboData.combos.filter((c: any) => c.is_active !== false);
          
          activeCombos.forEach((c: any) => {
            const existingIdx = currentProducts.findIndex(
              p => p.id === c.id || p.sku === `COMBO-${c.id}` || p.name.trim().toLowerCase() === c.name.trim().toLowerCase()
            );

            const comboProd: Product = {
              id: c.id || `combo-${Date.now()}`,
              name: c.name,
              sku: `COMBO-${c.id || c.name.replace(/\s+/g, '-').toUpperCase()}`,
              short_description: c.subtitle || c.description || 'Special combo deal',
              full_description: c.description || c.subtitle || '',
              description: c.description || c.subtitle || '',
              ingredients: Array.isArray(c.ingredients)
                ? c.ingredients
                : typeof c.ingredients === 'string'
                ? c.ingredients.split(',').map((s: string) => s.trim()).filter(Boolean)
                : [],
              base_price: Number(c.base_price || c.price || 0),
              compare_at_price: c.compare_at_price ? Number(c.compare_at_price) : undefined,
              rating: 5.0,
              reviews_count: 24,
              has_tax: true,
              has_service_charge: false,
              vat_category: 'STANDARD',
              image_url: c.image_url || '/placeholder-burger.svg',
              images: [c.image_url || '/placeholder-burger.svg'],
              category_id: comboCategory?.id || 'category-combo-offers',
              is_active: true,
              is_bestseller: true,
              modifiers: Array.isArray(c.modifiers) ? c.modifiers.map((m: any, mIdx: number) => ({
                id: `mod-${c.id}-${mIdx}`,
                name: m.name,
                price: Number(m.price || 0),
                is_required: false,
                is_active: true
              })) : []
            };

            if (existingIdx >= 0) {
              currentProducts[existingIdx] = { ...currentProducts[existingIdx], ...comboProd };
            } else {
              currentProducts.push(comboProd);
            }
          });
        }

        if (currentCategories.length > 0) {
          setCategories(currentCategories);
        }
        if (currentProducts.length > 0) {
          setProducts(currentProducts);
        }

        // Aggregate All Offers for top sliding strip
        const allOffers: OfferCard[] = [];
        const seenTitles = new Set<string>();

        if (comboData?.combos) {
          comboData.combos
            .filter((c: any) => c.is_active !== false)
            .forEach((c: any) => {
              seenTitles.add(c.name.trim().toLowerCase());
              allOffers.push({
                id: c.id,
                title: c.name,
                subtitle: c.subtitle || c.description,
                badge: c.badge || 'COMBO',
                image_url: c.image_url || '',
                price: c.base_price,
                isCombo: true
              });
            });
        }

        if (pageOffersData?.offers) {
          pageOffersData.offers.forEach((o: any) => {
            const key = o.title.trim().toLowerCase();
            if (!seenTitles.has(key)) {
              seenTitles.add(key);
              allOffers.push({
                id: o.id,
                title: o.title,
                subtitle: o.tag || o.description,
                badge: o.badge || (o.code ? `CODE: ${o.code}` : 'OFFER'),
                image_url: o.image || '',
                code: o.code,
                isCombo: o.category?.includes('combos') || o.title.toLowerCase().includes('combo')
              });
            }
          });
        }

        if (todayData?.cards) {
          todayData.cards.forEach((c: any) => {
            const key = c.title.trim().toLowerCase();
            if (!seenTitles.has(key)) {
              seenTitles.add(key);
              allOffers.push({
                id: c.id,
                title: c.title,
                subtitle: c.subtitle,
                badge: c.badge || 'TODAY',
                image_url: c.image_url || '',
                isCombo: c.title?.toLowerCase().includes('combo')
              });
            }
          });
        }

        if (allOffers.length > 0) {
          setOfferCards(allOffers);
        }
      } catch (err) {
        console.error('Menu load error:', err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    loadAllMenuData();

    return () => {
      isMounted = false;
    };
  }, [selectedBranch?.id]);

  const handleOfferClick = (offer: OfferCard) => {
    if (offer.isCombo || offer.title.toLowerCase().includes('combo') || offer.title.toLowerCase().includes('feast') || offer.title.toLowerCase().includes('deal')) {
      setSelectedCategory('COMBO_DEALS');
    } else {
      const match = products.find(p => p.name.toLowerCase().includes(offer.title.toLowerCase().split(' ')[0]));
      if (match) {
        setSelectedProduct(match);
      } else {
        setSelectedCategory('ALL');
      }
    }
  };

  const isComboProduct = (p: Product) => {
    const cat = categories.find((c) => c.id === p.category_id);
    const catSlug = (cat?.slug || (p as any).category?.slug || '').toLowerCase();
    const catName = (cat?.name || (p as any).category?.name || '').toLowerCase();
    const sku = (p.sku || '').toUpperCase();
    return (
      catSlug.includes('combo') ||
      catName.includes('combo') ||
      sku.startsWith('COMBO-') ||
      p.category_id === 'category-combo-offers' ||
      (p as any).is_combo === true
    );
  };

  // High-performance memoized product list
  const filteredProducts = useMemo(() => {
    if (selectedCategory === 'ALL') return products;
    if (selectedCategory === 'COMBO_DEALS') return products.filter(isComboProduct);
    const cat = categories.find((c) => c.id === selectedCategory);
    return products.filter(
      (p) => p.category_id === selectedCategory || (cat && (p as any).category?.slug === cat.slug)
    );
  }, [products, selectedCategory, categories]);

  const categoryIcons: Record<string, React.ReactNode> = {
    all: <LayoutGrid className="w-4 h-4" />,
    combos: <Sparkles className="w-4 h-4" />,
    'combo-offers': <Sparkles className="w-4 h-4" />,
    'combo offers': <Sparkles className="w-4 h-4" />,
    burgers: <Beef className="w-4 h-4" />,
    chicken: <Drumstick className="w-4 h-4" />,
    sides: <UtensilsCrossed className="w-4 h-4" />,
    extras: <Plus className="w-4 h-4" />,
    dips: <Flame className="w-4 h-4" />,
    drinks: <CupSoda className="w-4 h-4" />,
  };

  const getCategoryIcon = (slugName: string, isSelected: boolean) => {
    const key = slugName.toLowerCase();
    const iconElement = (categoryIcons[key] || <UtensilsCrossed className="w-4 h-4" />) as React.ReactElement<{ className?: string }>;
    return React.cloneElement(iconElement, {
      className: `w-4 h-4 ${isSelected ? 'text-white' : 'text-[#71717A]'}`
    });
  };

  return (
    <div className="w-full min-h-screen bg-black text-[#F5F5F5] pb-36 sm:pb-24">
      <div className="w-full max-w-[1720px] mx-auto px-4 sm:px-8 lg:px-16 pt-8 sm:pt-10 space-y-6 sm:space-y-7">
        {/* Page Heading & Subtitle */}
        <div className="pb-2 border-b border-[#1C1C1C]">
          <span className="text-xs text-[#FF5A00] tracking-[0.25em] font-extrabold uppercase block mb-1">
            PATTY PROJECT
          </span>
          <h1 className="text-3xl sm:text-4xl font-black text-white tracking-tight uppercase font-hero">
            OUR MENU
          </h1>
          <p className="text-xs sm:text-sm text-[#A1A1AA] mt-1 font-normal">
            Burgers, sides and more. Made fresh to order.
          </p>
        </div>

        {/* ============================================================ */}
        {/* FAST HARDWARE-ACCELERATED RIGHT-TO-LEFT SLIDING OFFERS STRIP */}
        {/* ============================================================ */}
        {offerCards.length > 0 && (
          <div className="relative overflow-hidden w-full -mt-1 group/strip">
            {/* Left and Right soft gradient fade edges */}
            <div className="absolute left-0 top-0 bottom-0 w-8 sm:w-14 bg-gradient-to-r from-black to-transparent z-10 pointer-events-none" />
            <div className="absolute right-0 top-0 bottom-0 w-8 sm:w-14 bg-gradient-to-l from-black to-transparent z-10 pointer-events-none" />

            {/* Continuous Fast Right-to-Left Moving Track */}
            <div className="animate-slide-right-to-left flex items-center gap-3 sm:gap-3.5 py-1 px-1 select-none">
              {[...offerCards, ...offerCards].map((offer, idx) => (
                <div
                  key={`${offer.id}-${idx}`}
                  onClick={() => handleOfferClick(offer)}
                  className="shrink-0 min-w-[250px] sm:min-w-[285px] max-w-[320px] h-[78px] sm:h-[86px] rounded-xl bg-gradient-to-r from-[#170E08] via-[#120B06] to-[#0D0D0D] border border-[#2D180E] hover:border-[#FF5A00] p-2.5 sm:p-3 flex items-center justify-between gap-3 relative overflow-hidden group cursor-pointer shadow-md hover:shadow-[#FF5A00]/30 transition-all hover:scale-[1.02]"
                >
                  {/* Glowing Background Radial */}
                  <div className="absolute top-0 right-0 w-24 h-24 bg-[#FF5A00]/10 rounded-full blur-xl pointer-events-none" />

                  {/* Text Details */}
                  <div className="min-w-0 flex-1 space-y-1 relative z-10">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {offer.badge && (
                        <span className="text-[9px] sm:text-[10px] font-black uppercase bg-[#FF5A00] text-white px-1.5 py-0.5 rounded tracking-wide shadow-sm">
                          {offer.badge}
                        </span>
                      )}
                      {offer.price !== undefined && (
                        <span className="text-[10px] sm:text-[11px] font-extrabold text-[#FF8844]">
                          £{offer.price.toFixed(2)}
                        </span>
                      )}
                    </div>
                    <h4 className="text-xs sm:text-sm font-extrabold uppercase text-white truncate group-hover:text-[#FF5A00] transition-colors leading-tight">
                      {offer.title}
                    </h4>
                    <p className="text-[10px] sm:text-[11px] text-[#A1A1AA] truncate leading-tight">
                      {offer.subtitle}
                    </p>
                  </div>

                  {/* Thumbnail Image */}
                  {offer.image_url ? (
                    <img
                      src={offer.image_url}
                      alt={offer.title}
                      loading="lazy"
                      decoding="async"
                      className="w-13 h-13 sm:w-16 sm:h-16 rounded-lg object-cover bg-black border border-[#2A2A2A] shrink-0 group-hover:scale-105 transition-transform relative z-10"
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                      }}
                    />
                  ) : (
                    <div className="w-13 h-13 sm:w-16 sm:h-16 rounded-lg bg-[#1C1C1C] border border-[#2A2A2A] flex items-center justify-center text-[#FF5A00] shrink-0 relative z-10">
                      <Sparkles className="w-5 h-5" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Horizontal Category Navigation Bar (Center Aligned) */}
        <div className="w-full flex items-center justify-start sm:justify-center gap-2.5 pb-3 mb-8 overflow-x-auto scrollbar-none scroll-smooth">
          <button
            onClick={() => setSelectedCategory('ALL')}
            className={`h-9 px-4 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shrink-0 cursor-pointer border ${
              selectedCategory === 'ALL'
                ? 'bg-[#FF5A00] text-white border-[#FF5A00] shadow-sm'
                : 'bg-[#0D0D0D] text-[#A1A1AA] border-[#242424] hover:text-[#F5F5F5] hover:bg-[#151515] hover:border-[#333333]'
            }`}
          >
            {getCategoryIcon('all', selectedCategory === 'ALL')}
            <span>All Items</span>
          </button>

          {/* Blinking Orange COMBO DEALS Category Button */}
          <button
            onClick={() => setSelectedCategory('COMBO_DEALS')}
            className={`h-9 px-4 rounded-lg text-xs font-bold flex items-center gap-2 transition-all shrink-0 cursor-pointer border ${
              selectedCategory === 'COMBO_DEALS'
                ? 'bg-[#FF5A00] text-white border-[#FF5A00] shadow-lg shadow-[#FF5A00]/50 ring-2 ring-[#FF5A00]'
                : 'bg-[#FF5A00]/15 text-[#FF5A00] border-[#FF5A00] hover:bg-[#FF5A00] hover:text-white animate-pulse shadow-[0_0_12px_rgba(255,90,0,0.5)] ring-1 ring-[#FF5A00]/60'
            }`}
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#FF5A00] opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#FF5A00]"></span>
            </span>
            <Sparkles className={`w-4 h-4 ${selectedCategory === 'COMBO_DEALS' ? 'text-white' : 'text-[#FF5A00]'}`} />
            <span className="tracking-wide uppercase">Combo Deals</span>
            <span className={`text-[9px] font-black uppercase px-1.5 py-0.5 rounded tracking-wider ${
              selectedCategory === 'COMBO_DEALS' ? 'bg-white text-[#FF5A00]' : 'bg-[#FF5A00] text-white'
            }`}>
              OFFER
            </span>
          </button>

          {categories
            .filter((c) => !c.slug?.toLowerCase().includes('combo') && !c.name.toLowerCase().includes('combo'))
            .map((c) => {
              const isSelected = selectedCategory === c.id;
              return (
                <button
                  key={c.id}
                  onClick={() => setSelectedCategory(c.id)}
                  className={`h-9 px-4 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shrink-0 cursor-pointer border ${
                    isSelected
                      ? 'bg-[#FF5A00] text-white border-[#FF5A00] shadow-sm'
                      : 'bg-[#0D0D0D] text-[#A1A1AA] border-[#242424] hover:text-[#F5F5F5] hover:bg-[#151515] hover:border-[#333333]'
                  }`}
                >
                  {getCategoryIcon(c.slug || c.name, isSelected)}
                  <span>{c.name}</span>
                </button>
              );
            })}
        </div>

        {/* Loading Shimmer Skeletons */}
        {isLoading && products.length === 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 sm:gap-5 animate-pulse">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-[#0D0D0D] border border-[#1C1C1C] rounded-lg p-3 sm:p-4 space-y-3">
                <div className="aspect-[4/3] bg-[#181818] rounded-md" />
                <div className="h-4 bg-[#181818] rounded w-3/4" />
                <div className="h-3 bg-[#141414] rounded w-full" />
                <div className="flex justify-between items-center pt-2">
                  <div className="h-4 bg-[#181818] rounded w-1/4" />
                  <div className="h-7 w-16 bg-[#181818] rounded" />
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Responsive Product Grid: 4 cols desktop, 3 cols med, 2 cols sm, 2 cols mobile */
          <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 sm:gap-5">
            {filteredProducts.map((p) => {
              const displayImg = p.image_url || '/placeholder-burger.svg';
              const isOutOfStock = p.is_available === false || (p.stock_quantity !== undefined && p.stock_quantity <= 0);

              const isVeg = p.name.includes('[VEG]');
              const isVegan = p.name.includes('[VEGAN]');
              const cleanName = p.name.replace('[VEG]', '').replace('[VEGAN]', '').trim();

              return (
                <div
                  key={p.id}
                  onClick={() => setSelectedProduct(p)}
                  className={`bg-[#0D0D0D] border rounded-lg sm:rounded-[10px] overflow-hidden transition-all duration-200 group flex flex-col justify-between cursor-pointer ${
                    isOutOfStock
                      ? 'border-[#262626] opacity-60'
                      : 'border-[#1C1C1C] hover:border-[#FF5A00]/50 hover:bg-[#111111]'
                  }`}
                >
                  <div>
                    {/* Product Image Area */}
                    <div className="relative aspect-[4/3] bg-black overflow-hidden flex items-center justify-center">
                      <img
                        src={displayImg}
                        alt={cleanName}
                        loading="lazy"
                        decoding="async"
                        className={`w-full h-full object-cover transition-transform duration-300 select-none ${
                          isOutOfStock ? 'grayscale' : 'group-hover:scale-105'
                        }`}
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                      />

                      {/* Out of Stock Overlay */}
                      {isOutOfStock && (
                        <div className="absolute inset-0 bg-black/70 flex items-center justify-center p-2">
                          <span className="text-[10px] sm:text-xs font-bold text-red-400 bg-red-950/80 border border-red-800 px-2 py-0.5 rounded">
                            SOLD OUT
                          </span>
                        </div>
                      )}

                      {/* Top Badges (Dietary & Savings) */}
                      <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
                        {isVeg && (
                          <span className="bg-emerald-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow">
                            VEG
                          </span>
                        )}
                        {isVegan && (
                          <span className="bg-green-600 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow">
                            VEGAN
                          </span>
                        )}
                        {p.compare_at_price && p.compare_at_price > p.base_price && (
                          <span className="bg-[#FF5A00] text-white text-[9px] font-extrabold px-1.5 py-0.5 rounded shadow">
                            SAVE £{(p.compare_at_price - p.base_price).toFixed(2)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Info Card */}
                    <div className="p-3 sm:p-4 space-y-1.5 sm:space-y-2">
                      <div className="flex items-start justify-between gap-1">
                        <h3 className="font-bold text-xs sm:text-sm text-[#F5F5F5] group-hover:text-[#FF5A00] transition-colors leading-snug line-clamp-1">
                          {cleanName}
                        </h3>
                      </div>

                      <p className="text-[11px] sm:text-xs text-[#71717A] line-clamp-2 leading-relaxed font-normal">
                        {p.description || p.short_description || 'Crafted with premium ingredients, made fresh to order.'}
                      </p>
                    </div>
                  </div>

                  {/* Bottom Row: Price & Add Button */}
                  <div className="p-3 sm:p-4 pt-0 flex items-center justify-between mt-auto">
                    <div className="flex items-baseline gap-1.5">
                      <span className="text-xs sm:text-sm font-bold text-[#F5F5F5]">
                        £{p.base_price.toFixed(2)}
                      </span>
                      {p.compare_at_price && p.compare_at_price > p.base_price && (
                        <span className="text-[10px] sm:text-xs text-[#71717A] line-through">
                          £{p.compare_at_price.toFixed(2)}
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      disabled={isOutOfStock}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedProduct(p);
                      }}
                      className={`h-7 px-2.5 sm:h-8 sm:px-3 rounded-md sm:rounded-lg text-[11px] sm:text-xs font-semibold flex items-center gap-1 transition-all ${
                        isOutOfStock
                          ? 'bg-[#1C1C1C] text-[#555] cursor-not-allowed'
                          : 'bg-[#141414] hover:bg-[#FF5A00] text-white border border-[#2B2B2B] hover:border-[#FF5A00] active:scale-95 cursor-pointer'
                      }`}
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Empty State */}
        {!isLoading && filteredProducts.length === 0 && (
          <div className="py-16 text-center space-y-3">
            <p className="text-sm text-[#71717A]">
              {selectedCategory === 'COMBO_DEALS'
                ? 'No published combo deals available at the moment.'
                : 'No items available in this category.'}
            </p>
            <button
              onClick={() => setSelectedCategory('ALL')}
              className="text-xs font-bold text-[#FF5A00] hover:underline cursor-pointer"
            >
              View All Items
            </button>
          </div>
        )}
      </div>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
        />
      )}
    </div>
  );
};

export default CustomerMenu;
