import React from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { User, MapPin } from 'lucide-react';
import { useCartStore } from '../../store/cartStore';
import { useAuthStore } from '../../store/authStore';

interface Props {
  onOpenLocationModal?: () => void;
}

export const OrderingHeader: React.FC<Props> = ({ onOpenLocationModal }) => {
  const { selectedBranch } = useCartStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <header className="sticky top-0 z-50 bg-[#0A0A0A] border-b border-[#1F1F1F] shadow-2xl">
      <div className="w-full max-w-[1720px] mx-auto px-4 sm:px-8 lg:px-12 py-3 flex items-center justify-between gap-3">

        {/* Left Section: Round Brand Logo (Text removed as requested) */}
        <div className="flex items-center">
          <Link to="/" className="flex items-center group">
            <img
              src="/logo.webp"
              alt="Patty Project"
              onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/logo.png'; }}
              className="w-10 h-10 sm:w-11 sm:h-11 object-contain group-hover:scale-105 transition-transform"
            />
          </Link>
        </div>

        {/* Right Top Corner: Aligned MENU -> Select Outlet -> LOGIN */}
        <div className="flex items-center gap-3 sm:gap-5">
          {/* 1. MENU Link */}
          <Link
            to="/order"
            className={`text-xs font-black tracking-widest uppercase transition-colors px-1 ${
              location.pathname === '/order' ? 'text-[#FF5500]' : 'text-[#9CA3AF] hover:text-white'
            }`}
          >
            MENU
          </Link>

          {/* 2. Select Outlet Switcher */}
          <button
            onClick={() => navigate('/select-location')}
            className="flex items-center gap-1.5 bg-[#141414] hover:bg-[#1A1A1A] border border-[#222222] px-3 sm:px-3.5 py-1.5 rounded-full text-xs font-bold text-white transition-all cursor-pointer"
          >
            <MapPin className="w-3.5 h-3.5 text-[#FF5500] shrink-0" />
            <span className="truncate max-w-[100px] sm:max-w-[150px] text-xs font-extrabold">
              {selectedBranch ? selectedBranch.name : 'Select Outlet'}
            </span>
          </button>

          {/* 3. LOGIN / User Profile */}
          {user ? (
            <Link
              to="/profile"
              className="flex items-center gap-2 text-xs font-bold text-white hover:text-[#FF5500] transition-colors bg-[#141414] border border-[#262626] px-3 sm:px-3.5 py-1.5 rounded-xl"
            >
              <User className="w-3.5 h-3.5 text-[#FF5500]" />
              <span className="hidden sm:inline-block uppercase tracking-wider">{user.full_name.split(' ')[0]}</span>
            </Link>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-1.5 text-xs font-extrabold text-white hover:text-[#FF5500] transition-colors bg-[#141414] border border-[#262626] px-3 sm:px-3.5 py-1.5 rounded-xl uppercase tracking-widest"
            >
              <User className="w-3.5 h-3.5" />
              <span className="hidden sm:inline-block">LOGIN</span>
            </Link>
          )}
        </div>

      </div>
    </header>
  );
};
