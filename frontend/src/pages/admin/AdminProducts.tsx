import React, { useEffect, useState } from 'react';
import { Search, Plus, Edit, Trash2, Download, Layers, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '../../api/client';
import { Product, Category, Branch } from '../../types';
import { useAuthStore } from '../../store/authStore';
import { AdminAddEditProductModal } from './AdminAddEditProductModal';
import { AdminCategoryModal } from './AdminCategoryModal';

interface InventoryItem {
  id: string;
  branch_id: string;
  product_id: string;
  stock_quantity: number;
  low_stock_threshold: number;
  is_available: boolean;
}

export const AdminProducts: React.FC = () => {
  const { user } = useAuthStore();
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [selectedBranchId, setSelectedBranchId] = useState<string>(
    user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids[0] ? user.branch_ids[0] : ''
  );
  const [inventoryMap, setInventoryMap] = useState<Record<string, InventoryItem>>({});
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  useEffect(() => {
    fetchInitialData();
  }, []);

  useEffect(() => {
    if (selectedBranchId) {
      fetchInventory(selectedBranchId);
    }
  }, [selectedBranchId]);

  const fetchInitialData = async () => {
    try {
      const timestamp = Date.now();
      const [prodData, catData, branchData] = await Promise.all([
        api.get<Product[]>(`/products?_t=${timestamp}`),
        api.get<Category[]>(`/categories?_t=${timestamp}`),
        api.get<Branch[]>('/branches')
      ]);
      const standardCategories = (catData || []).filter(
        (c) => !c.slug?.toLowerCase().includes('combo') && !c.name?.toLowerCase().includes('combo')
      );
      const standardProducts = (prodData || []).filter(
        (p) =>
          !p.sku?.startsWith('COMBO-') &&
          !catData?.some(
            (c) => c.id === p.category_id && (c.slug?.toLowerCase().includes('combo') || c.name?.toLowerCase().includes('combo'))
          )
      );
      setProducts(standardProducts);
      setCategories(standardCategories);
      
      let filteredBranches = branchData || [];
      if (user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids.length > 0) {
        filteredBranches = filteredBranches.filter((b) => user.branch_ids.includes(b.id));
      }
      setBranches(filteredBranches);

      const defaultBranch = user?.role === 'BRANCH_ADMIN' && user.branch_ids && user.branch_ids[0]
        ? user.branch_ids[0]
        : (filteredBranches[0]?.id || '');
      setSelectedBranchId(defaultBranch);
      if (defaultBranch) {
        fetchInventory(defaultBranch);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchInventory = async (branchId: string) => {
    try {
      const invData = await api.get<InventoryItem[]>(`/inventory?branch_id=${branchId}`);
      const map: Record<string, InventoryItem> = {};
      (invData || []).forEach((item) => {
        map[item.product_id] = item;
      });
      setInventoryMap(map);
    } catch (err) {
      console.error('Failed to fetch inventory:', err);
    }
  };

  const handleToggleStock = async (productId: string) => {
    if (!selectedBranchId) return;
    const currentInv = inventoryMap[productId];
    const currentStatus = currentInv ? currentInv.is_available : true;
    const newStatus = !currentStatus;

    try {
      const updated = await api.post<InventoryItem>('/inventory/toggle', {
        branch_id: selectedBranchId,
        product_id: productId,
        is_available: newStatus
      });
      setInventoryMap((prev) => ({
        ...prev,
        [productId]: updated
      }));
    } catch (err) {
      console.error('Failed to toggle stock availability:', err);
      alert('Failed to update stock status. Please try again.');
    }
  };

  const handleUpdateStockQuantity = async (productId: string, currentStock: number) => {
    if (!selectedBranchId) return;
    const newQtyStr = window.prompt(`Enter new stock quantity for this branch:`, String(currentStock));
    if (newQtyStr === null) return;
    const newQty = parseInt(newQtyStr, 10);
    if (isNaN(newQty) || newQty < 0) {
      alert('Please enter a valid non-negative number.');
      return;
    }

    try {
      const updated = await api.post<InventoryItem>('/inventory/toggle', {
        branch_id: selectedBranchId,
        product_id: productId,
        stock_quantity: newQty
      });
      setInventoryMap((prev) => ({
        ...prev,
        [productId]: updated
      }));
    } catch (err) {
      console.error('Failed to update stock quantity:', err);
      alert('Failed to update stock quantity. Please try again.');
    }
  };

  const handleDeleteProduct = async (id: string, name: string) => {
    if (user?.role !== 'SUPER_ADMIN') {
      alert('Only Super Administrators have permission to delete products.');
      return;
    }
    if (window.confirm(`Are you sure you want to delete "${name}"? This action cannot be undone.`)) {
      try {
        await api.delete(`/products/${id}`);
        await fetchInitialData();
      } catch (err: any) {
        console.error('Failed to delete product:', err);
        alert(err?.message || 'Failed to delete product. Please try again.');
      }
    }
  };

  const filteredProducts = products.filter(
    (p) =>
      (selectedCategory === 'ALL' || p.category_id === selectedCategory) &&
      (p.name.toLowerCase().includes(searchQuery.toLowerCase()) || p.sku.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="p-4 sm:p-6 lg:p-8 w-full max-w-[1680px] mx-auto space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-wide">Products & Stock</h1>
          <p className="text-[#9CA3AF] text-sm mt-0.5">
            {user?.role === 'BRANCH_ADMIN'
              ? 'Manage stock quantities and out-of-stock items for your assigned branch.'
              : 'Manage and view all products, categories, and branch inventory.'}
          </p>
        </div>

        {user?.role === 'SUPER_ADMIN' && (
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCategoryModal(true)}
              className="bg-[#1A1A1A] hover:bg-[#262626] border border-[#262626] text-white px-4 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all cursor-pointer"
            >
              <Layers className="w-4 h-4 text-[#FF5500]" />
              <span>Manage Categories</span>
            </button>
            <button
              onClick={() => {
                setEditingProduct(null);
                setShowAddModal(true);
              }}
              className="bg-[#FF5500] hover:bg-[#E04B00] text-white px-5 py-2.5 rounded-xl text-xs font-semibold flex items-center gap-2 transition-all shadow-md shadow-[#FF5500]/20 cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>Add Product</span>
            </button>
          </div>
        )}
      </div>

      {/* Filter Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 bg-[#121212] border border-[#262626] p-4 rounded-2xl">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-64">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Search products..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 pl-9 pr-4 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#FF5500]"
            />
          </div>

          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-4 text-xs text-white focus:outline-none focus:border-[#FF5500]"
          >
            <option value="ALL">All Categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>

          {/* Branch Stock Selector (Branch Admin only) */}
          {user?.role === 'BRANCH_ADMIN' && (
            <select
              value={selectedBranchId}
              onChange={(e) => setSelectedBranchId(e.target.value)}
              disabled={true}
              className="bg-[#1A1A1A] border border-[#262626] rounded-xl py-2 px-4 text-xs text-white focus:outline-none focus:border-[#FF5500] disabled:opacity-75 disabled:cursor-not-allowed"
            >
              {branches.map((b) => (
                <option key={b.id} value={b.id}>Branch: {b.name}</option>
              ))}
            </select>
          )}
        </div>

        <div className="flex items-center gap-3">
          <button className="bg-[#1A1A1A] hover:bg-[#262626] border border-[#262626] text-[#9CA3AF] px-4 py-2.5 rounded-xl text-xs font-medium flex items-center gap-2 transition-all cursor-pointer">
            <Download className="w-4 h-4" />
            <span>Export</span>
          </button>
        </div>
      </div>

      {/* Products Data Table */}
      <div className="bg-[#121212] border border-[#262626] rounded-2xl overflow-x-auto shadow-xl scrollbar-thin scrollbar-thumb-[#262626]">
        <table className="w-full text-left text-xs min-w-[750px]">
          <thead className="bg-[#1A1A1A] text-[#9CA3AF] uppercase text-[10px] font-semibold tracking-wider border-b border-[#262626]">
            <tr>
              <th className="px-4 sm:px-5 py-4 whitespace-nowrap">Product ID</th>
              <th className="px-4 sm:px-5 py-4 min-w-[240px]">Product</th>
              <th className="px-4 sm:px-5 py-4 whitespace-nowrap">Category</th>
              <th className="px-4 sm:px-5 py-4 text-right whitespace-nowrap">Price</th>
              {user?.role === 'BRANCH_ADMIN' && (
                <>
                  <th className="px-4 sm:px-5 py-4 text-right whitespace-nowrap">Branch Stock</th>
                  <th className="px-4 sm:px-5 py-4 text-center whitespace-nowrap">Availability</th>
                </>
              )}
              {user?.role === 'SUPER_ADMIN' && (
                <th className="px-4 sm:px-5 py-4 text-center whitespace-nowrap">Actions</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#262626]">
            {loading ? (
              <tr>
                <td colSpan={user?.role === 'BRANCH_ADMIN' ? 6 : 5} className="px-6 py-8 text-center text-[#9CA3AF]">
                  Loading products...
                </td>
              </tr>
            ) : filteredProducts.length === 0 ? (
              <tr>
                <td colSpan={user?.role === 'BRANCH_ADMIN' ? 6 : 5} className="px-6 py-8 text-center text-[#9CA3AF]">
                  No products found.
                </td>
              </tr>
            ) : (
              filteredProducts.map((p) => {
                const inv = inventoryMap[p.id];
                const stockQty = inv?.stock_quantity ?? 100;
                const isAvailable = inv ? inv.is_available : true;

                return (
                  <tr key={p.id} className="hover:bg-[#1A1A1A]/40 transition-colors">
                    <td className="px-4 sm:px-5 py-3.5 font-mono font-medium text-[#FF5500] whitespace-nowrap">#{p.sku}</td>
                    <td className="px-4 sm:px-5 py-3.5 flex items-center gap-3">
                      <img
                        src={p.image_url || '/placeholder-burger.svg'}
                        alt={p.name}
                        onError={(e) => {
                          (e.currentTarget as HTMLImageElement).src = '/placeholder-burger.svg';
                        }}
                        className="w-10 h-10 rounded-lg object-cover bg-[#1A1A1A] border border-[#262626] shrink-0"
                      />
                      <div className="min-w-0 max-w-[280px]">
                        <div className="flex items-center gap-2">
                          <p className="font-semibold text-white text-xs truncate">{p.name}</p>
                          {p.is_bestseller && (
                            <span className="text-[9px] bg-[#FF5500]/10 text-[#FF5500] border border-[#FF5500]/20 px-1.5 py-0.5 rounded font-semibold uppercase shrink-0">
                              Best Seller
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-[#9CA3AF] truncate">{p.short_description}</p>
                      </div>
                    </td>
                    <td className="px-4 sm:px-5 py-3.5 text-[#9CA3AF] whitespace-nowrap">
                      {categories.find((c) => c.id === p.category_id)?.name || 'Burgers'}
                    </td>
                    <td className="px-4 sm:px-5 py-3.5 text-right font-semibold text-white whitespace-nowrap">£{p.base_price.toFixed(2)}</td>
                    
                    {/* Branch Stock & Availability: ONLY Branch Admins See */}
                    {user?.role === 'BRANCH_ADMIN' && (
                      <>
                        <td className="px-4 sm:px-5 py-3.5 text-right font-semibold whitespace-nowrap">
                          <button
                            onClick={() => handleUpdateStockQuantity(p.id, stockQty)}
                            title="Click to update stock quantity"
                            className="text-white hover:text-[#FF5500] transition-colors cursor-pointer underline decoration-dotted font-mono"
                          >
                            {stockQty}
                          </button>
                        </td>
                        <td className="px-4 sm:px-5 py-3.5 text-center whitespace-nowrap">
                          <button
                            onClick={() => handleToggleStock(p.id)}
                            title={isAvailable ? 'Click to mark Out of Stock' : 'Click to mark In Stock'}
                            className={`px-2.5 py-1 rounded-lg text-[10px] font-semibold uppercase tracking-wider transition-colors cursor-pointer inline-flex items-center gap-1.5 ${
                              isAvailable
                                ? 'bg-[#22C55E]/10 text-[#22C55E] border border-[#22C55E]/30 hover:bg-[#22C55E]/20'
                                : 'bg-[#EF4444]/10 text-[#EF4444] border border-[#EF4444]/30 hover:bg-[#EF4444]/20'
                            }`}
                          >
                            {isAvailable ? (
                              <>
                                <CheckCircle2 className="w-3 h-3" />
                                <span>In Stock</span>
                              </>
                            ) : (
                              <>
                                <XCircle className="w-3 h-3" />
                                <span>Out of Stock</span>
                              </>
                            )}
                          </button>
                        </td>
                      </>
                    )}

                    {/* Actions Column: SUPER ADMIN */}
                    {user?.role === 'SUPER_ADMIN' && (
                      <td className="px-4 sm:px-5 py-3.5 text-center whitespace-nowrap">
                        <div className="flex items-center justify-center gap-2">
                          <button
                            onClick={() => {
                              setEditingProduct(p);
                              setShowAddModal(true);
                            }}
                            className="p-1.5 bg-[#1A1A1A] hover:bg-[#262626] border border-[#2A2A2A] hover:border-[#FF5500]/50 text-[#A1A1AA] hover:text-[#FF5500] rounded-lg transition-all cursor-pointer shadow-sm"
                            title="Edit Product"
                          >
                            <Edit className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteProduct(p.id, p.name)}
                            className="p-1.5 bg-[#1A1A1A] hover:bg-[#262626] border border-[#2A2A2A] hover:border-[#EF4444]/50 text-[#A1A1AA] hover:text-[#EF4444] rounded-lg transition-all cursor-pointer shadow-sm"
                            title="Delete Product"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {showAddModal && user?.role === 'SUPER_ADMIN' && (
        <AdminAddEditProductModal
          categories={categories}
          product={editingProduct}
          onClose={() => {
            setShowAddModal(false);
            setEditingProduct(null);
          }}
          onSuccess={() => {
            fetchInitialData();
            setShowAddModal(false);
            setEditingProduct(null);
          }}
        />
      )}
      {showCategoryModal && user?.role === 'SUPER_ADMIN' && (
        <AdminCategoryModal
          categories={categories}
          onClose={() => setShowCategoryModal(false)}
          onRefresh={fetchInitialData}
        />
      )}
    </div>
  );
};

