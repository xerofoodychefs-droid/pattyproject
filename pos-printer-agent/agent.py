"""
Patty Project - Local Windows POS Thermal Print Agent
Target Hardware: NetumScan NS-8360LW (80mm Thermal Receipt Printer, ESC/POS, Auto-Cutter)

Architecture:
- Binds strictly to 127.0.0.1:18360 (Localhost only, no external network exposure).
- Receives structured order JSON from https://pattyproject.co.uk admin portal.
- Validates origin and X-POS-Auth authentication token.
- Formats authoritative order data into 48-column printer-native ESC/POS bytes.
- Transmits RAW byte stream directly to the Windows Spooler API (winspool.drv) without shell execution.
- Emits partial auto-cut command (GS V 66 0) at the end of the receipt.
"""

import ctypes
import ctypes.wintypes
import hmac
import http.server
import json
import os
import sys

PORT = 18360
ALLOWED_ORIGINS = {
    "https://pattyproject.co.uk",
    "https://www.pattyproject.co.uk",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}

# Optional auth token configured locally on the POS machine
POS_AUTH_TOKEN = os.environ.get("POS_AUTH_TOKEN", "").strip()

# ESC/POS Constants
ESC = b'\x1b'
GS = b'\x1d'
INIT = ESC + b'@'
ALIGN_LEFT = ESC + b'a\x00'
ALIGN_CENTER = ESC + b'a\x01'
ALIGN_RIGHT = ESC + b'a\x02'
BOLD_ON = ESC + b'E\x01'
BOLD_OFF = ESC + b'E\x00'
DOUBLE_SIZE = GS + b'!\x11'
NORMAL_SIZE = GS + b'!\x00'
FEED_3_LINES = ESC + b'd\x03'
PARTIAL_CUT = GS + b'V\x42\x00'  # GS V 66 0 (Feed and partial cut)
FULL_CUT = GS + b'V\x41\x00'     # GS V 65 0 (Feed and full cut)

LINE_WIDTH = 48  # 80mm roll, 72mm active heating width (576 dots / 12x24 Font A)

# Win32 Spooler Structure Definition
class DOC_INFO_1W(ctypes.Structure):
    _fields_ = [
        ("pDocName", ctypes.c_wchar_p),
        ("pOutputFile", ctypes.c_wchar_p),
        ("pDataType", ctypes.c_wchar_p),
    ]

def print_raw_bytes_winspool(printer_name: str, raw_data: bytes, doc_name: str = "Patty POS Receipt") -> bool:
    """
    Direct Windows RAW Print Spooler submission using Win32 API.
    Bypasses GDI rasterization, avoids cmd.exe / shell execution, and does NOT require Windows Printer Sharing.
    """
    if sys.platform != 'win32':
        # On non-Windows environments (e.g. CI/mock tests), simulate success
        return True

    try:
        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        
        OpenPrinterW = winspool.OpenPrinterW
        OpenPrinterW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.wintypes.HANDLE), ctypes.c_void_p]
        OpenPrinterW.restype = ctypes.wintypes.BOOL

        StartDocPrinterW = winspool.StartDocPrinterW
        StartDocPrinterW.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.POINTER(DOC_INFO_1W)]
        StartDocPrinterW.restype = ctypes.wintypes.DWORD

        StartPagePrinter = winspool.StartPagePrinter
        StartPagePrinter.argtypes = [ctypes.wintypes.HANDLE]
        StartPagePrinter.restype = ctypes.wintypes.BOOL

        WritePrinter = winspool.WritePrinter
        WritePrinter.argtypes = [ctypes.wintypes.HANDLE, ctypes.c_char_p, ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD)]
        WritePrinter.restype = ctypes.wintypes.BOOL

        EndPagePrinter = winspool.EndPagePrinter
        EndPagePrinter.argtypes = [ctypes.wintypes.HANDLE]
        EndPagePrinter.restype = ctypes.wintypes.BOOL

        EndDocPrinter = winspool.EndDocPrinter
        EndDocPrinter.argtypes = [ctypes.wintypes.HANDLE]
        EndDocPrinter.restype = ctypes.wintypes.BOOL

        ClosePrinter = winspool.ClosePrinter
        ClosePrinter.argtypes = [ctypes.wintypes.HANDLE]
        ClosePrinter.restype = ctypes.wintypes.BOOL

        hPrinter = ctypes.wintypes.HANDLE()
        if not OpenPrinterW(printer_name, ctypes.byref(hPrinter), None):
            err = ctypes.get_last_error()
            print(f"[POS Agent] OpenPrinterW failed for '{printer_name}' (Windows Error: {err})", file=sys.stderr)
            return False

        try:
            doc_info = DOC_INFO_1W()
            doc_info.pDocName = doc_name
            doc_info.pOutputFile = None
            doc_info.pDataType = "RAW"

            job_id = StartDocPrinterW(hPrinter, 1, ctypes.byref(doc_info))
            if job_id == 0:
                err = ctypes.get_last_error()
                print(f"[POS Agent] StartDocPrinterW failed (Windows Error: {err})", file=sys.stderr)
                return False

            try:
                if not StartPagePrinter(hPrinter):
                    err = ctypes.get_last_error()
                    print(f"[POS Agent] StartPagePrinter failed (Windows Error: {err})", file=sys.stderr)
                    return False

                bytes_written = ctypes.wintypes.DWORD()
                success = WritePrinter(hPrinter, raw_data, len(raw_data), ctypes.byref(bytes_written))
                if not success or bytes_written.value != len(raw_data):
                    err = ctypes.get_last_error()
                    print(f"[POS Agent] WritePrinter failed (Written: {bytes_written.value}/{len(raw_data)}, Error: {err})", file=sys.stderr)
                    return False

                EndPagePrinter(hPrinter)
            finally:
                EndDocPrinter(hPrinter)
                
            return True
        finally:
            ClosePrinter(hPrinter)
    except Exception as e:
        print(f"[POS Agent] Winspool exception for {printer_name}: {e}", file=sys.stderr)
        return False

def wrap_text(text: str, max_width: int) -> list[str]:
    """Wrap text naturally at word boundaries to prevent truncation."""
    words = text.split()
    if not words:
        return [""]
    lines = []
    curr = ""
    for w in words:
        if not curr:
            curr = w
        elif len(curr) + 1 + len(w) <= max_width:
            curr += " " + w
        else:
            lines.append(curr)
            curr = w
    if curr:
        lines.append(curr)
    return lines

def format_row(left: str, right: str, width: int = LINE_WIDTH) -> str:
    """Format a two-column line with left and right alignment."""
    avail = width - len(right)
    if avail < 1:
        return (left[:width-len(right)] + right)[:width]
    return left[:avail].ljust(avail) + right

def build_escpos_receipt(order: dict) -> bytes:
    """Translate authoritative order JSON into printer-native ESC/POS bytes."""
    buf = bytearray()
    
    # 1. Initialize
    buf.extend(INIT)
    
    # 2. Header (Centered, Double Size)
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON)
    buf.extend(DOUBLE_SIZE)
    buf.extend("PATTY PROJECT\n".encode('ascii', 'replace'))
    buf.extend(NORMAL_SIZE)
    
    order_num = str(order.get('order_number', 'N/A'))
    buf.extend(f"Order: {order_num}\n".encode('ascii', 'replace'))
    buf.extend(BOLD_OFF)
    
    divider = ("-" * LINE_WIDTH) + "\n"
    buf.extend(divider.encode('ascii'))
    
    # 3. Customer Info (Left aligned)
    buf.extend(ALIGN_LEFT)
    cust_name = str(order.get('customer_name') or '').strip()
    cust_phone = str(order.get('customer_phone') or '').strip()
    if cust_name or cust_phone:
        buf.extend(BOLD_ON + b"CUSTOMER\n" + BOLD_OFF)
        if cust_name:
            buf.extend(f"Name : {cust_name}\n".encode('ascii', 'replace'))
        if cust_phone:
            buf.extend(f"Phone: {cust_phone}\n".encode('ascii', 'replace'))
        buf.extend(divider.encode('ascii'))
        
    # 4. Order Type & Delivery / Collection details
    order_type = str(order.get('order_type', 'COLLECTION')).upper()
    buf.extend(BOLD_ON + b"ORDER TYPE\n" + BOLD_OFF)
    buf.extend(f"{order_type}\n".encode('ascii', 'replace'))
    
    if order_type == 'DELIVERY':
        addr = order.get('delivery_address')
        if isinstance(addr, dict):
            lines = [
                addr.get('address_line1'),
                addr.get('address_line2'),
                addr.get('city'),
                f"{addr.get('postcode', '')} {addr.get('country', 'UK')}".strip()
            ]
            for l in lines:
                if l and str(l).strip():
                    for wl in wrap_text(str(l).strip(), LINE_WIDTH):
                        buf.extend(f"{wl}\n".encode('ascii', 'replace'))
        elif isinstance(addr, str) and addr.strip():
            for wl in wrap_text(addr.strip(), LINE_WIDTH):
                buf.extend(f"{wl}\n".encode('ascii', 'replace'))
    elif order_type == 'COLLECTION':
        slot = order.get('collection_slot_time')
        if slot:
            buf.extend(f"Slot: {slot}\n".encode('ascii', 'replace'))
            
    buf.extend(divider.encode('ascii'))
    
    # 5. Bill Items Table Header
    buf.extend(ALIGN_CENTER)
    buf.extend(BOLD_ON + b"BILL\n" + BOLD_OFF)
    buf.extend(ALIGN_LEFT)
    
    # Column Header: QTY (4) | ITEM & DETAILS (32) | PRICE (12)
    header_line = format_row("QTY  ITEM & DETAILS", "PRICE", LINE_WIDTH)
    buf.extend(BOLD_ON + header_line.encode('ascii') + b"\n" + BOLD_OFF)
    buf.extend(divider.encode('ascii'))
    
    items = order.get('items') or []
    total_qty = 0
    for item in items:
        qty = int(item.get('quantity', 1))
        total_qty += qty
        name = str(item.get('product_name', 'Item')).strip()
        price_val = float(item.get('total_price', 0.0))
        
        # First line: QTY + first line of item name + price
        first_line_text = f"{qty:<4} {name}"
        if len(first_line_text) > (LINE_WIDTH - 12):
            wrapped = wrap_text(name, LINE_WIDTH - 16)
            first_row = format_row(f"{qty:<4} {wrapped[0]}", f"\xa3{price_val:.2f}", LINE_WIDTH)
            buf.extend(first_row.encode('latin-1', 'replace') + b"\n")
            for sub_l in wrapped[1:]:
                buf.extend(f"     {sub_l}\n".encode('latin-1', 'replace'))
        else:
            row = format_row(first_line_text, f"\xa3{price_val:.2f}", LINE_WIDTH)
            buf.extend(row.encode('latin-1', 'replace') + b"\n")
            
        # Customizations (Add-ons, Removals, Selections)
        options = item.get('selected_options') or item.get('customizations') or {}
        if isinstance(options, dict):
            # Addons
            addons = options.get('addons') or options.get('add_ons') or []
            if addons:
                buf.extend(b"     * Add-ons:\n")
                for a in addons:
                    label = str(a.get('label') or a.get('name') or a)
                    p = a.get('price') if isinstance(a, dict) else None
                    if p:
                        buf.extend(f"       - {label:<26} \xa3{float(p):.2f}\n".encode('latin-1', 'replace'))
                    else:
                        buf.extend(f"       - {label}\n".encode('latin-1', 'replace'))
            # Removals
            removals = options.get('removals') or options.get('removed') or []
            if removals:
                buf.extend(b"     * Removals:\n")
                for r in removals:
                    label = str(r.get('label') or r.get('name') or r)
                    buf.extend(f"       - {label}\n".encode('latin-1', 'replace'))
            # Selections
            selections = options.get('selections') or options.get('choices') or []
            if selections:
                buf.extend(b"     * Options:\n")
                for s in selections:
                    label = str(s.get('label') or s.get('name') or s)
                    p = s.get('price') if isinstance(s, dict) else None
                    if p:
                        buf.extend(f"       - {label:<26} \xa3{float(p):.2f}\n".encode('latin-1', 'replace'))
                    else:
                        buf.extend(f"       - {label}\n".encode('latin-1', 'replace'))
                        
    buf.extend(divider.encode('ascii'))
    
    # 6. Subtotal & Discounts
    subtotal = float(order.get('subtotal', 0.0))
    discount = float(order.get('discount_amount', 0.0))
    total_due = float(order.get('total_amount', 0.0))
    vat_amt = float(order.get('vat_amount', 0.0))
    gross_amt = max(0.0, subtotal - discount)
    net_amt = max(0.0, gross_amt - vat_amt)
    
    buf.extend(format_row(f"{total_qty} ITEM(S)", f"\xa3{subtotal:.2f}", LINE_WIDTH).encode('latin-1', 'replace') + b"\n")
    if discount > 0:
        coupon = order.get('coupon_code')
        disc_label = f"DISCOUNT ({coupon})" if coupon else "DISCOUNT"
        buf.extend(format_row(disc_label, f"-\xa3{discount:.2f}", LINE_WIDTH).encode('latin-1', 'replace') + b"\n")
        
    buf.extend(divider.encode('ascii'))
    
    # 7. Total Amount Due (Bold, Double Height)
    buf.extend(BOLD_ON)
    buf.extend(format_row("AMOUNT DUE", f"\xa3{total_due:.2f}", LINE_WIDTH).encode('latin-1', 'replace') + b"\n")
    buf.extend(BOLD_OFF)
    buf.extend(divider.encode('ascii'))
    
    # 8. 4-Column VAT Breakdown
    buf.extend(BOLD_ON)
    vat_hdr = f"{'Rate':<8}{'Net':>12}{'Tax':>12}{'Gross':>16}"
    buf.extend(vat_hdr.encode('ascii') + b"\n")
    buf.extend(BOLD_OFF)
    vat_row = f"{'20%':<8}{f'\xa3{net_amt:.2f}':>12}{f'\xa3{vat_amt:.2f}':>12}{f'\xa3{gross_amt:.2f}':>16}"
    buf.extend(vat_row.encode('latin-1', 'replace') + b"\n")
    buf.extend(divider.encode('ascii'))
    
    # 9. Legal & Thank you footer
    buf.extend(ALIGN_CENTER)
    buf.extend(b"Tax is included in the Gross amount!\n")
    buf.extend(BOLD_ON + b"VAT NO: 525 5772 74\n" + BOLD_OFF)
    buf.extend(b"\nThank you for your order!\nWe hope to serve you again.\n")
    
    # 10. Feed 3 lines & Partial Autocut
    buf.extend(FEED_3_LINES)
    buf.extend(PARTIAL_CUT)
    
    return bytes(buf)

class PosPrintHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean custom logger
        print(f"[POS Agent] {self.address_string()} - {format % args}")

    def _send_cors_headers(self):
        origin = self.headers.get('Origin', '')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-POS-Auth')
        self.send_header('Access-Control-Allow-Private-Network', 'true')
        self.send_header('Access-Control-Max-Age', '86400')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        # Health check
        if self.path == '/' or self.path == '/status':
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            status_payload = {
                "status": "online",
                "service": "patty-pos-print-agent",
                "version": "1.0.0",
                "printer_target": os.environ.get("POS_PRINTER_NAME", "NetumScan NS-8360LW"),
                "paper_width": "80mm",
                "effective_width": "72mm (576 dots / 48 cols)",
                "transport": "Win32 RAW Spooler (winspool.drv)"
            }
            self.wfile.write(json.dumps(status_payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != '/print-receipt' and self.path != '/test-print':
            self.send_response(404)
            self.end_headers()
            return

        # 1. Validate X-POS-Auth token if POS_AUTH_TOKEN is configured
        if POS_AUTH_TOKEN:
            auth_header = self.headers.get('X-POS-Auth', '').strip()
            if not auth_header or not hmac.compare_digest(auth_header, POS_AUTH_TOKEN):
                self.send_response(401)
                self._send_cors_headers()
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Unauthorized POS Print Request"}).encode('utf-8'))
                return

        # 2. Limit payload size to 64KB
        content_len = int(self.headers.get('Content-Length', 0))
        if content_len > 65536:
            self.send_response(413)
            self.end_headers()
            return

        body = self.rfile.read(content_len).decode('utf-8', errors='replace')
        try:
            order_data = json.loads(body)
        except Exception as err:
            self.send_response(400)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {err}"}).encode('utf-8'))
            return

        # 3. Build ESC/POS bytes
        try:
            escpos_bytes = build_escpos_receipt(order_data)
        except Exception as err:
            self.send_response(500)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"ESC/POS generation failed: {err}"}).encode('utf-8'))
            return

        # 4. Send to Windows Spooler API
        printer_target = os.environ.get("POS_PRINTER_NAME", "NetumScan NS-8360LW")
        success = print_raw_bytes_winspool(printer_target, escpos_bytes, f"Order {order_data.get('order_number', '')}")
        
        print(f"[POS Agent] Dispatched {len(escpos_bytes)} ESC/POS bytes for Order #{order_data.get('order_number')} (Spool Success: {success})")
        
        self.send_response(200 if success else 500)
        self._send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response_payload = {
            "status": "ok" if success else "spool_error",
            "order_number": order_data.get('order_number'),
            "bytes_generated": len(escpos_bytes),
            "target": printer_target
        }
        self.wfile.write(json.dumps(response_payload).encode('utf-8'))

def run_server():
    server_address = ('127.0.0.1', PORT)
    httpd = http.server.HTTPServer(server_address, PosPrintHandler)
    print(f"============================================================")
    print(f"  Patty Project POS Print Agent for NetumScan NS-8360LW     ")
    print(f"  Listening exclusively on: http://127.0.0.1:{PORT}         ")
    print(f"  Spool Transport: Windows RAW Spooler (winspool.drv)       ")
    print(f"  ESC/POS Format: 48 Cols (72mm active on 80mm roll)        ")
    print(f"============================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping POS Print Agent.")
        httpd.server_close()

if __name__ == '__main__':
    run_server()
