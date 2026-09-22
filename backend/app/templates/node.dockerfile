FROM node:22-alpine

WORKDIR /app

COPY package*.json ./

RUN npm install

COPY . .

# Sécurité : passage sur l'utilisateur non-root intégré à l'image officiel Node
USER node

EXPOSE 3000

# Commande d'exécution conventionnelle
CMD ["npm", "start"]

# Il n'a pas besoin de savoir si le fichier d'entrée s'appelle index.js,
# server.js ou app.js.
# Il fonctionne aussi bien pour un projet pur JS que pour un projet 
# TypeScript compilé (ex: "start": "node dist/main.js") ou un framework 
# comme Next.js ("start": "next start").