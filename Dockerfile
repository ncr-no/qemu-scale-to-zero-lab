ARG CADDY_VERSION=2.8.4
FROM repository.ncr.ntnu.no/caddy:${CADDY_VERSION}-builder AS builder

RUN xcaddy build \
    --with github.com/sablierapp/sablier/plugins/caddy

FROM repository.ncr.ntnu.no/caddy:${CADDY_VERSION}

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
