import React from 'react';
import { Link } from 'react-router-dom';
import { Mail, MapPin, Phone, Clock, ExternalLink } from 'lucide-react';

export const CustomerFooter: React.FC = () => {
  return (
    <footer className="w-full bg-black pt-14 pb-8 text-white border-t border-white/[0.06]">
      {/* Standard desktop container */}
      <div className="w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12 space-y-12">
        {/* 5-Column Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-8 xl:gap-10">
          
          {/* Column 1: Brand & Logo */}
          <div className="space-y-4 lg:col-span-1">
            <Link to="/" className="inline-flex items-center gap-3 group">
              <img
                src="/logo.png"
                alt="Patty Project"
                className="w-12 h-12 object-contain group-hover:scale-105 transition-transform"
              />
              <div>
                <span className="text-base font-black text-white tracking-widest uppercase block font-hero">
                  PATTY PROJECT
                </span>
                <span className="text-[10px] text-[#FF5500] font-bold tracking-widest uppercase">
                  BURGER CO.
                </span>
              </div>
            </Link>

            <p className="text-xs text-[#9CA3AF] leading-relaxed">
              Handcrafted gourmet smash burgers, fried chicken sandos & loaded sides. Freshly prepared daily with premium ingredients and unmatched flavour.
            </p>

            {/* Social Icons */}
            <div className="flex items-center gap-2.5 pt-2">
              <a
                href="https://www.instagram.com/pattyprojectuk?igsi=ZGE2a2xrY3h6eWt6"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram"
                className="w-8 h-8 rounded-full bg-[#111111] border border-white/[0.08] flex items-center justify-center text-[#9CA3AF] hover:text-[#FF5500] hover:border-[#FF5500]/50 hover:bg-[#181818] transition-all"
              >
                <svg className="w-4 h-4 fill-currentColor" viewBox="0 0 24 24">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162s2.759 6.163 6.162 6.163 6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z"/>
                </svg>
              </a>
              <a
                href="https://www.facebook.com/share/19GqYUg1UM/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Facebook"
                className="w-8 h-8 rounded-full bg-[#111111] border border-white/[0.08] flex items-center justify-center text-[#9CA3AF] hover:text-[#FF5500] hover:border-[#FF5500]/50 hover:bg-[#181818] transition-all"
              >
                <svg className="w-4 h-4 fill-currentColor" viewBox="0 0 24 24">
                  <path d="M9 8H6v4h3v12h5V12h3.642L18 8h-4V6.333C14 5.374 14.5 5 15.5 5H18V0h-3.808C10.593 0 9 1.583 9 4.615V8z"/>
                </svg>
              </a>
              <a
                href="https://www.tiktok.com/@pattyprojectuk?_r=1&_t=ZN-998SUEBODDC"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="TikTok"
                className="w-8 h-8 rounded-full bg-[#111111] border border-white/[0.08] flex items-center justify-center text-[#9CA3AF] hover:text-[#FF5500] hover:border-[#FF5500]/50 hover:bg-[#181818] transition-all font-bold text-xs"
              >
                <span className="text-[11px] font-black">TT</span>
              </a>
            </div>
          </div>

          {/* Column 2: Quick Links */}
          <div className="space-y-4">
            <h4 className="text-xs font-black text-[#FF5500] uppercase tracking-widest">
              Quick Links
            </h4>
            <ul className="space-y-2.5 text-xs text-[#9CA3AF] font-medium">
              <li>
                <Link to="/" className="hover:text-white transition-colors">Home</Link>
              </li>
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Order Online</Link>
              </li>
              <li>
                <Link to="/offers" className="hover:text-white transition-colors">Special Offers</Link>
              </li>
              <li>
                <Link to="/contact" className="hover:text-white transition-colors">Contact & Locations</Link>
              </li>
              <li>
                <Link to="/select-location" className="hover:text-white transition-colors">Choose Branch</Link>
              </li>
            </ul>
          </div>

          {/* Column 3: Products / Categories */}
          <div className="space-y-4">
            <h4 className="text-xs font-black text-[#FF5500] uppercase tracking-widest">
              Products
            </h4>
            <ul className="space-y-2.5 text-xs text-[#9CA3AF] font-medium">
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Gourmet Burgers</Link>
              </li>
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Chicken Sandos</Link>
              </li>
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Loaded Fries & Sides</Link>
              </li>
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Handmade Shakes</Link>
              </li>
              <li>
                <Link to="/order" className="hover:text-white transition-colors">Dips & Beverages</Link>
              </li>
            </ul>
          </div>

          {/* Column 4: Contact Us */}
          <div className="space-y-4">
            <h4 className="text-xs font-black text-[#FF5500] uppercase tracking-widest">
              Contact Us
            </h4>
            <ul className="space-y-3 text-xs text-[#9CA3AF] font-medium">
              <li className="flex items-center gap-2.5">
                <Phone className="w-4 h-4 text-[#FF5500] shrink-0" />
                <a href="tel:+447417521128" className="hover:text-white transition-colors">
                  +44 7417 521128
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <Mail className="w-4 h-4 text-[#FF5500] shrink-0" />
                <a href="mailto:hello@pattyproject.co.uk" className="hover:text-white transition-colors">
                  hello@pattyproject.co.uk
                </a>
              </li>
              <li className="flex items-start gap-2.5">
                <MapPin className="w-4 h-4 text-[#FF5500] shrink-0 mt-0.5" />
                <a
                  href="https://maps.app.goo.gl/ucRr3c94PQKGgq4L7?g_st=aw"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-white transition-colors leading-relaxed"
                >
                  4 Market Parade, London N9 9HF, UK
                </a>
              </li>
              <li className="flex items-center gap-2.5">
                <Clock className="w-4 h-4 text-[#FF5500] shrink-0" />
                <span>Mon – Sun: 12:00 PM – 11:00 PM</span>
              </li>
            </ul>
          </div>

          {/* Column 5: Our Location / Map */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-black text-[#FF5500] uppercase tracking-widest">
                Our Location
              </h4>
              <a
                href="https://maps.app.goo.gl/ucRr3c94PQKGgq4L7?g_st=aw"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[10px] font-bold text-[#FF5500] hover:underline inline-flex items-center gap-1"
              >
                <span>Maps</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            {/* Embedded Google Map Preview */}
            <div className="relative rounded-2xl overflow-hidden border border-white/[0.08] bg-[#0E0E0E] group shadow-lg">
              <iframe
                title="Patty Project London Location"
                src="https://maps.google.com/maps?q=4%20Market%20Parade,%20London%20N9%209HF,%20United%20Kingdom&t=&z=14&ie=UTF8&iwloc=&output=embed"
                className="w-full h-32 sm:h-36 border-0 filter invert-[90%] hue-rotate-180 contrast-125 opacity-85 group-hover:opacity-100 transition-opacity"
                loading="lazy"
              />
              <a
                href="https://maps.app.goo.gl/ucRr3c94PQKGgq4L7?g_st=aw"
                target="_blank"
                rel="noopener noreferrer"
                className="absolute inset-0 z-10 flex items-end p-2 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <span className="text-[10px] font-semibold text-white bg-[#FF5500] px-2.5 py-1 rounded-lg flex items-center gap-1 shadow-md">
                  <MapPin className="w-3 h-3" />
                  <span>Open in Google Maps</span>
                </span>
              </a>
            </div>

            <p className="text-[11px] text-[#71717A]">
              London N9 9HF • Dine-in & Collection Available
            </p>
          </div>

        </div>

        {/* Sub-Footer Line & Copyright */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between text-xs text-[#9CA3AF] gap-4">
          <div className="flex flex-wrap items-center justify-center sm:justify-start gap-4 sm:gap-6">
            <Link to="/privacy" className="hover:text-white transition-colors">Privacy Policy</Link>
            <Link to="/refund-cancellation" className="hover:text-white transition-colors">Refund & Cancellation Policy</Link>
            <Link to="/terms-and-service" className="hover:text-white transition-colors">Terms of Service</Link>
          </div>
          <p className="font-medium text-white">Patty Project © 2026. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};
