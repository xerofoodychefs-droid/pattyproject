import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { api } from '../../api/client';

export const CustomerContact: React.FC = () => {
  const { user } = useAuthStore();

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      const parts = user.full_name ? user.full_name.split(' ') : ['', ''];
      setFirstName(parts[0] || '');
      setLastName(parts.slice(1).join(' ') || '');
      setEmail(user.email || '');
    }
  }, [user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;

    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await api.post('/contact', {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim(),
        subject: subject.trim(),
        message: message.trim(),
      });

      setSubmitted(true);
      setSubject('');
      setMessage('');
      if (!user) {
        setFirstName('');
        setLastName('');
        setEmail('');
      }
    } catch (err: any) {
      console.error('[ContactForm] Error submitting contact form:', err);
      const msg = err?.message || 'Unable to send your message. Please try again.';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-70px)] bg-black text-white selection:bg-[#FF5500] selection:text-white relative overflow-hidden flex flex-col justify-between">
      
      {/* Desktop Background Image filling the right half */}
      <div className="absolute top-0 right-0 bottom-0 w-full lg:w-[50%] xl:w-[52%] pointer-events-none z-0 hidden lg:block overflow-hidden">
        <img
          src="/contact_background.jpg"
          alt="Patty Project Restaurant Interior & Bar"
          className="w-full h-full object-cover object-center lg:object-right-top select-none"
        />
        {/* Soft edge gradient to blend seamlessly into solid black left half */}
        <div className="absolute inset-0 bg-gradient-to-r from-black via-black/40 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-transparent to-black/30" />
      </div>

      {/* Mobile Background Image filling the background with dark overlay */}
      <div className="absolute inset-0 pointer-events-none z-0 block lg:hidden overflow-hidden">
        <img
          src="/contact_background.jpg"
          alt="Patty Project Restaurant Interior & Bar"
          className="w-full h-full object-cover object-center select-none brightness-40"
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/80 via-black/85 to-black" />
      </div>

      {/* Main Content Container */}
      <div className="w-full max-w-[1240px] xl:max-w-[1280px] mx-auto px-6 sm:px-8 lg:px-10 py-8 sm:py-12 lg:py-14 relative z-10 flex-1 flex items-center">
        
        <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 xl:gap-12 items-center">
          
          {/* ========================================================================= */}
          {/* LEFT COLUMN: Contact Header, Info & Form */}
          {/* ========================================================================= */}
          <div className="lg:col-span-6 xl:col-span-6 space-y-5 max-w-lg">
            
            {/* Header Info */}
            <div className="space-y-2.5">
              <div>
                <span className="text-[11px] font-black uppercase tracking-[0.2em] text-[#FF5500] block">
                  CONTACT US
                </span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-[46px] font-black uppercase text-white tracking-tight font-hero leading-[0.94] pt-1">
                GET IN TOUCH
              </h1>

              <p className="text-sm sm:text-base text-[#A1A1A1] leading-relaxed">
                We'd love to hear from you. Whether it's a question, feedback or a custom request — drop us a message.
              </p>

              {/* Location notice matching screenshot */}
              <div className="flex items-start gap-2 text-sm text-white pt-1">
                <MapPin className="w-4 h-4 text-[#FF5500] shrink-0 mt-1" />
                <p className="leading-relaxed text-sm">
                  Find our{' '}
                  <Link to="/select-location" className="text-[#FF5500] font-bold hover:underline">
                    store locations here
                  </Link>
                  .<br />
                  We're excited to welcome you to{' '}
                  <span className="text-[#FF5500] font-bold">Patty Project</span>.
                </p>
              </div>
            </div>

            {/* Contact Form */}
            {submitted ? (
              <div className="p-6 bg-[#111111] border border-[#FF5500]/50 rounded-xl space-y-4 animate-fadeIn">
                <div className="flex items-center gap-2.5 text-[#FF5500]">
                  <CheckCircle2 className="w-5 h-5" />
                  <h3 className="text-base font-black text-white uppercase font-hero tracking-wide">
                    Message Submitted!
                  </h3>
                </div>
                <p className="text-xs sm:text-sm text-[#A1A1A1] leading-relaxed">
                  Thank you for reaching out to Patty Project. Your message has been sent to our team and we will get back to you shortly.
                </p>
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() => setSubmitted(false)}
                    className="text-xs font-bold text-[#FF5500] hover:text-[#FFAA00] uppercase tracking-wider underline cursor-pointer transition-colors"
                  >
                    Send another message
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Error Banner */}
                {errorMessage && (
                  <div className="p-4 bg-red-950/40 border border-red-500/40 rounded-xl text-xs sm:text-sm text-red-200 flex items-start gap-2.5 animate-fadeIn">
                    <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
                    <p className="leading-relaxed">{errorMessage}</p>
                  </div>
                )}

                {/* Row 1: First Name & Last Name */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                  <div className="space-y-1.5">
                    <label className="block text-[11px] font-extrabold uppercase tracking-wider text-white">
                      FIRST NAME <span className="text-neutral-500 font-normal lowercase">(required)</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Your first name"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      disabled={isSubmitting}
                      className="w-full h-[48px] bg-[#0E0E0E] border border-[#262626] focus:border-[#FF5500] rounded-lg px-4 text-sm text-white placeholder:text-[#555555] focus:outline-none transition-colors disabled:opacity-60"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-[11px] font-extrabold uppercase tracking-wider text-white">
                      LAST NAME <span className="text-neutral-500 font-normal lowercase">(required)</span>
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="Your last name"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      disabled={isSubmitting}
                      className="w-full h-[48px] bg-[#0E0E0E] border border-[#262626] focus:border-[#FF5500] rounded-lg px-4 text-sm text-white placeholder:text-[#555555] focus:outline-none transition-colors disabled:opacity-60"
                    />
                  </div>
                </div>

                {/* Row 2: Email */}
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-extrabold uppercase tracking-wider text-white">
                    EMAIL <span className="text-neutral-500 font-normal lowercase">(required)</span>
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="Your email address"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full h-[48px] bg-[#0E0E0E] border border-[#262626] focus:border-[#FF5500] rounded-lg px-4 text-sm text-white placeholder:text-[#555555] focus:outline-none transition-colors disabled:opacity-60"
                  />
                </div>

                {/* Row 3: Subject */}
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-extrabold uppercase tracking-wider text-white">
                    SUBJECT <span className="text-neutral-500 font-normal lowercase">(required)</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="What's this about?"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full h-[48px] bg-[#0E0E0E] border border-[#262626] focus:border-[#FF5500] rounded-lg px-4 text-sm text-white placeholder:text-[#555555] focus:outline-none transition-colors disabled:opacity-60"
                  />
                </div>

                {/* Row 4: Message */}
                <div className="space-y-1.5">
                  <label className="block text-[11px] font-extrabold uppercase tracking-wider text-white">
                    MESSAGE <span className="text-neutral-500 font-normal lowercase">(required)</span>
                  </label>
                  <textarea
                    rows={4}
                    required
                    placeholder="Write your message here..."
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    disabled={isSubmitting}
                    className="w-full h-[120px] bg-[#0E0E0E] border border-[#262626] focus:border-[#FF5500] rounded-lg p-4 text-sm text-white placeholder:text-[#555555] focus:outline-none transition-colors resize-none disabled:opacity-60"
                  />
                </div>

                {/* Row 5: Submit Button matching screenshot */}
                <div className="pt-2 flex items-center gap-4">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="bg-[#FF5500] hover:bg-[#E04B00] disabled:opacity-50 disabled:cursor-not-allowed text-white px-8 py-3.5 rounded-lg text-xs font-black uppercase tracking-wider transition-all active:scale-95 shadow-lg shadow-[#FF5500]/25 cursor-pointer flex items-center gap-2"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin text-white" />
                        <span>SENDING...</span>
                      </>
                    ) : (
                      <span>SUBMIT MESSAGE</span>
                    )}
                  </button>
                </div>
              </form>
            )}

          </div>
        </div>

      </div>
    </div>
  );
};

export default CustomerContact;
