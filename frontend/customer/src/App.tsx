import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CustomerHeader } from './components/customer/CustomerHeader';
import { OrderingHeader } from './components/customer/OrderingHeader';
import { MobileDrawer } from './components/customer/MobileDrawer';
import { MobileBottomNav } from './components/customer/MobileBottomNav';
import { LocationModal } from './components/customer/LocationModal';
import { FloatingCartBar } from './components/customer/FloatingCartBar';

import { CustomerHome } from './pages/customer/CustomerHome';
import { CustomerMenu } from './pages/customer/CustomerMenu';
import { CustomerCart } from './pages/customer/CustomerCart';
import { CustomerCheckout } from './pages/customer/CustomerCheckout';
import { OrderConfirmation } from './pages/customer/OrderConfirmation';
import { CustomerLoyaltyPortal } from './pages/customer/CustomerLoyaltyPortal';
import { CustomerOrderHistory } from './pages/customer/CustomerOrderHistory';
import { CustomerProfileSettings } from './pages/customer/CustomerProfileSettings';
import { CustomerAddresses } from './pages/customer/CustomerAddresses';
import { CustomerPaymentMethods } from './pages/customer/CustomerPaymentMethods';
import { ProductDetailPage } from './pages/customer/ProductDetailPage';
import { SelectLocationPage } from './pages/customer/SelectLocationPage';
import { CustomerLogin } from './pages/customer/CustomerLogin';
import { CustomerOffers } from './pages/customer/CustomerOffers';
import { CustomerContact } from './pages/customer/CustomerContact';
import { CustomerAbout } from './pages/customer/CustomerAbout';
import { CustomerPrivacyPolicy } from './pages/customer/CustomerPrivacyPolicy';
import { RefundCancellationPolicy } from './pages/customer/RefundCancellationPolicy';
import { TermsOfService } from './pages/customer/TermsOfService';
import { CustomerFooter } from './components/customer/CustomerFooter';
import { MockCheckoutPage } from './pages/customer/MockCheckoutPage';

const queryClient = new QueryClient();

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
        <Routes>
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
      </Router>
    </QueryClientProvider>
  );
}

export default App;
