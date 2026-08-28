import React from 'react';

export const CustomerAbout: React.FC = () => {
  return (
    <div className="min-h-screen bg-black text-white selection:bg-[#FF5A00] selection:text-white pb-20">
      
      {/* ========================================================================= */}
      {/* HERO SECTION: Exact Typography & Font matching Offers Page */}
      {/* ========================================================================= */}
      <section aria-label="About Us Hero" className="relative w-full bg-black h-[360px] sm:h-[420px] lg:h-[460px] xl:h-[500px] overflow-hidden flex items-center">
        {/* Background Banner Image with focal point at [right_25%] */}
        <div className="absolute inset-0 z-0">
          <img
            src="/about_hero_banner.png"
            alt="Patty Project Hero Burger"
            className="w-full h-full object-cover object-[right_25%] select-none pointer-events-none"
            loading="eager"
          />
          {/* Soft dark gradient on left for guaranteed text readability */}
          <div className="absolute inset-0 bg-gradient-to-r from-black via-black/80 lg:via-black/35 to-transparent pointer-events-none" />
        </div>

        {/* Hero Text Content using exact Offers page font & typography scale */}
        <div className="relative z-10 w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12">
          <div className="max-w-xl space-y-2 sm:space-y-2.5">
            <span className="text-[#FF5A00] text-[12px] sm:text-[13px] font-extrabold uppercase tracking-[0.1em] block mb-1.5 sm:mb-2">
              ABOUT US
            </span>

            <h1 className="text-3xl sm:text-4xl lg:text-[44px] xl:text-[50px] font-black uppercase tracking-tight leading-[0.94]">
              <span className="text-white block">FOUR MATES.</span>
              <span className="text-white block">ONE PROJECT.</span>
              <span className="text-[#FF5A00] block">PROPER BURGERS.</span>
            </h1>
          </div>
        </div>
      </section>

      {/* ========================================================================= */}
      {/* MAIN CONTENT: Full Desktop Container */}
      {/* ========================================================================= */}
      <div className="w-full max-w-[1360px] mx-auto px-6 sm:px-10 lg:px-12 pt-10 sm:pt-14">
        
        {/* Two-Column Grid: Left Story (7 cols) / Right Brand Principles (5 cols) */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 xl:gap-24 items-start">
          
          {/* ========================================================================= */}
          {/* LEFT COLUMN: Authentic Brand Story */}
          {/* ========================================================================= */}
          <div className="lg:col-span-7 space-y-6 text-sm sm:text-base lg:text-[16px] text-[#A1A1A1] leading-[1.8] max-w-[850px]">
            <p>
              <span className="text-[#FF5A00] font-semibold">Patty Project</span> started with four mates, years of experience in London's kitchens, and one shared idea — to build something of our own.
            </p>

            <p>
              Having worked across different kitchens in London, from cooking on the line to supervising busy services and leading teams, we've experienced first-hand what goes into running a good kitchen. Along the way, we learnt that great food doesn't need to be complicated. It needs quality ingredients, proper preparation, bold flavours and consistency.
            </p>

            <p>
              So we decided to put that experience into our own project.
            </p>

            <p className="text-white font-bold text-base sm:text-lg">
              <span className="text-[#FF5A00]">Patty Project.</span>
            </p>

            <p>
              Starting in Edmonton, North London, we're focused on the food we love — proper burgers, crispy chicken, loaded fries, wings and sides made for people who appreciate big flavours and good food.
            </p>

            <p>
              London has played a huge part in our story. Its kitchens brought the four of us together, gave us experience and introduced us to different people, cultures, flavours and ways of cooking. Patty Project takes that experience and puts our own stamp on it.
            </p>

            <p>
              We're an independent business built by four mates who have spent years working in other people's kitchens.
            </p>

            <div className="space-y-1 pt-1">
              <p className="text-white font-semibold">
                Now, we're building one of our own.
              </p>
              <p className="text-base sm:text-lg font-bold text-[#FF5A00]">
                And Edmonton is where it all begins.
              </p>
            </div>
          </div>

          {/* ========================================================================= */}
          {/* RIGHT COLUMN: 4 Brand Principles with Outline Icons & Vertical Dividers */}
          {/* ========================================================================= */}
          <div className="lg:col-span-5 border-t lg:border-t-0 border-white/[0.08] divide-y divide-white/[0.08]">
            
            {/* 01: FOUR MATES */}
            <div className="py-6 sm:py-7 flex items-center gap-6">
              <div className="text-[#FF5A00] shrink-0">
                <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9 sm:w-10 sm:h-10">
                  <path d="M12 34v-3a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v3" />
                  <circle cx="20" cy="15" r="5" />
                  <path d="M6 34v-2a5 5 0 0 1 4-4.9" />
                  <path d="M34 34v-2a5 5 0 0 0-4-4.9" />
                  <circle cx="10" cy="18" r="3.5" />
                  <circle cx="30" cy="18" r="3.5" />
                </svg>
              </div>

              {/* Vertical subtle divider */}
              <div className="w-[1px] h-12 bg-white/[0.08] shrink-0" />

              <div className="space-y-1">
                <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-white">
                  FOUR MATES
                </h3>
                <p className="text-xs sm:text-sm text-[#A1A1A1] leading-relaxed">
                  Different strengths, same passion for proper food.
                </p>
              </div>
            </div>

            {/* 02: YEARS OF EXPERIENCE */}
            <div className="py-6 sm:py-7 flex items-center gap-6">
              <div className="text-[#FF5A00] shrink-0">
                <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9 sm:w-10 sm:h-10">
                  <path d="M10 24a7 7 0 0 1 2.5-13.5 7.5 7.5 0 0 1 15 0A7 7 0 0 1 30 24v8H10v-8z" />
                  <line x1="10" y1="28" x2="30" y2="28" />
                </svg>
              </div>

              {/* Vertical subtle divider */}
              <div className="w-[1px] h-12 bg-white/[0.08] shrink-0" />

              <div className="space-y-1">
                <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-white">
                  YEARS OF EXPERIENCE
                </h3>
                <p className="text-xs sm:text-sm text-[#A1A1A1] leading-relaxed">
                  From kitchen hands to team leaders — we've done it all.
                </p>
              </div>
            </div>

            {/* 03: ROOTED IN LONDON */}
            <div className="py-6 sm:py-7 flex items-center gap-6">
              <div className="text-[#FF5A00] shrink-0">
                <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9 sm:w-10 sm:h-10">
                  <path d="M20 35s-10-8.889-10-16.667a10 10 0 0 1 20 0C30 26.111 20 35 20 35z" />
                  <circle cx="20" cy="18.333" r="4.167" />
                </svg>
              </div>

              {/* Vertical subtle divider */}
              <div className="w-[1px] h-12 bg-white/[0.08] shrink-0" />

              <div className="space-y-1">
                <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-white">
                  ROOTED IN LONDON
                </h3>
                <p className="text-xs sm:text-sm text-[#A1A1A1] leading-relaxed">
                  London's kitchens shaped our journey and our flavour.
                </p>
              </div>
            </div>

            {/* 04: PROPER FOOD */}
            <div className="py-6 sm:py-7 flex items-center gap-6">
              <div className="text-[#FF5A00] shrink-0">
                <svg viewBox="0 0 40 40" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" className="w-9 h-9 sm:w-10 sm:h-10">
                  <path d="M7 19a13 13 0 0 1 26 0H7z" />
                  <rect x="5" y="23" width="30" height="3" rx="1.5" />
                  <path d="M7 29a4 4 0 0 0 4 4h18a4 4 0 0 0 4-4H7z" />
                </svg>
              </div>

              {/* Vertical subtle divider */}
              <div className="w-[1px] h-12 bg-white/[0.08] shrink-0" />

              <div className="space-y-1">
                <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-white">
                  PROPER FOOD
                </h3>
                <p className="text-xs sm:text-sm text-[#A1A1A1] leading-relaxed">
                  Quality ingredients. Proper prep. Bold flavours.
                </p>
              </div>
            </div>

          </div>

        </section>

        {/* ========================================================================= */}
        {/* FOOTER SIGNATURE: Minimal Clean Lockup */}
        {/* ========================================================================= */}
        <footer className="mt-16 sm:mt-20 pt-8 border-t border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <h2 className="text-base sm:text-lg font-black uppercase tracking-[0.2em] text-white font-hero">
              PATTY PROJECT
            </h2>
            <p className="text-xs sm:text-sm text-[#FF5A00] font-medium">
              Four mates. One project. Proper food.
            </p>
          </div>

          <div className="text-xs text-[#A1A1A1]">
            A <span className="text-[#FF5A00] font-semibold">Foody Chefs Ltd</span> Brand
          </div>
        </footer>

      </div>
    </div>
  );
};

export default CustomerAbout;
