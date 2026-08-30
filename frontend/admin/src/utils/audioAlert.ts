/**
 * Production Web Audio API Alert Manager for Patty Project UK Admin
 *
 * Features:
 * - High-visibility dual-tone kitchen chime (880 Hz -> 1174.66 Hz).
 * - Web Audio API lookahead clock scheduling against audioContext.currentTime to prevent
 *   background tab timer throttling / jitter.
 * - Deterministic, recoverable multi-tab leadership via BroadcastChannel & localStorage heartbeat lease.
 * - Cross-tab mute state synchronization.
 * - Proactive AudioContext unlock and auto-recovery on user interaction & WebSocket events.
 * - Strict lifecycle and node cleanup (zero oscillator/gain node leaks).
 */

export interface AudioAlertState {
  isLooping: boolean;
  isMuted: boolean;
  isPermissionGranted: boolean;
  isBlockedByBrowser: boolean;
  isLeader: boolean;
  tabId: string;
}

export type StateListener = (state: AudioAlertState) => void;

interface LeaderLease {
  tabId: string;
  heartbeat: number;
}

const LEADER_KEY = 'patty_admin_audio_leader';
const MUTE_KEY = 'patty_admin_audio_muted';
const CHANNEL_NAME = 'patty_admin_alerts';
const LEADER_HEARTBEAT_INTERVAL_MS = 800;
const LEADER_TIMEOUT_MS = 2400;
const CHIME_INTERVAL_SEC = 0.70; // 700ms repeating cadence
const SCHEDULER_INTERVAL_MS = 100;
const SCHEDULE_LOOKAHEAD_SEC = 0.35;

class OrderAudioAlertManager {
  public readonly tabId: string;
  private audioCtx: AudioContext | null = null;
  private isLooping = false;
  private isMuted = false;
  private isLeader = false;
  private isPermissionGranted = false;
  private isBlockedByBrowser = false;

  private schedulerTimerId: ReturnType<typeof setInterval> | null = null;
  private leaderHeartbeatTimerId: ReturnType<typeof setInterval> | null = null;
  private nextToneTime = 0;
  private activeNodes: Set<OscillatorNode | GainNode> = new Set();
  private listeners: Set<StateListener> = new Set();
  private broadcastChannel: BroadcastChannel | null = null;

  constructor() {
    this.tabId = typeof window !== 'undefined'
      ? `tab_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
      : 'tab_ssr';

    if (typeof window !== 'undefined') {
      // 1. Restore mute preference
      try {
        const savedMute = localStorage.getItem(MUTE_KEY);
        this.isMuted = savedMute === 'true';
      } catch {}

      // 2. Initialize BroadcastChannel for cross-tab messaging
      this.initBroadcastChannel();

      // 3. Register global user interaction unlock handlers
      this.initInteractionListeners();

      // 4. Start leadership lease evaluation & heartbeat
      this.initLeadershipManagement();
    }
  }

  private initBroadcastChannel(): void {
    if (typeof window === 'undefined') return;

    if ('BroadcastChannel' in window) {
      try {
        this.broadcastChannel = new BroadcastChannel(CHANNEL_NAME);
        this.broadcastChannel.onmessage = (event: MessageEvent) => {
          this.handleBroadcastMessage(event.data);
        };
      } catch (e) {
        console.warn('[AudioAlert] BroadcastChannel init error, falling back to storage:', e);
      }
    }

    // Storage event listener fallback / cross-window sync
    window.addEventListener('storage', (e: StorageEvent) => {
      if (e.key === MUTE_KEY && e.newValue !== null) {
        const newMute = e.newValue === 'true';
        if (this.isMuted !== newMute) {
          this.isMuted = newMute;
          this.notify();
        }
      } else if (e.key === LEADER_KEY) {
        this.evaluateLeadership();
      }
    });

    // Cleanup on window unload
    window.addEventListener('beforeunload', () => {
      if (this.isLeader) {
        this.releaseLeadership();
      }
      this.stopAlertLoop();
    });
  }

  private handleBroadcastMessage(data: any): void {
    if (!data || typeof data !== 'object') return;

    switch (data.type) {
      case 'MUTE_TOGGLED':
        if (typeof data.isMuted === 'boolean' && this.isMuted !== data.isMuted) {
          this.isMuted = data.isMuted;
          this.notify();
        }
        break;

      case 'AUDIO_LEADER_CLAIM':
        if (data.tabId !== this.tabId && this.isLeader) {
          // Relinquish leadership if another tab legitimately claimed it
          this.isLeader = false;
          this.notify();
        }
        break;

      case 'AUDIO_LEADER_RELEASE':
        this.evaluateLeadership();
        break;

      case 'REQUEST_ALERT_STATE':
        // If we are leader and looping, broadcast loop status
        if (this.isLeader && this.isLooping) {
          this.postMessage({ type: 'SYNC_ALERT_STATE', isLooping: true });
        }
        break;
    }
  }

  private postMessage(message: any): void {
    try {
      if (this.broadcastChannel) {
        this.broadcastChannel.postMessage(message);
      }
    } catch {}
  }

  private initInteractionListeners(): void {
    if (typeof window === 'undefined') return;

    const unlock = () => {
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume().then(() => {
          if (this.audioCtx?.state === 'running') {
            this.isPermissionGranted = true;
            this.isBlockedByBrowser = false;
            this.notify();
          }
        }).catch(() => {});
      } else if (this.audioCtx && this.audioCtx.state === 'running') {
        this.isPermissionGranted = true;
        this.isBlockedByBrowser = false;
        this.notify();
      }
    };

    window.addEventListener('click', unlock, { passive: true });
    window.addEventListener('keydown', unlock, { passive: true });
    window.addEventListener('touchstart', unlock, { passive: true });

    // When tab receives focus, attempt claiming leadership so active tab plays sound
    window.addEventListener('focus', () => {
      this.claimLeadership();
      unlock();
    });
  }

  private initLeadershipManagement(): void {
    this.evaluateLeadership();

    this.leaderHeartbeatTimerId = setInterval(() => {
      if (this.isLeader) {
        this.writeLeaderLease();
      } else {
        this.evaluateLeadership();
      }
    }, LEADER_HEARTBEAT_INTERVAL_MS);
  }

  private getLeaderLease(): LeaderLease | null {
    if (typeof localStorage === 'undefined') return null;
    try {
      const raw = localStorage.getItem(LEADER_KEY);
      if (!raw) return null;
      return JSON.parse(raw) as LeaderLease;
    } catch {
      return null;
    }
  }

  private writeLeaderLease(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      const lease: LeaderLease = {
        tabId: this.tabId,
        heartbeat: Date.now(),
      };
      localStorage.setItem(LEADER_KEY, JSON.stringify(lease));
    } catch {}
  }

  public claimLeadership(): boolean {
    this.writeLeaderLease();
    const wasLeader = this.isLeader;
    this.isLeader = true;
    this.postMessage({ type: 'AUDIO_LEADER_CLAIM', tabId: this.tabId });

    if (!wasLeader) {
      this.notify();
      // If we became leader while looping was desired, resume audio clock
      if (this.isLooping) {
        this.startScheduler();
      }
    }
    return true;
  }

  private releaseLeadership(): void {
    if (typeof localStorage === 'undefined') return;
    try {
      const current = this.getLeaderLease();
      if (current && current.tabId === this.tabId) {
        localStorage.removeItem(LEADER_KEY);
      }
      this.isLeader = false;
      this.postMessage({ type: 'AUDIO_LEADER_RELEASE', tabId: this.tabId });
      this.notify();
    } catch {}
  }

  private evaluateLeadership(): void {
    const lease = this.getLeaderLease();
    const now = Date.now();

    if (!lease || now - lease.heartbeat > LEADER_TIMEOUT_MS) {
      // Lease expired or missing; claim leadership
      this.claimLeadership();
    } else if (lease.tabId === this.tabId) {
      if (!this.isLeader) {
        this.isLeader = true;
        this.notify();
      }
    } else {
      if (this.isLeader) {
        this.isLeader = false;
        this.notify();
      }
    }
  }

  private getAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.audioCtx) {
      const AudioCtxClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtxClass) {
        this.audioCtx = new AudioCtxClass();
      }
    }
    return this.audioCtx;
  }

  /**
   * Initializes or unlocks the AudioContext upon user interaction.
   */
  public async initAudio(): Promise<boolean> {
    const ctx = this.getAudioContext();
    if (!ctx) return false;

    try {
      if (ctx.state === 'suspended') {
        await ctx.resume();
      }
      const running = ctx.state === 'running';
      this.isPermissionGranted = running;
      this.isBlockedByBrowser = !running;
      this.notify();
      return running;
    } catch (e) {
      console.warn('[AudioAlert] Failed to resume AudioContext:', e);
      this.isBlockedByBrowser = true;
      this.notify();
      return false;
    }
  }

  /**
   * Schedules a single high-visibility dual-tone kitchen chime (Tone 1: 880Hz, Tone 2: 1174.66Hz)
   * at an exact target timestamp on the Web Audio timeline.
   */
  private scheduleBeepPair(targetTime: number): void {
    if (this.isMuted) return;
    const ctx = this.getAudioContext();
    if (!ctx || ctx.state !== 'running') return;

    try {
      const t1Start = Math.max(targetTime, ctx.currentTime);
      const t2Start = t1Start + 0.12;

      // ==========================================
      // Tone 1: 880 Hz (A5) Triangle Wave (180ms)
      // ==========================================
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'triangle';
      osc1.frequency.setValueAtTime(880, t1Start);

      gain1.gain.setValueAtTime(0.001, t1Start);
      gain1.gain.exponentialRampToValueAtTime(0.65, t1Start + 0.03);
      gain1.gain.exponentialRampToValueAtTime(0.001, t1Start + 0.16);

      osc1.connect(gain1);
      gain1.connect(ctx.destination);

      this.activeNodes.add(osc1);
      this.activeNodes.add(gain1);

      osc1.start(t1Start);
      osc1.stop(t1Start + 0.18);

      // ==========================================
      // Tone 2: 1174.66 Hz (D6) Triangle Wave (220ms)
      // ==========================================
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(1174.66, t2Start);

      gain2.gain.setValueAtTime(0.001, t2Start);
      gain2.gain.exponentialRampToValueAtTime(0.75, t2Start + 0.03);
      gain2.gain.exponentialRampToValueAtTime(0.001, t2Start + 0.20);

      osc2.connect(gain2);
      gain2.connect(ctx.destination);

      this.activeNodes.add(osc2);
      this.activeNodes.add(gain2);

      osc2.start(t2Start);
      osc2.stop(t2Start + 0.22);

      // Safe Node Disconnection and Disposal
      osc1.onended = () => {
        try {
          osc1.disconnect();
          gain1.disconnect();
        } catch {}
        this.activeNodes.delete(osc1);
        this.activeNodes.delete(gain1);
      };

      osc2.onended = () => {
        try {
          osc2.disconnect();
          gain2.disconnect();
        } catch {}
        this.activeNodes.delete(osc2);
        this.activeNodes.delete(gain2);
      };
    } catch (e) {
      console.warn('[AudioAlert] Web Audio oscillator schedule error:', e);
    }
  }

  /**
   * Lookahead Scheduler Loop running against audioContext.currentTime.
   * Eliminates timing drift and audio stutter when browser throttles background tab timers.
   */
  private runScheduler = (): void => {
    if (!this.isLooping) return;

    // Only the leader tab actually outputs Web Audio
    if (!this.isLeader) return;

    const ctx = this.getAudioContext();
    if (!ctx) return;

    if (ctx.state === 'suspended') {
      this.isBlockedByBrowser = true;
      this.notify();
      return;
    } else if (ctx.state === 'running') {
      if (this.isBlockedByBrowser) {
        this.isBlockedByBrowser = false;
        this.isPermissionGranted = true;
        this.notify();
      }
    }

    const currentTime = ctx.currentTime;
    if (this.nextToneTime < currentTime) {
      this.nextToneTime = currentTime + 0.02;
    }

    // Schedule any chimes due within the lookahead window
    while (this.nextToneTime < currentTime + SCHEDULE_LOOKAHEAD_SEC) {
      this.scheduleBeepPair(this.nextToneTime);
      this.nextToneTime += CHIME_INTERVAL_SEC;
    }
  };

  private startScheduler(): void {
    if (this.schedulerTimerId) {
      clearInterval(this.schedulerTimerId);
    }

    const ctx = this.getAudioContext();
    if (ctx) {
      if (ctx.state === 'suspended') {
        this.isBlockedByBrowser = true;
        // Attempt immediate resume
        ctx.resume().then(() => {
          if (ctx.state === 'running') {
            this.isBlockedByBrowser = false;
            this.isPermissionGranted = true;
            this.notify();
          }
        }).catch(() => {});
      } else if (ctx.state === 'running') {
        this.isBlockedByBrowser = false;
        this.isPermissionGranted = true;
      }
      this.nextToneTime = ctx.currentTime + 0.02;
    }

    // Immediate initial tick
    this.runScheduler();
    this.schedulerTimerId = setInterval(this.runScheduler, SCHEDULER_INTERVAL_MS);
  }

  private stopScheduler(): void {
    if (this.schedulerTimerId) {
      clearInterval(this.schedulerTimerId);
      this.schedulerTimerId = null;
    }

    // Safely disconnect all currently active oscillators and gains
    this.activeNodes.forEach((node) => {
      try {
        if ('stop' in node && typeof (node as OscillatorNode).stop === 'function') {
          (node as OscillatorNode).stop();
        }
        node.disconnect();
      } catch {}
    });
    this.activeNodes.clear();
  }

  /**
   * Starts repeating the alert chime continuously until stopAlertLoop() is called.
   * Guaranteed idempotent — multiple calls do not start duplicate timers or overlapping audio.
   */
  public startAlertLoop(): void {
    if (this.isLooping) return;
    this.isLooping = true;

    this.evaluateLeadership();
    this.startScheduler();
    this.notify();
  }

  /**
   * Immediately terminates the repeating chime loop and cancels all scheduled audio nodes.
   */
  public stopAlertLoop(): void {
    if (!this.isLooping && !this.schedulerTimerId) return;
    this.isLooping = false;

    this.stopScheduler();
    this.notify();
  }

  /**
   * Plays a single test chime pair.
   */
  public playBeepPair(): void {
    const ctx = this.getAudioContext();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume().then(() => {
        this.scheduleBeepPair(ctx.currentTime + 0.02);
      }).catch(() => {});
    } else {
      this.scheduleBeepPair(ctx.currentTime + 0.02);
    }
  }

  /**
   * Toggles audio mute preference and synchronizes across all browser tabs.
   */
  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem(MUTE_KEY, String(this.isMuted));
      } catch {}
    }
    this.postMessage({ type: 'MUTE_TOGGLED', isMuted: this.isMuted });
    this.notify();
    return this.isMuted;
  }

  public setMute(muted: boolean): void {
    if (this.isMuted === muted) return;
    this.isMuted = muted;
    if (typeof localStorage !== 'undefined') {
      try {
        localStorage.setItem(MUTE_KEY, String(this.isMuted));
      } catch {}
    }
    this.postMessage({ type: 'MUTE_TOGGLED', isMuted: this.isMuted });
    this.notify();
  }

  public getState(): AudioAlertState {
    return {
      isLooping: this.isLooping,
      isMuted: this.isMuted,
      isPermissionGranted: this.isPermissionGranted,
      isBlockedByBrowser: this.isBlockedByBrowser,
      isLeader: this.isLeader,
      tabId: this.tabId,
    };
  }

  public subscribe(listener: StateListener): () => void {
    this.listeners.add(listener);
    listener(this.getState());
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    const state = this.getState();
    this.listeners.forEach((listener) => {
      try {
        listener(state);
      } catch {}
    });
  }
}

export const audioAlert = new OrderAudioAlertManager();
