import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, Eye, EyeOff, AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import { api } from '../../api/client';
import { useAuthStore } from '../../store/authStore';

export const AdminLogin: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const { setAuth } = useAuthStore();
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail) {
      setError('Please enter your email address.');
      return;
    }
    if (!password) {
      setError('Please enter your password.');
      return;
    }

    setLoading(true);

    try {
      localStorage.removeItem('patty_token');
      localStorage.removeItem('patty_refresh_token');
      localStorage.removeItem('patty_user');

      const res: any = await api.post('/auth/login', { email: cleanEmail, password });
      
      if (!res || !res.access_token || !res.user) {
        setError('Invalid response received from authentication server.');
        return;
      }

      if (res.user.role !== 'SUPER_ADMIN' && res.user.role !== 'BRANCH_ADMIN') {
        setError('Access denied. Administrator privileges required to access this portal.');
        return;
      }

      setAuth(res.access_token, res.user, res.refresh_token);
      navigate('/dashboard', { replace: true });
    } catch (err: any) {
      const errMsg = err?.detail || err?.message || 'Incorrect email or password.';
      setError(errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen lg:h-screen bg-[#070707] text-white flex flex-col justify-between relative overflow-x-hidden">
      {/* Desktop Right Side Hero Burger Container */}
      <div className="hidden lg:block absolute inset-y-0 right-0 w-[55%] xl:w-[58%] pointer-events-none overflow-hidden z-0">
        <div className="relative w-full h-full">
          <img
            src="/herobackground.png"
            alt="Patty Project Hero Burger"
            className="w-full h-full object-cover object-center select-none"
          />
          {/* Soft Dark Gradient overlays */}
          <div className="absolute inset-0 bg-gradient-to-r from-[#070707] via-[#070707]/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-t from-[#070707]/50 via-transparent to-[#070707]/30" />
        </div>
      </div>

      {/* Main Content Area */}
      <div className="relative z-10 flex-1 flex items-center justify-center lg:w-[50%] xl:w-[48%] lg:pl-[8vw] lg:justify-center px-6 sm:px-12 lg:px-8 py-8 my-auto">
        <div className="w-full max-w-[520px] min-h-[660px] bg-[#121212] border border-[#222222] rounded-2xl p-11 sm:p-14 sm:py-16 shadow-2xl shadow-black/90 my-auto flex flex-col justify-between">
          <div>
            {/* Industry Standard Patty Project Brand Logo */}
            <div className="w-20 h-20 sm:w-24 sm:h-24 mx-auto mb-8 flex items-center justify-center">
              <img
                src="/logo.png"
                alt="Patty Project"
                className="w-full h-full object-contain select-none"
              />
            </div>

            {/* Error Alert Box */}
            {error && (
              <div className="mb-6 bg-[#2A1215] border border-[#EF4444]/40 text-[#FCA5A5] text-xs font-semibold px-4 py-4 rounded-xl flex items-center gap-2.5 animate-fadeIn">
                <AlertCircle className="w-4 h-4 text-[#EF4444] shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* LOGIN FORM */}
            <div className="flex flex-col justify-between flex-1 w-full">
              <div>
                <div>
                  <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight text-center">Admin Login</h1>
                  <p className="text-xs sm:text-sm text-[#9CA3AF] text-center mt-3 leading-relaxed">
                    Welcome back! Please login to your admin account.
                  </p>
                </div>

                <form onSubmit={handleLogin} className="mt-9 space-y-6">
                  {/* Email Address Field */}
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-[#D1D5DB]">Email Address</label>
                    <div className="flex items-center bg-[#181818] border border-[#282828] focus-within:border-[#FF5500] rounded-xl px-4 py-4 transition-colors">
                      <Mail className="w-4 h-4 text-[#FF5500] mr-3 shrink-0" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="admin@pattyproject.co.uk"
                        className="w-full bg-transparent text-xs sm:text-sm text-white placeholder-[#6B7280] focus:outline-none"
                        required
                      />
                    </div>
                  </div>

                  {/* Password Field */}
                  <div className="space-y-2">
                    <label className="block text-xs font-semibold text-[#D1D5DB]">Password</label>
                    <div className="flex items-center bg-[#181818] border border-[#282828] focus-within:border-[#FF5500] rounded-xl px-4 py-4 transition-colors">
                      <Lock className="w-4 h-4 text-[#FF5500] mr-3 shrink-0" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        className="w-full bg-transparent text-xs sm:text-sm text-white placeholder-[#6B7280] focus:outline-none"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="ml-2 text-[#9CA3AF] hover:text-white transition-colors cursor-pointer"
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Remember Me Row */}
                  <div className="flex items-center text-xs pt-2">
                    <label className="flex items-center gap-2 text-[#9CA3AF] font-medium cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={rememberMe}
                        onChange={(e) => setRememberMe(e.target.checked)}
                        className="w-4 h-4 accent-[#FF5500] rounded border-[#282828] bg-[#181818] cursor-pointer"
                      />
                      <span>Remember me</span>
                    </label>
                  </div>

                  {/* Primary Orange Login Button */}
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full mt-7 bg-[#FF5500] hover:bg-[#E04B00] active:scale-[0.99] text-white font-black py-5 px-6 rounded-xl text-base uppercase tracking-widest transition-all shadow-2xl shadow-[#FF5500]/40 hover:shadow-[#FF5500]/60 flex items-center justify-center gap-2.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>LOGGING IN...</span>
                      </>
                    ) : (
                      <span>LOGIN</span>
                    )}
                  </button>
                </form>
              </div>

              {/* Bottom Security / Access Notice */}
              <div className="mt-12 flex items-center justify-center gap-2 text-xs text-[#9CA3AF] font-medium">
                <ShieldCheck className="w-4 h-4 text-[#10B981]" />
                <span>Secure admin access only</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
