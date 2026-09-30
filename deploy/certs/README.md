# Private CA Certificates

RadiusDeck should stay behind a reverse proxy. TLS certificates and private
keys should be mounted only into that reverse proxy container, not into the
RadiusDeck application container.

## Private CA / Corporate CA

Recommended for production private networks:

- issue `radiusdeck.crt` and `radiusdeck.key` from your internal CA;
- include a Subject Alternative Name matching the RadiusDeck hostname;
- mount cert/key only into the reverse proxy container;
- set `APP_PUBLIC_URL` to the HTTPS URL.

## Caddy Internal CA

Caddy can issue certificates from its internal CA with `tls internal`.
Client browsers and API clients must trust the Caddy internal root CA before
the browser warning disappears.

## Lab Self-Signed Certificate

For local testing, generate a single self-signed certificate with a Subject
Alternative Name:

```bash
openssl req -x509 -newkey rsa:4096 -sha256 -days 365 -nodes \
  -keyout radiusdeck.key \
  -out radiusdeck.crt \
  -subj "/CN=radiusdeck.local" \
  -addext "subjectAltName=DNS:radiusdeck.local,IP:192.168.1.10"
```

A single self-signed server certificate will trigger browser warnings unless
the certificate or CA is trusted by the client. Prefer a private CA for shared
internal deployments.
