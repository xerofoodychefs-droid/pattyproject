import React, { useEffect, useState, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Star, ChevronRight, Wheat, Sparkles } from 'lucide-react';
import { api } from '../../api/client';
import { Product } from '../../types';
import { ProductDetailModal } from './ProductDetailModal';
import { useCartStore } from '../../store/cartStore';
import { useProductRealtime } from '../../hooks/useProductRealtime';
import categoryBannerImg from '../../assets/categories_showcase_banner.webp';
import categoryBannerMobileImg from '../../assets/categories_showcase_mobile.webp';
import offerBg1 from '../../assets/offer_bg_1.webp';
import offerBg2 from '../../assets/offer_bg_2.webp';
import offerBg3 from '../../assets/offer_bg_3.webp';

export const CustomerHome: React.FC = () => {
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);

  const handleCloseProductModal = useCallback(() => {
    setSelectedProduct(null);
  }, []);
  const [todaysOffersData, setTodaysOffersData] = useState<any>({
    section_title: "TODAY'S OFFERS",
    view_all_link: "/offers",
    view_all_text: "VIEW ALL OFFERS",
    cards: [
      {
        id: "card-1",
        title: "BURGER COMBO",
        subtitle: "Burger + Fries + Drink",
        badge: "SAVE 15%",
        image_url: "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=500&q=80",
        link_url: "/order"
      },
      {
        id: "card-2",
        title: "WING WEDNESDAY",
        subtitle: "On All Wings",
        badge: "20% OFF",
        image_url: "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=500&q=80",
        link_url: "/order"
      },
      {
        id: "card-3",
        title: "STUDENT OFFER",
        subtitle: "On All Orders",
        badge: "10% OFF",
        badge_type: "id_badge",
        image_url: "",
        link_url: "/order"
      }
    ]
  });
  const navigate = useNavigate();
  const { selectedBranch, setOrderType } = useCartStore();

  // Realtime product availability subscription
  useProductRealtime({
    onProductChange: (event) => {
      const currentBranch = useCartStore.getState().selectedBranch;
      if (event.branch_id && currentBranch?.id && event.branch_id !== currentBranch.id) {
        return;
      }
      fetchProducts();
    },
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
      if (selectedProduct && selectedProduct.id === productId) {
        setSelectedProduct((prev) =>
          prev
            ? {
                ...prev,
                is_out_of_stock: boolOutOfStock,
                is_available: !boolOutOfStock,
                stock_quantity: boolOutOfStock ? 0 : (prev.stock_quantity && prev.stock_quantity > 0 ? prev.stock_quantity : 100),
              }
            : null
        );
      }
    },
    onReconnect: () => {
      fetchProducts();
    },
  });

  const fetchProducts = async () => {
    try {
      const branchParam = selectedBranch?.id ? `?branch_id=${selectedBranch.id}&_t=${Date.now()}` : `?_t=${Date.now()}`;
      const data = await api.get<Product[]>(`/products${branchParam}`);
      if (Array.isArray(data)) {
        setProducts(data);
      } else {
        console.error('[CustomerHome] Unexpected products API response shape:', data);
        throw new Error('Unexpected products API response shape');
      }
    } catch (err) {
      console.error('[CustomerHome] Failed to fetch products:', err);
    }
  };

  const fetchTodaysOffers = async () => {
    try {
      const data = await api.getCached<any>('/promotions/settings/todays-offers', 30000);
      if (data && Array.isArray(data.cards) && data.cards.length > 0) {
        setTodaysOffersData(data);
      }
    } catch (err) {
      console.error('[CustomerHome] Failed to load today offers config:', err);
    }
  };

  useEffect(() => {
    fetchProducts();
    fetchTodaysOffers();

    const intervalId = setInterval(() => {
      fetchProducts();
    }, 30000);

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchProducts();
        fetchTodaysOffers();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [selectedBranch?.id]);

  const mcProduct = products.find(p => p.name.toLowerCase().includes('mc project') && !p.name.toLowerCase().includes('vegan'));
  const outlawProduct = products.find(p => p.name.toLowerCase().includes('outlaw project') && !p.name.toLowerCase().includes('vegan'));
  const pastramiProduct = products.find(p => p.name.toLowerCase().includes('pastrami'));
  const chickenProduct = products.find(p => p.name.toLowerCase().includes('chicken sando') || p.name.toLowerCase().includes('buffalo chicken'));
  const halloumiProduct = products.find(p => p.name.toLowerCase().includes('halloumi'));

  return (
    <div className="pb-0 space-y-6 sm:space-y-16">
      {/* Hero Section matching exact reference image */}
      <section id="hero" className="relative bg-black min-h-[calc(100vh-68px)] lg:h-[calc(100vh-68px)] flex flex-col justify-between overflow-hidden px-6 sm:px-10 lg:px-16 xl:px-20 2xl:px-24 pt-6 lg:pt-8 pb-6 lg:pb-8">
        
        {/* Full-bleed right side burger background image overlay */}
        <div className="absolute inset-y-0 right-0 w-full lg:w-[62%] xl:w-[66%] pointer-events-none overflow-hidden flex items-center justify-end z-0">
          <img
            src="/herobackground.webp"
            alt="Hero Smash Burger"
            onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/herobackground.png'; }}
            className="w-full h-full object-cover object-center lg:object-right select-none opacity-95 lg:opacity-100"
          />
          {/* Left-to-right soft gradient overlay for seamless text readability */}
          <div className="absolute inset-0 bg-gradient-to-r from-black via-black/75 lg:via-black/20 to-transparent pointer-events-none" />
        </div>

        {/* Top/Middle Hero Content (Headline + Description + Buttons) */}
        <div className="relative z-10 my-auto max-w-[560px]">
          {/* Orange Location Tag */}
          <span className="text-xs lg:text-sm text-[#FF5500] tracking-[0.25em] font-extrabold uppercase block mb-3 sm:mb-4">
            LONDON
          </span>

          {/* Giant Headline matching exact reference screenshot */}
          <h1 className="text-5xl sm:text-7xl lg:text-[4.5rem] xl:text-[5.5rem] 2xl:text-[6.2rem] font-black leading-[0.9] tracking-tight font-hero uppercase">
            <span className="text-white">SMASH.</span><br />
            <span className="text-[#FF5500]">STACK.</span><br />
            <span className="text-white">SATISFY.</span>
          </h1>

          {/* Supporting Paragraph */}
          <p className="text-[#9CA3AF] text-sm sm:text-base font-medium leading-relaxed max-w-[440px] mt-4 lg:mt-6 mb-6 lg:mb-8">
            London-made burgers. Fresh ingredients.<br className="hidden sm:inline" />
            Bold flavours.
          </p>

          <div className="flex flex-wrap items-center gap-4">
            <button
              onClick={() => {
                setOrderType('DELIVERY');
                navigate('/select-location');
              }}
              className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-7 py-3.5 rounded-xl font-bold text-xs sm:text-sm uppercase tracking-wider transition-all shadow-lg shadow-[#FF5500]/30 flex items-center gap-2 cursor-pointer"
            >
              <span>ORDER NOW</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>

      {/* WELCOME TO PATTY PROJECT BRAND INTRODUCTION SECTION */}
      <section className="w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12 pt-8 pb-0 text-center text-white space-y-6">
        {/* Top 3 Stars */}
        <div className="flex items-center justify-center gap-1.5 text-[#FF5500]">
          <Star className="w-4 h-4 fill-[#FF5500]" />
          <Star className="w-5 h-5 fill-[#FF5500]" />
          <Star className="w-4 h-4 fill-[#FF5500]" />
        </div>

        {/* Tagline */}
        <p className="text-xs font-black tracking-[0.25em] uppercase text-white font-hero">
          WELCOME TO <span className="text-[#FF5500]">PATTY PROJECT</span>
        </p>

        {/* Serif Headline */}
        <h2 className="text-4xl sm:text-5xl lg:text-5xl font-serif text-white tracking-tight leading-tight font-normal">
          Good Food. Great Times.
        </h2>

        {/* Description Paragraph */}
        <p className="text-xs sm:text-sm text-[#9CA3AF] max-w-xl mx-auto font-medium leading-relaxed">
          Rooted in classic Native flavors with a modern twist.<br className="hidden sm:inline" />
          Join us for lunch, dinner, or your next celebration.
        </p>

        {/* 3 Pillars Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 sm:gap-10 pt-2 max-w-5xl mx-auto">
          {/* Pillar 1 */}
          <div className="flex flex-col items-center text-center space-y-2.5">
            <div className="w-20 h-20 rounded-full bg-[#121212] border border-[#282828] flex items-center justify-center text-[#FF5500] shadow-xl">
              <Wheat className="w-9 h-9 text-[#FF5500]" />
            </div>
            <h3 className="text-xs sm:text-sm font-black tracking-widest text-white uppercase pt-1">
              QUALITY INGREDIENTS
            </h3>
            <p className="text-xs text-[#9CA3AF] font-medium leading-relaxed max-w-[260px]">
              We source locally and seasonally, bringing out the best in every dish.
            </p>
          </div>

          {/* Pillar 2 (Featured Glowing Center Circle) */}
          <div className="flex flex-col items-center text-center space-y-2.5">
            <div className="w-20 h-20 rounded-full bg-gradient-to-tr from-[#FF5500] to-[#FFAA00] flex items-center justify-center text-white shadow-2xl shadow-[#FF5500]/40 scale-105">
              <Star className="w-10 h-10 text-white stroke-[1.5]" />
            </div>
            <h3 className="text-xs sm:text-sm font-black tracking-widest text-white uppercase pt-1">
              MADE WITH CARE
            </h3>
            <p className="text-xs text-[#9CA3AF] font-medium leading-relaxed max-w-[260px]">
              From scratch kitchens and signature recipes made just for you.
            </p>
          </div>

          {/* Pillar 3 */}
          <div className="flex flex-col items-center text-center space-y-2.5">
            <div className="w-20 h-20 rounded-full bg-[#121212] border border-[#282828] flex items-center justify-center text-[#FF5500] shadow-xl">
              <Sparkles className="w-9 h-9 text-[#FF5500]" />
            </div>
            <h3 className="text-xs sm:text-sm font-black tracking-widest text-white uppercase pt-1">
              WARM HOSPITALITY
            </h3>
            <p className="text-xs text-[#9CA3AF] font-medium leading-relaxed max-w-[260px]">
              A cozy vibe, a friendly team, and great vibes always.
            </p>
          </div>
        </div>
      </section>

      {/* CATEGORIES SHOWCASE BANNER (DIRECTLY ABOVE SIGNATURE BURGERS) */}
      <section className="w-full max-w-[1360px] mx-auto px-4 sm:px-10 lg:px-12 pt-2 pb-0 sm:pt-4 sm:pb-1">
        <Link to="/order" className="block w-full overflow-hidden rounded-2xl sm:rounded-3xl hover:opacity-95 transition-opacity">
          {/* Mobile View: 2-column + full width stack matching attached photo */}
          <img
            src="/categories_showcase_mobile.webp"
            alt="Menu Categories: Breakfast Buns, Burgers & Sandos, Wings & Tenders, Shakes & Drinks, Fries & Sides"
            onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/categories_showcase_mobile.png'; }}
            className="w-full h-auto object-contain sm:object-cover rounded-2xl sm:rounded-3xl shadow-2xl block md:hidden"
            loading="lazy"
            decoding="async"
          />

          {/* Desktop / Tablet View: Landscape banner */}
          <img
            src="/categories_showcase_banner.webp"
            alt="Menu Categories: Breakfast Buns, Burgers & Sandos, Wings & Tenders, Shakes & Drinks, Fries & Sides"
            onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/categories_showcase_banner.png'; }}
            className="w-full h-auto object-cover rounded-2xl sm:rounded-3xl shadow-2xl hidden md:block"
            loading="lazy"
            decoding="async"
          />
        </Link>
      </section>

      {/* SIGNATURE BURGERS & TODAY'S OFFERS SECTION */}
      <section className="w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12 space-y-8 sm:space-y-14 pt-4 sm:pt-6 pb-2 sm:pb-14">
        {/* SIGNATURE BURGERS SHOWCASE SECTION (Full Width & Large Scale matching reference poster) */}
        <div className="space-y-8 sm:space-y-10">
          <div className="flex items-center justify-between">
            <h2 className="text-xl sm:text-2xl font-black text-white tracking-widest uppercase font-hero">
              SIGNATURE BURGERS
            </h2>
            <Link to="/order" className="text-xs sm:text-sm font-extrabold text-[#FF5500] hover:underline flex items-center gap-1 uppercase tracking-wider">
              <span>VIEW ALL</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          {/* Top Row: 3 Signature Burgers spanning full width */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8 xl:gap-10">
            {/* 1. MC PROJECT */}
            <div
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className="flex items-center gap-4 sm:gap-5 cursor-pointer p-2.5 sm:p-4 bg-transparent border border-white/[0.05] rounded-2xl"
            >
              <div className="w-32 sm:w-44 lg:w-40 xl:w-44 h-32 sm:h-44 lg:h-40 xl:h-44 shrink-0 relative overflow-hidden rounded-2xl bg-transparent">
                <img
                  src={mcProduct?.image_url || '/product_the_mc_project.webp'}
                  alt="MC Project"
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/product_the_mc_project.png'; }}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl lg:text-2xl font-serif font-black tracking-wide uppercase leading-tight">
                  <span className="text-white">MC </span>
                  <br className="hidden sm:inline" />
                  <span className="text-[#FF5500]">PROJECT</span>
                </h3>
                <p className="text-xs sm:text-sm text-[#D1D5DB] font-medium leading-relaxed max-w-[280px]">
                  Double beef, double American cheese, burger sauce, lettuce, onion & gherkins
                </p>
              </div>
            </div>

            {/* 2. OUTLAW PROJECT */}
            <div
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className="flex items-center gap-4 sm:gap-5 cursor-pointer p-2.5 sm:p-4 bg-transparent border border-white/[0.05] rounded-2xl"
            >
              <div className="w-32 sm:w-44 lg:w-40 xl:w-44 h-32 sm:h-44 lg:h-40 xl:h-44 shrink-0 relative overflow-hidden rounded-2xl bg-transparent">
                <img
                  src={outlawProduct?.image_url || '/product_the_outlaw_project_.webp'}
                  alt="Outlaw Project"
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/product_the_outlaw_project_.png'; }}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl lg:text-2xl font-serif font-black tracking-wide uppercase leading-tight">
                  <span className="text-white">OUTLAW </span>
                  <br className="hidden sm:inline" />
                  <span className="text-[#FF5500]">PROJECT</span>
                </h3>
                <p className="text-xs sm:text-sm text-[#D1D5DB] font-medium leading-relaxed max-w-[280px]">
                  Double beef, mature cheddar, bacon, smoky BBQ, jalapeños & jalapeño mayo
                </p>
              </div>
            </div>

            {/* 3. PASTRAMI BURGER */}
            <div
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className="flex items-center gap-4 sm:gap-5 cursor-pointer p-2.5 sm:p-4 bg-transparent border border-white/[0.05] rounded-2xl"
            >
              <div className="w-32 sm:w-44 lg:w-40 xl:w-44 h-32 sm:h-44 lg:h-40 xl:h-44 shrink-0 relative overflow-hidden rounded-2xl bg-transparent">
                <img
                  src={pastramiProduct?.image_url || '/product_pastrami_burger_.webp'}
                  alt="Pastrami Burger"
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/product_pastrami_burger_.png'; }}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl lg:text-2xl font-serif font-black tracking-wide uppercase leading-tight">
                  <span className="text-white">PASTRAMI </span>
                  <br className="hidden sm:inline" />
                  <span className="text-[#FF5500]">BURGER</span>
                </h3>
                <p className="text-xs sm:text-sm text-[#D1D5DB] font-medium leading-relaxed max-w-[280px]">
                  Pastrami, Emmental, Russian sauce & pickled gherkins
                </p>
              </div>
            </div>
          </div>

          {/* Bottom Row: 2 Signature Burgers Large Centered */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 max-w-5xl mx-auto pt-2 sm:pt-4">
            {/* 4. FRIED CHICKEN SANDO */}
            <div
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className="flex items-center gap-4 sm:gap-5 cursor-pointer p-2.5 sm:p-4 bg-transparent border border-white/[0.05] rounded-2xl"
            >
              <div className="w-32 sm:w-44 lg:w-40 xl:w-44 h-32 sm:h-44 lg:h-40 xl:h-44 shrink-0 relative overflow-hidden rounded-2xl bg-transparent">
                <img
                  src={chickenProduct?.image_url || '/product_buffalo_chicken_sando_.webp'}
                  alt="Fried Chicken Sando"
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/product_buffalo_chicken_sando_.png'; }}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl lg:text-2xl font-serif font-black tracking-wide uppercase leading-tight">
                  <span className="text-white">FRIED CHICKEN </span>
                  <br className="hidden sm:inline" />
                  <span className="text-[#FF5500]">SANDO</span>
                </h3>
                <p className="text-xs sm:text-sm text-[#D1D5DB] font-medium leading-relaxed max-w-[280px]">
                  Buffalo buttermilk chicken, coleslaw, lime mayo & gherkins
                </p>
              </div>
            </div>

            {/* 5. HALLOUMI BURGER */}
            <div
              onClick={() => {
                window.scrollTo({ top: 0, behavior: 'smooth' });
              }}
              className="flex items-center gap-4 sm:gap-5 cursor-pointer p-2.5 sm:p-4 bg-transparent border border-white/[0.05] rounded-2xl"
            >
              <div className="w-32 sm:w-44 lg:w-40 xl:w-44 h-32 sm:h-44 lg:h-40 xl:h-44 shrink-0 relative overflow-hidden rounded-2xl bg-transparent">
                <img
                  src={halloumiProduct?.image_url || '/product_the_halloumi_project_veg.webp'}
                  alt="Halloumi Burger"
                  className="w-full h-full object-cover"
                  loading="lazy"
                  decoding="async"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/product_the_halloumi_project_veg.png'; }}
                />
              </div>
              <div className="space-y-2">
                <h3 className="text-lg sm:text-xl lg:text-2xl font-serif font-black tracking-wide uppercase leading-tight">
                  <span className="text-white">HALLOUMI </span>
                  <br className="hidden sm:inline" />
                  <span className="text-[#FF5500]">BURGER</span>
                </h3>
                <p className="text-xs sm:text-sm text-[#D1D5DB] font-medium leading-relaxed max-w-[280px]">
                  Halloumi, guacamole, tomato, pickled onion & hot-honey ketchup
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* TODAY'S OFFERS SUB-SECTION */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-xl sm:text-2xl font-black text-white tracking-widest uppercase font-hero">
              {todaysOffersData.section_title || "TODAY'S OFFERS"}
            </h2>
            <Link to={todaysOffersData.view_all_link || "/offers"} className="text-xs sm:text-sm font-extrabold text-[#FF5500] hover:underline flex items-center gap-1 uppercase tracking-wider">
              <span>{todaysOffersData.view_all_text || "VIEW ALL OFFERS"}</span>
              <ChevronRight className="w-4 h-4" />
            </Link>
          </div>

          {/* 3 Promotional Banner Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 lg:gap-6">
            {todaysOffersData.cards.map((card: any, idx: number) => {
              const bgTexture = idx === 0 ? offerBg1 : idx === 1 ? offerBg2 : offerBg3;
              return (
                <div 
                  key={card.id || idx}
                  onClick={() => navigate(card.link_url || '/order')}
                  className="bg-[#120B07] border border-[#2A1810] hover:border-[#FF5500]/60 rounded-xl p-4 sm:p-5 flex items-center justify-between relative overflow-hidden shadow-2xl transition-all hover:scale-[1.02] cursor-pointer group min-h-[160px] sm:min-h-[180px]"
                >
                  {/* Background texture overlay */}
                  <div
                    className="absolute inset-0 bg-cover bg-center opacity-85 group-hover:opacity-95 transition-opacity pointer-events-none"
                    style={{ backgroundImage: `url(${bgTexture})` }}
                  />
                  <div className="absolute inset-0 bg-gradient-to-r from-black/85 via-black/45 to-black/70 pointer-events-none" />

                  <div className="space-y-2.5 relative z-10 max-w-[55%]">
                    <h3 className="font-black text-white text-lg sm:text-xl tracking-wide uppercase font-hero leading-tight">
                      {card.title}
                    </h3>
                    {card.badge && (
                      <div className="pt-0.5">
                        <span className="inline-block px-3 py-1 bg-[#FF5500] text-white text-[11px] font-extrabold rounded uppercase tracking-wider shadow-md shadow-[#FF5500]/30">
                          {card.badge}
                        </span>
                      </div>
                    )}
                    <p className="text-xs text-[#D1D5DB] font-medium">{card.subtitle}</p>
                  </div>

                  {card.image_url ? (
                    <img
                      src={card.image_url}
                      alt={card.title}
                      className="w-28 sm:w-36 lg:w-40 h-28 sm:h-32 lg:h-34 object-cover rounded-lg border border-[#262626] shadow-xl shrink-0 group-hover:scale-105 transition-transform duration-300 relative z-10"
                    />
                  ) : (
                    <div className="w-28 sm:w-36 lg:w-40 h-28 sm:h-32 lg:h-34 bg-[#161616]/90 border border-[#262626] rounded-lg p-3 flex flex-col items-center justify-center text-center shadow-xl shrink-0 group-hover:border-[#FF5500]/40 transition-colors relative z-10">
                      <div className="w-9 h-9 rounded-full bg-[#FF5500]/20 border border-[#FF5500]/40 flex items-center justify-center text-[#FF5500] font-extrabold text-xs mb-1.5 shadow-md">
                        ID
                      </div>
                      <span className="text-[11px] font-extrabold text-white uppercase tracking-wider">{card.title}</span>
                      <span className="text-[9px] text-[#9CA3AF] mt-0.5">PATTY PROJECT - LONDON</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* HUNGRY? UNLOCK YOUR PATTYPROJECT MEAL BANNER matching Screenshot */}
      <section className="w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12 pt-2 pb-8 sm:py-12 text-center text-white space-y-4 sm:space-y-6">
        {/* Main 2-Line Headline in Serif */}
        <h2 className="text-3xl sm:text-4xl lg:text-5xl font-serif tracking-wide leading-tight max-w-4xl mx-auto uppercase">
          <span className="text-white">HUNGRY? </span>
          <span className="text-[#FF5500]">UNLOCK YOUR</span>
          <br />
          <span className="text-white">PATTYPROJECT MEAL</span>
        </h2>

        {/* Subtext Paragraph */}
        <p className="text-xs sm:text-sm text-[#9CA3AF] max-w-2xl mx-auto font-medium leading-relaxed">
          Don’t just eat — experience.{' '}
          <span className="text-[#FF5500] font-bold">Order online</span> and get your project-crafted meal delivered to your door, piping hot and packed with flavor.
        </p>

        {/* GET STARTED Pill Button */}
        <div className="pt-2">
          <button
            onClick={() => {
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            className="bg-[#FF5500] hover:bg-[#E04B00] text-white text-xs sm:text-sm font-black uppercase tracking-widest px-9 py-3.5 rounded-full shadow-2xl shadow-[#FF5500]/30 transition-all hover:scale-105 cursor-pointer"
          >
            GET STARTED
          </button>
        </div>
      </section>

      {/* Product Detail Modal */}
      {selectedProduct && (
        <ProductDetailModal
          product={selectedProduct}
          onClose={handleCloseProductModal}
        />
      )}
    </div>
  );
};
