import React from 'react';

export const RefundCancellationPolicy: React.FC = () => {
  return (
    <div className="w-full bg-[#050505] text-white min-h-screen selection:bg-[#FF5500] selection:text-white">
      {/* ========================================================================= */}
      {/* HERO BANNER WITH OVERLAPPING FLOATING TITLE CARD (Reference Alignment) */}
      {/* ========================================================================= */}
      <div className="relative w-full bg-gradient-to-r from-[#1A0A00] via-[#0D0D0D] to-[#140600] border-b border-white/[0.06] h-[160px] sm:h-[200px] lg:h-[220px] flex items-center justify-center overflow-visible">
        {/* Subtle decorative background pattern / glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(255,85,0,0.25),rgba(255,255,255,0))]" />
        
        {/* Floating Title Card in Black Theme */}
        <div className="absolute bottom-0 translate-y-1/2 z-20 w-full max-w-[1240px] px-6 sm:px-10 lg:px-16 flex justify-start sm:justify-center lg:justify-start">
          <div className="bg-[#111111] text-white shadow-2xl shadow-black/90 rounded-xl sm:rounded-2xl px-8 sm:px-12 lg:px-16 py-6 sm:py-8 border border-white/[0.12] inline-flex flex-col items-start min-w-[280px] sm:min-w-[360px]">
            <h1 className="text-2xl sm:text-3xl lg:text-[38px] font-black text-white tracking-tight leading-tight font-hero">
              Refund &amp; Cancellation Policy
            </h1>
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* MAIN DOCUMENT CONTAINER (Left-Aligned Clean Legal Layout) */}
      {/* ========================================================================= */}
      <div className="w-full max-w-[1240px] mx-auto px-6 sm:px-10 lg:px-16 pt-20 sm:pt-24 lg:pt-28 pb-20">
        
        {/* Header Metadata & Intro */}
        <div className="mb-10 sm:mb-12 pb-8 border-b border-white/[0.08] text-left">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <span className="text-[12px] font-bold tracking-[0.16em] uppercase text-[#FF5500]">
              PATTY PROJECT REFUND &amp; CANCELLATION POLICY
            </span>
            <span className="text-[13px] text-[#71717A] font-medium">
              A Foody Chefs Ltd Brand
            </span>
          </div>

          <p className="text-[15.5px] sm:text-[16.5px] text-[#D4D4D8] leading-[1.8]">
            This policy explains how cancellations, refunds, payment issues, delivery and collection problems, promotional discounts and Patty Points are handled for orders placed with Patty Project.
          </p>
        </div>

        {/* Legal Sections (Exact Verbatim Text from PDF) */}
        <div className="space-y-10 sm:space-y-12 text-left">

          {/* 1. Order Cancellations */}
          <section id="section-1" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">1.</span> Order Cancellations
            </h2>
            <div className="space-y-6 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  Before preparation begins
                </h3>
                <p>
                  Customers may request cancellation as soon as possible after placing an order. Where the order has not yet entered preparation and cancellation is operationally possible, Patty Project may cancel the order and issue a full refund to the original payment method.
                </p>
              </div>

              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  After preparation has started
                </h3>
                <p>
                  Because food is prepared specifically for each order and may be perishable, an order normally cannot be cancelled simply because the customer has changed their mind once preparation has started. This does not limit any statutory rights where goods or services are faulty, not as described, or otherwise legally entitle the customer to a remedy.
                </p>
              </div>

              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  After the order is ready, collected or dispatched
                </h3>
                <p>
                  Cancellation will normally not be available once an order is ready for collection, has been collected, or has been dispatched for delivery, except where a refund or other remedy is appropriate because of an order, food-quality, delivery or payment issue.
                </p>
              </div>
            </div>
          </section>

          {/* 2. Refund Eligibility */}
          <section id="section-2" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">2.</span> Refund Eligibility
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                A full or partial refund may be considered where appropriate, including situations such as:
              </p>
              <ul className="space-y-2 pl-5 list-disc marker:text-[#FF5500] text-[#D4D4D8]">
                <li>An incorrect item was supplied.</li>
                <li>A paid item is missing from the order.</li>
                <li>The order was not received.</li>
                <li>The order was cancelled by Patty Project.</li>
                <li>There is a genuine and significant food-quality or preparation issue.</li>
                <li>The customer was charged more than once for the same order.</li>
                <li>Payment was successfully captured but the corresponding order was not created or could not be fulfilled.</li>
                <li>Another verified order or payment issue reasonably requires a full or partial refund.</li>
              </ul>
            </div>
          </section>

          {/* 3. Full and Partial Refunds */}
          <section id="section-3" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">3.</span> Full and Partial Refunds
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Where the entire order is affected, a full refund may be issued. Where only part of an order is affected, Patty Project may issue a partial refund for the affected item(s) or amount. The appropriate remedy will depend on the circumstances of the order and the customer&apos;s statutory rights.
              </p>
            </div>
          </section>

          {/* 4. Payment Issues */}
          <section id="section-4" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">4.</span> Payment Issues
            </h2>
            <div className="space-y-6 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  Payment taken but no order confirmation
                </h3>
                <p>
                  If a customer believes payment has been taken but no order has been confirmed, the payment and order records should be checked before another payment is made. Where Patty Project has successfully captured payment but cannot fulfil the order, the appropriate refund will be issued.
                </p>
              </div>

              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  Pending or failed payments
                </h3>
                <p>
                  A transaction shown as pending by a bank or payment provider does not always mean that Patty Project has received the funds. Failed or incomplete authorisations may be automatically released by the customer&apos;s bank or payment provider. The time taken for a pending amount to disappear is controlled by the relevant bank or payment provider.
                </p>
              </div>

              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  Duplicate payments
                </h3>
                <p>
                  If the same order has genuinely been charged more than once, the duplicate successful charge should be refunded after verification.
                </p>
              </div>

              <div>
                <h3 className="font-bold text-white text-base mb-2">
                  Card, Apple Pay and Google Pay
                </h3>
                <p>
                  Refunds for card, Apple Pay, Google Pay or other supported electronic payment methods will normally be sent back through the original payment method used for the transaction.
                </p>
              </div>
            </div>
          </section>

          {/* 5. Refund Processing */}
          <section id="section-5" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">5.</span> Refund Processing
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Once a refund is approved and initiated by Patty Project, the time it takes to appear in the customer&apos;s account can vary depending on the bank, card issuer, wallet or payment provider. Patty Project cannot control the processing time after a refund has been successfully submitted to the payment provider.
              </p>
            </div>
          </section>

          {/* 6. Delivery Orders */}
          <section id="section-6" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">6.</span> Delivery Orders
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <ul className="space-y-2.5 pl-5 list-disc marker:text-[#FF5500] text-[#D4D4D8]">
                <li>Customers are responsible for providing a complete and accurate delivery address and contact details.</li>
                <li>If delivery cannot be completed because the address supplied is incorrect or incomplete, or the customer cannot reasonably be contacted or found, a refund may not be available for food already prepared.</li>
                <li>Where an order is not delivered because of a failure attributable to Patty Project or its delivery arrangements, the circumstances should be reviewed and an appropriate refund or remedy provided.</li>
                <li>Significant delivery delays should be assessed according to the circumstances, food condition and any applicable consumer rights.</li>
              </ul>
            </div>
          </section>

          {/* 7. Collection Orders */}
          <section id="section-7" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">7.</span> Collection Orders
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Customers should collect their order within the selected or communicated collection period. If a customer does not collect an order after it has been prepared, a refund will normally not be provided solely because the order was not collected. If Patty Project is unable to provide the order as agreed, an appropriate refund or remedy will be considered.
              </p>
            </div>
          </section>

          {/* 8. Food Quality, Incorrect or Missing Items */}
          <section id="section-8" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">8.</span> Food Quality, Incorrect or Missing Items
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Customers should report significant food-quality issues, incorrect items or missing items as soon as reasonably possible. Patty Project may request the order number, details of the affected item and, where reasonable and relevant, photographs to help assess the issue. This information is used to investigate the complaint and determine the appropriate remedy.
              </p>
            </div>
          </section>

          {/* 9. Situations Where a Refund May Not Be Available */}
          <section id="section-9" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">9.</span> Situations Where a Refund May Not Be Available
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Subject always to the customer&apos;s statutory rights, a refund may not normally be available where:
              </p>
              <ul className="space-y-2.5 pl-5 list-disc marker:text-[#FF5500] text-[#D4D4D8]">
                <li>The customer changes their mind after food preparation has begun.</li>
                <li>The customer provides an incorrect delivery address or materially incorrect order information.</li>
                <li>A prepared collection order is not collected.</li>
                <li>The customer ordered the wrong item by mistake and the correct ordered item was supplied.</li>
                <li>The issue results solely from a personal preference rather than the food being faulty, unsafe or materially not as described.</li>
                <li>The claim cannot reasonably be verified and there is no evidence of an order, payment or fulfilment issue.</li>
              </ul>
            </div>
          </section>

          {/* 10. Promotions, Discounts & Promo Codes */}
          <section id="section-10" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">10.</span> Promotions, Discounts &amp; Promo Codes
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Where a refund is issued on an order that used a promotional discount or promo code, the refund should be based on the amount actually paid for the affected item(s), subject to applicable consumer rights. Promo codes and promotional discounts are not normally converted into cash. Whether a promotional code is restored after cancellation may depend on the terms of that promotion.
              </p>
            </div>
          </section>

          {/* 11. Patty Points & Loyalty Rewards */}
          <section id="section-11" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">11.</span> Patty Points &amp; Loyalty Rewards
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Points earned on a fully refunded order should be reversed. For a partial refund, the relevant points should be adjusted according to the eligible refunded amount. Where Patty Points were redeemed on an order that is subsequently cancelled or refunded and restoration is appropriate, the applicable redeemed points should be returned to the customer&apos;s loyalty balance.
              </p>
            </div>
          </section>

          {/* 12. Refund Records */}
          <section id="section-12" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">12.</span> Refund Records
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Refunds and cancellations should be linked to the original order and payment transaction. Records should include the order reference, refund amount, reason, payment status, date and any relevant loyalty or promotional adjustment.
              </p>
            </div>
          </section>

          {/* 13. Customer Contact */}
          <section id="section-13" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">13.</span> Customer Contact
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Customers requesting a cancellation, refund or investigation should provide their order number and enough information to identify the order and explain the issue. Patty Project may request additional reasonable information where needed to investigate a claim.
              </p>
            </div>
          </section>

          {/* 14. Statutory Rights */}
          <section id="section-14" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">14.</span> Statutory Rights
            </h2>
            <div className="space-y-3.5 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Nothing in this policy is intended to exclude, restrict or replace any rights or remedies that customers have under applicable UK consumer law. Where a customer&apos;s statutory rights provide a greater remedy than this policy, those statutory rights will apply.
              </p>
            </div>
          </section>

        </div>

        {/* Footer Document Attribution & Review Notice */}
        <div className="mt-16 pt-8 border-t border-white/[0.08] text-left space-y-4">
          <div>
            <p className="text-base font-bold text-white tracking-wide uppercase">PATTY PROJECT</p>
            <p className="text-sm text-[#FF5500] font-semibold">A Foody Chefs Ltd Brand</p>
          </div>
          <p className="text-xs text-[#71717A] italic leading-relaxed">
            Policy wording should be reviewed before publication to ensure it reflects Patty Project&apos;s final ordering, delivery, payment and operational arrangements.
          </p>
        </div>

      </div>
    </div>
  );
};
