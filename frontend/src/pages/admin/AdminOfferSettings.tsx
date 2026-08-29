import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  Save,
  RotateCcw,
  Plus,
  Trash2,
  Edit2,
  CheckCircle2,
  AlertCircle,
  Eye,
  Tag,
  Upload,
  Camera,
  Image as ImageIcon,
  Clock,
  Gift,
  Utensils,
  UtensilsCrossed,
  Sliders,
  Check,
  X
} from 'lucide-react';
import { api } from '../../api/client';
import offerBg1 from '../../assets/offer_bg_1.png';
import offerBg2 from '../../assets/offer_bg_2.png';
import offerBg3 from '../../assets/offer_bg_3.png';

interface TodaysOfferCard {
  id: string;
  title: string;
  subtitle: string;
  badge: string;
  badge_type?: string;
  image_url: string;
  bg_image?: string;
  link_url?: string;
}

interface TodaysOffersConfig {
  section_title: string;
  view_all_link: string;
  view_all_text: string;
  cards: TodaysOfferCard[];
}

interface OfferPageItem {
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

interface OffersPageConfig {
  banner: {
    tagline: string;
    headline_main: string;
    headline_highlight: string;
    description: string;
    image_url: string;
  };
  offers: OfferPageItem[];
}

interface ComboDealItem {
  id: string;
  name: string;
  subtitle: string;
  badge: string;
  description: string;
  base_price: number;
  compare_at_price?: number;
  image_url: string;
  category_slug?: string;
  is_active: boolean;
  modifiers: { name: string; price: number }[];
  ingredients?: string;
}

interface ComboDealsConfig {
  combos: ComboDealItem[];
}

const DEFAULT_TODAYS_CONFIG: TodaysOffersConfig = {
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
      bg_image: "offer_bg_1.png",
      link_url: "/order"
    },
    {
      id: "card-2",
      title: "WING WEDNESDAY",
      subtitle: "On All Wings",
      badge: "20% OFF",
      image_url: "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=500&q=80",
      bg_image: "offer_bg_2.png",
      link_url: "/order"
    },
    {
      id: "card-3",
      title: "STUDENT OFFER",
      subtitle: "On All Orders",
      badge: "10% OFF",
      badge_type: "id_badge",
      image_url: "",
      bg_image: "offer_bg_3.png",
      link_url: "/order"
    }
  ]
};

const DEFAULT_OFFERS_PAGE_CONFIG: OffersPageConfig = {
  banner: {
    tagline: "EXCLUSIVE OFFERS",
    headline_main: "DEALS THAT",
    headline_highlight: "HIT DIFFERENT.",
    description: "Handpicked combos, limited-time treats and exclusive perks crafted to make your meal even better.",
    image_url: "/offers_combo_banner.png"
  },
  offers: [
    {
      id: "combo",
      category: ["combos", "burgers"],
      title: "BURGER COMBO",
      tag: "BURGER + FRIES + DRINK",
      tagIcon: "utensils",
      badge: "SAVE 15%",
      code: "COMBO15",
      image: "/product_the_mc_project.png",
      description: "Get our signature double smash burger served with seasoned skin-on fries and any cold drink of your choice."
    },
    {
      id: "family",
      category: ["combos", "burgers", "sides"],
      title: "PATTY FEAST (FEEDS 4)",
      tag: "4 BURGERS + 2 FRIES + 4 DRINKS",
      tagIcon: "utensils",
      badge: "POPULAR",
      code: "FEAST20",
      image: "/product_the_outlaw_project_.png",
      description: "The ultimate burger party box! Includes 4 classic smash burgers, 2 large rosemary salt fries, and 4 refreshing drinks."
    },
    {
      id: "lunch",
      category: ["limited", "burgers"],
      title: "LUNCH SPECIAL",
      tag: "MON - FRI, 12PM - 4PM",
      tagIcon: "clock",
      badge: "£5.99 ONLY",
      code: "LUNCH599",
      image: "/product_pastrami_burger_.png",
      description: "Quick lunch win! Single smash patty burger or crispy chicken sandwich with skin-on fries for just £5.99."
    },
    {
      id: "shake",
      category: ["drinks", "limited"],
      title: "FREE SHAKE UPGRADE",
      tag: "WITH ANY BURGER & FRIES ORDER",
      tagIcon: "gift",
      badge: "LIMITED TIME",
      code: "SHAKEUP",
      image: "https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=600&q=80",
      description: "Upgrade your soft drink to any handmade gourmet milkshake for free when you order a burger and sides."
    }
  ]
};

const DEFAULT_COMBO_DEALS_CONFIG: ComboDealsConfig = {
  combos: []
};

export const AdminOfferSettings: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'today' | 'offersPage' | 'comboSetting'>('today');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Today's Offers State
  const [todaysConfig, setTodaysConfig] = useState<TodaysOffersConfig>(DEFAULT_TODAYS_CONFIG);

  // Offers Page State
  const [offersPageConfig, setOffersPageConfig] = useState<OffersPageConfig>(DEFAULT_OFFERS_PAGE_CONFIG);

  // Combo Deals State
  const [comboDealsConfig, setComboDealsConfig] = useState<ComboDealsConfig>(DEFAULT_COMBO_DEALS_CONFIG);

  // Edit Offer Modal State for Tab 2
  const [editingOffer, setEditingOffer] = useState<OfferPageItem | null>(null);
  const [isAddingNewOffer, setIsAddingNewOffer] = useState(false);

  // Edit Combo Modal State for Tab 3
  const [editingCombo, setEditingCombo] = useState<ComboDealItem | null>(null);
  const [isAddingNewCombo, setIsAddingNewCombo] = useState(false);
  const [editingComboIngredients, setEditingComboIngredients] = useState<string[]>([]);

  // Hidden File Input refs
  const cardFileInputRefs = [
    useRef<HTMLInputElement | null>(null),
    useRef<HTMLInputElement | null>(null),
    useRef<HTMLInputElement | null>(null)
  ];
  const modalFileInputRef = useRef<HTMLInputElement | null>(null);
  const comboFileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const [todayData, pageData, comboData] = await Promise.all([
        api.get<TodaysOffersConfig>('/promotions/settings/todays-offers').catch(() => DEFAULT_TODAYS_CONFIG),
        api.get<OffersPageConfig>('/promotions/settings/offers-page').catch(() => DEFAULT_OFFERS_PAGE_CONFIG),
        api.get<ComboDealsConfig>('/promotions/settings/combo-deals').catch(() => DEFAULT_COMBO_DEALS_CONFIG)
      ]);
      if (todayData && todayData.cards) setTodaysConfig(todayData);
      if (pageData && pageData.banner) setOffersPageConfig(pageData);
      if (comboData && comboData.combos) setComboDealsConfig(comboData);
    } catch (err: any) {
      console.error('Failed to load offer settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const showNotification = (msg: string, isError = false) => {
    if (isError) {
      setErrorMsg(msg);
      setSuccessMsg(null);
    } else {
      setSuccessMsg(msg);
      setErrorMsg(null);
    }
    setTimeout(() => {
      setSuccessMsg(null);
      setErrorMsg(null);
    }, 3500);
  };

  // Convert uploaded image file to Data URL
  const handleFileUpload = (
    e: React.ChangeEvent<HTMLInputElement>,
    onComplete: (dataUrl: string) => void
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 8 * 1024 * 1024) {
      showNotification('Image size exceeds 8MB limit. Please choose a smaller photo.', true);
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        onComplete(reader.result);
        showNotification('Photo uploaded successfully!');
      }
    };
    reader.onerror = () => {
      showNotification('Failed to read image file.', true);
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  const handleSaveTodaysOffers = async () => {
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await api.put<TodaysOffersConfig>('/promotions/settings/todays-offers', todaysConfig);
      setTodaysConfig(updated);
      showNotification("Today's Offers saved successfully! Customer Home is now updated.");
    } catch (err: any) {
      console.error(err);
      showNotification(err?.message || "Failed to save Today's Offers.", true);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveOffersPage = async () => {
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await api.put<OffersPageConfig>('/promotions/settings/offers-page', offersPageConfig);
      setOffersPageConfig(updated);
      showNotification("Offers Page settings saved successfully! /offers is now updated.");
    } catch (err: any) {
      console.error(err);
      showNotification(err?.message || "Failed to save Offers Page settings.", true);
    } finally {
      setSaving(false);
    }
  };

  const handleSaveComboDeals = async () => {
    setSaving(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await api.put<ComboDealsConfig>('/promotions/settings/combo-deals', comboDealsConfig);
      if (updated && Array.isArray(updated.combos)) {
        setComboDealsConfig(updated);
      }
      showNotification("Combo settings saved! All combo deals synced to the Customer Menu.");
    } catch (err: any) {
      console.error(err);
      showNotification(err?.message || "Failed to save Combo Deals.", true);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateCardField = (index: number, field: keyof TodaysOfferCard, value: string) => {
    setTodaysConfig(prev => {
      const updatedCards = [...prev.cards];
      updatedCards[index] = { ...updatedCards[index], [field]: value };
      return { ...prev, cards: updatedCards };
    });
  };

  const handleSaveOfferItem = (offerItem: OfferPageItem) => {
    setOffersPageConfig(prev => {
      const existingIndex = prev.offers.findIndex(o => o.id === offerItem.id);
      let newOffers = [...prev.offers];
      if (existingIndex >= 0) {
        newOffers[existingIndex] = offerItem;
      } else {
        newOffers.push(offerItem);
      }
      return { ...prev, offers: newOffers };
    });
    setEditingOffer(null);
    setIsAddingNewOffer(false);
  };

  const handleDeleteOfferItem = (id: string) => {
    setOffersPageConfig(prev => ({
      ...prev,
      offers: prev.offers.filter(o => o.id !== id)
    }));
  };

  const handleSaveComboItem = async (comboItem: ComboDealItem) => {
    const finalCombo = {
      ...comboItem,
      ingredients: editingComboIngredients.filter(i => i.trim() !== '').join(', ')
    };

    const newCombos = [...comboDealsConfig.combos];
    const existingIndex = newCombos.findIndex(c => c.id === finalCombo.id);
    if (existingIndex >= 0) {
      newCombos[existingIndex] = finalCombo;
    } else {
      newCombos.push(finalCombo);
    }

    setComboDealsConfig({ combos: newCombos });
    setEditingCombo(null);
    setIsAddingNewCombo(false);

    // Auto sync to backend
    try {
      const updated = await api.put<ComboDealsConfig>('/promotions/settings/combo-deals', { combos: newCombos });
      if (updated && Array.isArray(updated.combos)) {
        setComboDealsConfig(updated);
      }
      showNotification("Combo deal saved & synced to Customer Menu under 'Combo Deals (Offer)'!");
    } catch (err: any) {
      console.error('Failed to sync combo deal:', err);
      showNotification(err?.message || "Failed to sync combo deal to menu.", true);
    }
  };

  const handleDeleteComboItem = async (id: string) => {
    const newCombos = comboDealsConfig.combos.filter(c => c.id !== id);
    setComboDealsConfig({ combos: newCombos });
    try {
      const updated = await api.put<ComboDealsConfig>('/promotions/settings/combo-deals', { combos: newCombos });
      if (updated && Array.isArray(updated.combos)) {
        setComboDealsConfig(updated);
      }
      showNotification("Combo deal removed from menu.");
    } catch (err: any) {
      console.error(err);
      showNotification(err?.message || "Failed to remove combo deal.", true);
    }
  };

  const handleOpenEditCombo = (combo: ComboDealItem) => {
    setEditingCombo({
      ...combo,
      modifiers: Array.isArray(combo.modifiers) ? [...combo.modifiers] : []
    });
    setIsAddingNewCombo(false);
    let ingList: string[] = [];
    if (typeof combo.ingredients === 'string') {
      ingList = combo.ingredients.split(',').map(s => s.trim()).filter(Boolean);
    } else if (Array.isArray(combo.ingredients)) {
      ingList = combo.ingredients;
    }
    setEditingComboIngredients(ingList);
  };

  const handleOpenCreateCombo = () => {
    const newCombo: ComboDealItem = {
      id: `combo-${Date.now()}`,
      name: '',
      subtitle: '',
      badge: '',
      description: '',
      base_price: 0,
      compare_at_price: undefined,
      image_url: '',
      category_slug: 'combo-offers',
      is_active: true,
      modifiers: [],
      ingredients: ''
    };
    setEditingCombo(newCombo);
    setIsAddingNewCombo(true);
    setEditingComboIngredients([]);
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[400px]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-[#FF5500] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-[#9CA3AF]">Loading Offer & Combo Settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#262626]">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#FF5500]/10 border border-[#FF5500]/30 rounded-2xl text-[#FF5500]">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-wide">Offers & Combo Deals</h1>
              <p className="text-[#9CA3AF] text-xs sm:text-sm mt-0.5">
                Manage Today's Offers, Offers Page banners, and declare Product Combo Deals synced to the menu.
              </p>
            </div>
          </div>
        </div>

        {/* Global Save Button */}
        <div className="flex items-center gap-3">
          <button
            onClick={
              activeTab === 'today'
                ? handleSaveTodaysOffers
                : activeTab === 'offersPage'
                ? handleSaveOffersPage
                : handleSaveComboDeals
            }
            disabled={saving}
            className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all shadow-md shadow-[#FF5500]/20 disabled:opacity-50 cursor-pointer"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving Changes...' : 'Save & Publish'}</span>
          </button>
        </div>
      </div>

      {/* Toast Alert */}
      {successMsg && (
        <div className="p-3.5 bg-[#132A1B] border border-[#22C55E]/40 text-[#86EFAC] rounded-xl text-xs font-semibold flex items-center gap-2.5 shadow-lg animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}
      {errorMsg && (
        <div className="p-3.5 bg-[#2A1215] border border-[#EF4444]/40 text-[#FCA5A5] rounded-xl text-xs font-semibold flex items-center gap-2.5 shadow-lg animate-in fade-in">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tabs Navigation Bar */}
      <div className="flex border-b border-[#262626] gap-2">
        <button
          onClick={() => setActiveTab('today')}
          className={`px-5 py-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 flex items-center gap-2 cursor-pointer ${
            activeTab === 'today'
              ? 'border-[#FF5500] text-white bg-[#FF5500]/10 rounded-t-xl'
              : 'border-transparent text-[#9CA3AF] hover:text-white'
          }`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Today's Offers (Home)</span>
        </button>

        <button
          onClick={() => setActiveTab('offersPage')}
          className={`px-5 py-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 flex items-center gap-2 cursor-pointer ${
            activeTab === 'offersPage'
              ? 'border-[#FF5500] text-white bg-[#FF5500]/10 rounded-t-xl'
              : 'border-transparent text-[#9CA3AF] hover:text-white'
          }`}
        >
          <Tag className="w-4 h-4" />
          <span>Offers Page (/offers)</span>
        </button>

        <button
          onClick={() => setActiveTab('comboSetting')}
          className={`px-5 py-3 text-xs font-bold tracking-wider uppercase transition-all border-b-2 flex items-center gap-2 cursor-pointer ${
            activeTab === 'comboSetting'
              ? 'border-[#FF5500] text-white bg-[#FF5500]/10 rounded-t-xl'
              : 'border-transparent text-[#9CA3AF] hover:text-white'
          }`}
        >
          <UtensilsCrossed className="w-4 h-4" />
          <span>Combo Deals & Menu Setting</span>
        </button>
      </div>

      {/* ============================================================ */}
      {/* TAB 1: TODAY'S OFFERS CONFIGURATION */}
      {/* ============================================================ */}
      {activeTab === 'today' && (
        <div className="space-y-6">
          <div className="bg-[#181818] border border-[#262626] rounded-2xl p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#262626]">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider font-hero">
                  Home Page Today's Offer Cards (3 Cards)
                </h2>
                <p className="text-xs text-[#9CA3AF]">
                  Directly upload photos and edit text for the 3 interactive offer cards displayed on the customer home page.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setTodaysConfig(DEFAULT_TODAYS_CONFIG)}
                className="text-xs text-[#A1A1AA] hover:text-white flex items-center gap-1.5 px-3 py-2 bg-[#1A1A1A] hover:bg-[#262626] rounded-xl border border-[#2A2A2A] cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Defaults</span>
              </button>
            </div>

            {/* 3 Offer Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {todaysConfig.cards.map((card, idx) => (
                <div key={card.id} className="bg-[#121212] border border-[#262626] rounded-2xl p-5 space-y-4 flex flex-col justify-between">
                  <div className="space-y-4">
                    {/* Header with Card Number & Badge */}
                    <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                      <span className="text-xs font-bold text-[#FF5500]">Card #{idx + 1}</span>
                      <span className="text-[10px] font-extrabold uppercase bg-[#FF5500] text-white px-2 py-0.5 rounded">
                        {card.badge || 'BADGE'}
                      </span>
                    </div>

                    {/* DIRECT PHOTO UPLOAD PREVIEW */}
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                        Card Photo
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        ref={cardFileInputRefs[idx]}
                        onChange={(e) => handleFileUpload(e, (dataUrl) => handleUpdateCardField(idx, 'image_url', dataUrl))}
                        className="hidden"
                      />

                      {card.image_url ? (
                        <div className="relative group rounded-xl overflow-hidden border border-[#262626] bg-black h-36 flex items-center justify-center">
                          <img
                            src={card.image_url}
                            alt={card.title}
                            className="w-full h-full object-contain p-2 group-hover:scale-105 transition-transform select-none"
                            onError={(e) => {
                              (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                            }}
                          />
                          <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-2 transition-opacity">
                            <button
                              type="button"
                              onClick={() => cardFileInputRefs[idx].current?.click()}
                              className="p-2 bg-[#222] hover:bg-[#333] text-white rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer"
                            >
                              <Camera className="w-3.5 h-3.5" />
                              <span>Change</span>
                            </button>
                            <button
                              type="button"
                              onClick={() => handleUpdateCardField(idx, 'image_url', '')}
                              className="p-2 bg-[#2A1215] text-[#EF4444] rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          type="button"
                          onClick={() => cardFileInputRefs[idx].current?.click()}
                          className="w-full h-36 border-2 border-dashed border-[#333] hover:border-[#FF5500] bg-[#161616] rounded-xl flex flex-col items-center justify-center gap-2 text-xs font-bold text-white transition-colors cursor-pointer group"
                        >
                          <Upload className="w-5 h-5 text-[#FF5500] group-hover:scale-110 transition-transform" />
                          <span>Click to Upload Card Photo</span>
                          <span className="text-[10px] text-[#666]">PNG, JPG, WEBP up to 8MB</span>
                        </button>
                      )}
                    </div>

                    {/* Text Inputs */}
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Headline Title</label>
                        <input
                          type="text"
                          value={card.title}
                          onChange={(e) => handleUpdateCardField(idx, 'title', e.target.value)}
                          className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#666] focus:outline-none focus:border-[#FF5500]"
                          placeholder="e.g. BURGER COMBO"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Subtitle / Details</label>
                        <input
                          type="text"
                          value={card.subtitle}
                          onChange={(e) => handleUpdateCardField(idx, 'subtitle', e.target.value)}
                          className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#666] focus:outline-none focus:border-[#FF5500]"
                          placeholder="e.g. Burger + Fries + Drink"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Badge Tag Text</label>
                        <input
                          type="text"
                          value={card.badge}
                          onChange={(e) => handleUpdateCardField(idx, 'badge', e.target.value)}
                          className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#666] focus:outline-none focus:border-[#FF5500]"
                          placeholder="e.g. SAVE 15%"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 2: OFFERS PAGE CONFIGURATION (/offers) */}
      {/* ============================================================ */}
      {activeTab === 'offersPage' && (
        <div className="space-y-6">
          {/* Active Offers List Grid */}
          <div className="bg-[#181818] border border-[#262626] rounded-2xl p-6 space-y-6">
            <div className="flex items-center justify-between pb-4 border-b border-[#262626]">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider font-hero">
                  Active Offer Deals List ({offersPageConfig.offers.length})
                </h2>
                <p className="text-xs text-[#9CA3AF]">Create, edit, or delete deals rendered on the Offers page.</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setOffersPageConfig(DEFAULT_OFFERS_PAGE_CONFIG)}
                  className="text-xs text-[#A1A1AA] hover:text-white flex items-center gap-1.5 px-3 py-2 bg-[#1A1A1A] hover:bg-[#262626] rounded-xl border border-[#2A2A2A] cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset Defaults</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setEditingOffer({
                      id: `offer-${Date.now()}`,
                      category: ['combos', 'burgers'],
                      title: '',
                      tag: '',
                      tagIcon: 'utensils',
                      badge: '',
                      code: '',
                      image: '',
                      description: ''
                    });
                    setIsAddingNewOffer(true);
                  }}
                  className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-[#FF5500]/20 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  <span>Add Offer Deal</span>
                </button>
              </div>
            </div>

            {/* Offer Cards Table/Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {offersPageConfig.offers.map((offer) => (
                <div key={offer.id} className="bg-[#121212] border border-[#262626] rounded-2xl p-4 space-y-3 flex flex-col justify-between">
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-extrabold uppercase bg-[#FF5500] text-white px-2 py-0.5 rounded">
                        {offer.badge || 'PROMO'}
                      </span>
                      <span className="text-[10px] text-[#A1A1AA] font-mono bg-[#1C1C1C] px-2 py-0.5 rounded">
                        Code: {offer.code || 'N/A'}
                      </span>
                    </div>

                    <div className="flex gap-3">
                      {offer.image ? (
                        <img
                          src={offer.image}
                          alt={offer.title}
                          className="w-16 h-16 rounded-xl object-cover bg-black border border-[#262626] shrink-0"
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                          }}
                        />
                      ) : (
                        <div className="w-16 h-16 rounded-xl bg-[#1C1C1C] border border-[#262626] flex items-center justify-center text-[#666] shrink-0">
                          <ImageIcon className="w-6 h-6" />
                        </div>
                      )}
                      <div className="min-w-0 flex-1">
                        <h3 className="text-xs font-bold text-white uppercase truncate">{offer.title}</h3>
                        <p className="text-[11px] text-[#FF5500] font-semibold truncate">{offer.tag}</p>
                        <p className="text-[10px] text-[#9CA3AF] line-clamp-2 mt-1">{offer.description}</p>
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#262626] flex items-center justify-between">
                    <span className="text-[10px] text-[#6B7280]">
                      Categories: {offer.category.join(', ')}
                    </span>
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => {
                          setEditingOffer(offer);
                          setIsAddingNewOffer(false);
                        }}
                        className="p-1.5 text-[#9CA3AF] hover:text-[#FF5500] hover:bg-[#1A1A1A] rounded-lg transition-colors cursor-pointer"
                        title="Edit Offer"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteOfferItem(offer.id)}
                        className="p-1.5 text-[#9CA3AF] hover:text-[#EF4444] hover:bg-[#2A1215] rounded-lg transition-colors cursor-pointer"
                        title="Delete Offer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Offer Edit / Add Modal */}
          {editingOffer && (
            <div className="admin-modal-overlay">
              <div className="admin-modal-container bg-[#121212] border border-[#262626] rounded-2xl max-w-lg shadow-2xl p-4 sm:p-6 relative space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626] shrink-0">
                  <h3 className="text-sm font-bold text-white uppercase">
                    {isAddingNewOffer ? 'Add New Offer Deal' : `Edit Offer (${editingOffer.title})`}
                  </h3>
                  <button
                    onClick={() => setEditingOffer(null)}
                    className="text-[#9CA3AF] hover:text-white text-xs px-2 py-1 bg-[#1A1A1A] rounded-lg cursor-pointer shrink-0"
                  >
                    Cancel
                  </button>
                </div>

                <div className="space-y-3 flex-1 overflow-y-auto pr-1">
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Offer Title</label>
                    <input
                      type="text"
                      value={editingOffer.title}
                      onChange={(e) => setEditingOffer({ ...editingOffer, title: e.target.value })}
                      className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                      placeholder="e.g. BURGER COMBO"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Tag / Inclusion</label>
                      <input
                        type="text"
                        value={editingOffer.tag}
                        onChange={(e) => setEditingOffer({ ...editingOffer, tag: e.target.value })}
                        className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="e.g. BURGER + FRIES + DRINK"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Badge Text</label>
                      <input
                        type="text"
                        value={editingOffer.badge}
                        onChange={(e) => setEditingOffer({ ...editingOffer, badge: e.target.value })}
                        className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="e.g. SAVE 15%"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Coupon Promo Code</label>
                      <input
                        type="text"
                        value={editingOffer.code}
                        onChange={(e) => setEditingOffer({ ...editingOffer, code: e.target.value.toUpperCase() })}
                        className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500] font-mono uppercase"
                        placeholder="e.g. COMBO15"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Icon Style</label>
                      <select
                        value={editingOffer.tagIcon}
                        onChange={(e) => setEditingOffer({ ...editingOffer, tagIcon: e.target.value as any })}
                        className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                      >
                        <option value="utensils">Utensils (Food / Meals)</option>
                        <option value="clock">Clock (Time / Lunch)</option>
                        <option value="gift">Gift (Freebie / Bonus)</option>
                      </select>
                    </div>
                  </div>

                  {/* DIRECT FILE UPLOAD FOR OFFER PHOTO */}
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">Offer Photo</label>
                    <input
                      type="file"
                      accept="image/*"
                      ref={modalFileInputRef}
                      onChange={(e) => handleFileUpload(e, (dataUrl) => setEditingOffer({ ...editingOffer, image: dataUrl }))}
                      className="hidden"
                    />

                    {editingOffer.image ? (
                      <div className="flex items-center gap-3 bg-[#1A1A1A] border border-[#262626] rounded-xl p-2">
                        <img
                          src={editingOffer.image}
                          alt="Offer preview"
                          className="w-16 h-16 rounded-lg object-cover bg-black"
                        />
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => modalFileInputRef.current?.click()}
                            className="px-2.5 py-1 bg-[#262626] hover:bg-[#333] text-white rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer"
                          >
                            <Camera className="w-3.5 h-3.5" />
                            <span>Change Photo</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingOffer({ ...editingOffer, image: '' })}
                            className="px-2 py-1 bg-[#2A1215] text-[#EF4444] rounded-lg text-xs font-bold cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => modalFileInputRef.current?.click()}
                        className="w-full py-4 border-2 border-dashed border-[#333] hover:border-[#FF5500] bg-[#161616] rounded-xl flex flex-col items-center justify-center gap-1 text-xs font-bold text-white cursor-pointer group"
                      >
                        <Upload className="w-4 h-4 text-[#FF5500] group-hover:scale-110 transition-transform" />
                        <span>Upload Photo from Device</span>
                        <span className="text-[10px] text-[#666]">PNG, JPG, WEBP up to 8MB</span>
                      </button>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Category Tags (comma separated)</label>
                    <input
                      type="text"
                      value={editingOffer.category.join(', ')}
                      onChange={(e) =>
                        setEditingOffer({
                          ...editingOffer,
                          category: e.target.value.split(',').map(s => s.trim().toLowerCase()).filter(Boolean)
                        })
                      }
                      className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                      placeholder="combos, burgers, sides, drinks, limited"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">Description</label>
                    <textarea
                      rows={3}
                      value={editingOffer.description}
                      onChange={(e) => setEditingOffer({ ...editingOffer, description: e.target.value })}
                      className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                      placeholder="Detailed offer perks description..."
                    />
                  </div>
                </div>

                <div className="pt-3 border-t border-[#262626] flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditingOffer(null)}
                    className="px-4 py-2 bg-[#1A1A1A] hover:bg-[#262626] text-white rounded-xl text-xs font-semibold cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveOfferItem(editingOffer)}
                    className="px-5 py-2 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-xl text-xs font-bold cursor-pointer"
                  >
                    Confirm & Update Card
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/* TAB 3: COMBO DEALS & MENU CATEGORY SETTING */}
      {/* ============================================================ */}
      {activeTab === 'comboSetting' && (
        <div className="space-y-6">
          {/* Active Combos List Card */}
          <div className="bg-[#181818] border border-[#262626] rounded-2xl p-6 space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#262626]">
              <div>
                <h2 className="text-sm font-bold text-white uppercase tracking-wider font-hero">
                  Product Combo Offers ({comboDealsConfig.combos.length})
                </h2>
                <p className="text-xs text-[#9CA3AF]">
                  Declare combo prices, included items & add-ons. All active combos automatically show under the <span className="text-[#FF5500] font-semibold">"Combo Offers"</span> category on the customer menu.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setComboDealsConfig(DEFAULT_COMBO_DEALS_CONFIG)}
                  className="text-xs text-[#A1A1AA] hover:text-white flex items-center gap-1.5 px-3 py-2 bg-[#1A1A1A] hover:bg-[#262626] rounded-xl border border-[#2A2A2A] cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset Defaults</span>
                </button>
                <button
                  type="button"
                  onClick={handleOpenCreateCombo}
                  className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all shadow-md shadow-[#FF5500]/20 cursor-pointer"
                >
                  <Plus className="w-4 h-4" />
                  <span>Create New Combo</span>
                </button>
              </div>
            </div>

            {/* Combos Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {comboDealsConfig.combos.map((combo) => (
                <div
                  key={combo.id}
                  className="bg-[#121212] border border-[#262626] rounded-2xl overflow-hidden flex flex-col justify-between hover:border-[#FF5500]/40 transition-colors group"
                >
                  <div>
                    {/* Image Area */}
                    <div className="relative h-44 bg-black overflow-hidden border-b border-[#262626]">
                      <img
                        src={combo.image_url || '/placeholder-burger.svg'}
                        alt={combo.name}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300 select-none"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                      />
                      <div className="absolute top-2.5 left-2.5 flex items-center gap-1.5">
                        <span className="bg-[#FF5500] text-white text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded shadow">
                          {combo.badge || 'COMBO'}
                        </span>
                        {combo.is_active ? (
                          <span className="bg-[#22C55E]/90 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow">
                            Active in Menu
                          </span>
                        ) : (
                          <span className="bg-[#71717A]/90 text-white text-[9px] font-bold px-1.5 py-0.5 rounded shadow">
                            Inactive
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Content Area */}
                    <div className="p-4 space-y-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-sm font-bold text-white uppercase">{combo.name}</h3>
                        <div className="text-right shrink-0">
                          <span className="text-sm font-extrabold text-[#FF5500]">
                            £{combo.base_price.toFixed(2)}
                          </span>
                          {combo.compare_at_price && combo.compare_at_price > combo.base_price && (
                            <span className="text-xs text-[#71717A] line-through block">
                              £{combo.compare_at_price.toFixed(2)}
                            </span>
                          )}
                        </div>
                      </div>

                      <p className="text-[11px] font-semibold text-[#FF8844]">
                        {combo.subtitle}
                      </p>

                      <p className="text-xs text-[#9CA3AF] line-clamp-2">
                        {combo.description}
                      </p>

                      {/* Custom Choices count */}
                      {combo.modifiers && combo.modifiers.length > 0 && (
                        <div className="pt-2 border-t border-[#222]">
                          <span className="text-[10px] text-[#71717A] font-semibold block mb-1 uppercase tracking-wider">
                            Custom Choices ({combo.modifiers.length}):
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {combo.modifiers.slice(0, 3).map((mod, i) => (
                              <span key={i} className="text-[10px] bg-[#1C1C1C] border border-[#2C2C2C] text-[#D1D5DB] px-1.5 py-0.5 rounded">
                                {mod.name} {mod.price > 0 ? `(+£${mod.price.toFixed(2)})` : ''}
                              </span>
                            ))}
                            {combo.modifiers.length > 3 && (
                              <span className="text-[10px] text-[#71717A] py-0.5 px-1 font-semibold">
                                +{combo.modifiers.length - 3} more
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions Footer */}
                  <div className="p-4 pt-3 border-t border-[#262626] bg-[#141414] flex items-center justify-between">
                    <span className="text-[10px] text-[#6B7280]">
                      Category: Combo Offers
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleOpenEditCombo(combo)}
                        className="px-3 py-1.5 bg-[#222] hover:bg-[#333] text-white rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer transition-colors border border-[#333]"
                      >
                        <Edit2 className="w-3 h-3 text-[#FF5500]" />
                        <span>Edit</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDeleteComboItem(combo.id)}
                        className="p-1.5 bg-[#2A1215] text-[#EF4444] rounded-lg text-xs font-bold cursor-pointer hover:bg-[#3D1A1F] transition-colors"
                        title="Delete Combo"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Create / Edit Combo Deal Modal */}
          {editingCombo && (
            <div className="admin-modal-overlay">
              <div className="admin-modal-container bg-[#121212] border border-[#262626] rounded-2xl max-w-2xl shadow-2xl p-4 sm:p-6 relative flex flex-col text-white">
                <div className="flex items-center justify-between pb-3 sm:pb-4 border-b border-[#262626] shrink-0">
                  <div className="flex items-center gap-2.5">
                    <div className="p-2 bg-[#FF5500]/10 border border-[#FF5500]/30 rounded-xl text-[#FF5500]">
                      <UtensilsCrossed className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-white uppercase">
                        {isAddingNewCombo ? 'Create New Combo Deal' : `Edit Combo (${editingCombo.name})`}
                      </h3>
                      <p className="text-xs text-[#9CA3AF]">
                        Configure bundle price, photo, included items & choices
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setEditingCombo(null)}
                    className="p-1.5 text-[#9CA3AF] hover:text-white rounded-lg hover:bg-[#1A1A1A] cursor-pointer"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="space-y-4 overflow-y-auto pr-1 py-4 flex-1">
                  {/* Title & Subtitle */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                        Combo Title *
                      </label>
                      <input
                        type="text"
                        value={editingCombo.name}
                        onChange={(e) => setEditingCombo({ ...editingCombo, name: e.target.value })}
                        className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="e.g. Double Trouble Burger Combo"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                        Inclusions / Subtitle *
                      </label>
                      <input
                        type="text"
                        value={editingCombo.subtitle}
                        onChange={(e) => setEditingCombo({ ...editingCombo, subtitle: e.target.value })}
                        className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="e.g. Double Smash Burger + Fries + Drink"
                        required
                      />
                    </div>
                  </div>

                  {/* Pricing & Badge */}
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                        Combo Price (£) *
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={editingCombo.base_price}
                        onChange={(e) => setEditingCombo({ ...editingCombo, base_price: parseFloat(e.target.value || '0') })}
                        className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="9.95"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                        Compare Price (£)
                      </label>
                      <input
                        type="number"
                        step="0.01"
                        value={editingCombo.compare_at_price || ''}
                        onChange={(e) => setEditingCombo({ ...editingCombo, compare_at_price: e.target.value ? parseFloat(e.target.value) : undefined })}
                        className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="13.50"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                        Badge Tag
                      </label>
                      <input
                        type="text"
                        value={editingCombo.badge}
                        onChange={(e) => setEditingCombo({ ...editingCombo, badge: e.target.value })}
                        className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                        placeholder="e.g. SAVE 25%"
                      />
                    </div>
                  </div>

                  {/* Direct Photo Upload */}
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Combo Photo
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      ref={comboFileInputRef}
                      onChange={(e) => handleFileUpload(e, (dataUrl) => setEditingCombo({ ...editingCombo, image_url: dataUrl }))}
                      className="hidden"
                    />

                    {editingCombo.image_url ? (
                      <div className="flex items-center gap-3 bg-[#181818] border border-[#262626] rounded-xl p-3">
                        <img
                          src={editingCombo.image_url}
                          alt="Combo preview"
                          className="w-20 h-20 rounded-lg object-cover bg-black"
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                          }}
                        />
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => comboFileInputRef.current?.click()}
                            className="px-3 py-1.5 bg-[#262626] hover:bg-[#333] text-white rounded-lg text-xs font-bold flex items-center gap-1 cursor-pointer"
                          >
                            <Camera className="w-3.5 h-3.5" />
                            <span>Change Photo</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => setEditingCombo({ ...editingCombo, image_url: '' })}
                            className="px-2.5 py-1.5 bg-[#2A1215] text-[#EF4444] rounded-lg text-xs font-bold cursor-pointer"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => comboFileInputRef.current?.click()}
                        className="w-full py-5 border-2 border-dashed border-[#333] hover:border-[#FF5500] bg-[#161616] rounded-xl flex flex-col items-center justify-center gap-1 text-xs font-bold text-white cursor-pointer group"
                      >
                        <Upload className="w-5 h-5 text-[#FF5500] group-hover:scale-110 transition-transform" />
                        <span>Upload Combo Photo</span>
                        <span className="text-[10px] text-[#666]">PNG, JPG, WEBP up to 8MB</span>
                      </button>
                    )}
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1">
                      Combo Description
                    </label>
                    <textarea
                      rows={2}
                      value={editingCombo.description}
                      onChange={(e) => setEditingCombo({ ...editingCombo, description: e.target.value })}
                      className="w-full bg-[#181818] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                      placeholder="Detailed combo perks description..."
                    />
                  </div>

                  {/* Customizable Choices (Modifiers) */}
                  <div className="bg-[#181818] border border-[#262626] p-4 rounded-xl space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-[#262626]">
                      <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                        Customizable Choices ({editingCombo.modifiers?.length || 0})
                      </h4>
                      <button
                        type="button"
                        onClick={() =>
                          setEditingCombo({
                            ...editingCombo,
                            modifiers: [...(editingCombo.modifiers || []), { name: '', price: 0 }]
                          })
                        }
                        className="text-[10px] bg-[#FF5500]/15 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 cursor-pointer hover:bg-[#FF5500] hover:text-white transition-all"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Choice</span>
                      </button>
                    </div>

                    {(!editingCombo.modifiers || editingCombo.modifiers.length === 0) ? (
                      <p className="text-xs text-[#71717A] italic py-2 text-center">
                        No custom choices defined (e.g. drink selection or fries upgrade).
                      </p>
                    ) : (
                      <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                        {editingCombo.modifiers.map((mod, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="e.g. Coke Zero / Peri Fries Upgrade"
                              value={mod.name}
                              onChange={(e) => {
                                const updated = [...editingCombo.modifiers];
                                updated[idx].name = e.target.value;
                                setEditingCombo({ ...editingCombo, modifiers: updated });
                              }}
                              className="flex-1 bg-[#121212] border border-[#262626] rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                            />
                            <input
                              type="number"
                              step="0.1"
                              placeholder="+£0.00"
                              value={mod.price}
                              onChange={(e) => {
                                const updated = [...editingCombo.modifiers];
                                updated[idx].price = parseFloat(e.target.value || '0');
                                setEditingCombo({ ...editingCombo, modifiers: updated });
                              }}
                              className="w-20 bg-[#121212] border border-[#262626] rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const updated = editingCombo.modifiers.filter((_, i) => i !== idx);
                                setEditingCombo({ ...editingCombo, modifiers: updated });
                              }}
                              className="p-1.5 text-[#EF4444] hover:bg-[#2A1212] rounded-lg cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Removable Ingredients */}
                  <div className="bg-[#181818] border border-[#262626] p-4 rounded-xl space-y-3">
                    <div className="flex items-center justify-between pb-2 border-b border-[#262626]">
                      <h4 className="text-xs font-bold text-white uppercase tracking-wider">
                        Removable Ingredients ({editingComboIngredients.length})
                      </h4>
                      <button
                        type="button"
                        onClick={() => setEditingComboIngredients([...editingComboIngredients, ''])}
                        className="text-[10px] bg-[#FF5500]/15 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 cursor-pointer hover:bg-[#FF5500] hover:text-white transition-all"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Ingredient</span>
                      </button>
                    </div>

                    {editingComboIngredients.length === 0 ? (
                      <p className="text-xs text-[#71717A] italic py-2 text-center">
                        No removable ingredients defined.
                      </p>
                    ) : (
                      <div className="space-y-2 max-h-36 overflow-y-auto pr-1">
                        {editingComboIngredients.map((ing, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <input
                              type="text"
                              placeholder="e.g. Pickles, American Cheese..."
                              value={ing}
                              onChange={(e) => {
                                const updated = [...editingComboIngredients];
                                updated[idx] = e.target.value;
                                setEditingComboIngredients(updated);
                              }}
                              className="flex-1 bg-[#121212] border border-[#262626] rounded-lg py-1.5 px-2.5 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                            />
                            <button
                              type="button"
                              onClick={() => setEditingComboIngredients(editingComboIngredients.filter((_, i) => i !== idx))}
                              className="p-1.5 text-[#EF4444] hover:bg-[#2A1212] rounded-lg cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Active Toggle */}
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-xs font-semibold text-white">
                      Show in Customer Menu under "Combo Offers"
                    </span>
                    <input
                      type="checkbox"
                      checked={editingCombo.is_active}
                      onChange={(e) => setEditingCombo({ ...editingCombo, is_active: e.target.checked })}
                      className="w-4 h-4 rounded bg-[#181818] border-[#262626] accent-[#FF5500] cursor-pointer"
                    />
                  </div>
                </div>

                <div className="pt-4 border-t border-[#262626] flex justify-end gap-3 shrink-0">
                  <button
                    type="button"
                    onClick={() => setEditingCombo(null)}
                    className="px-4 py-2 bg-[#1A1A1A] hover:bg-[#262626] text-white rounded-xl text-xs font-semibold cursor-pointer border border-[#2A2A2A]"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSaveComboItem(editingCombo)}
                    className="px-5 py-2 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-xl text-xs font-bold cursor-pointer shadow-md shadow-[#FF5500]/20"
                  >
                    Save & Sync to Menu
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AdminOfferSettings;
