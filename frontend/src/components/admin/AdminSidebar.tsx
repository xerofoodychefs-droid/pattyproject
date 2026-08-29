import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  ClipboardList,
  Package,
  Users,
  Star,
  Ticket,
  Sparkles,
  Settings,
  LogOut,
  ChevronLeft
} from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

const lazyPreloadMap: Record<string, () => Promise<any>> = {
  '/admin/dashboard': () => import('../../pages/admin/AdminDashboard'),
  '/admin/orders': () => import('../../pages/admin/AdminOrderBoard'),
  '/admin/products': () => import('../../pages/admin/AdminProducts'),
  '/admin/customers': () => import('../../pages/admin/AdminCustomers'),
  '/admin/loyalty': () => import('../../pages/admin/AdminLoyalty'),
  '/admin/coupons': () => import('../../pages/admin/AdminCoupons'),
  '/admin/offers': () => import('../../pages/admin/AdminOfferSettings'),
  '/admin/settings': () => import('../../pages/admin/AdminProfileSettings'),
};

interface AdminSidebarProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const AdminSidebar: React.FC<AdminSidebarProps> = ({
  isCollapsed = false,
  onToggleCollapse,
}) => {
  const { logout, user } = useAuthStore();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/admin');
  };

  const allNavItems = [
    { label: 'Dashboard', path: '/admin/dashboard', icon: LayoutDashboard },
    { label: 'Orders', path: '/admin/orders', icon: ClipboardList },
    { label: 'Products & Stock', path: '/admin/products', icon: Package },
    { label: 'Customers', path: '/admin/customers', icon: Users },
    { label: 'Loyalty Points', path: '/admin/loyalty', icon: Star, superAdminOnly: true },
    { label: 'Coupons', path: '/admin/coupons', icon: Ticket, superAdminOnly: true },
    { label: 'Offers', path: '/admin/offers', icon: Sparkles, superAdminOnly: true },
    { label: 'Profile Settings', path: '/admin/settings', icon: Settings },
  ];

  const navItems = allNavItems.filter((item) => !item.superAdminOnly || user?.role === 'SUPER_ADMIN');

  return (
    <aside
      className={`fixed top-0 left-0 bottom-0 z-40 bg-[#0A0A0A] border-r border-[#1F1F1F] flex flex-col justify-between h-screen transition-all duration-300 ease-in-out select-none ${
        isCollapsed ? 'w-0 -translate-x-full opacity-0 pointer-events-none' : 'w-64 translate-x-0 opacity-100'
      }`}
    >
      <div className="flex flex-col h-full overflow-hidden">
        {/* Brand Logo Header with Standard Chevron Collapse Button */}
        <div className="p-4 flex items-center justify-between border-b border-[#1A1A1A] h-16 shrink-0 bg-[#0A0A0A]">
          <div className="flex items-center gap-3 min-w-0">
            <img
              src="/logo.png"
              alt="Patty Project"
              className="w-10 h-10 object-contain shrink-0"
            />
            <div className="min-w-0">
              <h1 className="text-white font-bold text-sm tracking-tight truncate leading-tight">
                PATTY PROJECT
              </h1>
              <p className="text-[#FF5500] text-[10px] font-bold uppercase tracking-wider mt-0.5 truncate">
                {user?.role === 'SUPER_ADMIN' ? 'Super Admin' : 'Branch Admin'}
              </p>
            </div>
          </div>

          {/* Industry Standard Collapse Button */}
          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              title="Collapse sidebar"
              className="p-2 text-[#9CA3AF] hover:text-white hover:bg-[#1A1A1A] rounded-lg border border-[#262626] hover:border-[#3A3A3A] transition-all cursor-pointer shrink-0 ml-1"
              aria-label="Collapse sidebar"
            >
              <ChevronLeft className="w-4 h-4 text-[#A1A1AA] hover:text-white" />
            </button>
          )}
        </div>

        {/* Navigation Menu */}
        <nav className="p-3 space-y-1.5 flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-[#222222]">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onMouseEnter={() => {
                  try {
                    lazyPreloadMap[item.path]?.();
                  } catch {}
                }}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? 'bg-[#1C130D] text-[#FF5500] border-l-4 border-[#FF5500] shadow-sm font-bold'
                      : 'text-[#9CA3AF] hover:text-white hover:bg-[#141414]'
                  }`
                }
              >
                <Icon className="w-4.5 h-4.5 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Logout Footer */}
        <div className="p-3 border-t border-[#1A1A1A] bg-[#0A0A0A] shrink-0">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold text-[#EF4444] hover:bg-[#EF4444]/10 transition-colors cursor-pointer"
          >
            <LogOut className="w-4.5 h-4.5 shrink-0" />
            <span>Logout</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
