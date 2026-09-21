# Build context is the repository root, so paths below start from there.

# --- Stage 1: install packages -------------------------------------------
# A small Linux base with Node. "AS deps" names the stage so later stages
# can copy out of it. This stage is thrown away.
FROM node:20-alpine AS deps

# Folder to work in. Created if missing.
WORKDIR /app

# Only the package files, so this install layer stays cached when you edit
# a component. Copying the source first would reinstall on every change.
COPY web/package.json web/package-lock.json ./

# ci installs strictly from the lockfile and never updates it, unlike
# install. That is what makes the build reproducible.
RUN npm ci


# --- Stage 2: compile the app --------------------------------------------
# A new FROM means a fresh empty image. Nothing carries over automatically.
FROM node:20-alpine AS builder
WORKDIR /app

# Reach into the previous stage for the installed packages instead of
# installing them again.
COPY --from=deps /app/node_modules ./node_modules

# Now the source code.
COPY web/ .

# The API address is baked into the JavaScript bundle at build time, not
# read at runtime. ARG is the value you pass with --build-arg, defaulting
# to localhost so local builds work. ENV makes it visible to npm, which
# cannot see ARG on its own.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Produces .next/standalone, a self-contained server, because next.config
# sets output: "standalone".
RUN npm run build


# --- Stage 3: run it -----------------------------------------------------
# The only stage that becomes the final image. Everything above is dropped,
# so no source code, no compiler, no full node_modules.
FROM node:20-alpine AS runner
WORKDIR /app

# production turns off Next's development behaviour. HOSTNAME 0.0.0.0 is
# the important one: the server binds to localhost otherwise, and nothing
# outside the container could reach it.
ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Node images run as root by default. Create an unprivileged account so a
# compromise lands somewhere with no permissions.
RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001

# The compiled server, plus only the packages it actually reaches.
# --chown hands ownership to the new user, who otherwise could not read it.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Standalone mode leaves the CSS and fonts out, so they are copied
# separately. Skip this line and the page loads unstyled.
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# Standalone mode leaves public/ out too. It holds the PDF.js worker, which
# the build script copies in, and without it the viewer never renders a page.
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Everything from here runs unprivileged.
USER nextjs

# Documentation only. No runtime effect.
EXPOSE 3000

# Standalone produced a plain Node script, so there is no npm project here
# to run "npm start" from.
CMD ["node", "server.js"]
