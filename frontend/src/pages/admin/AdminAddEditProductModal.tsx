import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
  X,
  Plus,
  Trash2,
  Upload,
  Camera,
  Image as ImageIcon,
  CheckCircle2,
  Package,
  DollarSign,
  Layers,
  Sparkles,
  Info,
  Sliders,
  Utensils,
} from 'lucide-react';
import { Category, Product } from '../../types';
import { api } from '../../api/client';

interface Props {
  categories: Category[];
  product?: Product | null;
  onClose: () => void;
  onSuccess: () => void;
}

export const AdminAddEditProductModal: React.FC<Props> = ({ categories, product, onClose, onSuccess }) => {
  const [name, setName] = useState(product?.name || '');
  const [sku, setSku] = useState(product?.sku || '');
  const [categoryId, setCategoryId] = useState(product?.category_id || categories[0]?.id || '');
  const [shortDescription, setShortDescription] = useState(product?.short_description || '');
  const [allergens, setAllergens] = useState(product?.allergens || '');
  
  // Ingredients List (same structure as modifiers)
  const [ingredientsList, setIngredientsList] = useState<string[]>(() => {
    if (!product?.ingredients) return [];
    if (Array.isArray(product.ingredients)) return product.ingredients.filter(Boolean);
    if (typeof product.ingredients === 'string') {
      return (product.ingredients as string)
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
    }
    return [];
  });

  const [price, setPrice] = useState(product?.base_price ? String(product.base_price) : '');
  const [comparePrice, setComparePrice] = useState(product?.compare_at_price ? String(product.compare_at_price) : '');
  const [rating, setRating] = useState(product?.rating ? String(product.rating) : '4.7');
  const [isBestseller, setIsBestseller] = useState(product?.is_bestseller ?? false);
  const [hasTax, setHasTax] = useState(product?.has_tax ?? true);
  const [hasServiceCharge, setHasServiceCharge] = useState(product?.has_service_charge ?? false);
  const [stock, setStock] = useState(product?.stock_quantity ? String(product.stock_quantity) : '100');
  const [imageUrl, setImageUrl] = useState(product?.image_url || '');
  const [galleryImages, setGalleryImages] = useState<string[]>(
    product?.images && product.images.length > 0 ? product.images : []
  );
  const [error, setError] = useState<string | null>(null);

  const [modifiers, setModifiers] = useState<{ name: string; price: string }[]>(
    product?.modifiers && product.modifiers.length > 0
      ? product.modifiers.map((m) => ({ name: m.name, price: String(m.price) }))
      : []
  );

  const [choiceGroups, setChoiceGroups] = useState<{
    name: string;
    min_selections: number;
    max_selections: number;
    is_required: boolean;
    options: { name: string; price_delta: string; is_active: boolean }[];
  }[]>(() => {
    if (!product?.choice_groups || product.choice_groups.length === 0) return [];
    return product.choice_groups.map((g) => ({
      name: g.name,
      min_selections: g.min_selections,
      max_selections: g.max_selections,
      is_required: g.is_required,
      options: (g.options || []).map((o) => ({
        name: o.name,
        price_delta: String(o.price_delta ?? 0),
        is_active: o.is_active ?? true
      }))
    }));
  });

  const [loading, setLoading] = useState(false);

  const mainImageInputRef = useRef<HTMLInputElement | null>(null);
  const galleryImageInputRef = useRef<HTMLInputElement | null>(null);

  // Prevent background body scroll while modal is open
  useEffect(() => {
    const orig = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = orig;
    };
  }, []);

  useEffect(() => {
    if (product) {
      setName(product.name || '');
      setSku(product.sku || '');
      setCategoryId(product.category_id || categories[0]?.id || '');
      setShortDescription(product.short_description || '');
      setAllergens(product.allergens || '');
      
      let parsedIng: string[] = [];
      if (Array.isArray(product.ingredients)) {
        parsedIng = product.ingredients.filter(Boolean);
      } else if (typeof product.ingredients === 'string') {
        parsedIng = (product.ingredients as string).split(',').map((s) => s.trim()).filter(Boolean);
      }
      setIngredientsList(parsedIng);

      setPrice(product.base_price ? String(product.base_price) : '');
      setComparePrice(product.compare_at_price ? String(product.compare_at_price) : '');
      setRating(product.rating ? String(product.rating) : '4.7');
      setIsBestseller(product.is_bestseller ?? false);
      setImageUrl(product.image_url || '');
      setGalleryImages(product.images || []);
      setModifiers(
        product.modifiers && product.modifiers.length > 0
          ? product.modifiers.map((m) => ({ name: m.name, price: String(m.price) }))
          : []
      );
      setChoiceGroups(
        product.choice_groups && product.choice_groups.length > 0
          ? product.choice_groups.map((g) => ({
              name: g.name,
              min_selections: g.min_selections,
              max_selections: g.max_selections,
              is_required: g.is_required,
              options: (g.options || []).map((o) => ({
                name: o.name,
                price_delta: String(o.price_delta ?? 0),
                is_active: o.is_active ?? true
              }))
            }))
          : []
      );
    }
  }, [product, categories]);

  const handleAddIngredient = () => {
    setIngredientsList([...ingredientsList, '']);
  };

  const handleRemoveIngredient = (idx: number) => {
    setIngredientsList(ingredientsList.filter((_, i) => i !== idx));
  };

  const handleAddModifier = () => {
    setModifiers([...modifiers, { name: '', price: '1.00' }]);
  };

  const handleRemoveModifier = (idx: number) => {
    setModifiers(modifiers.filter((_, i) => i !== idx));
  };

  const handleAddChoiceGroup = () => {
    setChoiceGroups([
      ...choiceGroups,
      {
        name: 'Choose any 2',
        min_selections: 2,
        max_selections: 2,
        is_required: true,
        options: [
          { name: '', price_delta: '0.00', is_active: true },
          { name: '', price_delta: '0.00', is_active: true }
        ]
      }
    ]);
  };

  const handleRemoveChoiceGroup = (gIdx: number) => {
    setChoiceGroups(choiceGroups.filter((_, i) => i !== gIdx));
  };

  const handleAddOptionToGroup = (gIdx: number) => {
    const updated = [...choiceGroups];
    updated[gIdx].options.push({ name: '', price_delta: '0.00', is_active: true });
    setChoiceGroups(updated);
  };

  const handleRemoveOptionFromGroup = (gIdx: number, oIdx: number) => {
    const updated = [...choiceGroups];
    updated[gIdx].options = updated[gIdx].options.filter((_, i) => i !== oIdx);
    setChoiceGroups(updated);
  };

  const handleMainImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 8 * 1024 * 1024) {
        setError('Photo size exceeds 8MB. Please choose a smaller image.');
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        if (typeof reader.result === 'string') {
          setImageUrl(reader.result);
        }
      };
      reader.readAsDataURL(file);
    }
    e.target.value = '';
  };

  const handleGalleryFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    Array.from(files).forEach((file) => {
      if (file.size > 8 * 1024 * 1024) return;
      const reader = new FileReader();
      reader.onloadend = () => {
        if (typeof reader.result === 'string') {
          setGalleryImages((prev) => [...prev, reader.result as string]);
        }
      };
      reader.readAsDataURL(file);
    });
    e.target.value = '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const payload = {
        category_id: categoryId || (categories[0]?.id || ''),
        name,
        sku: sku || `SKU-${Math.floor(1000 + Math.random() * 9000)}`,
        short_description: shortDescription,
        full_description: shortDescription,
        allergens: allergens,
        ingredients: ingredientsList.filter((i) => i.trim() !== '').join(', '),
        base_price: parseFloat(price || '0'),
        compare_at_price: comparePrice ? parseFloat(comparePrice) : null,
        rating: parseFloat(rating || '4.7'),
        is_bestseller: isBestseller,
        has_tax: hasTax,
        has_service_charge: hasServiceCharge,
        stock_quantity: parseInt(stock || '100'),
        image_url: imageUrl || '/placeholder-burger.svg',
        images: galleryImages.length > 0 ? galleryImages : [imageUrl || '/placeholder-burger.svg'],
        modifiers: modifiers
          .filter((m) => m.name.trim() !== '')
          .map((m) => ({ name: m.name, price: parseFloat(m.price || '0') })),
        choice_groups: choiceGroups
          .filter((g) => g.name.trim() !== '')
          .map((g, gIdx) => ({
            name: g.name.trim(),
            min_selections: Number(g.min_selections) || 1,
            max_selections: Number(g.max_selections) || 1,
            is_required: Boolean(g.is_required),
            display_order: gIdx,
            options: g.options
              .filter((o) => o.name.trim() !== '')
              .map((o, oIdx) => ({
                name: o.name.trim(),
                price_delta: parseFloat(o.price_delta || '0'),
                is_active: Boolean(o.is_active),
                display_order: oIdx
              }))
          }))
      };

      if (product?.id) {
        await api.put(`/products/${product.id}`, payload);
      } else {
        await api.post('/products', payload);
      }
      onSuccess();
    } catch (err: any) {
      console.error(err);
      setError(err?.message || 'Failed to save product. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const modalContent = (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-xs flex items-center justify-center p-3 sm:p-4 md:p-6 overflow-hidden">
      <div className="bg-[#121212] border border-[#262626] rounded-2xl w-full max-w-6xl shadow-2xl p-4 sm:p-6 md:p-7 relative text-white max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#262626] mb-4 sm:mb-6 shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#FF5500]/10 border border-[#FF5500]/30 rounded-xl text-[#FF5500]">
              <Package className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg sm:text-xl font-bold text-white tracking-wide">
                {product ? 'Edit Product' : 'Add New Product'}
              </h2>
              <p className="text-xs text-[#9CA3AF]">
                Configure product details, removable ingredients, add-ons, and photos
              </p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-2 text-[#9CA3AF] hover:text-white rounded-xl hover:bg-[#1A1A1A] cursor-pointer shrink-0"
            aria-label="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3.5 bg-[#2A1215] border border-[#EF4444]/40 text-[#FCA5A5] rounded-xl text-xs font-semibold shrink-0">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex-1 min-h-0 flex flex-col">
          <div className="flex-1 overflow-y-auto pr-1 sm:pr-2 space-y-6">
            {/* Main 3-Column Aligned Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
            
            {/* ============================================================ */}
            {/* COLUMN 1: Basic Information & Pricing */}
            {/* ============================================================ */}
            <div className="space-y-5">
              {/* Product Information Card */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-[#262626]">
                  <Info className="w-4 h-4 text-[#FF5500]" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    General Information
                  </h3>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                    Product Name *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g. The Mc Project Burger"
                    className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2.5 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Category *
                    </label>
                    <select
                      value={categoryId}
                      onChange={(e) => setCategoryId(e.target.value)}
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2.5 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                    >
                      {categories
                        .filter((c) => !c.slug?.toLowerCase().includes('combo') && !c.name?.toLowerCase().includes('combo'))
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.name}
                          </option>
                        ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      SKU Code
                    </label>
                    <input
                      type="text"
                      value={sku}
                      onChange={(e) => setSku(e.target.value)}
                      placeholder="Auto (Optional)"
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2.5 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                    Short Description
                  </label>
                  <textarea
                    rows={2}
                    value={shortDescription}
                    onChange={(e) => setShortDescription(e.target.value)}
                    placeholder="Aged British beef patty with molten cheddar..."
                    className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                    Allergens Description
                  </label>
                  <textarea
                    rows={2}
                    value={allergens}
                    onChange={(e) => setAllergens(e.target.value)}
                    placeholder="Contains Gluten, Milk, Mustard, Sesame seeds"
                    className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                  />
                </div>
              </div>

              {/* Pricing & Stock Card */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center gap-2 pb-3 border-b border-[#262626]">
                  <DollarSign className="w-4 h-4 text-[#FF5500]" />
                  <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                    Pricing & Inventory
                  </h3>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Price (£) *
                    </label>
                    <input
                      type="text"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder="8.95"
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2.5 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Stock Quantity *
                    </label>
                    <input
                      type="number"
                      value={stock}
                      onChange={(e) => setStock(e.target.value)}
                      placeholder="100"
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2.5 px-3 text-xs text-white focus:outline-none focus:border-[#FF5500]"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Compare Price (£)
                    </label>
                    <input
                      type="text"
                      value={comparePrice}
                      onChange={(e) => setComparePrice(e.target.value)}
                      placeholder="e.g. 10.95"
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-[#D1D5DB] mb-1.5">
                      Rating (1-5)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="1.0"
                      max="5.0"
                      value={rating}
                      onChange={(e) => setRating(e.target.value)}
                      placeholder="4.7"
                      className="w-full bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs pt-1 border-t border-[#262626]">
                  <span className="text-white font-medium flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-[#FF5500]" />
                    Featured as Best Seller
                  </span>
                  <input
                    type="checkbox"
                    checked={isBestseller}
                    onChange={(e) => setIsBestseller(e.target.checked)}
                    className="w-4 h-4 rounded bg-[#121212] border-[#262626] accent-[#FF5500] cursor-pointer"
                  />
                </div>
              </div>
            </div>

            {/* ============================================================ */}
            {/* COLUMN 2: Customer Removable Ingredients & Add-ons (EXACT TWIN STYLE) */}
            {/* ============================================================ */}
            <div className="space-y-5">
              
              {/* Removable Ingredients Card (Exact identical structure to Add-ons) */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                  <div className="flex items-center gap-2">
                    <Sliders className="w-4 h-4 text-[#FF5500]" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Removable Ingredients ({ingredientsList.length})
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddIngredient}
                    className="text-[10px] bg-[#FF5500]/10 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 hover:bg-[#FF5500] hover:text-white transition-all cursor-pointer"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add Ingredient</span>
                  </button>
                </div>

                {ingredientsList.length === 0 ? (
                  <p className="text-xs text-[#71717A] italic py-4 text-center border border-dashed border-[#262626] rounded-xl">
                    No removable ingredients configured. Click "+ Add Ingredient" to create choices.
                  </p>
                ) : (
                  <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
                    {ingredientsList.map((ing, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="e.g. Pickles, American Cheese, Onions..."
                          value={ing}
                          onChange={(e) => {
                            const updated = [...ingredientsList];
                            updated[idx] = e.target.value;
                            setIngredientsList(updated);
                          }}
                          className="flex-1 bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveIngredient(idx)}
                          className="p-2 text-[#EF4444] hover:bg-[#2A1212] rounded-lg cursor-pointer transition-colors"
                          title="Remove Ingredient"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Add-ons / Modifiers Card */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-[#FF5500]" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Add-ons / Modifiers ({modifiers.length})
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddModifier}
                    className="text-[10px] bg-[#FF5500]/10 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 hover:bg-[#FF5500] hover:text-white transition-all cursor-pointer"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add Add-on</span>
                  </button>
                </div>

                {modifiers.length === 0 ? (
                  <p className="text-xs text-[#71717A] italic py-4 text-center border border-dashed border-[#262626] rounded-xl">
                    No add-ons configured. Click "+ Add Add-on" to create choices.
                  </p>
                ) : (
                  <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
                    {modifiers.map((mod, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <input
                          type="text"
                          placeholder="e.g. Extra Cheese"
                          value={mod.name}
                          onChange={(e) => {
                            const updated = [...modifiers];
                            updated[idx].name = e.target.value;
                            setModifiers(updated);
                          }}
                          className="flex-1 bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                        />
                        <input
                          type="text"
                          placeholder="+£1.50"
                          value={mod.price}
                          onChange={(e) => {
                            const updated = [...modifiers];
                            updated[idx].price = e.target.value;
                            setModifiers(updated);
                          }}
                          className="w-20 bg-[#121212] border border-[#262626] rounded-xl py-2 px-3 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                        />
                        <button
                          type="button"
                          onClick={() => handleRemoveModifier(idx)}
                          className="p-2 text-[#EF4444] hover:bg-[#2A1212] rounded-lg cursor-pointer transition-colors"
                          title="Remove Add-on"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Menu Choice Groups Card (Optional) */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                  <div className="flex items-center gap-2">
                    <Utensils className="w-4 h-4 text-[#FF5500]" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Menu Choice Groups ({choiceGroups.length})
                    </h3>
                  </div>
                  <button
                    type="button"
                    onClick={handleAddChoiceGroup}
                    className="text-[10px] bg-[#FF5500]/10 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 hover:bg-[#FF5500] hover:text-white transition-all cursor-pointer"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Add Choice Group</span>
                  </button>
                </div>

                {choiceGroups.length === 0 ? (
                  <p className="text-xs text-[#71717A] italic py-3 text-center border border-dashed border-[#262626] rounded-xl">
                    Optional. Add a choice group (e.g. "Choose any 2", "Choose your rasher").
                  </p>
                ) : (
                  <div className="space-y-4 max-h-80 overflow-y-auto pr-1">
                    {choiceGroups.map((grp, gIdx) => (
                      <div key={gIdx} className="p-3 bg-[#121212] border border-[#262626] rounded-xl space-y-3">
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            placeholder="Group Name (e.g. Choose any 2)"
                            value={grp.name}
                            onChange={(e) => {
                              const updated = [...choiceGroups];
                              updated[gIdx].name = e.target.value;
                              setChoiceGroups(updated);
                            }}
                            className="flex-1 bg-[#181818] border border-[#262626] rounded-lg py-1.5 px-2.5 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                          />
                          <button
                            type="button"
                            onClick={() => handleRemoveChoiceGroup(gIdx)}
                            className="p-1.5 text-[#EF4444] hover:bg-[#2A1212] rounded-lg cursor-pointer transition-colors"
                            title="Delete Choice Group"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        {/* Rules: Min / Max / Required */}
                        <div className="flex items-center gap-3 text-[11px]">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[#A1A1AA]">Min:</span>
                            <input
                              type="number"
                              min="0"
                              max="10"
                              value={grp.min_selections}
                              onChange={(e) => {
                                const updated = [...choiceGroups];
                                updated[gIdx].min_selections = parseInt(e.target.value) || 0;
                                setChoiceGroups(updated);
                              }}
                              className="w-12 bg-[#181818] border border-[#262626] rounded px-1.5 py-1 text-center text-white"
                            />
                          </div>

                          <div className="flex items-center gap-1.5">
                            <span className="text-[#A1A1AA]">Max:</span>
                            <input
                              type="number"
                              min="1"
                              max="10"
                              value={grp.max_selections}
                              onChange={(e) => {
                                const updated = [...choiceGroups];
                                updated[gIdx].max_selections = parseInt(e.target.value) || 1;
                                setChoiceGroups(updated);
                              }}
                              className="w-12 bg-[#181818] border border-[#262626] rounded px-1.5 py-1 text-center text-white"
                            />
                          </div>

                          <label className="flex items-center gap-1.5 text-[#A1A1AA] cursor-pointer ml-auto">
                            <input
                              type="checkbox"
                              checked={grp.is_required}
                              onChange={(e) => {
                                const updated = [...choiceGroups];
                                updated[gIdx].is_required = e.target.checked;
                                setChoiceGroups(updated);
                              }}
                              className="accent-[#FF5500]"
                            />
                            <span>Required</span>
                          </label>
                        </div>

                        {/* Options */}
                        <div className="space-y-2 pt-1 border-t border-[#1F1F1F]">
                          <div className="flex items-center justify-between text-[10px] text-[#71717A] uppercase font-bold">
                            <span>Choices ({grp.options.length})</span>
                            <button
                              type="button"
                              onClick={() => handleAddOptionToGroup(gIdx)}
                              className="text-[#FF5500] hover:underline flex items-center gap-0.5 cursor-pointer"
                            >
                              <Plus className="w-2.5 h-2.5" /> Add Choice
                            </button>
                          </div>

                          {grp.options.map((opt, oIdx) => (
                            <div key={oIdx} className="flex items-center gap-2">
                              <input
                                type="text"
                                placeholder="Choice name (e.g. Sausage, Bacon)"
                                value={opt.name}
                                onChange={(e) => {
                                  const updated = [...choiceGroups];
                                  updated[gIdx].options[oIdx].name = e.target.value;
                                  setChoiceGroups(updated);
                                }}
                                className="flex-1 bg-[#181818] border border-[#262626] rounded-lg py-1 px-2 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                              />
                              <input
                                type="text"
                                placeholder="+£0.00"
                                value={opt.price_delta}
                                onChange={(e) => {
                                  const updated = [...choiceGroups];
                                  updated[gIdx].options[oIdx].price_delta = e.target.value;
                                  setChoiceGroups(updated);
                                }}
                                className="w-16 bg-[#181818] border border-[#262626] rounded-lg py-1 px-2 text-xs text-white placeholder-[#555] focus:outline-none focus:border-[#FF5500]"
                              />
                              <button
                                type="button"
                                onClick={() => handleRemoveOptionFromGroup(gIdx, oIdx)}
                                className="p-1 text-[#EF4444] hover:bg-[#2A1212] rounded cursor-pointer"
                                title="Remove Choice"
                              >
                                <Trash2 className="w-3 h-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

            </div>

            {/* ============================================================ */}
            {/* COLUMN 3: Direct Photo Uploads & Gallery */}
            {/* ============================================================ */}
            <div className="space-y-5">
              {/* Main Product Image Card */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                  <div className="flex items-center gap-2">
                    <Camera className="w-4 h-4 text-[#FF5500]" />
                    <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                      Main Product Photo
                    </h3>
                  </div>
                  {imageUrl && (
                    <span className="text-[10px] text-[#86EFAC] font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      Uploaded
                    </span>
                  )}
                </div>

                {/* Hidden File Input */}
                <input
                  type="file"
                  accept="image/*"
                  ref={mainImageInputRef}
                  onChange={handleMainImageUpload}
                  className="hidden"
                />

                {imageUrl ? (
                  <div className="space-y-3">
                    <div className="relative group rounded-xl overflow-hidden border border-[#262626] bg-[#121212] h-44 flex items-center justify-center">
                      <img
                        src={imageUrl}
                        alt="Product Preview"
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => mainImageInputRef.current?.click()}
                        className="flex-1 py-2 bg-[#222] hover:bg-[#2A2A2A] text-white rounded-xl text-xs font-bold flex items-center justify-center gap-1.5 cursor-pointer border border-[#333] transition-colors"
                      >
                        <Camera className="w-3.5 h-3.5" />
                        <span>Change Photo</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => setImageUrl('')}
                        className="px-3 py-2 bg-[#2A1215] hover:bg-[#3D1A1F] text-[#EF4444] rounded-xl text-xs font-bold flex items-center justify-center gap-1 cursor-pointer border border-[#EF4444]/30 transition-colors"
                        title="Remove Photo"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => mainImageInputRef.current?.click()}
                    className="w-full py-8 border-2 border-dashed border-[#333] hover:border-[#FF5500] bg-[#141414] hover:bg-[#1A1A1A] rounded-xl flex flex-col items-center justify-center gap-2 transition-all cursor-pointer group text-center"
                  >
                    <div className="w-10 h-10 rounded-full bg-[#FF5500]/10 border border-[#FF5500]/30 flex items-center justify-center text-[#FF5500] group-hover:scale-110 transition-transform">
                      <Upload className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-bold text-white group-hover:text-[#FF5500] transition-colors">
                      Click to Upload Product Photo
                    </span>
                    <span className="text-[10px] text-[#6B7280]">PNG, JPG, WEBP up to 8MB</span>
                  </button>
                )}
              </div>

              {/* Product Preview Gallery Card */}
              <div className="bg-[#181818] border border-[#262626] p-5 rounded-2xl space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-[#262626]">
                  <div className="flex items-center gap-2">
                    <ImageIcon className="w-4 h-4 text-[#FF5500]" />
                    <div>
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                        Gallery Photos ({galleryImages.length})
                      </h3>
                      <p className="text-[10px] text-[#9CA3AF]">Additional carousel photos for customer view</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => galleryImageInputRef.current?.click()}
                    className="text-[10px] bg-[#FF5500]/10 text-[#FF5500] border border-[#FF5500]/30 px-2.5 py-1 rounded-lg font-bold flex items-center gap-1 hover:bg-[#FF5500] hover:text-white transition-all cursor-pointer shrink-0"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Upload Photo</span>
                  </button>
                </div>

                {/* Hidden Multi-file Input */}
                <input
                  type="file"
                  multiple
                  accept="image/*"
                  ref={galleryImageInputRef}
                  onChange={handleGalleryFileUpload}
                  className="hidden"
                />

                {galleryImages.length > 0 ? (
                  <div className="grid grid-cols-4 gap-2">
                    {galleryImages.map((img, idx) => (
                      <div
                        key={idx}
                        className="relative group rounded-xl overflow-hidden border border-[#262626] bg-[#121212] aspect-square"
                      >
                        <img
                          src={img}
                          alt={`Preview ${idx + 1}`}
                          onError={(e) => {
                            (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                          }}
                          className="w-full h-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => setGalleryImages(galleryImages.filter((_, i) => i !== idx))}
                          className="absolute inset-0 bg-black/75 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-[#EF4444] cursor-pointer"
                          title="Remove Photo"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => galleryImageInputRef.current?.click()}
                    className="w-full py-5 border border-dashed border-[#2E2E2E] hover:border-[#FF5500] bg-[#141414] rounded-xl flex flex-col items-center justify-center gap-1.5 transition-all cursor-pointer text-center group"
                  >
                    <Upload className="w-4 h-4 text-[#FF5500] group-hover:scale-110 transition-transform" />
                    <span className="text-xs font-semibold text-[#D1D5DB] group-hover:text-white">
                      Upload Gallery Photos
                    </span>
                    <span className="text-[10px] text-[#6B7280]">Select one or multiple photos</span>
                  </button>
                )}
              </div>
            </div>

            </div>
          </div>

          {/* Action Bar Footer */}
          <div className="flex flex-wrap items-center justify-between gap-3 pt-4 sm:pt-5 border-t border-[#262626] shrink-0 mt-3">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 bg-[#1A1A1A] hover:bg-[#262626] text-white rounded-xl text-xs font-semibold cursor-pointer border border-[#2A2A2A] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-6 py-2.5 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-xl text-xs font-bold shadow-md shadow-[#FF5500]/20 cursor-pointer disabled:opacity-50 transition-all"
            >
              {loading ? 'Saving Product...' : product ? 'Update Product' : 'Save & Publish Product'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
};
