import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Tag, 
  Clock, 
  Gift, 
  Utensils, 
  LayoutGrid, 
  UtensilsCrossed, 
  Flame, 
  Coffee, 
  ArrowRight, 
  Check, 
  Sparkles
} from 'lucide-react';
import { api } from '../../api/client';

interface OfferItem {
  id: string;
  category: string[];
  title: string;
  tag: string;
  tagIcon: 'utensils' | 'clock' | 'gift';
  badge: string;
  code: string;
  image: string;
  description: string;
}

export const CustomerOffers: React.FC = () => {
  const navigate = useNavigate();
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const [offersData, setOffersData] = useState<{
    banner: {
      tagline: string;
      headline_main: string;
      headline_highlight: string;
      description: string;
      image_url: string;
    };
    offers: OfferItem[];
  }>({
    banner: {
      tagline: "EXCLUSIVE OFFERS",
      headline_main: "DEALS THAT",
      headline_highlight: "HIT DIFFERENT.",
      description: "Handpicked combos, limited-time treats and exclusive perks crafted to make your meal even better.",
      image_url: "/offers_combo_banner.png"
    },
    offers: [
      {
        id: 'combo',
        category: ['combos', 'burgers'],
        title: 'BURGER COMBO',
        tag: 'BURGER + FRIES + DRINK',
        tagIcon: 'utensils',
        badge: 'SAVE 15%',
        code: 'COMBO15',
        image: '/product_the_mc_project.png',
        description: 'Get our signature double smash burger served with seasoned skin-on fries and any cold drink of your choice.'
      },
      {
        id: 'family',
        category: ['combos', 'burgers', 'sides'],
        title: 'PATTY FEAST (FEEDS 4)',
        tag: '4 BURGERS + 2 FRIES + 4 DRINKS',
        tagIcon: 'utensils',
        badge: 'POPULAR',
        code: 'FEAST20',
        image: '/product_the_outlaw_project_.png',
        description: 'The ultimate burger party box! Includes 4 classic smash burgers, 2 large rosemary salt fries, and 4 refreshing drinks.'
      },
      {
        id: 'lunch',
        category: ['limited', 'burgers'],
        title: 'LUNCH SPECIAL',
        tag: 'MON - FRI, 12PM - 4PM',
        tagIcon: 'clock',
        badge: '£5.99 ONLY',
        code: 'LUNCH599',
        image: '/product_pastrami_burger_.png',
        description: 'Quick lunch win! Single smash patty burger or crispy chicken sandwich with skin-on fries for just £5.99.'
      },
      {
        id: 'shake',
        category: ['drinks', 'limited'],
        title: 'FREE SHAKE UPGRADE',
        tag: 'WITH ANY BURGER & FRIES ORDER',
        tagIcon: 'gift',
        badge: 'LIMITED TIME',
        code: 'SHAKEUP',
        image: 'https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=600&q=80',
        description: 'Upgrade your soft drink to any handmade gourmet milkshake for free when you order a burger and sides.'
      }
    ]
  });

  useEffect(() => {
    fetchOffersData();
  }, []);

  const fetchOffersData = async () => {
    try {
      const data = await api.get<any>('/promotions/settings/offers-page');
      if (data && data.banner && data.offers) {
        setOffersData(data);
      }
    } catch (err) {
      console.error('Failed to load offers page config:', err);
    }
  };

  const categories = [
    { id: 'all', label: 'ALL OFFERS', icon: LayoutGrid },
    { id: 'combos', label: 'COMBOS', icon: UtensilsCrossed },
    { id: 'burgers', label: 'BURGERS', icon: Utensils },
    { id: 'sides', label: 'SIDES', icon: Flame },
    { id: 'drinks', label: 'DRINKS', icon: Coffee },
    { id: 'limited', label: 'LIMITED TIME', icon: Clock },
  ];

  const handleCopyCode = (code: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard?.writeText(code);
    setCopiedCode(code);
    setToastMessage(`Coupon code "${code}" copied to clipboard!`);
    setTimeout(() => {
      setCopiedCode(null);
      setToastMessage(null);
    }, 2500);
  };

  const handleClaimDeal = (offer: OfferItem) => {
    navigator.clipboard?.writeText(offer.code);
    setCopiedCode(offer.code);
    setToastMessage(`Claiming ${offer.title} (Code: ${offer.code})!`);
    setTimeout(() => {
      navigate('/menu');
    }, 600);
  };

  const filteredOffers = activeCategory === 'all'
    ? offersData.offers
    : offersData.offers.filter(o => o.category.includes(activeCategory));

  const renderTagIcon = (type: 'utensils' | 'clock' | 'gift') => {
    switch (type) {
      case 'utensils':
        return <Utensils className="w-3.5 h-3.5 text-[#FF5A00] shrink-0" />;
      case 'clock':
        return <Clock className="w-3.5 h-3.5 text-[#FF5A00] shrink-0" />;
      case 'gift':
        return <Gift className="w-3.5 h-3.5 text-[#FF5A00] shrink-0" />;
    }
  };

  return (
    <div className="min-h-screen bg-black text-white flex flex-col justify-between selection:bg-[#FF5A00] selection:text-white">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#1A1A1A] border border-[#FF5A00] text-white px-5 py-3 rounded-2xl shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div className="w-6 h-6 rounded-full bg-[#FF5A00]/20 flex items-center justify-center text-[#FF5A00]">
            <Check className="w-4 h-4" />
          </div>
          <p className="text-xs sm:text-sm font-semibold">{toastMessage}</p>
        </div>
      )}

      {/* HEADER BANNER WITH FITTED COMBO BACKGROUND IMAGE */}
      <section 
        aria-label="Exclusive Offers Banner"
        className="w-full bg-black relative overflow-hidden min-h-[260px] sm:min-h-[300px] lg:h-[340px] xl:h-[380px] flex items-center justify-center"
      >
        {/* Right-aligned combo visual fitted inside the banner */}
        <div className="absolute top-0 right-0 bottom-0 h-full w-full max-w-[1200px] flex justify-end items-center pointer-events-none select-none z-0 p-3 sm:p-5 lg:p-6">
          <img
            src={offersData.banner.image_url || "/offers_combo_banner.png"}
            alt="Patty Project Exclusive Offers Combo"
            className="h-full w-auto max-h-[92%] sm:max-h-[95%] object-contain object-right select-none"
            loading="eager"
          />
        </div>

        {/* Soft edge gradient to ensure 100% crisp text readability */}
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/85 to-transparent sm:via-black/50 md:via-transparent z-[1] pointer-events-none" />

        {/* Banner Content Container */}
        <div className="w-full max-w-[1720px] h-full mx-auto px-4 sm:px-8 lg:px-16 flex items-center relative z-10 py-8 sm:py-0">
          <div className="w-full sm:w-1/2 lg:max-w-[560px] text-left">
            <span className="text-[#FF5A00] text-[12px] sm:text-[13px] font-extrabold uppercase tracking-[0.14em] block mb-2 sm:mb-2.5">
              {offersData.banner.tagline || "EXCLUSIVE OFFERS"}
            </span>
            <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-[50px] font-black uppercase tracking-tight leading-[0.98]">
              <span className="text-white block">{offersData.banner.headline_main || "DEALS THAT"}</span>
              <span className="text-[#FF5A00] block mt-1">{offersData.banner.headline_highlight || "HIT DIFFERENT."}</span>
            </h1>
            <p className="mt-3 sm:mt-4 text-[#A1A1AA] text-xs sm:text-sm md:text-base leading-relaxed max-w-[460px]">
              {offersData.banner.description || "Handpicked combos, limited-time treats and exclusive perks crafted to make your meal even better."}
            </p>
          </div>
        </div>
      </section>

      {/* MAIN CONTENT AREA (SEAMLESS FLOW WITH PURE BLACK BACKGROUND) */}
      <main className="flex-1 w-full max-w-[1720px] mx-auto px-4 sm:px-8 lg:px-16 pt-4 pb-12 sm:pt-6 sm:pb-16 space-y-8">
        {/* CATEGORY FILTER BAR (MATCHING MENU PAGE SHAPE) */}
        <section className="w-full flex justify-center">
          <div className="w-full flex items-center justify-start sm:justify-center gap-2.5 pb-2 overflow-x-auto scrollbar-none scroll-smooth">
            {categories.map((cat) => {
              const Icon = cat.icon;
              const isActive = activeCategory === cat.id;
              return (
                <button
                  key={cat.id}
                  onClick={() => setActiveCategory(cat.id)}
                  className={`h-9 px-4 rounded-lg text-xs font-semibold flex items-center gap-2 transition-colors shrink-0 cursor-pointer border ${
                    isActive
                      ? 'bg-[#FF5A00] text-white border-[#FF5A00] shadow-sm'
                      : 'bg-[#0D0D0D] text-[#A1A1AA] border-[#242424] hover:text-[#F5F5F5] hover:bg-[#151515] hover:border-[#333333]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-[#A1A1AA]'}`} />
                  <span>{cat.label}</span>
                </button>
              );
            })}
          </div>
        </section>

        {/* OFFERS CARDS GRID WITH REAL PRODUCT PICTURES */}
        <section className="w-full">
          {filteredOffers.length === 0 ? (
            <div className="text-center py-16 bg-[#111] border border-[#222] rounded-3xl space-y-3">
              <Sparkles className="w-8 h-8 text-[#FF5A00] mx-auto animate-pulse" />
              <h3 className="text-lg font-bold text-white uppercase">No offers in this category right now</h3>
              <p className="text-xs text-[#888]">Check back soon or explore our full menu for great daily prices.</p>
              <button
                onClick={() => setActiveCategory('all')}
                className="mt-2 text-xs font-bold text-[#FF5A00] underline hover:text-[#FF7733]"
              >
                View all offers
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 sm:gap-5">
              {filteredOffers.map((offer) => (
                <div
                  key={offer.id}
                  className="bg-[#0D0D0D] border border-[#242424] rounded-xl overflow-hidden transition-all duration-200 group flex flex-col justify-between hover:border-[#FF5A00]/50"
                >
                  {/* Top Card Image Area (4/3 Aspect Ratio matching Menu Page) */}
                  <div className="w-full aspect-[4/3] overflow-hidden bg-[#111111] relative border-b border-[#1C1C1C]">
                    <img
                      src={offer.image}
                      alt={offer.title}
                      className="w-full h-full object-cover group-hover:scale-[1.02] transition-transform duration-200 select-none"
                    />
                    <span className="absolute top-2 left-2 bg-[#FF5A00] text-white text-[9px] sm:text-[10px] font-black uppercase tracking-wider px-1.5 sm:px-2 py-0.5 rounded shadow-md z-10">
                      {offer.badge}
                    </span>
                  </div>

                  {/* Card Content Area */}
                  <div className="p-2.5 sm:p-4 space-y-2 sm:space-y-3 bg-[#0D0D0D] flex flex-col justify-between flex-1">
                    <div className="space-y-1 sm:space-y-2">
                      {/* Subtitle / Inclusion Tag */}
                      <div className="flex items-center gap-1 sm:gap-1.5 text-[10px] sm:text-[11px] font-bold text-[#FF5A00] uppercase tracking-wider truncate">
                        {renderTagIcon(offer.tagIcon)}
                        <span className="truncate">{offer.tag}</span>
                      </div>

                      {/* Offer Title */}
                      <h3 className="text-xs sm:text-base font-black uppercase tracking-wide text-[#F5F5F5] group-hover:text-[#FF5A00] transition-colors leading-snug line-clamp-1">
                        {offer.title}
                      </h3>

                      {/* Description */}
                      <p className="text-[11px] sm:text-xs text-[#9CA3AF] leading-relaxed line-clamp-2">
                        {offer.description}
                      </p>
                    </div>

                    {/* Bottom Action Row */}
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between pt-2 sm:pt-3 border-t border-[#1C1C1C] gap-1.5 sm:gap-2">
                      {/* Coupon Code Pill */}
                      <button
                        onClick={(e) => handleCopyCode(offer.code, e)}
                        title="Click to copy coupon code"
                        className="flex items-center justify-center gap-1 sm:gap-1.5 text-[10px] sm:text-xs font-mono font-bold bg-[#141414] hover:bg-[#1A1A1A] border border-[#2B2B2B] hover:border-[#FF5A00]/60 px-2 sm:px-3 py-1 sm:py-1.5 rounded-md sm:rounded-lg text-white transition-all cursor-pointer group/code"
                      >
                        {copiedCode === offer.code ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Tag className="w-3 h-3 text-[#FF5A00] group-hover/code:scale-110 transition-transform" />
                        )}
                        <span>{offer.code}</span>
                      </button>

                      {/* Claim Deal Button */}
                      <button
                        onClick={() => handleClaimDeal(offer)}
                        className="bg-[#FF5A00] hover:bg-[#E04B00] active:scale-95 text-white px-2.5 sm:px-3.5 py-1 sm:py-1.5 rounded-md sm:rounded-lg text-[10px] sm:text-xs font-bold flex items-center justify-center gap-1 sm:gap-1.5 transition-all shadow-sm shadow-[#FF5A00]/20 cursor-pointer whitespace-nowrap"
                      >
                        <span>Claim Deal</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
};

export default CustomerOffers;
