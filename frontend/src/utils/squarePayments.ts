/**
 * Square Web Payments SDK Utility
 * Provides singleton script loading, payments initialization, and theme styling.
 */

declare global {
  interface Window {
    Square?: any;
  }
}

let sdkLoadingPromise: Promise<any> | null = null;

/**
 * Dynamically loads the Square Web Payments SDK script in a safe, singleton manner.
 */
export function loadSquareSdk(isSandbox: boolean): Promise<any> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Square SDK can only be loaded in a browser environment.'));
  }

  if (window.Square) {
    return Promise.resolve(window.Square);
  }

  if (sdkLoadingPromise) {
    return sdkLoadingPromise;
  }

  const sdkSrc = isSandbox
    ? 'https://sandbox.web.squarecdn.com/v1/square.js'
    : 'https://web.squarecdn.com/v1/square.js';

  sdkLoadingPromise = new Promise((resolve, reject) => {
    // Check if script element already exists in document
    const existingScript = document.querySelector<HTMLScriptElement>(`script[src="${sdkSrc}"]`);
    if (existingScript) {
      if (window.Square) {
        resolve(window.Square);
        return;
      }
      existingScript.addEventListener('load', () => {
        if (window.Square) {
          resolve(window.Square);
        } else {
          reject(new Error('Square SDK script loaded but window.Square is undefined.'));
        }
      });
      existingScript.addEventListener('error', () => {
        sdkLoadingPromise = null;
        reject(new Error('Failed to load Square Web Payments SDK script.'));
      });
      return;
    }

    const script = document.createElement('script');
    script.src = sdkSrc;
    script.type = 'text/javascript';
    script.async = true;

    script.onload = () => {
      if (window.Square) {
        resolve(window.Square);
      } else {
        sdkLoadingPromise = null;
        reject(new Error('Square SDK script loaded but window.Square is undefined.'));
      }
    };

    script.onerror = () => {
      sdkLoadingPromise = null;
      reject(new Error('Failed to load Square Web Payments SDK. Please check your internet connection.'));
    };

    document.head.appendChild(script);
  });

  return sdkLoadingPromise;
}

/**
 * Standard dark theme styling for the Square Card payment component matching Patty Project UI.
 */
export const SQUARE_CARD_STYLE = {
  '.input-container': {
    borderColor: '#242424',
    borderRadius: '8px',
    backgroundColor: '#151515',
  },
  'input': {
    color: '#F5F5F5',
    fontSize: '14px',
    fontFamily: 'inherit',
  },
  'input::placeholder': {
    color: '#71717A',
  },
  '.input-container.is-focus': {
    borderColor: '#FF5A00',
  },
  '.input-container.is-error': {
    borderColor: '#EF4444',
  },
};
