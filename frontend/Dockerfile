FROM node:22

WORKDIR /app
RUN corepack enable && corepack prepare yarn@1.22.22 --activate

COPY package.json yarn.lock ./
RUN yarn install --frozen-lockfile

EXPOSE 3000
CMD ["yarn", "start"]
