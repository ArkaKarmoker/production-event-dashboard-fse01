FROM node:20-alpine

WORKDIR /app

# Copy dependency files
COPY package*.json ./
RUN npm install

# Copy source files
COPY . .

# Expose port
EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["npm", "run", "dev", "--", "-H", "0.0.0.0"]
