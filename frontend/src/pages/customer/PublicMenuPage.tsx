import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Star,
  ChevronRight,
  LayoutGrid,
  Beef,
  Drumstick,
  UtensilsCrossed,
  Flame,
  CupSoda,
  Plus
} from 'lucide-react';
import { api } from '../../api/client';
import { Product, Category } from '../../types';
import { useCartStore } from '../../store/cartStore';
import { useProductRealtime } from '../../hooks/useProductRealtime';

export const PublicMenuPage: React.FC = () => {
  const navigate = useNavigate();
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');
  const [loading, setLoading] = useState(true);
  const { selectedBranch } = useCartStore();

  const fetchData = async () => {
    try {
      const branchParam = selectedBranch?.id ? `?branch_id=${selectedBranch.id}&_t=${Date.now()}` : `?_t=${Date.now()}`;
      const [catData, prodData] = await Promise.all([
        api.get<Category[]>(`/categories?_t=${Date.now()}`).catch(() => []),
        api.get<Product[]>(`/products${branchParam}`).catch(() => [])
      ]);
      if (catData && Array.isArray(catData)) setCategories(catData);
      if (prodData && Array.isArray(prodData)) setProducts(prodData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // Periodic schedule revalidation (every 30s) + immediate revalidation when returning to tab
  useEffect(() => {
    fetchData();

    const intervalId = setInterval(() => {
      fetchData();
    }, 30000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchData();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [selectedBranch?.id]);

  useProductRealtime({
    onProductChange: (event) => {
      const currentBranch = useCartStore.getState().selectedBranch;
      if (event.branch_id && currentBranch?.id && event.branch_id !== currentBranch.id) {
        return;
      }
      fetchData();
    },
    onProductAvailabilityChange: (productId: string, isOutOfStock: boolean) => {
      const boolOutOfStock = Boolean(isOutOfStock);
      setProducts((prev) =>
        prev.map((p) => {
          if (p.id !== productId) return p;
          const cat = categories.find((c) => c.id === p.category_id);
          const isCategoryClosed = cat && cat.schedule_enabled && cat.schedule_status === 'CLOSED';
          const effectivelyAvailable = !boolOutOfStock && !isCategoryClosed;
          return {
            ...p,
            is_out_of_stock: boolOutOfStock,
            is_available: effectivelyAvailable,
            stock_quantity: boolOutOfStock ? 0 : (p.stock_quantity && p.stock_quantity > 0 ? p.stock_quantity : 100),
          };
        })
      );
    },
    onReconnect: () => {
      fetchData();
    },
  });

  const filteredProducts = products.filter((p) => {
    if (selectedCategory === 'ALL') return true;
    const cat = categories.find((c) => c.id === selectedCategory);
    return p.category_id === selectedCategory || (cat && (p as any).category?.slug === cat.slug);
  });

  const categoryIcons: Record<string, React.ReactNode> = {
    all: <LayoutGrid className="w-4 h-4" />,
    burgers: <Beef className="w-4 h-4" />,
    chicken: <Drumstick className="w-4 h-4" />,
    sides: <UtensilsCrossed className="w-4 h-4" />,
    extras: <Plus className="w-4 h-4" />,
    dips: <Flame className="w-4 h-4" />,
    drinks: <CupSoda className="w-4 h-4" />,
  };

  const getCategoryIcon = (slugName: string, isSelected: boolean) => {
    const key = slugName.toLowerCase();
    const iconElement = categoryIcons[key] || <UtensilsCrossed className="w-4 h-4" />;
    return React.cloneElement(iconElement as React.ReactElement<{ className?: string }>, {
      className: `w-4 h-4 ${isSelected ? 'text-white' : 'text-[#71717A]'}`
    });
  };

  // Clicking any product goes directly to Hero section on Home page
  const handleProductClick = () => {
    navigate('/');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-black text-[#F5F5F5] pb-24">
      <div className="w-full max-w-[1720px] mx-auto px-4 sm:px-8 lg:px-16 pt-8 sm:pt-10 space-y-8">
        
        {/* Header Title & Subtitle */}
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

        {/* Category Navigation Bar (Center Aligned) */}
        <div className="w-full flex items-center justify-start sm:justify-center gap-2.5 pb-2 overflow-x-auto scrollbar-none scroll-smooth">
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

          {categories.map((c) => {
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

        {/* Product Cards Grid (No Price, No Cart Button, Click navigates to Home Hero) */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5 animate-pulse">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] h-64" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 sm:gap-5">
            {filteredProducts.map((p) => {
              const displayImg = p.image_url || '/placeholder-burger.svg';
              const isOutOfStock = p.is_available === false || (p.stock_quantity !== undefined && p.stock_quantity <= 0);
              const isVeg = p.name.includes('[VEG]');
              const isVegan = p.name.includes('[VEGAN]');
              const cleanName = p.name.replace('[VEG]', '').replace('[VEGAN]', '').trim();

              return (
                <div
                  key={p.id}
                  onClick={handleProductClick}
                  className={`bg-[#0D0D0D] border rounded-[10px] overflow-hidden transition-all duration-200 group flex flex-col justify-between cursor-pointer ${
                    isOutOfStock
                      ? 'border-[#242424] opacity-85 hover:border-[#3F3F46]'
                      : 'border-[#242424] hover:border-[#FF5A00]/50'
                  }`}
                >
                  {/* Product Image Area (4/3 Aspect Ratio) */}
                  <div className="w-full aspect-[4/3] overflow-hidden bg-[#111111] relative border-b border-[#1C1C1C]">
                    <img
                      src={displayImg}
                      alt={p.name}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                      }}
                      className={`w-full h-full object-cover transition-transform duration-200 ${
                        isOutOfStock ? 'brightness-75' : 'group-hover:scale-[1.02]'
                      }`}
                    />

                    {/* Dietary Badges */}
                    {(isVeg || isVegan) && (
                      <span className="absolute top-2.5 left-2.5 bg-[#22C55E]/10 border border-[#22C55E]/30 text-[#22C55E] text-[10px] font-semibold px-2 py-0.5 rounded-md backdrop-blur-sm z-10">
                        {isVegan ? 'VEGAN' : 'VEG'}
                      </span>
                    )}

                    {/* OUT OF STOCK Badge Overlay on Image */}
                    {isOutOfStock && (
                      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px] flex items-center justify-center p-2 z-10">
                        <span className="bg-[#18181B]/95 text-[#EF4444] border border-[#EF4444]/40 text-[11px] sm:text-xs font-black px-3 py-1.5 rounded-lg tracking-wider uppercase shadow-xl">
                          Out of Stock
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Product Information Area (Name & Star rating only - NO Price & NO Cart Button) */}
                  <div className="p-4 space-y-2.5 bg-[#0D0D0D]">
                    <h3 className={`font-semibold text-sm leading-snug line-clamp-2 min-h-[40px] ${isOutOfStock ? 'text-[#A1A1AA]' : 'text-[#F5F5F5]'}`}>
                      {cleanName}
                    </h3>

                    {/* Rating Row only */}
                    <div className="flex items-center gap-1 pt-2 border-t border-[#1C1C1C]">
                      {[...Array(5)].map((_, i) => (
                        <Star key={i} className={`w-3.5 h-3.5 ${isOutOfStock ? 'fill-[#52525B] text-[#52525B]' : 'fill-[#FF5A00] text-[#FF5A00]'}`} />
                      ))}
                      <span className="text-xs text-[#71717A] font-normal ml-1">
                        {p.rating || 4.7}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
