import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AdminSidebar } from './components/admin/AdminSidebar';
import { CustomerHeader } from './components/customer/CustomerHeader';
import { OrderingHeader } from './components/customer/OrderingHeader';
import { MobileDrawer } from './components/customer/MobileDrawer';
import { MobileBottomNav } from './components/customer/MobileBottomNav';
import { LocationModal } from './components/customer/LocationModal';
import { FloatingCartBar } from './components/customer/FloatingCartBar';
import { Menu } from 'lucide-react';

import { CustomerFooter } from './components/customer/CustomerFooter';
import { useAuthStore } from './store/authStore';

// Dynamic Browser Title & Favicon Manager for Admin and Customer routes
const DynamicTitleManager: React.FC = () => {
  const location = useLocation();

  useEffect(() => {
    // Dynamic favicon update with cache buster
    const updateFavicon = () => {
      const existingIcons = document.querySelectorAll<HTMLLinkElement>("link[rel*='icon']");
      existingIcons.forEach(icon => {
        icon.href = `/favicon-32x32.png?v=patty2026`;
      });
      if (existingIcons.length === 0) {
        const newIcon = document.createElement('link');
        newIcon.rel = 'icon';
        newIcon.type = 'image/png';
        newIcon.href = `/favicon-32x32.png?v=patty2026`;
        document.head.appendChild(newIcon);
      }
    };
    updateFavicon();

    const path = location.pathname;
    if (path === '/admin/login') {
      document.title = 'Patty Project Admin | Login';
    } else if (path === '/admin/dashboard' || path === '/admin') {
      document.title = 'Patty Project Admin | Dashboard';
    } else if (path === '/admin/orders') {
      document.title = 'Patty Project Admin | Orders Management';
    } else if (path === '/admin/products') {
      document.title = 'Patty Project Admin | Menu & Inventory';
    } else if (path === '/admin/customers') {
      document.title = 'Patty Project Admin | Customers Management';
    } else if (path === '/admin/loyalty') {
      document.title = 'Patty Project Admin | Loyalty Points System';
    } else if (path === '/admin/coupons') {
      document.title = 'Patty Project Admin | Coupons & Promo Codes';
    } else if (path === '/admin/offers') {
      document.title = 'Patty Project Admin | Offers & Banner Settings';
    } else if (path === '/admin/settings') {
      document.title = 'Patty Project Admin | Branch & Profile Settings';
    } else if (path.startsWith('/admin')) {
      document.title = 'Patty Project Admin | Management Portal';
    } else if (path === '/order' || path === '/menu') {
      document.title = 'Menu & Order Online | Patty Project';
    } else if (path === '/offers') {
      document.title = 'Special Offers & Deals | Patty Project';
    } else if (path === '/about') {
      document.title = 'About Us | Patty Project';
    } else if (path === '/contact') {
      document.title = 'Contact & Locations | Patty Project';
    } else if (path === '/cart') {
      document.title = 'Your Cart | Patty Project';
    } else if (path === '/checkout') {
      document.title = 'Checkout | Patty Project';
    } else {
      document.title = 'Patty Project | Gourmet Smashed Burgers & Shakes in London';
    }
  }, [location.pathname]);

  return null;
};

// Code-splitting lazy loaders for all routes to make initial home page open instantly
const AdminLogin = React.lazy(() => import('./pages/admin/AdminLogin').then(m => ({ default: m.AdminLogin })));
const AdminDashboard = React.lazy(() => import('./pages/admin/AdminDashboard').then(m => ({ default: m.AdminDashboard })));
const AdminOrderBoard = React.lazy(() => import('./pages/admin/AdminOrderBoard').then(m => ({ default: m.AdminOrderBoard })));
const AdminProducts = React.lazy(() => import('./pages/admin/AdminProducts').then(m => ({ default: m.AdminProducts })));
const AdminCustomers = React.lazy(() => import('./pages/admin/AdminCustomers').then(m => ({ default: m.AdminCustomers })));
const AdminLoyalty = React.lazy(() => import('./pages/admin/AdminLoyalty').then(m => ({ default: m.AdminLoyalty })));
const AdminCoupons = React.lazy(() => import('./pages/admin/AdminCoupons').then(m => ({ default: m.AdminCoupons })));
const AdminOfferSettings = React.lazy(() => import('./pages/admin/AdminOfferSettings').then(m => ({ default: m.AdminOfferSettings })));
const AdminProfileSettings = React.lazy(() => import('./pages/admin/AdminProfileSettings').then(m => ({ default: m.AdminProfileSettings })));

const CustomerHome = React.lazy(() => import('./pages/customer/CustomerHome').then(m => ({ default: m.CustomerHome })));
const CustomerMenu = React.lazy(() => import('./pages/customer/CustomerMenu').then(m => ({ default: m.CustomerMenu })));
const CustomerCart = React.lazy(() => import('./pages/customer/CustomerCart').then(m => ({ default: m.CustomerCart })));
const CustomerCheckout = React.lazy(() => import('./pages/customer/CustomerCheckout').then(m => ({ default: m.CustomerCheckout })));
const OrderConfirmation = React.lazy(() => import('./pages/customer/OrderConfirmation').then(m => ({ default: m.OrderConfirmation })));
const CustomerLoyaltyPortal = React.lazy(() => import('./pages/customer/CustomerLoyaltyPortal').then(m => ({ default: m.CustomerLoyaltyPortal })));
const CustomerOrderHistory = React.lazy(() => import('./pages/customer/CustomerOrderHistory').then(m => ({ default: m.CustomerOrderHistory })));
const CustomerProfileSettings = React.lazy(() => import('./pages/customer/CustomerProfileSettings').then(m => ({ default: m.CustomerProfileSettings })));
const CustomerAddresses = React.lazy(() => import('./pages/customer/CustomerAddresses').then(m => ({ default: m.CustomerAddresses })));
const CustomerPaymentMethods = React.lazy(() => import('./pages/customer/CustomerPaymentMethods').then(m => ({ default: m.CustomerPaymentMethods })));
const ProductDetailPage = React.lazy(() => import('./pages/customer/ProductDetailPage').then(m => ({ default: m.ProductDetailPage })));
const SelectLocationPage = React.lazy(() => import('./pages/customer/SelectLocationPage').then(m => ({ default: m.SelectLocationPage })));
const CustomerLogin = React.lazy(() => import('./pages/customer/CustomerLogin').then(m => ({ default: m.CustomerLogin })));
const CustomerOffers = React.lazy(() => import('./pages/customer/CustomerOffers').then(m => ({ default: m.CustomerOffers })));
const CustomerContact = React.lazy(() => import('./pages/customer/CustomerContact').then(m => ({ default: m.CustomerContact })));
const CustomerAbout = React.lazy(() => import('./pages/customer/CustomerAbout').then(m => ({ default: m.CustomerAbout })));
const CustomerPrivacyPolicy = React.lazy(() => import('./pages/customer/CustomerPrivacyPolicy').then(m => ({ default: m.CustomerPrivacyPolicy })));
const RefundCancellationPolicy = React.lazy(() => import('./pages/customer/RefundCancellationPolicy').then(m => ({ default: m.RefundCancellationPolicy })));
const TermsOfService = React.lazy(() => import('./pages/customer/TermsOfService').then(m => ({ default: m.TermsOfService })));
const MockCheckoutPage = React.lazy(() => import('./pages/customer/MockCheckoutPage').then(m => ({ default: m.MockCheckoutPage })));

const RouteLoadingSpinner = () => (
  <div className="min-h-[50vh] flex items-center justify-center">
    <div className="w-8 h-8 border-2 border-[#FF5500] border-t-transparent rounded-full animate-spin"></div>
  </div>
);

const queryClient = new QueryClient();

// Admin Layout Shell with Protection Guard & Sidebar Collapse Toggle
const AdminLayoutShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token, user } = useAuthStore();
  const [isCollapsed, setIsCollapsed] = useState(() => {
    return localStorage.getItem('admin_sidebar_collapsed') === 'true';
  });

  const toggleSidebar = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem('admin_sidebar_collapsed', String(next));
      return next;
    });
  };

  const isAdmin = token && user && (user.role === 'SUPER_ADMIN' || user.role === 'BRANCH_ADMIN');

  if (!isAdmin) {
    return <Navigate to="/admin/login" replace />;
  }

  return (
    <div className="min-h-screen bg-black text-white flex">
      {/* Sidebar Component with Hide Button */}
      <AdminSidebar isCollapsed={isCollapsed} onToggleCollapse={toggleSidebar} />

      {/* Main Content Area */}
      <main
        className={`flex-1 min-w-0 transition-all duration-300 ease-in-out ${
          isCollapsed ? 'ml-0' : 'ml-64'
        }`}
      >
        {/* Floating/Top Bar Show Sidebar Button when Collapsed */}
        {isCollapsed && (
          <div className="sticky top-4 left-4 z-30 px-6 pt-4 pb-0">
            <button
              onClick={toggleSidebar}
              className="inline-flex items-center gap-2 px-3 py-2 bg-[#121212]/95 backdrop-blur-md hover:bg-[#1C1C1C] text-white border border-[#2E2E2E] hover:border-[#FF5500]/50 rounded-xl shadow-2xl transition-all text-xs font-semibold cursor-pointer group"
              title="Show sidebar"
            >
              <Menu className="w-4 h-4 text-[#FF5500] group-hover:scale-110 transition-transform" />
              <span>Sidebar</span>
            </button>
          </div>
        )}
        {children}
      </main>
    </div>
  );
};

// Customer Layout Shell
const CustomerLayoutShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [showLocationModal, setShowLocationModal] = useState(false);
  const [showMobileDrawer, setShowMobileDrawer] = useState(false);
  const location = useLocation();

  const orderingPortalPages = ['/order', '/cart', '/checkout', '/orders', '/profile', '/addresses', '/payment-methods', '/mock-checkout'];
  const isOrderingPortal = orderingPortalPages.includes(location.pathname) || location.pathname.startsWith('/order-confirmation') || location.pathname.startsWith('/mock-checkout');

  const hideBottomNavPages = ['/', '/contact', '/select-location', '/about', '/privacy', '/privacy-policy', '/offers', '/refund-cancellation', '/terms-and-service', '/terms', '/terms-of-service'];
  const showBottomNav = !hideBottomNavPages.includes(location.pathname);

  // Footer only on public marketing/showcase pages
  const publicPagesWithFooter = ['/', '/offers', '/about', '/contact', '/privacy', '/privacy-policy', '/refund-cancellation', '/terms-and-service', '/terms', '/terms-of-service'];
  const showFooter = publicPagesWithFooter.includes(location.pathname);

  // - Selection Location: /select-location (Excluded per user request)
  // - Menu Page (Order Now menu): /order, /product/:productId
  // - Cart Page: /cart
  // - Checkout Page: /checkout
  // - Payment Pages: /mock-checkout, /payment-methods
  // - Post-order / Account Portal: /order-confirmation, /orders, /addresses, /profile, /loyalty
  // Explicitly EXCLUDED from:
  // - Select location page ('/select-location')
  // - Landing page ('/')
  // - Marketing showcase pages ('/about', '/contact', '/offers')
  const isOrderNowFlowPage =
    location.pathname === '/order' ||
    location.pathname.startsWith('/product/') ||
    location.pathname === '/cart' ||
    location.pathname === '/checkout' ||
    location.pathname.startsWith('/mock-checkout') ||
    location.pathname.startsWith('/order-confirmation') ||
    location.pathname === '/payment-methods' ||
    location.pathname === '/orders' ||
    location.pathname === '/loyalty' ||
    location.pathname === '/profile' ||
    location.pathname === '/addresses';

  return (
    <div className="min-h-screen bg-black text-white flex flex-col justify-between relative">
      {/* Dark Burger Watermark Graphic exclusively for Order Now flow pages */}
      {isOrderNowFlowPage && (
        <>
          {/* Mobile View: Vertical / Portrait Burger Background */}
          <div
            className="fixed inset-0 z-0 bg-cover bg-right bg-no-repeat pointer-events-none block md:hidden"
            style={{
              backgroundImage: `url('/order_now_mobile_bg.png')`,
              backgroundAttachment: 'fixed',
            }}
            aria-hidden="true"
          />

          {/* Desktop & Tablet View: Landscape Burger Background */}
          <div
            className="fixed inset-0 z-0 bg-cover bg-right-top md:bg-right bg-no-repeat pointer-events-none hidden md:block"
            style={{
              backgroundImage: `url('/order_now_bg.png')`,
              backgroundAttachment: 'fixed',
            }}
            aria-hidden="true"
          />
        </>
      )}

      <div className="relative z-10 flex-1 flex flex-col justify-between">
        <div>
          {isOrderingPortal ? (
            <OrderingHeader onOpenLocationModal={() => setShowLocationModal(true)} />
          ) : (
            <CustomerHeader
              onOpenLocationModal={() => setShowLocationModal(true)}
              onOpenMobileDrawer={() => setShowMobileDrawer(true)}
            />
          )}
          <main className={showBottomNav ? 'pb-16 md:pb-0' : ''}>{children}</main>
        </div>

        {/* Footer only on public customer pages */}
        {showFooter && <CustomerFooter />}
      </div>

      {showBottomNav && <MobileBottomNav />}
      <FloatingCartBar />

      {showMobileDrawer && (
        <MobileDrawer
          onClose={() => setShowMobileDrawer(false)}
          onOpenLocationModal={() => setShowLocationModal(true)}
        />
      )}

      {showLocationModal && (
        <LocationModal onClose={() => setShowLocationModal(false)} />
      )}
    </div>
  );
};

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <DynamicTitleManager />
        <React.Suspense fallback={<RouteLoadingSpinner />}>
          <Routes>
            {/* Admin Routes */}
            <Route path="/admin" element={<Navigate to="/admin/login" replace />} />
            <Route path="/admin/login" element={<AdminLogin />} />
            <Route path="/admin/dashboard" element={<AdminLayoutShell><AdminDashboard /></AdminLayoutShell>} />
            <Route path="/admin/orders" element={<AdminLayoutShell><AdminOrderBoard /></AdminLayoutShell>} />
            <Route path="/admin/products" element={<AdminLayoutShell><AdminProducts /></AdminLayoutShell>} />
            <Route path="/admin/customers" element={<AdminLayoutShell><AdminCustomers /></AdminLayoutShell>} />
            <Route path="/admin/loyalty" element={<AdminLayoutShell><AdminLoyalty /></AdminLayoutShell>} />
            <Route path="/admin/coupons" element={<AdminLayoutShell><AdminCoupons /></AdminLayoutShell>} />
            <Route path="/admin/offers" element={<AdminLayoutShell><AdminOfferSettings /></AdminLayoutShell>} />
            <Route path="/admin/settings" element={<AdminLayoutShell><AdminProfileSettings /></AdminLayoutShell>} />

            {/* Customer Routes */}
            <Route path="/" element={<CustomerLayoutShell><CustomerHome /></CustomerLayoutShell>} />
            <Route path="/select-location" element={<CustomerLayoutShell><SelectLocationPage /></CustomerLayoutShell>} />
            <Route path="/menu" element={<Navigate to="/order" replace />} />
            <Route path="/order" element={<CustomerLayoutShell><CustomerMenu /></CustomerLayoutShell>} />
            <Route path="/offers" element={<CustomerLayoutShell><CustomerOffers /></CustomerLayoutShell>} />
            <Route path="/about" element={<CustomerLayoutShell><CustomerAbout /></CustomerLayoutShell>} />
            <Route path="/contact" element={<CustomerLayoutShell><CustomerContact /></CustomerLayoutShell>} />
            <Route path="/privacy" element={<CustomerLayoutShell><CustomerPrivacyPolicy /></CustomerLayoutShell>} />
            <Route path="/privacy-policy" element={<CustomerLayoutShell><CustomerPrivacyPolicy /></CustomerLayoutShell>} />
            <Route path="/refund-cancellation" element={<CustomerLayoutShell><RefundCancellationPolicy /></CustomerLayoutShell>} />
            <Route path="/terms-and-service" element={<CustomerLayoutShell><TermsOfService /></CustomerLayoutShell>} />
            <Route path="/terms-of-service" element={<CustomerLayoutShell><TermsOfService /></CustomerLayoutShell>} />
            <Route path="/terms" element={<CustomerLayoutShell><TermsOfService /></CustomerLayoutShell>} />
            <Route path="/product/:productId" element={<CustomerLayoutShell><ProductDetailPage /></CustomerLayoutShell>} />
            <Route path="/cart" element={<CustomerLayoutShell><CustomerCart /></CustomerLayoutShell>} />
            <Route path="/checkout" element={<CustomerLayoutShell><CustomerCheckout /></CustomerLayoutShell>} />
            <Route path="/mock-checkout/:transactionId" element={<CustomerLayoutShell><MockCheckoutPage /></CustomerLayoutShell>} />
            <Route path="/mock-checkout" element={<CustomerLayoutShell><MockCheckoutPage /></CustomerLayoutShell>} />
            <Route path="/order-confirmation/:orderNumber" element={<CustomerLayoutShell><OrderConfirmation /></CustomerLayoutShell>} />
            <Route path="/loyalty" element={<CustomerLayoutShell><CustomerLoyaltyPortal /></CustomerLayoutShell>} />
            <Route path="/orders" element={<CustomerLayoutShell><CustomerOrderHistory /></CustomerLayoutShell>} />
            <Route path="/profile" element={<CustomerLayoutShell><CustomerProfileSettings /></CustomerLayoutShell>} />
            <Route path="/addresses" element={<CustomerLayoutShell><CustomerAddresses /></CustomerLayoutShell>} />
            <Route path="/payment-methods" element={<CustomerLayoutShell><CustomerPaymentMethods /></CustomerLayoutShell>} />
            <Route path="/login" element={<CustomerLogin />} />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </React.Suspense>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
