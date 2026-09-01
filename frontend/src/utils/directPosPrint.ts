import { Order } from '../types';

const LOCAL_POS_PRINT_AGENT_URL = 'http://127.0.0.1:18360/print-receipt';

/**
 * Dispatch authoritative order data directly to the local Windows POS Print Agent.
 * Bypasses window.print(), Chrome Print Preview, Save as PDF, and all browser canvas boxes.
 *
 * @param order Authoritative Order object from backend
 * @returns Promise<boolean> true if accepted by local POS print agent, false otherwise.
 */
export const sendDirectPosPrint = async (order: Order): Promise<boolean> => {
  if (!order || !order.id) {
    return false;
  }

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 1500);

    const authToken = typeof window !== 'undefined' ? (localStorage.getItem('pos_auth_token') || '') : '';

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (authToken) {
      headers['X-POS-Auth'] = authToken;
    }

    const response = await fetch(LOCAL_POS_PRINT_AGENT_URL, {
      method: 'POST',
      headers,
      body: JSON.stringify(order),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (response.ok) {
      console.log(`[POS Direct Print] Order ${order.order_number} successfully sent to NetumScan NS-8360LW.`);
      return true;
    }
  } catch (err: any) {
    // Non-blocking: If the local print agent is offline, uninstalled, or the manager is on a phone/laptop,
    // log silently without interrupting the admin interface or order acceptance.
    if (err.name !== 'AbortError') {
      console.info('[POS Direct Print] Local POS agent unreachable (device is not the primary POS terminal).');
    }
  }

  return false;
};
