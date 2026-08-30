import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { Product } from '../../types';
import { ProductDetailModal } from './ProductDetailModal';
import { useCartStore } from '../../store/cartStore';
import { useProductRealtime } from '../../hooks/useProductRealtime';

export const ProductDetailPage: React.FC = () => {
  const { productId } = useParams<{ productId: string }>();
  const navigate = useNavigate();
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const { selectedBranch } = useCartStore();

  useProductRealtime({
    onProductAvailabilityChange: (id: string, isOutOfStock: boolean) => {
      if (productId === id) {
        setProduct((prev) =>
          prev
            ? {
                ...prev,
                is_out_of_stock: isOutOfStock,
                is_available: isOutOfStock ? false : (prev.is_available ?? true),
              }
            : null
        );
      }
    },
    onReconnect: () => {
      if (productId) fetchProduct(productId);
    },
  });

  useEffect(() => {
    if (productId) {
      fetchProduct(productId);
    }
  }, [productId, selectedBranch?.id]);

  const fetchProduct = async (id: string) => {
    try {
      const branchParam = selectedBranch?.id ? `?branch_id=${selectedBranch.id}` : '';
      const data = await api.get<Product>(`/products/${id}${branchParam}`);
      setProduct(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center text-[#9CA3AF]">
        Loading product details...
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center gap-4 text-[#9CA3AF]">
        <p>Product not found.</p>
        <button
          onClick={() => navigate('/menu')}
          className="px-5 py-2.5 bg-[#FF5500] text-white rounded-xl font-bold text-xs"
        >
          Back to Menu
        </button>
      </div>
    );
  }

  return (
    <ProductDetailModal
      product={product}
      onClose={() => navigate('/menu')}
    />
  );
};
