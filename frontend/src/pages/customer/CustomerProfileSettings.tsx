import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { User, MapPin, CreditCard, Gift, LogOut, ChevronRight, Headphones, Package } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

export const CustomerProfileSettings: React.FC = () => {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  // Strictly check user.role === 'CUSTOMER'; fail closed if missing or admin
  const isCustomer = user?.role === 'CUSTOMER';

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 pb-28 space-y-6 text-white">
      <div>
        <h1 className="text-2xl font-extrabold text-white tracking-wide">Profile Settings</h1>
        <p className="text-[#9CA3AF] text-xs mt-0.5">Manage your loyalty account and preferences</p>
      </div>

      {/* User Info Header Card - Strictly for Customer Accounts */}
      {isCustomer && (
        <div className="bg-[#121212] border border-[#262626] p-5 rounded-2xl flex items-center justify-between shadow-xl">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-[#FF5500]/20 text-[#FF5500] font-black text-xl flex items-center justify-center border border-[#FF5500]/40">
              {user?.full_name ? user.full_name.charAt(0) : 'U'}
            </div>
            <div>
              <h2 className="font-extrabold text-white text-base">{user?.full_name || 'Loyalty Customer'}</h2>
              <p className="text-xs text-[#9CA3AF]">{user?.email || 'customer@pattyproject.co.uk'}</p>
              <span className="inline-block mt-1 bg-[#FF5500]/20 text-[#FF5500] text-[10px] font-black uppercase px-2 py-0.5 rounded border border-[#FF5500]/30 tracking-wider">
                LOYALTY MEMBER
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Account Settings Navigation List */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#9CA3AF] uppercase tracking-wider">Account & Saved Info</h3>
        <div className="bg-[#121212] border border-[#262626] rounded-2xl overflow-hidden divide-y divide-[#1F1F1F]">
          <Link to="/orders" className="p-4 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors">
            <div className="flex items-center gap-3">
              <Package className="w-5 h-5 text-[#FF5500]" />
              <div>
                <p className="text-xs font-bold text-white">My Orders</p>
                <p className="text-[10px] text-[#9CA3AF]">View past order history and track active orders</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#6B7280]" />
          </Link>

          <Link to="/addresses" className="p-4 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors">
            <div className="flex items-center gap-3">
              <MapPin className="w-5 h-5 text-[#FF5500]" />
              <div>
                <p className="text-xs font-bold text-white">My Addresses</p>
                <p className="text-[10px] text-[#9CA3AF]">Manage your saved delivery locations</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#6B7280]" />
          </Link>

          <Link to="/payment-methods" className="p-4 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors">
            <div className="flex items-center gap-3">
              <CreditCard className="w-5 h-5 text-[#FF5500]" />
              <div>
                <p className="text-xs font-bold text-white">Payment Methods</p>
                <p className="text-[10px] text-[#9CA3AF]">Manage saved credit & debit cards</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#6B7280]" />
          </Link>
        </div>
      </div>

      {/* Loyalty & Support Section */}
      <div className="space-y-3">
        <h3 className="text-xs font-bold text-[#9CA3AF] uppercase tracking-wider">Loyalty & Support</h3>
        <div className="bg-[#121212] border border-[#262626] rounded-2xl overflow-hidden divide-y divide-[#1F1F1F]">
          <Link to="/loyalty" className="p-4 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors">
            <div className="flex items-center gap-3">
              <Gift className="w-5 h-5 text-[#FF5500]" />
              <div>
                <p className="text-xs font-bold text-white">Loyalty & Rewards Portal</p>
                <p className="text-[10px] text-[#9CA3AF]">Check points balance, milestones & claim offers</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#6B7280]" />
          </Link>

          <Link to="/contact" className="p-4 flex items-center justify-between hover:bg-[#1A1A1A] transition-colors">
            <div className="flex items-center gap-3">
              <Headphones className="w-5 h-5 text-[#FF5500]" />
              <div>
                <p className="text-xs font-bold text-white">Contact & Customer Support</p>
                <p className="text-[10px] text-[#9CA3AF]">Get help with your loyalty account or orders</p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-[#6B7280]" />
          </Link>
        </div>
      </div>

      {/* Logout Button */}
      <button
        onClick={handleLogout}
        className="w-full bg-[#121212] border border-[#EF4444]/30 hover:bg-[#EF4444]/10 text-[#EF4444] font-extrabold py-3.5 rounded-2xl transition-colors text-xs flex items-center justify-center gap-2 cursor-pointer"
      >
        <LogOut className="w-4 h-4" />
        <span>Log Out</span>
      </button>
    </div>
  );
};
