FROM node:18-alpine
WORKDIR /app
COPY front/package.json package-lock.json* ./
RUN npm install
COPY front .
EXPOSE 5173
CMD ["npm", "run", "dev"]
