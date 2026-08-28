/**
 * Production Web Audio API Alert Manager for Patty Project UK Admin
 *
 * Features:
 * - Generates high-volume dual-tone kitchen alert without external MP3 files.
 * - Handles browser autoplay security policies gracefully.
 * - Strict lifecycle management (prevents overlapping loops, leaks, or runaway volume).
 * - Immediate stop when no unaccepted orders remain.
 */

export interface AudioAlertState {
  isLooping: boolean;
  isMuted: boolean;
  isPermissionGranted: boolean;
  isBlockedByBrowser: boolean;
}

type StateListener = (state: AudioAlertState) => void;

class OrderAudioAlertManager {
  private audioCtx: AudioContext | null = null;
  private isLooping = false;
  private isMuted = false;
  private timerId: ReturnType<typeof setInterval> | null = null;
  private isPermissionGranted = false;
  private isBlockedByBrowser = false;
  private listeners: Set<StateListener> = new Set();

  constructor() {
    if (typeof window !== 'undefined') {
      // Check localStorage preference
      const savedMute = localStorage.getItem('patty_admin_audio_muted');
      if (savedMute === 'true') {
        this.isMuted = true;
      }

      // Proactively listen for user interactions to unlock AudioContext if needed
      const unlockAudio = () => {
        if (this.audioCtx && this.audioCtx.state === 'suspended') {
          this.audioCtx.resume().then(() => {
            if (this.audioCtx?.state === 'running') {
              this.isPermissionGranted = true;
              this.isBlockedByBrowser = false;
              this.notify();
              if (this.isLooping) {
                this.playBeepPair();
              }
            }
          }).catch(() => {});
        }
      };

      window.addEventListener('click', unlockAudio, { passive: true });
      window.addEventListener('keydown', unlockAudio, { passive: true });
      window.addEventListener('touchstart', unlockAudio, { passive: true });
    }
  }

  private getAudioContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.audioCtx) {
      const AudioCtxClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
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
   * Plays a single high-visibility 2-tone kitchen chime (A5 880Hz -> D6 1174Hz).
   */
  public playBeepPair(): void {
    if (this.isMuted) return;
    const ctx = this.getAudioContext();
    if (!ctx) return;

    if (ctx.state !== 'running') {
      this.isBlockedByBrowser = true;
      this.notify();
      return;
    }

    try {
      const now = ctx.currentTime;

      // Tone 1: 880 Hz (A5)
      const osc1 = ctx.createOscillator();
      const gain1 = ctx.createGain();
      osc1.type = 'triangle';
      osc1.frequency.setValueAtTime(880, now);

      gain1.gain.setValueAtTime(0.001, now);
      gain1.gain.exponentialRampToValueAtTime(0.65, now + 0.03);
      gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.16);

      osc1.connect(gain1);
      gain1.connect(ctx.destination);

      osc1.start(now);
      osc1.stop(now + 0.18);

      // Tone 2: 1174.66 Hz (D6)
      const osc2 = ctx.createOscillator();
      const gain2 = ctx.createGain();
      osc2.type = 'triangle';
      osc2.frequency.setValueAtTime(1174.66, now + 0.12);

      gain2.gain.setValueAtTime(0.001, now + 0.12);
      gain2.gain.exponentialRampToValueAtTime(0.75, now + 0.15);
      gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.32);

      osc2.connect(gain2);
      gain2.connect(ctx.destination);

      osc2.start(now + 0.12);
      osc2.stop(now + 0.34);

      // Node cleanup
      osc1.onended = () => {
        try {
          osc1.disconnect();
          gain1.disconnect();
        } catch {}
      };
      osc2.onended = () => {
        try {
          osc2.disconnect();
          gain2.disconnect();
        } catch {}
      };
    } catch (e) {
      console.warn('[AudioAlert] Web Audio oscillator error:', e);
    }
  }

  /**
   * Starts repeating the alert chime continuously until stopAlertLoop() is called.
   */
  public startAlertLoop(): void {
    if (this.isLooping) return;
    this.isLooping = true;

    const ctx = this.getAudioContext();
    if (ctx && ctx.state === 'suspended') {
      this.isBlockedByBrowser = true;
    } else if (ctx && ctx.state === 'running') {
      this.isPermissionGranted = true;
      this.isBlockedByBrowser = false;
    }

    this.notify();
    this.playBeepPair();

    this.timerId = setInterval(() => {
      if (!this.isLooping) {
        if (this.timerId) {
          clearInterval(this.timerId);
          this.timerId = null;
        }
        return;
      }
      this.playBeepPair();
    }, 700);
  }

  /**
   * Immediately terminates the repeating chime loop.
   */
  public stopAlertLoop(): void {
    this.isLooping = false;
    if (this.timerId) {
      clearInterval(this.timerId);
      this.timerId = null;
    }
    this.notify();
  }

  /**
   * Toggles audio mute preference.
   */
  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('patty_admin_audio_muted', String(this.isMuted));
    }
    this.notify();
    return this.isMuted;
  }

  public setMute(muted: boolean): void {
    this.isMuted = muted;
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('patty_admin_audio_muted', String(this.isMuted));
    }
    this.notify();
  }

  public getState(): AudioAlertState {
    return {
      isLooping: this.isLooping,
      isMuted: this.isMuted,
      isPermissionGranted: this.isPermissionGranted,
      isBlockedByBrowser: this.isBlockedByBrowser,
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
