import React, { useEffect } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import { 
  X, 
  Home, 
  Tag, 
  Info, 
  Headphones, 
  User, 
  MapPin, 
  LogOut, 
  ChevronRight
} from 'lucide-react';
import { useCartStore } from '../../store/cartStore';
import { useAuthStore } from '../../store/authStore';

interface Props {
  onClose: () => void;
  onOpenLocationModal?: () => void;
}

export const MobileDrawer: React.FC<Props> = ({ onClose }) => {
  const { selectedBranch } = useCartStore();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  // Close on Escape key press and lock body scroll while open
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = originalOverflow;
    };
  }, [onClose]);

  const handleNav = (path: string) => {
    onClose();
    navigate(path);
  };

  const handleLogout = () => {
    logout();
    onClose();
    navigate('/');
  };

  const navLinks = [
    { label: 'HOME', path: '/', icon: Home },
    { label: 'OFFERS', path: '/offers', icon: Tag },
    { label: 'ABOUT', path: '/about', icon: Info },
    { label: 'CONTACT', path: '/contact', icon: Headphones },
  ];

  return (
    <div 
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex overflow-hidden select-none drawer-overlay-animate cursor-pointer transition-colors hover:bg-black/85"
      aria-modal="true"
      role="dialog"
      aria-label="Mobile Navigation Menu"
    >
      {/* STATIC BACKGROUND FOOD IMAGE LAYER */}
      <div 
        className="absolute inset-0 bg-cover bg-center pointer-events-none z-0 opacity-15 filter contrast-125 brightness-75"
        style={{ 
          backgroundImage: `url('/herobackground.webp')`,
        }}
        aria-hidden="true"
      />

      {/* SIDEBAR DRAWER CONTAINER */}
      <aside 
        onClick={(e) => e.stopPropagation()}
        className="w-[80vw] max-w-[290px] sm:w-[320px] h-full bg-[#090909]/95 backdrop-blur-md border-r border-[#242424] rounded-r-2xl shadow-2xl shadow-black flex flex-col justify-between overflow-hidden relative z-10 drawer-content-animate cursor-default"
      >
        {/* TOP HEADER SECTION */}
        <div className="px-4.5 pt-4.5 pb-3.5 border-b border-[#1F1F1F] flex items-center justify-between shrink-0 bg-[#090909]">
          {/* Logo & Brand Identity with Hover Glow */}
          <Link 
            to="/" 
            onClick={onClose} 
            className="flex items-center gap-2.5 group focus:outline-none transition-transform"
          >
            <img
              src="/logo.webp"
              alt="Patty Project"
              loading="lazy"
              decoding="async"
              onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/logo.png'; }}
              className="w-9 h-9 object-contain shrink-0 group-hover:scale-110 transition-transform duration-200"
            />
            <div className="flex flex-col">
              <span className="font-hero font-black text-white text-[16px] uppercase tracking-tight leading-none group-hover:text-[#FF5A00] transition-colors duration-200">
                PATTY PROJECT
              </span>
              <span className="text-[9px] tracking-[0.16em] font-bold text-[#9CA3AF] uppercase block mt-0.5 group-hover:text-white transition-colors duration-200">
                BURGERS DONE RIGHT
              </span>
            </div>
          </Link>

          {/* Close Button with Smooth Rotate & Glowing Orange Hover */}
          <button
            onClick={onClose}
            aria-label="Close navigation drawer"
            className="w-9 h-9 min-w-[36px] min-h-[36px] rounded-full bg-[#141414] border border-[#262626] text-[#A1A1AA] hover:text-white hover:border-[#FF5A00] hover:bg-[#FF5A00] hover:shadow-[0_0_15px_rgba(255,90,0,0.5)] flex items-center justify-center transition-all duration-200 cursor-pointer active:scale-95 focus:outline-none"
          >
            <X className="w-4 h-4 stroke-[2.2] transition-transform duration-200 hover:rotate-90" />
          </button>
        </div>

        {/* SCROLLABLE MAIN BODY */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-none">
          {/* CURRENT OUTLET SELECTION CARD WITH INTERACTIVE HOVER OVERLAY */}
          <div 
            onClick={() => {
              onClose();
              navigate('/select-location');
            }}
            className="bg-[#111111] hover:bg-[#161616] active:bg-[#1A1A1A] border border-[#242424] hover:border-[#FF5A00] hover:shadow-lg hover:shadow-[#FF5A00]/15 rounded-xl p-3.5 space-y-2 transition-all duration-200 cursor-pointer group relative overflow-hidden"
          >
            {/* Soft Ambient Radial Overlay on Hover */}
            <div className="absolute -right-8 -top-8 w-24 h-24 bg-[#FF5A00]/10 rounded-full blur-xl group-hover:bg-[#FF5A00]/25 transition-all pointer-events-none" />

            {/* Top Row: Label & Change Button */}
            <div className="flex items-center justify-between relative z-10">
              <span className="text-[10px] font-extrabold text-[#FF5A00] uppercase tracking-wider group-hover:tracking-widest transition-all">
                CURRENT OUTLET
              </span>
              <span className="text-[10px] font-bold text-[#FF5A00] group-hover:text-white flex items-center gap-0.5 transition-colors">
                <span>Change</span>
                <ChevronRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
              </span>
            </div>

            {/* Outlet Name & Dynamic Address */}
            <div className="flex items-start gap-2 pt-0.5 relative z-10">
              <MapPin className="w-4 h-4 text-[#FF5A00] shrink-0 mt-0.5 group-hover:scale-110 transition-transform" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-bold text-white tracking-tight truncate leading-tight group-hover:text-[#FF5A00] transition-colors">
                  {selectedBranch ? selectedBranch.name : 'London - Central'}
                </p>
                <p className="text-[11px] text-[#9CA3AF] group-hover:text-[#D1D5DB] font-normal truncate mt-0.5 leading-snug transition-colors">
                  {selectedBranch 
                    ? `${selectedBranch.address_line1}, ${selectedBranch.postcode}` 
                    : '4 Market Parade, N9 9HF'}
                </p>
              </div>
            </div>
          </div>

          {/* MAIN NAVIGATION LIST WITH HOVER OVERLAY GLOW & SLIDE */}
          <nav className="space-y-1.5" aria-label="Main Mobile Navigation">
            {navLinks.map((link) => {
              const Icon = link.icon;
              const isActive = location.pathname === link.path;

              return (
                <NavLink
                  key={link.path}
                  to={link.path}
                  onClick={onClose}
                  className={`min-h-[46px] h-[46px] px-3.5 flex items-center justify-between rounded-xl transition-all duration-200 group focus:outline-none relative overflow-hidden ${
                    isActive
                      ? 'bg-[#1A1A1A] border border-[#FF5A00] text-white font-bold shadow-md shadow-[#FF5A00]/20'
                      : 'text-[#D1D5DB] hover:text-white hover:bg-gradient-to-r hover:from-[#FF5A00]/15 hover:via-[#161616] hover:to-[#111111] hover:border-[#FF5A00]/60 hover:translate-x-1.5 hover:shadow-md hover:shadow-[#FF5A00]/10 border border-transparent'
                  }`}
                >
                  {/* Active/Hover Orange Indicator Strip */}
                  <div 
                    className={`absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r transition-all duration-200 ${
                      isActive 
                        ? 'bg-[#FF5A00] opacity-100 shadow-[0_0_8px_#FF5A00]' 
                        : 'bg-[#FF5A00] opacity-0 group-hover:opacity-100 group-hover:shadow-[0_0_8px_#FF5A00]'
                    }`} 
                  />

                  <div className="flex items-center gap-3 pl-1">
                    <Icon 
                      className={`w-4 h-4 shrink-0 transition-all duration-200 ${
                        isActive 
                          ? 'text-[#FF5A00]' 
                          : 'text-[#9CA3AF] group-hover:text-[#FF5A00] group-hover:scale-115'
                      }`} 
                    />
                    <span 
                      className={`text-[13px] tracking-wider uppercase transition-colors duration-200 ${
                        isActive 
                          ? 'text-white font-bold' 
                          : 'text-[#D1D5DB] group-hover:text-white font-semibold'
                      }`}
                    >
                      {link.label}
                    </span>
                  </div>

                  <ChevronRight 
                    className={`w-4 h-4 shrink-0 transition-all duration-200 ${
                      isActive 
                        ? 'text-[#FF5A00] opacity-100' 
                        : 'text-[#71717A] opacity-0 group-hover:opacity-100 group-hover:text-[#FF5A00] group-hover:translate-x-1'
                    }`} 
                  />
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* PINNED FOOTER CTA SECTION WITH GLOWING HOVER */}
        <div className="p-4 border-t border-[#1F1F1F] bg-[#090909] shrink-0 mt-auto">
          {user ? (
            <div className="space-y-2.5">
              {/* User Info Card */}
              <div
                onClick={() => handleNav('/profile')}
                className="flex items-center gap-2.5 p-2.5 bg-[#111111] hover:bg-[#181818] border border-[#242424] hover:border-[#FF5A00] rounded-xl cursor-pointer transition-all duration-200 group hover:shadow-md hover:shadow-[#FF5A00]/10"
              >
                <div className="w-8 h-8 rounded-full bg-[#FF5A00]/20 border border-[#FF5A00]/50 text-[#FF5A00] font-black text-xs flex items-center justify-center shrink-0 group-hover:scale-105 group-hover:bg-[#FF5A00] group-hover:text-white transition-all duration-200">
                  {user.full_name?.charAt(0) || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold text-white group-hover:text-[#FF5A00] truncate transition-colors">
                    {user.full_name}
                  </p>
                  <p className="text-[10px] text-[#9CA3AF] group-hover:text-[#D1D5DB] truncate transition-colors">
                    {user.email}
                  </p>
                </div>
                <ChevronRight className="w-3.5 h-3.5 text-[#9CA3AF] group-hover:text-[#FF5A00] group-hover:translate-x-1 transition-all" />
              </div>

              {/* Log Out Button */}
              <button
                onClick={handleLogout}
                className="w-full h-10 min-h-[40px] flex items-center justify-center gap-1.5 bg-[#121212] hover:bg-[#EF4444] border border-[#EF4444]/40 hover:border-[#EF4444] text-[#EF4444] hover:text-white text-[11px] font-bold uppercase tracking-wider rounded-xl transition-all duration-200 cursor-pointer active:scale-95 focus:outline-none hover:shadow-[0_0_15px_rgba(239,68,68,0.4)]"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>LOG OUT</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleNav('/login')}
              className="w-full h-11 min-h-[44px] bg-[#FF5A00] hover:bg-[#E04B00] text-white font-bold text-xs tracking-wider uppercase rounded-xl shadow-lg shadow-[#FF5A00]/30 hover:shadow-[#FF5A00]/50 hover:scale-[1.02] active:scale-[0.98] transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#FF5A00]/60"
            >
              <User className="w-4 h-4 stroke-[2.5]" />
              <span>LOGIN / SIGN UP</span>
            </button>
          )}
        </div>
      </aside>

      {/* Backdrop Area to click and dismiss */}
      <div 
        className="flex-1 cursor-pointer relative z-10" 
        onClick={onClose} 
        aria-hidden="true" 
      />
    </div>
  );
};

export default MobileDrawer;
