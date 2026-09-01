import React, { useState } from 'react';
import { X, MapPin, Search, Navigation, Clock, AlertTriangle, ShoppingBag, RotateCcw } from 'lucide-react';
import { api } from '../../api/client';
import { useCartStore } from '../../store/cartStore';
import { Branch } from '../../types';

interface Props {
  onClose: () => void;
}

export const LocationModal: React.FC<Props> = ({ onClose }) => {
  const [useCurrentLocation, setUseCurrentLocation] = useState(false);
  const [postcode, setPostcode] = useState('');
  const [loading, setLoading] = useState(false);
  const [resultBranch, setResultBranch] = useState<Branch | null>(null);
  const [nearestBranch, setNearestBranch] = useState<Branch | null>(null);
  const [distanceMiles, setDistanceMiles] = useState<number | null>(null);
  const [isDeliveryEligible, setIsDeliveryEligible] = useState<boolean>(false);
  const [errorTitle, setErrorTitle] = useState<string>('');
  const [errorDetails, setErrorDetails] = useState<string>('');
  const [canRetry, setCanRetry] = useState<boolean>(false);
  const [msg, setMsg] = useState('');
  const [userCoords, setUserCoordsState] = useState<{ lat: number; lng: number; accuracy?: number } | null>(null);
  const requestIdRef = React.useRef<number>(0);

  const { setSelectedBranch, setOrderType } = useCartStore();

  const handleGeocode = async (lat?: number, lng?: number, pc?: string, accuracy?: number) => {
    const currentRequestId = ++requestIdRef.current;
    setLoading(true);
    setMsg('');
    setErrorTitle('');
    setErrorDetails('');
    setCanRetry(false);

    if (lat !== undefined && lng !== undefined) {
      setUserCoordsState({ lat, lng, accuracy });
    }

    try {
      const res: any = await api.post('/branches/nearest', {
        latitude: lat,
        longitude: lng,
        postcode: pc
      });

      if (currentRequestId !== requestIdRef.current) return;

      const eligible = Boolean(res.is_delivery_eligible ?? (res.assigned_branch && res.distance_miles !== null && res.distance_miles <= 2.0));
      const effectiveNearest = res.nearest_branch || res.assigned_branch || null;

      setIsDeliveryEligible(eligible);
      setDistanceMiles(res.distance_miles ?? null);
      setResultBranch(res.assigned_branch || null);
      setNearestBranch(effectiveNearest);

      if (eligible && res.assigned_branch) {
        setMsg('');
      } else {
        setMsg('WE PROVIDE DELIVERY UP TO 2 MILES ONLY');
      }
    } catch {
      if (currentRequestId !== requestIdRef.current) return;
      setIsDeliveryEligible(false);
      setErrorTitle('Unable to verify delivery availability.');
      setErrorDetails('Please search with your UK postcode or select Collection.');
    } finally {
      if (currentRequestId === requestIdRef.current) {
        setLoading(false);
      }
    }
  };

  const handleToggleLocation = (checked: boolean) => {
    setUseCurrentLocation(checked);
    if (!checked) {
      setUserCoordsState(null);
      setIsDeliveryEligible(false);
      setErrorTitle('');
      setErrorDetails('');
      return;
    }

    if (!('geolocation' in navigator)) {
      setUseCurrentLocation(false);
      setErrorTitle('Geolocation is not supported by your browser.');
      setErrorDetails('Please enter your UK postcode below or select Collection.');
      setCanRetry(false);
      return;
    }

    setLoading(true);
    setErrorTitle('');
    setErrorDetails('');
    setCanRetry(false);

    const geoOptions: PositionOptions = {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 30000
    };

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude;
        const lng = pos.coords.longitude;
        const accuracy = pos.coords.accuracy;

        // Bounds validation
        if (lat === undefined || lng === undefined || isNaN(lat) || isNaN(lng) || lat < -90 || lat > 90 || lng < -180 || lng > 180) {
          setLoading(false);
          setUseCurrentLocation(false);
          setErrorTitle('Invalid coordinates received.');
          setErrorDetails('Please enter your UK postcode or select Collection.');
          setCanRetry(false);
          return;
        }

        // Accuracy check (> 5km)
        if (accuracy && accuracy > 5000) {
          setLoading(false);
          setUseCurrentLocation(false);
          setErrorTitle('Location accuracy is too low to verify 2-mile delivery radius.');
          setErrorDetails(`Device accuracy is ±${Math.round(accuracy / 1000)} km. Please enter your UK postcode.`);
          setCanRetry(false);
          return;
        }

        handleGeocode(lat, lng, undefined, accuracy);
      },
      (error) => {
        setLoading(false);
        setUseCurrentLocation(false);
        setIsDeliveryEligible(false);

        switch (error.code) {
          case 1: // PERMISSION_DENIED
            setErrorTitle('Location access is required to check delivery availability.');
            setErrorDetails('Please enable location access in your browser settings, or choose Collection from your nearest store.');
            setCanRetry(false);
            break;
          case 2: // POSITION_UNAVAILABLE
            setErrorTitle('Unable to determine your device location.');
            setErrorDetails('GPS coordinates could not be determined. Please search with your postcode below or select Collection.');
            setCanRetry(true);
            break;
          case 3: // TIMEOUT
            setErrorTitle('Location request timed out.');
            setErrorDetails('The location check took too long to respond. Tap Retry or enter your postcode manually.');
            setCanRetry(true);
            break;
          default:
            setErrorTitle('Location access error.');
            setErrorDetails('Please enter your UK postcode below or select Collection.');
            setCanRetry(true);
            break;
        }
      },
      geoOptions
    );
  };

  const handleConfirmDelivery = () => {
    if (resultBranch && isDeliveryEligible && distanceMiles !== null && distanceMiles <= 2.0) {
      setSelectedBranch(resultBranch, distanceMiles, true, nearestBranch, null, userCoords, postcode);
      setOrderType('DELIVERY');
      onClose();
    }
  };

  const handleConfirmCollection = (branchToUse?: Branch | null) => {
    const targetBranch = branchToUse || nearestBranch || resultBranch;
    if (targetBranch) {
      setSelectedBranch(targetBranch, distanceMiles, false, targetBranch, 'WE PROVIDE DELIVERY UP TO 2 MILES ONLY', userCoords, postcode);
      setOrderType('COLLECTION');
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#121212] border border-[#262626] rounded-2xl w-full max-w-md p-6 shadow-2xl relative space-y-5 text-white">
        {/* Header */}
        <div className="flex flex-col items-center text-center relative">
          <img
            src="/logo.webp"
            alt="Patty Project"
            loading="lazy"
            decoding="async"
            onError={(e) => { (e.currentTarget as HTMLImageElement).src = '/logo.png'; }}
            className="w-14 h-14 object-contain mb-2"
          />
          <h2 className="text-xl font-bold text-white">Select location</h2>
          <p className="text-xs text-[#9CA3AF] mt-0.5">Find nearest store & check delivery availability.</p>
          <button onClick={onClose} className="absolute top-0 right-0 p-1 text-[#9CA3AF] hover:text-white cursor-pointer">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Current Location Toggle Card */}
        <div className="bg-[#1A1A1A] border border-[#262626] p-4 rounded-xl flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center border shrink-0 ${
              useCurrentLocation ? 'bg-[#FF5500]/10 border-[#FF5500]/30 text-[#FF5500]' : 'bg-[#151515] border-[#262626] text-[#A1A1AA]'
            }`}>
              <MapPin className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-bold text-white">Use your current location</p>
              <p className="text-[10px] text-[#9CA3AF]">Allow location access to check 2-mile delivery radius</p>
            </div>
          </div>
          <input
            type="checkbox"
            checked={useCurrentLocation}
            onChange={(e) => handleToggleLocation(e.target.checked)}
            disabled={loading}
            className="w-5 h-5 rounded bg-[#121212] border-[#262626] accent-[#FF5500] cursor-pointer"
          />
        </div>

        {/* Divider */}
        <div className="relative text-center">
          <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#262626]"></div></div>
          <span className="relative bg-[#121212] px-3 text-[10px] text-[#6B7280] uppercase tracking-wider font-bold">OR</span>
        </div>

        {/* Postcode Search Bar */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3 top-3 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Enter your location / UK Postcode"
              value={postcode}
              onChange={(e) => setPostcode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleGeocode(undefined, undefined, postcode);
              }}
              className="w-full bg-[#1A1A1A] border border-[#262626] rounded-xl py-2.5 pl-9 pr-3 text-xs text-white placeholder-[#6B7280] focus:outline-none focus:border-[#FF5500]"
            />
          </div>
          <button
            onClick={() => handleGeocode(undefined, undefined, postcode)}
            disabled={loading}
            className="bg-[#1A1A1A] border border-[#262626] p-2.5 rounded-xl text-[#FF5500] hover:bg-[#262626] cursor-pointer disabled:opacity-50"
          >
            <Navigation className="w-4 h-4" />
          </button>
        </div>

        {/* Location Error / Denial Banner */}
        {errorTitle && (
          <div className="bg-[#2A1215] border border-[#EF4444]/40 p-4 rounded-xl text-xs space-y-1.5">
            <p className="font-bold text-[#EF4444] flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorTitle}</span>
            </p>
            {errorDetails && (
              <p className="text-[#FCA5A5] text-[11px] leading-relaxed">
                {errorDetails}
              </p>
            )}
            {canRetry && (
              <div className="pt-1 flex justify-end">
                <button
                  onClick={() => handleToggleLocation(true)}
                  className="px-2.5 py-1 bg-[#EF4444]/20 hover:bg-[#EF4444]/30 border border-[#EF4444]/40 text-[#FCA5A5] rounded text-[10px] font-bold flex items-center gap-1 cursor-pointer"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Retry</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Outside 2-Mile Delivery Radius Warning Banner */}
        {!isDeliveryEligible && nearestBranch && !errorTitle && (
          <div className="bg-[#241209] border border-[#6B2A0D] p-4 rounded-xl space-y-2 text-xs">
            <div className="flex items-center gap-2 text-[#FF5500] font-extrabold tracking-wide uppercase text-[11px]">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>WE PROVIDE DELIVERY UP TO 2 MILES ONLY</span>
            </div>
            <p className="text-[#D1D5DB] text-[11px]">
              Please collect your food from the nearest store.
            </p>

            <div className="pt-2 border-t border-[#6B2A0D]/50 flex items-center justify-between">
              <div>
                <p className="text-[10px] text-[#A1A1AA] uppercase font-semibold">Nearest store:</p>
                <p className="text-xs font-bold text-white">Patty Project — {nearestBranch.name}</p>
                {distanceMiles !== null && (
                  <p className="text-[10px] text-[#FF5500] font-semibold">{distanceMiles} miles away</p>
                )}
              </div>

              <button
                onClick={() => handleConfirmCollection(nearestBranch)}
                className="px-3 py-2 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-md"
              >
                <ShoppingBag className="w-3.5 h-3.5" />
                <span>COLLECT FROM THIS STORE</span>
              </button>
            </div>
          </div>
        )}

        {/* Eligible Delivery Branch Result Card */}
        {isDeliveryEligible && resultBranch && (
          <div className="bg-[#1A1A1A] border border-[#22C55E]/40 p-4 rounded-xl space-y-3 shadow-lg">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-[#22C55E]/10 text-[#22C55E] font-bold text-sm flex items-center justify-center border border-[#22C55E]/30 shrink-0">
                  {resultBranch.code}
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white">{resultBranch.name}</h4>
                  <p className="text-[10px] text-[#9CA3AF]">{resultBranch.address_line1}, {resultBranch.postcode}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs font-bold text-[#22C55E]">{distanceMiles || 1.2} miles</p>
                <p className="text-[10px] text-[#22C55E] font-semibold">Delivery Available ✓</p>
              </div>
            </div>

            <div className="pt-2 border-t border-[#262626] flex items-center justify-between text-xs">
              <span className="flex items-center gap-1 text-[#22C55E] font-semibold text-[11px]">
                <Clock className="w-3.5 h-3.5" /> Open Now (10:00 AM - 11:00 PM)
              </span>
            </div>

            <button
              onClick={handleConfirmDelivery}
              className="w-full mt-2 bg-[#FF5500] hover:bg-[#E04B00] text-white font-bold py-3 rounded-xl transition-all shadow-lg flex items-center justify-center gap-2 cursor-pointer"
            >
              <MapPin className="w-4 h-4" />
              <span>Confirm Delivery Location &gt;</span>
            </button>
          </div>
        )}

        {/* Non-eligible general message */}
        {msg && !errorTitle && !resultBranch && !nearestBranch && (
          <p className="text-xs text-center text-[#FF5500] font-semibold">{msg}</p>
        )}
      </div>
    </div>
  );
};
