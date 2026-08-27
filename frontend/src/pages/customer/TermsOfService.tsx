import React from 'react';

export const TermsOfService: React.FC = () => {
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
              Terms of Service
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
              PATTY PROJECT TERMS OF SERVICE
            </span>
            <span className="text-[13px] text-[#71717A] font-medium">
              A Foody Chefs Ltd Brand
            </span>
          </div>

          <div className="space-y-4 text-[15.5px] sm:text-[16.5px] text-[#D4D4D8] leading-[1.8]">
            <p>
              These Terms of Service (“Terms”) apply to the use of the Patty Project website and to orders placed through our website.
            </p>
            <p>
              Patty Project is operated by Foody Chefs Ltd, a company registered in England and Wales (“we”, “us”, “our”).
            </p>
            <p>
              By using our website, creating an account, joining our loyalty programme, or placing an order, you agree to these Terms.
            </p>
          </div>
        </div>

        {/* Legal Sections (Exact Verbatim Text from Document (2).pdf) */}
        <div className="space-y-10 sm:space-y-12 text-left">

          {/* 1. About Us */}
          <section id="section-1" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">1.</span> About Us
            </h2>
            <div className="space-y-3 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8] bg-[#0E0E0E] p-6 rounded-xl border border-white/[0.06]">
              <p><strong className="text-white">Trading name:</strong> Patty Project</p>
              <p><strong className="text-white">Company:</strong> Foody Chefs Ltd</p>
              <p><strong className="text-white">Registered address:</strong> 124–128 City Road, London, EC1V 2NX</p>
              <p>
                <strong className="text-white">Email:</strong>{' '}
                <a href="mailto:hellofoodychefs@gmail.com" className="text-[#FF5500] hover:underline">
                  hellofoodychefs@gmail.com
                </a>
              </p>
              <p className="pt-2 text-white">Our food business operates in Edmonton, London.</p>
            </div>
          </section>

          {/* 2. Using Our Website */}
          <section id="section-2" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">2.</span> Using Our Website
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>You may use our website to:</p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Browse our menu and prices.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Place orders for collection or delivery where available.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Create and manage a customer account.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Earn and redeem Patty Project loyalty points.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Use valid promotional codes or vouchers.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>View previous orders and saved account information.</span>
                </li>
              </ul>
              <p className="pt-2">
                You must provide accurate and complete information when placing an order or creating an account.
              </p>
              <p>
                You are responsible for keeping your account login details secure.
              </p>
            </div>
          </section>

          {/* 3. Orders */}
          <section id="section-3" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">3.</span> Orders
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                When you place an order, you are making an offer to purchase the selected products from us.
              </p>
              <p>
                An order is accepted once we provide confirmation that it has been accepted.
              </p>
              <p>
                We reserve the right to reject or cancel an order where reasonably necessary, including where:
              </p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>An item is unavailable.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>We cannot fulfil the order.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>The delivery address is outside our delivery area.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Payment has not been successfully authorised.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>There is an obvious pricing or website error.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>We reasonably suspect fraudulent or abusive activity.</span>
                </li>
              </ul>
              <p className="pt-2">
                If we cancel an order after payment has been taken, any amount due back to you will be refunded to the original payment method, subject to our Refund and Cancellation Policy.
              </p>
            </div>
          </section>

          {/* 4. Menu, Prices and Availability */}
          <section id="section-4" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">4.</span> Menu, Prices and Availability
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Menu items, ingredients, availability and prices may change from time to time.
              </p>
              <p>
                Prices shown at checkout will be the prices applicable to your order, subject to correction of obvious errors.
              </p>
              <p>
                Where VAT is applicable, prices displayed to consumers will include VAT unless clearly stated otherwise.
              </p>
              <p>
                We may temporarily remove products or mark them unavailable when they are out of stock.
              </p>
              <p>
                Images of food on our website are for presentation purposes. The appearance of the actual product may vary.
              </p>
            </div>
          </section>

          {/* 5. Allergies and Dietary Requirements */}
          <section id="section-5" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">5.</span> Allergies and Dietary Requirements
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Our kitchen handles a range of ingredients and allergens.
              </p>
              <div className="bg-[#1A0A00] border-l-4 border-[#FF5500] p-4 rounded-r-xl">
                <p className="text-white">
                  If you have a food allergy, intolerance or specific dietary requirement, <strong className="text-[#FF5500]">please contact us before ordering</strong> and inform our team of your requirements.
                </p>
              </div>
              <p>
                Although we take reasonable precautions, we cannot guarantee that any product will be completely free from traces of allergens where cross-contact is possible.
              </p>
              <p>
                Customers with serious allergies should not rely solely on menu descriptions or website filters when deciding whether a product is suitable.
              </p>
            </div>
          </section>

          {/* 6. Collection Orders */}
          <section id="section-6" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">6.</span> Collection Orders
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Customers must select an available collection option when ordering.
              </p>
              <p>
                Collection times provided through the website are estimates unless expressly confirmed otherwise.
              </p>
              <p>
                During busy periods, preparation may take longer than the estimated time.
              </p>
              <p>
                Customers should collect their food as close as reasonably possible to the confirmed collection time.
              </p>
            </div>
          </section>

          {/* 7. Delivery Orders */}
          <section id="section-7" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">7.</span> Delivery Orders
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Delivery is available only to eligible addresses within our current delivery area.
              </p>
              <p>
                The website may use the delivery address or postcode supplied by you to determine whether delivery is available.
              </p>
              <p>
                Delivery times are estimates and may be affected by traffic, weather, order volumes and circumstances outside our reasonable control.
              </p>
              <p>You are responsible for:</p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Providing the correct delivery address.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Providing accurate contact information.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Being available to receive the order.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Providing any necessary access or delivery instructions.</span>
                </li>
              </ul>
              <p className="pt-2">
                We are not responsible for delays or failed delivery caused by incorrect information supplied by the customer or where reasonable attempts to deliver the order are unsuccessful.
              </p>
            </div>
          </section>

          {/* 8. Payments */}
          <section id="section-8" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">8.</span> Payments
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Available payment methods will be displayed during checkout.
              </p>
              <p>
                Payment must be successfully authorised before an order can be processed unless another payment arrangement is expressly offered.
              </p>
              <p>
                Payments may be processed by third-party payment providers. Their own terms and privacy practices may also apply to the processing of your payment information.
              </p>
              <p>
                We do not intentionally store complete payment card details on our own systems where payments are securely processed by our payment provider.
              </p>
            </div>
          </section>

          {/* 9. Cancellations and Refunds */}
          <section id="section-9" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">9.</span> Cancellations and Refunds
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Because our products include freshly prepared and perishable food, cancellation rights that normally apply to certain online purchases may not apply in the same way to food orders.
              </p>
              <p>
                If you need to cancel an order, contact us as soon as possible.
              </p>
              <p>
                If preparation has already started, we may be unable to cancel or refund the order.
              </p>
              <p>
                If an order is incorrect, missing items, materially damaged or otherwise not as ordered, please contact us promptly with your order details so that we can investigate.
              </p>
              <p>
                Any refund, replacement or other remedy will be handled in accordance with applicable UK consumer law and our Refund and Cancellation Policy.
              </p>
              <p className="text-white font-medium">
                Nothing in these Terms affects your statutory consumer rights.
              </p>
            </div>
          </section>

          {/* 10. Patty Project Loyalty Programme */}
          <section id="section-10" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">10.</span> Patty Project Loyalty Programme
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Eligible registered customers may earn loyalty points on qualifying purchases.
              </p>
              <p>Our current loyalty structure is:</p>
              <div className="bg-[#111111] p-5 rounded-xl border border-white/[0.08]">
                <p className="text-white font-semibold text-base sm:text-lg">
                  <strong className="text-[#FF5500]">£1 spent = 100 points</strong>, equivalent to a reward value of <strong className="text-[#FF5500]">10% of qualifying spend</strong>, subject to the programme rules displayed on the website.
                </p>
              </div>
              <p>
                Rewards may be redeemed once the applicable minimum redemption threshold is reached. The current base redemption threshold is <strong className="text-white">4,000 points</strong>.
              </p>
              <p>Points:</p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Have no cash value.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Cannot normally be exchanged for cash.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Cannot normally be transferred between accounts.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>May only be earned on qualifying purchases.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>May be subject to exclusions for certain offers, discounts or promotions.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>May be adjusted where an order is cancelled, refunded or found to have earned points incorrectly.</span>
                </li>
              </ul>
              <p className="pt-2">
                We may reasonably amend the loyalty programme, including earning rates, redemption thresholds and available rewards. Where a change materially disadvantages existing customers, we will aim to provide reasonable notice where appropriate.
              </p>
              <p>
                We may suspend or close a loyalty account where there is reasonable evidence of fraud, misuse or manipulation of the programme.
              </p>
            </div>
          </section>

          {/* 11. Promotional Codes and Vouchers */}
          <section id="section-11" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">11.</span> Promotional Codes and Vouchers
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Promotional codes and vouchers are subject to any specific conditions stated when they are issued.
              </p>
              <p>Unless otherwise stated:</p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>They cannot be exchanged for cash.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>They cannot be applied retrospectively.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Only one promotional code may be used per order.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>They may have expiry dates or minimum-spend requirements.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Certain menu items may be excluded.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>They may not be combined with other promotions.</span>
                </li>
              </ul>
              <p className="pt-2">
                We may refuse a voucher or promotional code where it is expired, invalid, used contrary to its conditions, or obtained or used fraudulently.
              </p>
            </div>
          </section>

          {/* 12. Customer Accounts */}
          <section id="section-12" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">12.</span> Customer Accounts
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                You may be able to create a Patty Project account to access features including order history, saved addresses and loyalty rewards.
              </p>
              <p>
                You must provide accurate information and keep your account details up to date.
              </p>
              <p>
                You are responsible for activity carried out through your account where caused by your failure to keep your login credentials reasonably secure.
              </p>
              <p>
                Please contact us promptly if you believe someone has gained unauthorised access to your account.
              </p>
            </div>
          </section>

          {/* 13. Personal Information and Privacy */}
          <section id="section-13" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">13.</span> Personal Information and Privacy
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                We process personal information in accordance with our <strong className="text-white">Privacy Policy</strong> and applicable UK data protection legislation, including the UK GDPR and Data Protection Act 2018.
              </p>
              <p>
                Information may be used to process orders, manage customer accounts, operate our loyalty programme, provide customer service, prevent fraud and fulfil our legal obligations.
              </p>
              <p>
                Marketing communications will be handled in accordance with applicable law and the choices available to you.
              </p>
              <p>
                Please read our Privacy Policy for further information about how personal information is collected, used, stored and protected.
              </p>
            </div>
          </section>

          {/* 14. Website Availability */}
          <section id="section-14" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">14.</span> Website Availability
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                We aim to keep our website available and accurate, but we cannot guarantee uninterrupted or error-free access.
              </p>
              <p>
                We may temporarily suspend or restrict parts of the website for maintenance, security, updates or circumstances outside our reasonable control.
              </p>
            </div>
          </section>

          {/* 15. Intellectual Property */}
          <section id="section-15" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">15.</span> Intellectual Property
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                The Patty Project name, branding, logos, website design, photographs, graphics and original website content belong to Foody Chefs Ltd or are used with appropriate permission.
              </p>
              <p>
                You may not reproduce, commercially exploit or distribute our protected content without permission except where permitted by law.
              </p>
            </div>
          </section>

          {/* 16. Our Responsibility */}
          <section id="section-16" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">16.</span> Our Responsibility
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                Nothing in these Terms excludes or limits liability where doing so would be unlawful, including liability for death or personal injury caused by negligence, fraud or fraudulent misrepresentation.
              </p>
              <p>
                Subject to applicable consumer law, we are not responsible for losses that were not reasonably foreseeable when the contract was formed or for business losses arising from a consumer’s use of our services.
              </p>
              <p className="text-white font-medium">
                Nothing in these Terms limits any rights or remedies that cannot legally be excluded.
              </p>
            </div>
          </section>

          {/* 17. Misuse of the Website */}
          <section id="section-17" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">17.</span> Misuse of the Website
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>You must not:</p>
              <ul className="space-y-2 pl-2">
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Attempt to gain unauthorised access to our website, accounts or systems.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Introduce malicious software or harmful code.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Fraudulently obtain loyalty points, vouchers, discounts or refunds.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Use another person’s account without permission.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="text-[#FF5500] mt-1 text-lg leading-none">•</span>
                  <span>Use the website for unlawful purposes.</span>
                </li>
              </ul>
              <p className="pt-2">
                We may restrict or suspend access where reasonably necessary to protect our customers, business or systems.
              </p>
            </div>
          </section>

          {/* 18. Changes to These Terms */}
          <section id="section-18" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">18.</span> Changes to These Terms
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                We may update these Terms from time to time to reflect changes to our services, website, loyalty programme or legal requirements.
              </p>
              <p>
                The latest version will be published on our website with the updated effective date.
              </p>
              <p>
                The Terms applicable to an individual order will generally be those in force when that order was placed.
              </p>
            </div>
          </section>

          {/* 19. Governing Law */}
          <section id="section-19" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">19.</span> Governing Law
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                These Terms are governed by the laws of England and Wales.
              </p>
              <p>
                If you are a consumer, you may also have rights to bring proceedings in the part of the United Kingdom where you live where applicable.
              </p>
            </div>
          </section>

          {/* 20. Contact Us */}
          <section id="section-20" className="scroll-mt-28">
            <h2 className="text-xl sm:text-2xl font-black text-white uppercase tracking-tight mb-4 flex items-center gap-3">
              <span className="text-[#FF5500]">20.</span> Contact Us
            </h2>
            <div className="space-y-4 text-[15px] sm:text-[16px] text-[#D4D4D8] leading-[1.8]">
              <p>
                For questions about these Terms, an order, your account or the Patty Project loyalty programme, contact:
              </p>
              <div className="bg-[#0E0E0E] p-6 rounded-xl border border-white/[0.06] space-y-2 mt-3">
                <p className="font-bold text-white text-base">Foody Chefs Ltd – Patty Project</p>
                <p className="text-[#D4D4D8]">124–128 City Road</p>
                <p className="text-[#D4D4D8]">London</p>
                <p className="text-[#D4D4D8]">EC1V 2NX</p>
                <p className="pt-2">
                  <strong className="text-white">Email:</strong>{' '}
                  <a href="mailto:hellofoodychefs@gmail.com" className="text-[#FF5500] hover:underline">
                    hellofoodychefs@gmail.com
                  </a>
                </p>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
};
export default TermsOfService;
