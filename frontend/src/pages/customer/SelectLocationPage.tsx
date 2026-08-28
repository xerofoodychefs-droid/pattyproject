import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { MapPin, Search, Navigation, ChevronRight, Store, X, LocateFixed, AlertTriangle, ShoppingBag, RotateCcw, Loader2, Truck } from 'lucide-react';
import { Branch } from '../../types';
import { useCartStore } from '../../store/cartStore';
import { api, setSafeStorage } from '../../api/client';

export type LocationResolutionState =
  | 'IDLE'
  | 'RESOLVING'
  | 'OUTLET_RESOLVED'
  | 'OUTSIDE_RADIUS'
  | 'NO_ELIGIBLE_OUTLET'
  | 'LOCATION_ERROR'
  | 'OUTLET_ERROR';

export const SelectLocationPage: React.FC = () => {
  const navigate = useNavigate();
  const {
    setSelectedBranch,
    selectedBranch: storeBranch,
    setOrderType,
    orderType: storeOrderType,
    userCoords: storeCoords
  } = useCartStore();

  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchesLoading, setBranchesLoading] = useState<boolean>(true);
  const [branchesError, setBranchesError] = useState<string | null>(null);
  
  // Tripartite branch state: recommended, manual override, and active
  const [recommendedBranch, setRecommendedBranch] = useState<Branch | null>(null);
  const [manualOverrideBranch, setManualOverrideBranch] = useState<Branch | null>(storeBranch);
  const [nearestBranch, setNearestBranch] = useState<Branch | null>(null);
  const [distanceMiles, setDistanceMiles] = useState<number | null>(null);
  const [isDeliveryEligible, setIsDeliveryEligible] = useState<boolean>(false);
  const [fulfillmentType, setFulfillmentType] = useState<'DELIVERY' | 'COLLECTION'>(storeOrderType || 'COLLECTION');
  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number; accuracy?: number } | null>(storeCoords);

  // Explicit Location Resolution State Machine
  const [resolutionState, setResolutionState] = useState<LocationResolutionState>(
    storeBranch ? (storeCoords ? 'OUTLET_RESOLVED' : 'IDLE') : 'IDLE'
  );

  // Request cancellation and race condition tracking (latest request wins)
  const requestIdRef = useRef<number>(0);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Location Toggle & Error States
  const [locationToggle, setLocationToggle] = useState<boolean>(Boolean(storeCoords));
  const [locationErrorTitle, setLocationErrorTitle] = useState<string>('');
  const [locationErrorDetails, setLocationErrorDetails] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showModal, setShowModal] = useState<boolean>(false);

  const calculateHaversineMiles = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const R = 3958.8; // Earth's radius in miles
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) *
        Math.cos((lat2 * Math.PI) / 180) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  // Active branch derived strictly from explicit customer choice or system recommendation.
  const activeBranch: Branch | null = manualOverrideBranch ?? recommendedBranch ?? null;

  // Calculate distance for the currently active branch
  const displayedDistance: number | null = activeBranch
    ? (activeBranch.id === recommendedBranch?.id
        ? distanceMiles
        : (userCoords && activeBranch.latitude !== undefined && activeBranch.longitude !== undefined
            ? Math.round(calculateHaversineMiles(userCoords.lat, userCoords.lng, activeBranch.latitude, activeBranch.longitude) * 100) / 100
            : null))
    : null;

  // Check if active manual override is valid for delivery
  const isManualOverrideDeliveryEligible = Boolean(
    activeBranch &&
    activeBranch.delivery_enabled &&
    displayedDistance !== null &&
    displayedDistance <= 2.0
  );

  const checkEligibilityWithBackend = useCallback(async (
    lat?: number,
    lng?: number,
    pc?: string,
    branchList?: Branch[]
  ) => {
    const currentRequestId = ++requestIdRef.current;
    
    // Cancel any ongoing in-flight HTTP request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    setResolutionState('RESOLVING');
    setLocationErrorTitle('');
    setLocationErrorDetails('');

    if (lat !== undefined && lng !== undefined) {
      setUserCoords({ lat, lng });
    }

    const cleanPc = pc ? pc.trim().toUpperCase().replace(/\s+/g, '') : undefined;

    try {
      const res: any = await api.post('/branches/nearest', {
        latitude: lat,
        longitude: lng,
        postcode: cleanPc,
        fulfillment_method: fulfillmentType
      }, {
        signal: abortController.signal
      });

      if (currentRequestId !== requestIdRef.current) return;

      const dist = res.distance_miles !== null && res.distance_miles !== undefined ? Number(res.distance_miles) : null;
      const eligible = Boolean(res.delivery_available ?? res.is_delivery_eligible ?? (dist !== null && dist <= 2.0));
      const effNearest = res.nearest_branch || res.assigned_branch || null;
      const assigned = res.assigned_branch || effNearest;

      setIsDeliveryEligible(eligible);
      setDistanceMiles(dist);
      setNearestBranch(effNearest);
      setRecommendedBranch(assigned);
      
      // Clear manual override so fresh geographic location recommendation takes effect
      setManualOverrideBranch(null);

      if (eligible && assigned) {
        setResolutionState('OUTLET_RESOLVED');
        setFulfillmentType('DELIVERY');
      } else if (effNearest) {
        setResolutionState('OUTSIDE_RADIUS');
        setFulfillmentType('COLLECTION');
      } else {
        setResolutionState('NO_ELIGIBLE_OUTLET');
        setFulfillmentType('COLLECTION');
      }
    } catch (err: any) {
      if (currentRequestId !== requestIdRef.current) return;
      if (err?.name === 'AbortError' || err?.name === 'CanceledError') return;

      setIsDeliveryEligible(false);
      setRecommendedBranch(null);
      setNearestBranch(null);
      setDistanceMiles(null);
      setLocationErrorTitle('Unable to verify delivery availability.');
      setLocationErrorDetails('Our server could not resolve your nearest outlet. Please select a store from the list or try again.');
      // If a branch is already loaded, keep user on IDLE so they can pick manually
      setResolutionState(manualOverrideBranch ? 'OUTLET_RESOLVED' : 'IDLE');
    }
  }, [fulfillmentType, manualOverrideBranch]);

  const requestBrowserLocation = useCallback((branchList?: Branch[]) => {
    const list = branchList || branches;

    if (!('geolocation' in navigator)) {
      setLocationToggle(false);
      setLocationErrorTitle('Geolocation is not supported by your browser.');
      setLocationErrorDetails('Please enter your UK postcode below or select an outlet from the list.');
      setIsDeliveryEligible(false);
      setFulfillmentType('COLLECTION');
      return;
    }

    setResolutionState('RESOLVING');
    setLocationErrorTitle('');
    setLocationErrorDetails('');

    const geoOptions: PositionOptions = {
      enableHighAccuracy: true,
      timeout: 8000,
      maximumAge: 30000
    };

    navigator.geolocation.getCurrentPosition(
      (position) => {
        const userLat = position.coords.latitude;
        const userLng = position.coords.longitude;
        const accuracy = position.coords.accuracy;

        if (
          userLat === undefined || userLng === undefined ||
          isNaN(userLat) || isNaN(userLng) ||
          userLat < -90 || userLat > 90 ||
          userLng < -180 || userLng > 180
        ) {
          setLocationToggle(false);
          setLocationErrorTitle('Invalid coordinates received from device.');
          setLocationErrorDetails('Please search with your UK postcode below or select an outlet from the list.');
          setIsDeliveryEligible(false);
          setFulfillmentType('COLLECTION');
          setResolutionState(manualOverrideBranch ? 'OUTLET_RESOLVED' : 'IDLE');
          return;
        }

        if (accuracy && accuracy > 5000) {
          setLocationToggle(false);
          setLocationErrorTitle('Location accuracy is too low to verify 2-mile delivery eligibility.');
          setLocationErrorDetails(
            `Device accuracy is approximately ±${Math.round(accuracy / 1000)} km. Please enter your exact UK postcode for delivery verification.`
          );
          setIsDeliveryEligible(false);
          setFulfillmentType('COLLECTION');
          setResolutionState(manualOverrideBranch ? 'OUTLET_RESOLVED' : 'IDLE');
          return;
        }

        setLocationToggle(true);
        setUserCoords({ lat: userLat, lng: userLng, accuracy });
        checkEligibilityWithBackend(userLat, userLng, undefined, list);
      },
      (error) => {
        setLocationToggle(false);
        setIsDeliveryEligible(false);
        setFulfillmentType('COLLECTION');
        setResolutionState(manualOverrideBranch ? 'OUTLET_RESOLVED' : 'IDLE');

        switch (error.code) {
          case 1:
            setLocationErrorTitle('Location access is required to check delivery availability.');
            setLocationErrorDetails(
              'Location permission was denied. You can choose Collection from your nearest store or enter a UK postcode below.'
            );
            break;
          case 2:
            setLocationErrorTitle('Unable to determine your device location.');
            setLocationErrorDetails(
              'Your browser or device could not retrieve GPS coordinates. Please search with your UK postcode below or choose an outlet from the list.'
            );
            break;
          case 3:
            setLocationErrorTitle('Location request timed out.');
            setLocationErrorDetails(
              'The location check took too long to respond. You can select an outlet manually from the list or enter your postcode.'
            );
            break;
          default:
            setLocationErrorTitle('Location access error.');
            setLocationErrorDetails('Please enter your UK postcode below or select an outlet from the list.');
            break;
        }
      },
      geoOptions
    );
  }, [branches, checkEligibilityWithBackend, manualOverrideBranch]);

  // Primary branch loader: independent of geolocation and resilient across all WebViews
  const fetchBranches = useCallback(async () => {
    setBranchesLoading(true);
    setBranchesError(null);
    console.info('[SelectLocationPage] Initiating branches fetch from API...');
    try {
      const rawData = await api.get<any>('/branches');
      console.info('[SelectLocationPage] Branches API response received:', Array.isArray(rawData) ? `Array(${rawData.length})` : typeof rawData);
      const list: Branch[] = Array.isArray(rawData)
        ? rawData
        : Array.isArray(rawData?.branches)
        ? rawData.branches
        : Array.isArray(rawData?.data)
        ? rawData.data
        : Array.isArray(rawData?.value)
        ? rawData.value
        : [];

      const activeList = list.filter(
        (b) => b && typeof b === 'object' && b.id && (b.is_active === undefined || b.is_active === true)
      );

      console.info(`[SelectLocationPage] Processed ${activeList.length} active branches.`);

      if (activeList.length > 0) {
        setBranches(activeList);
        setBranchesLoading(false);
        setBranchesError(null);

        // If user already had coordinates stored, check distance in background
        if (storeCoords) {
          checkEligibilityWithBackend(storeCoords.lat, storeCoords.lng, undefined, activeList);
        }
      } else {
        setBranches([]);
        setBranchesLoading(false);
        setResolutionState('NO_ELIGIBLE_OUTLET');
      }
    } catch (err: any) {
      console.error('[SelectLocationPage] Error loading branches:', {
        message: err?.message,
        status: err?.status,
        name: err?.name
      });
      setBranches([]);
      setBranchesLoading(false);
      setBranchesError('Unable to load outlets. Please try again.');
      setResolutionState('OUTLET_ERROR');
    }
  }, [storeCoords, checkEligibilityWithBackend]);

  useEffect(() => {
    fetchBranches();
  }, [fetchBranches]);

  const handleToggleLocation = () => {
    if (resolutionState === 'RESOLVING') return;
    if (!locationToggle) {
      setManualOverrideBranch(null);
      requestBrowserLocation(branches);
    } else {
      setLocationToggle(false);
      setUserCoords(null);
      setIsDeliveryEligible(false);
      setDistanceMiles(null);
      setRecommendedBranch(null);
      setFulfillmentType('COLLECTION');
      setResolutionState('IDLE');
      setLocationErrorTitle('');
      setLocationErrorDetails('');
    }
  };

  const handleSearchSubmit = () => {
    const raw = searchQuery.trim();
    if (!raw) return;
    setLocationErrorTitle('');
    setLocationErrorDetails('');
    setManualOverrideBranch(null);
    checkEligibilityWithBackend(undefined, undefined, raw, branches);
  };

  const handleSelectDelivery = () => {
    // Re-verify eligibility for active branch
    if (manualOverrideBranch) {
      if (!isManualOverrideDeliveryEligible) return;
    } else {
      if (!isDeliveryEligible || (distanceMiles !== null && distanceMiles > 2.0)) return;
    }
    setFulfillmentType('DELIVERY');
  };

  const handleSelectCollection = (branchToUse?: Branch) => {
    setFulfillmentType('COLLECTION');
    if (branchToUse) {
      setManualOverrideBranch(branchToUse);
      setResolutionState('OUTLET_RESOLVED');
    }
  };

  const handleConfirmCollectionDirectly = (branchToUse: Branch) => {
    const targetBranch = branchToUse || nearestBranch || activeBranch;
    if (!targetBranch) return;

    setSelectedBranch(
      targetBranch,
      distanceMiles,
      false,
      targetBranch,
      'WE PROVIDE DELIVERY UP TO 2 MILES ONLY',
      userCoords,
      searchQuery || undefined
    );

    setOrderType('COLLECTION');
    setSafeStorage('patty_selected_branch', JSON.stringify(targetBranch));
    navigate('/order');
  };

  const handleConfirmLocation = () => {
    if (!activeBranch) return;

    const isTargetRecommended = !manualOverrideBranch || manualOverrideBranch.id === recommendedBranch?.id;
    const isEligible = isTargetRecommended
      ? (isDeliveryEligible && distanceMiles !== null && distanceMiles <= 2.0)
      : isManualOverrideDeliveryEligible;

    const finalOrderType = fulfillmentType === 'DELIVERY' && isEligible ? 'DELIVERY' : 'COLLECTION';
    const finalDist = displayedDistance;

    setSelectedBranch(
      activeBranch,
      finalDist,
      isEligible,
      nearestBranch || activeBranch,
      isEligible ? null : 'WE PROVIDE DELIVERY UP TO 2 MILES ONLY',
      userCoords,
      searchQuery || undefined
    );

    setOrderType(finalOrderType);

    setSafeStorage('patty_selected_branch', JSON.stringify(activeBranch));

    navigate('/order');
  };

  const hasActiveBranches = branches.length > 0;
  const isResolving = resolutionState === 'RESOLVING';

  return (
    <div className="w-full max-w-[1160px] mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10 pb-20 text-[#F5F5F5]">
      {/* Page Heading & Subtitle */}
      <div className="mb-8 sm:mb-10">
        <h1 className="text-3xl font-bold text-[#F5F5F5] tracking-tight">
          Select location
        </h1>
        <p className="text-sm text-[#A1A1AA] mt-2 font-normal">
          Find your nearest Patty Project outlet & check delivery eligibility (up to 2 miles).
        </p>
      </div>

      {/* STATE: OUTLET LOADING ERROR */}
      {resolutionState === 'OUTLET_ERROR' && (
        <div className="bg-[#2A1215] border border-[#EF4444]/30 rounded-xl p-6 text-center space-y-3 mb-8">
          <AlertTriangle className="w-8 h-8 text-[#EF4444] mx-auto" />
          <h2 className="text-lg font-bold text-white">Unable to Load Outlets</h2>
          <p className="text-xs text-[#D1D5DB]">
            We could not connect to the store service. Please tap Retry to reload.
          </p>
          <button
            type="button"
            onClick={fetchBranches}
            className="px-5 py-2.5 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-lg text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer shadow-md"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Retry</span>
          </button>
        </div>
      )}

      {/* STATE: NO ACTIVE BRANCHES */}
      {resolutionState === 'NO_ELIGIBLE_OUTLET' && (
        <div className="bg-[#1C0E07] border border-[#6B2A0D] rounded-xl p-6 text-center space-y-3 mb-8">
          <AlertTriangle className="w-8 h-8 text-[#FF5500] mx-auto" />
          <h2 className="text-lg font-bold text-white">No Active Stores Currently Available</h2>
          <p className="text-xs text-[#D1D5DB]">
            Our outlets are currently unavailable for online ordering. Please check back shortly.
          </p>
          <button
            type="button"
            onClick={fetchBranches}
            className="px-4 py-2 bg-[#242424] hover:bg-[#333333] text-[#F5F5F5] rounded-lg text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      )}

      {/* 2-Column Desktop Grid Layout */}
      {resolutionState !== 'NO_ELIGIBLE_OUTLET' && resolutionState !== 'OUTLET_ERROR' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start mb-8">
          
          {/* LEFT COLUMN: Current Location Action, Postcode Search & Fulfillment Selector */}
          <div className="lg:col-span-5 space-y-6">
            
            {/* Use your current location Card */}
            <div className="bg-[#0D0D0D] border border-[#242424] rounded-[10px] p-5 flex items-center justify-between gap-4 transition-colors hover:border-[#333333]">
              <div className="flex items-center gap-3.5 min-w-0">
                <div className={`w-10 h-10 rounded-lg border flex items-center justify-center shrink-0 ${
                  locationToggle && (resolutionState === 'OUTLET_RESOLVED' || resolutionState === 'OUTSIDE_RADIUS')
                    ? 'bg-[#FF5500]/10 border-[#FF5500]/30 text-[#FF5500]'
                    : 'bg-[#151515] border-[#242424] text-[#A1A1AA]'
                }`}>
                  {isResolving ? (
                    <Loader2 className="w-5 h-5 animate-spin text-[#FF5500]" />
                  ) : (
                    <LocateFixed className="w-5 h-5" />
                  )}
                </div>
                <div className="min-w-0">
                  <h3 className="font-semibold text-sm text-[#F5F5F5] truncate">
                    Use your current location
                  </h3>
                  <p className="text-xs text-[#A1A1AA] mt-0.5 font-normal leading-tight">
                    Allow location access to check 2-mile delivery radius
                  </p>
                </div>
              </div>

              {/* Toggle Switch */}
              <button
                onClick={handleToggleLocation}
                disabled={isResolving}
                type="button"
                aria-label="Toggle location detection"
                className={`w-10 h-6 flex items-center rounded-full p-0.5 transition-colors cursor-pointer shrink-0 focus:outline-none focus:ring-2 focus:ring-[#FF5500]/50 ${
                  locationToggle && (resolutionState === 'OUTLET_RESOLVED' || resolutionState === 'OUTSIDE_RADIUS')
                    ? 'bg-[#FF5500]'
                    : 'bg-[#242424]'
                } ${isResolving ? 'opacity-60 cursor-wait' : ''}`}
              >
                <div
                  className={`bg-white w-5 h-5 rounded-full shadow transform transition-transform ${
                    locationToggle && (resolutionState === 'OUTLET_RESOLVED' || resolutionState === 'OUTSIDE_RADIUS')
                      ? 'translate-x-4'
                      : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Location Error Message */}
            {locationErrorTitle && (
              <div className="bg-[#2A1215] border border-[#EF4444]/30 p-3.5 rounded-lg text-xs space-y-2">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-[#EF4444] mt-0.5" />
                  <div className="space-y-0.5 min-w-0">
                    <p className="font-semibold text-[#FCA5A5] leading-snug">{locationErrorTitle}</p>
                    {locationErrorDetails && (
                      <p className="text-[11px] text-[#F87171] leading-relaxed">{locationErrorDetails}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Search UK Postcode Input */}
            <div className="space-y-2">
              <label className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider block">
                Or enter UK postcode
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="w-4 h-4 text-[#71717A] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleSearchSubmit();
                    }}
                    placeholder="e.g. N9 9HF"
                    disabled={isResolving}
                    className="w-full bg-[#151515] border border-[#242424] focus:border-[#FF5500] rounded-lg pl-10 pr-3.5 py-2.5 text-xs text-[#F5F5F5] placeholder-[#71717A] focus:outline-none transition-colors"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleSearchSubmit}
                  disabled={isResolving || !searchQuery.trim()}
                  className="px-4 py-2.5 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0 shadow-md"
                >
                  <Navigation className="w-3.5 h-3.5" />
                  <span>Check</span>
                </button>
              </div>
            </div>

            {/* Fulfillment Selector: Delivery vs Collection */}
            <div className="space-y-2 pt-2">
              <label className="text-xs font-semibold text-[#A1A1AA] uppercase tracking-wider block">
                Fulfillment method
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={handleSelectDelivery}
                  disabled={
                    manualOverrideBranch
                      ? !isManualOverrideDeliveryEligible
                      : !isDeliveryEligible || (distanceMiles !== null && distanceMiles > 2.0)
                  }
                  className={`py-3 px-4 rounded-lg border text-xs font-bold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    fulfillmentType === 'DELIVERY'
                      ? 'bg-[#FF5500] border-[#FF5500] text-white shadow-md'
                      : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                  } disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <Truck className="w-4 h-4" />
                  <span>Delivery (≤2 mi)</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectCollection()}
                  className={`py-3 px-4 rounded-lg border text-xs font-bold flex items-center justify-center gap-2 transition-all cursor-pointer ${
                    fulfillmentType === 'COLLECTION'
                      ? 'bg-[#FF5500] border-[#FF5500] text-white shadow-md'
                      : 'bg-[#151515] border-[#242424] text-[#A1A1AA] hover:border-[#333333]'
                  }`}
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Collection</span>
                </button>
              </div>
            </div>
          </div>

          {/* RIGHT COLUMN: Outlet Details & Selection Status */}
          <div className="lg:col-span-7 space-y-4">
            {/* Delivery Outside Radius Banner */}
            {resolutionState === 'OUTSIDE_RADIUS' && nearestBranch && (
              <div className="bg-[#1C0E07] border border-[#6B2A0D] rounded-xl p-5 space-y-3 shadow-lg">
                <div className="flex items-center gap-2 text-[#FF5500] font-black text-xs uppercase tracking-wider">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>WE PROVIDE DELIVERY UP TO 2 MILES ONLY</span>
                </div>
                <p className="text-xs text-[#D1D5DB] leading-relaxed">
                  Please collect your food from the nearest store.
                </p>

                <div className="pt-3 border-t border-[#6B2A0D]/60 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div>
                    <span className="text-[10px] font-semibold text-[#A1A1AA] uppercase tracking-wider block">Nearest store:</span>
                    <p className="text-sm font-bold text-white">Patty Project — {nearestBranch.name}</p>
                    {distanceMiles !== null && (
                      <p className="text-xs text-[#FF5500] font-semibold mt-0.5">{distanceMiles} miles away</p>
                    )}
                  </div>

                  <button
                    type="button"
                    onClick={() => handleConfirmCollectionDirectly(nearestBranch)}
                    className="px-4 py-2.5 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 cursor-pointer shadow-md shrink-0 focus:outline-none focus:ring-2 focus:ring-[#FF5500]/50"
                  >
                    <ShoppingBag className="w-3.5 h-3.5" />
                    <span>COLLECT FROM THIS STORE</span>
                  </button>
                </div>
              </div>
            )}

            <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-6 space-y-5">
              {/* Header Row */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-[#151515] border border-[#242424] flex items-center justify-center text-[#FF5500]">
                    <MapPin className="w-4 h-4" />
                  </div>
                  <h2 className="text-lg font-semibold text-[#F5F5F5]">
                    Selected outlet
                  </h2>
                </div>

                <button
                  type="button"
                  onClick={() => setShowModal(true)}
                  className="text-xs font-medium text-[#FF5500] hover:text-[#E84F00] flex items-center gap-1 cursor-pointer transition-colors"
                >
                  <span>Select from list</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>

              {isResolving ? (
                <div className="p-8 bg-[#121212] border border-[#242424] rounded-lg text-center space-y-2">
                  <Loader2 className="w-6 h-6 animate-spin text-[#FF5500] mx-auto" />
                  <p className="text-xs text-[#A1A1AA]">Finding nearest outlet & verifying delivery radius...</p>
                </div>
              ) : activeBranch ? (
                /* Selected Outlet Card Surface */
                <div className="bg-[#140B06] border border-[#6B2A0D] rounded-lg p-5 transition-all space-y-4">
                  <div className="flex items-start justify-between gap-4">
                    {/* Store Icon & Details */}
                    <div className="flex items-start gap-3.5 min-w-0">
                      <div className="w-10 h-10 rounded-lg bg-[#FF5500]/10 border border-[#FF5500]/30 flex items-center justify-center text-[#FF5500] shrink-0 mt-0.5">
                        <Store className="w-5 h-5" />
                      </div>
                      <div className="min-w-0 space-y-1">
                        <h3 className="text-lg font-semibold text-[#F5F5F5] truncate">
                          {activeBranch.name}
                        </h3>
                        <p className="text-sm text-[#A1A1AA] leading-snug">
                          {activeBranch.address_line1}
                        </p>
                        <p className="text-xs text-[#71717A]">
                          {activeBranch.city}, {activeBranch.postcode}
                        </p>
                        {activeBranch.phone && (
                          <p className="text-xs text-[#A1A1AA] pt-0.5">
                            Tel: {activeBranch.phone}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Distance Readout in Miles */}
                    {displayedDistance !== null && (
                      <div className="text-right shrink-0">
                        <p className="text-lg font-bold text-[#FF5500]">
                          {displayedDistance} miles
                        </p>
                        <span className="text-[11px] text-[#71717A] font-medium block">
                          Distance
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Open Status & Operating Hours */}
                  <div className="flex items-center gap-2.5 bg-[#050505] border border-[#242424] rounded-lg p-3">
                    <div className="w-2 h-2 rounded-full bg-[#22C55E] shrink-0" />
                    <span className="text-xs font-semibold text-[#22C55E]">
                      Open now
                    </span>
                    <span className="text-xs text-[#71717A]">•</span>
                    <span className="text-xs text-[#A1A1AA] font-normal">
                      10:00 AM – 11:00 PM
                    </span>
                  </div>
                </div>
              ) : (
                /* IDLE / NO SELECTION STATE */
                <div className="p-8 bg-[#121212] border border-[#242424] rounded-lg text-center space-y-3 text-[#A1A1AA]">
                  <MapPin className="w-6 h-6 text-[#71717A] mx-auto" />
                  <p className="text-sm font-semibold text-[#F5F5F5]">No Outlet Selected</p>
                  <p className="text-xs">
                    Please allow location access above, enter a UK postcode, or select an outlet from the list.
                  </p>
                  {hasActiveBranches && (
                    <button
                      type="button"
                      onClick={() => setShowModal(true)}
                      className="px-4 py-2 bg-[#FF5500] hover:bg-[#E04B00] text-white rounded-lg text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer shadow-md"
                    >
                      <Store className="w-3.5 h-3.5" />
                      <span>Choose Outlet from List</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* CONFIRM LOCATION Full-Width Primary CTA Button */}
      {resolutionState !== 'NO_ELIGIBLE_OUTLET' && resolutionState !== 'OUTLET_ERROR' && (
        <button
          onClick={handleConfirmLocation}
          disabled={!activeBranch || isResolving}
          className="w-full h-12 bg-[#FF5500] hover:bg-[#E84F00] text-white text-sm font-semibold rounded-lg shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-[#FF5500]/50"
        >
          <MapPin className="w-4 h-4" />
          <span>
            {!activeBranch
              ? 'Please Select an Outlet to Continue'
              : fulfillmentType === 'DELIVERY' && (isDeliveryEligible || isManualOverrideDeliveryEligible)
                ? 'Confirm Delivery Location & View Menu'
                : 'Confirm Store for Collection & View Menu'}
          </span>
          <ChevronRight className="w-4 h-4" />
        </button>
      )}

      {/* Select Outlet Branch Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0D0D0D] border border-[#242424] rounded-xl p-6 max-w-lg w-full space-y-5 text-[#F5F5F5] shadow-2xl animate-in fade-in duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-[#1C1C1C]">
              <h2 className="text-base font-semibold">Select Outlet Branch</h2>
              <button
                onClick={() => setShowModal(false)}
                aria-label="Close modal"
                className="text-[#A1A1AA] hover:text-white p-1 rounded-lg transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {branchesLoading ? (
              <div className="p-8 text-center space-y-2">
                <Loader2 className="w-6 h-6 animate-spin text-[#FF5500] mx-auto" />
                <p className="text-xs text-[#A1A1AA]">Loading outlets...</p>
              </div>
            ) : branchesError ? (
              <div className="p-6 bg-[#2A1215] border border-[#EF4444]/30 rounded-lg text-center space-y-3">
                <AlertTriangle className="w-6 h-6 text-[#EF4444] mx-auto" />
                <p className="text-xs text-[#FCA5A5] font-semibold">{branchesError}</p>
                <button
                  type="button"
                  onClick={fetchBranches}
                  className="px-4 py-2 bg-[#EF4444]/20 hover:bg-[#EF4444]/30 border border-[#EF4444]/40 text-[#FCA5A5] rounded-lg text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Retry</span>
                </button>
              </div>
            ) : branches.length === 0 ? (
              <div className="p-6 bg-[#151515] border border-[#242424] rounded-lg text-center space-y-3">
                <Store className="w-6 h-6 text-[#71717A] mx-auto" />
                <p className="text-xs text-[#A1A1AA]">No outlets are currently available.</p>
                <button
                  type="button"
                  onClick={fetchBranches}
                  className="px-4 py-2 bg-[#242424] hover:bg-[#333333] text-[#F5F5F5] rounded-lg text-xs font-bold transition-all inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Refresh</span>
                </button>
              </div>
            ) : (
              <div className="space-y-2.5 max-h-[60vh] overflow-y-auto pr-1">
                {branches.map((b) => {
                  const isSelected = activeBranch?.id === b.id;

                  return (
                    <div
                      key={b.id}
                      onClick={() => {
                        setManualOverrideBranch(b);
                        setResolutionState('OUTLET_RESOLVED');
                        setShowModal(false);
                      }}
                      className={`p-3.5 rounded-lg border cursor-pointer flex items-center justify-between transition-all ${
                        isSelected
                          ? 'bg-[#140B06] border-[#6B2A0D] text-[#F5F5F5]'
                          : 'bg-[#121212] border-[#242424] text-[#A1A1AA] hover:border-[#333333] hover:text-[#F5F5F5]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                            isSelected
                              ? 'bg-[#FF5A00] text-white'
                              : 'bg-[#151515] border border-[#242424] text-[#A1A1AA]'
                          }`}
                        >
                          <Store className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="font-semibold text-sm text-[#F5F5F5]">{b.name}</p>
                          <p className="text-xs text-[#A1A1AA]">
                            {b.address_line1}, {b.city} ({b.postcode})
                          </p>
                        </div>
                      </div>

                      {isSelected && (
                        <span className="text-xs font-semibold text-[#FF5A00] bg-[#FF5A00]/10 border border-[#6B2A0D] px-2.5 py-0.5 rounded">
                          Selected
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
