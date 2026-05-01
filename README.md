# QR Menu Ordering App

A simple food ordering web app where customers scan a QR code, browse your menu, place an order, and the order is sent to your ethernet receipt printer(s).

## Run

```bash
python3 app.py
```

Then open:
- Menu: `http://localhost:8080/`
- QR code page: `http://localhost:8080/qr`
- Orders admin: `http://localhost:8080/admin`

## Configure for real usage

Set environment variables before running:

- `PUBLIC_BASE_URL` - your public URL customers can access (for QR link), e.g. `https://order.mystore.com`
- `PRINTERS` - comma-separated ethernet printers in `ip:port` format (port usually `9100`), e.g.:

```bash
export PUBLIC_BASE_URL="https://order.mystore.com"
export PRINTERS="192.168.1.50:9100,192.168.1.51:9100"
python3 app.py
```

## Notes

- The app uses direct TCP socket printing to network printers.
- Keep the server on the same network as your printers.
- This is intentionally simple; production improvements would include auth, payment, database, kitchen routing, and menu management UI.
