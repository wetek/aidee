# Tailscale phone access

Tailscale is Aidee's recommended first option for opening a loopback-bound dashboard from a phone. It keeps the dashboard inside a private tailnet and does not require a domain or public firewall port.

## Open from a phone

Give these steps to the owner after the server is on the tailnet and the dashboard URL is an `https://<device>.<tailnet>.ts.net` address. Do not send host install commands.

1. Install the Tailscale app on your phone.
2. Sign in with the same email you used to approve the server.
3. Turn the Tailscale VPN on. Wait until the app shows connected.
4. Open the dashboard from the Telegram bot menu button.
5. If the dashboard asks you to sign in, use the dashboard username and password from host setup.

The page will not load if the VPN is off. A browser on a network outside the tailnet cannot open the URL.

## Limits

As of September 2026, Tailscale's free Personal plan includes:

- Up to 6 users.
- Unlimited user devices.
- Up to 50 tagged resources.
- Up to 3 access-control groups.

The Personal plan is intended for non-commercial use. Check current terms before using it for company or client work. Paid plans use per-user pricing.

## Install

Run the reviewed Aidee installer:

~~~bash
sudo /opt/aidee/source/platform/scripts/install-tailscale.sh
~~~

The script installs Tailscale from its official stable Apt repository. It does not authenticate the server.

## Authenticate

Run:

~~~bash
sudo tailscale up
~~~

Open the displayed authorization URL yourself and approve the server. Do not send that URL or an auth key through chat.

Then follow [Open from a phone](#open-from-a-phone).

## Publish the controller dashboard privately

Keep Hermes bound to `127.0.0.1:9119`, then run:

~~~bash
sudo tailscale serve --bg 9119
sudo tailscale serve status
~~~

Tailscale may ask you to enable HTTPS certificates through a web consent page. The command prints a private `https://<device>.<tailnet>.ts.net` URL. Only devices and users allowed by the tailnet policy can open it.

Set that exact HTTPS origin as Hermes `dashboard.public_url` (or `HERMES_DASHBOARD_PUBLIC_URL`) and configure a dashboard login before the owner opens it. Without those, Hermes rejects the Serve hostname with `Invalid Host header`.

Do not use Tailscale Funnel. Funnel publishes the service to the public internet.

## Validate

1. Disable Wi-Fi on the phone to test a real remote path.
2. Confirm the Tailscale app shows connected.
3. Open the private HTTPS dashboard URL.
4. Confirm the dashboard loads and the gateway remains healthy.
5. Confirm port 9119 is still closed in the VPS provider firewall.

Remove the proxy with:

~~~bash
sudo tailscale serve reset
~~~
