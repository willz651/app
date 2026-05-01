#!/usr/bin/env python3
import json
import os
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, quote

HOST = os.environ.get("APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("APP_PORT", "8080"))
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", f"http://localhost:{PORT}")

# Configure ethernet printers as host:port pairs (default port 9100)
# Example: PRINTERS="192.168.1.50:9100,192.168.1.51:9100"
PRINTERS = []
for item in os.environ.get("PRINTERS", "").split(","):
    item = item.strip()
    if not item:
        continue
    if ":" in item:
        h, p = item.split(":", 1)
        PRINTERS.append((h.strip(), int(p)))
    else:
        PRINTERS.append((item, 9100))

MENU = [
    {"id": "burger", "name": "Classic Burger", "price": 10.99},
    {"id": "fries", "name": "Fries", "price": 3.49},
    {"id": "salad", "name": "Garden Salad", "price": 6.99},
    {"id": "soda", "name": "Soda", "price": 2.49},
]

ORDERS = []
LOCK = threading.Lock()


def print_to_printer(order):
    lines = [
        "\n\n=== NEW ORDER ===",
        f"Order #: {order['id']}",
        f"Time: {order['time']}",
        f"Name: {order['customer']}",
        "Items:",
    ]
    for item in order["items"]:
        lines.append(f" - {item['qty']}x {item['name']} (${item['line_total']:.2f})")
    lines.extend([
        f"Total: ${order['total']:.2f}",
        "=================\n\n\n"
    ])
    payload = "\n".join(lines).encode("utf-8", errors="replace")

    failures = []
    for host, port in PRINTERS:
        try:
            with socket.create_connection((host, port), timeout=3) as s:
                s.sendall(payload)
        except Exception as e:
            failures.append(f"{host}:{port} ({e})")
    return failures


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, body, content_type="text/html; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, obj):
        self._send(status, json.dumps(obj), "application/json; charset=utf-8")

    def do_GET(self):
        p = urlparse(self.path)
        if p.path == "/":
            menu_html = "".join(
                f"<label><input type='number' min='0' value='0' name='{m['id']}' /> {m['name']} - ${m['price']:.2f}</label><br/>"
                for m in MENU
            )
            html = f"""<!doctype html><html><head><title>Menu</title></head><body>
<h1>Restaurant Menu</h1>
<form method='post' action='/order'>
  <label>Name: <input name='customer' required /></label><br/><br/>
  {menu_html}<br/>
  <button type='submit'>Place Order</button>
</form>
<p><a href='/admin'>View Orders</a></p>
</body></html>"""
            return self._send(200, html)
        if p.path == "/qr":
            target = f"{PUBLIC_BASE_URL}/"
            qr_url = f"https://chart.googleapis.com/chart?cht=qr&chs=300x300&chl={quote(target)}"
            html = f"""<!doctype html><html><body>
<h1>Scan to Order</h1>
<p>Point customer phones at this code:</p>
<img alt='QR code for menu' src='{qr_url}' />
<p>Menu URL: <a href='{target}'>{target}</a></p>
</body></html>"""
            return self._send(200, html)
        if p.path == "/admin":
            with LOCK:
                rows = "".join(
                    f"<tr><td>{o['id']}</td><td>{o['time']}</td><td>{o['customer']}</td><td>${o['total']:.2f}</td></tr>"
                    for o in reversed(ORDERS)
                )
            return self._send(200, f"<html><body><h1>Orders</h1><table border='1'><tr><th>ID</th><th>Time</th><th>Name</th><th>Total</th></tr>{rows}</table></body></html>")
        self._send(404, "Not Found", "text/plain")

    def do_POST(self):
        p = urlparse(self.path)
        if p.path != "/order":
            return self._send(404, "Not Found", "text/plain")
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        form = parse_qs(body)

        customer = (form.get("customer", ["Guest"])[0] or "Guest").strip()
        items = []
        total = 0.0
        for m in MENU:
            try:
                qty = int(form.get(m["id"], ["0"])[0])
            except ValueError:
                qty = 0
            if qty > 0:
                line_total = qty * m["price"]
                total += line_total
                items.append({"id": m["id"], "name": m["name"], "qty": qty, "line_total": line_total})

        if not items:
            return self._send(400, "Please select at least one item.")

        with LOCK:
            order_id = len(ORDERS) + 1
            order = {
                "id": order_id,
                "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
                "customer": customer,
                "items": items,
                "total": round(total, 2)
            }
            ORDERS.append(order)

        failures = print_to_printer(order)
        printer_msg = ""
        if not PRINTERS:
            printer_msg = "<p><strong>Note:</strong> No printers configured. Set PRINTERS env variable.</p>"
        elif failures:
            printer_msg = "<p><strong>Printer errors:</strong> " + "; ".join(failures) + "</p>"
        else:
            printer_msg = "<p>Sent to ethernet printer(s).</p>"

        self._send(200, f"<html><body><h1>Order Received</h1><p>Order #{order_id} total: ${order['total']:.2f}</p>{printer_msg}<p><a href='/'>Back to Menu</a></p></body></html>")


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Running on {HOST}:{PORT}")
    print(f"Menu: {PUBLIC_BASE_URL}/")
    print(f"QR page: {PUBLIC_BASE_URL}/qr")
    server.serve_forever()
