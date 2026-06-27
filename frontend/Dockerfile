# Stage 1: Build the Angular application
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files first to leverage cache for dependencies
COPY package*.json ./

# Install dependencies (use npm ci for reliable builds)
RUN npm ci

# Copy the rest of the application source code
COPY . .

# Build the application for production (SSR enabled)
RUN npm run build

# Stage 2: Serve the application
FROM node:22-alpine

WORKDIR /app

# Copy package files to install production dependencies (if any are externalized)
COPY package*.json ./

# Install only production dependencies
RUN npm ci --omit=dev

# Copy built artifacts from the builder stage
# Adjust the path 'pickleball-league-app' based on your 'dist' folder structure found in angular.json/output
COPY --from=builder /app/dist ./dist

# Expose the port the app runs on (default 4000)
EXPOSE 4000

# Start the server
# Using the direct node command as typically defined in package.json for SSR
CMD ["node", "dist/pickleball-league-app/server/server.mjs"]
