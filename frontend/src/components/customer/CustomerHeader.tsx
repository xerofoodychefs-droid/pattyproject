import React from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { ShoppingBag, User, MapPin, Menu as MenuIcon } from 'lucide-react';
import { useCartStore } from '../../store/cartStore';
import { useAuthStore } from '../../store/authStore';

interface Props {
  onOpenLocationModal: () => void;
  onOpenMobileDrawer: () => void;
}

export const CustomerHeader: React.FC<Props> = ({ onOpenLocationModal, onOpenMobileDrawer }) => {
  const { items, selectedBranch } = useCartStore();
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const totalCartCount = items.reduce((sum, item) => sum + item.quantity, 0);

  const navLinks = [
    { label: 'HOME', path: '/' },
    { label: 'OFFERS', path: '/offers' },
    { label: 'ABOUT', path: '/about' },
    { label: 'CONTACT', path: '/contact' },
  ];

  return (
    <header className="sticky top-0 z-50 bg-black/95 backdrop-blur-md border-b border-white/[0.06]">
      <div className="w-full max-w-[1360px] mx-auto px-4 sm:px-8 lg:px-12 py-2.5 sm:py-3 md:py-3.5 flex items-center justify-between gap-2">
        {/* Left Logo Section matching navbar.png */}
        <div className="flex items-center gap-2 sm:gap-3">
          <button
            onClick={onOpenMobileDrawer}
            aria-label="Open navigation menu"
            type="button"
            className="md:hidden text-white p-2 hover:bg-[#1A1A1A] active:scale-95 rounded-xl transition-all cursor-pointer flex items-center justify-center shrink-0"
          >
            <MenuIcon className="w-6 h-6 text-white" />
          </button>

          <Link to="/" className="flex items-center group">
            <img
              src="/logo.webp"
              alt="Patty Project"
              loading="eager"
              decoding="async"
              onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/logo.png'; }}
              className="w-11 h-11 sm:w-14 sm:h-14 object-contain group-hover:scale-105 transition-transform"
            />
          </Link>
        </div>

        {/* Center Desktop Navigation Links (Hidden on /select-location) */}
        {location.pathname !== '/select-location' && (
          <nav className="hidden md:flex items-center gap-10">
            {navLinks.map((link) => (
              <NavLink
                key={link.path}
                to={link.path}
                className={({ isActive }) =>
                  `text-xs font-extrabold tracking-widest transition-all py-1 relative ${
                    isActive
                      ? 'text-white border-b-2 border-[#FF5500] pb-1'
                      : 'text-[#9CA3AF] hover:text-white'
                  }`
                }
              >
                {link.label}
              </NavLink>
            ))}
          </nav>
        )}

        {/* Right Action Controls matching navbar.png */}
        <div className="flex items-center gap-3 sm:gap-5">
          {/* Branch Location Switcher (Hidden on /select-location) */}
          {location.pathname !== '/select-location' && (
            <button
              onClick={() => navigate('/select-location')}
              className="flex items-center gap-1.5 bg-[#121212] hover:bg-[#1A1A1A] border border-[#222222] px-2.5 sm:px-3.5 py-1.5 rounded-full text-[11px] sm:text-xs font-semibold text-[#9CA3AF] hover:text-white transition-all cursor-pointer"
            >
              <MapPin className="w-3.5 h-3.5 text-[#FF5500] shrink-0" />
              <span className="truncate max-w-[85px] sm:max-w-[130px]">
                {selectedBranch ? selectedBranch.name : 'Outlet'}
              </span>
            </button>
          )}

          {/* User Auth Link matching LOGIN button in navbar.png */}
          {user ? (
            <Link
              to="/profile"
              className="flex items-center gap-2 text-xs font-bold text-white hover:text-[#FF5500] transition-colors"
            >
              <User className="w-4 h-4 text-[#FF5500]" />
              <span className="hidden sm:inline-block uppercase tracking-wider">{user.full_name.split(' ')[0]}</span>
            </Link>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-2 text-xs font-bold text-white hover:text-[#FF5500] transition-colors uppercase tracking-widest"
            >
              <User className="w-4 h-4" />
              <span className="hidden sm:inline-block">LOGIN</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
