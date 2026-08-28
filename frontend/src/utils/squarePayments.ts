/**
 * Square Web Payments SDK Utility
 * Provides singleton script loading and payments initialization.
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
    if (window.Square) {
      resolve(window.Square);
      return;
    }

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
      setTimeout(() => {
        if (window.Square) {
          resolve(window.Square);
        }
      }, 500);
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
