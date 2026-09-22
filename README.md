# 🚀 ValaDeploy

> **ValaDeploy — Internal Developer Platform (IDP) On-Premise**

ValaDeploy est une **Internal Developer Platform (IDP) On-Premise** conçue pour simplifier le déploiement d'applications conteneurisées.

L'objectif est d'abstraire une partie de la complexité liée à **Docker, au réseau, au reverse proxy, aux variables d'environnement et aux contrôles de sécurité**, afin qu'un développeur puisse déployer une application sans avoir à gérer manuellement toute l'infrastructure sous-jacente.

Le projet s'appuie sur **Docker comme moteur d'exécution** et sur **Traefik comme reverse proxy**, avec une API FastAPI permettant d'automatiser le cycle de vie des applications.

---

## 📌 Pourquoi ValaDeploy ?

Dans une infrastructure traditionnelle, même une application relativement simple peut nécessiter plusieurs opérations :

```text
Clone du dépôt
      ↓
Identifier le type d'application
      ↓
Préparer le build
      ↓
Créer / adapter le Dockerfile
      ↓
Construire l'image
      ↓
Scanner l'image et le code
      ↓
Créer le réseau
      ↓
Créer le conteneur
      ↓
Configurer les volumes
      ↓
Configurer le reverse proxy
      ↓
Configurer les variables d'environnement
      ↓
Déployer
```

ValaDeploy cherche à regrouper ces opérations derrière une interface et une API uniques.

L'utilisateur fournit principalement les informations nécessaires à son projet, notamment le ou les dépôts Git, tandis que ValaDeploy automatise les opérations d'infrastructure nécessaires au déploiement.

---

# ✨ Fonctionnalités

## 📦 Déploiement depuis Git

ValaDeploy permet de déployer une application directement depuis un dépôt Git.

Le workflow actuel est :

```text
URL Git
   │
   ▼
Clone du repository
   │
   ▼
Détection du framework
   │
   ▼
Préparation du build
   │
   ▼
Génération du Dockerfile
   │
   ▼
Build de l'image Docker
```

La détection automatique prend actuellement en charge certains frameworks et types d'applications.

---

## 🐳 Build et déploiement Docker

ValaDeploy utilise le **Docker SDK for Python** pour automatiser les opérations Docker.

Le backend peut notamment gérer :

* création des images ;
* création des conteneurs ;
* configuration des réseaux ;
* montage des volumes ;
* démarrage et arrêt des conteneurs ;
* suppression des ressources ;
* gestion du cycle de vie des déploiements.

L'objectif est de ne pas demander à l'utilisateur de manipuler directement les commandes Docker pour les opérations courantes.

---

## 🛡️ DevSecOps intégré

La sécurité est intégrée directement dans le workflow de déploiement.

Le pipeline actuel suit cette logique :

```text
             Build
               │
               ▼
       ┌───────────────┐
       │ Security Scan │
       └───────┬───────┘
               │
        ┌──────┴──────┐
        ▼             ▼
      Trivy        Gitleaks
        │             │
        └──────┬──────┘
               ▼
         Security Report
               │
               ▼
       Security Decision
          │          │
          ▼          ▼
       BLOCK       ALLOW
          │          │
          │          ▼
          │       Deploy
          │
          ▼
       Stop
```

### Trivy

Trivy est utilisé pour analyser les vulnérabilités des images/conteneurs.

Un déploiement est bloqué lorsqu'une **vulnérabilité critique sans correctif disponible** est détectée.

Cela permet notamment d'éviter de considérer automatiquement toutes les vulnérabilités détectées comme bloquantes.

### Gitleaks

Gitleaks est utilisé pour rechercher des secrets potentiellement exposés dans le code source.

### Rapport de sécurité

Les résultats des analyses sont conservés et peuvent être consultés depuis l'interface ValaDeploy.

---

# 🌐 Réseau et routage

ValaDeploy utilise **Traefik** comme reverse proxy central.

Les requêtes destinées à ValaDeploy passent par le conteneur Traefik :

```text
                    Browser
                       │
                       ▼
                ┌────────────┐
                │   Traefik  │
                └─────┬──────┘
                      │
             ┌────────┴────────┐
             │                 │
             ▼                 ▼
          Frontend           Backend
             │
             │
             ▼
        Applications
```

Traefik permet également de router les requêtes vers les applications déployées en fonction de leur configuration et de leurs ports.

### Wildcard domain

Le projet prévoit l'utilisation de domaines de type :

```text
<application>.<server-ip>.sslip.io
```

afin de simplifier l'accès aux applications dans un environnement local.

> **Note :** le routage Traefik fonctionne actuellement, mais l'automatisation complète de la gestion DNS n'est pas encore implémentée.

---

# 🧩 Déploiement de projets et de stacks

ValaDeploy distingue deux concepts.

## Mono-project

Un seul dépôt Git correspond à une application.

Exemple :

```text
Git repository
      │
      ▼
   ValaDeploy
      │
      ▼
 Docker image
      │
      ▼
 Container
      │
      ▼
   Traefik
```

Le workflow complet de build, scan et déploiement est automatisé.

---

## Stack

Une stack ValaDeploy ne correspond pas à l'exécution directe d'un fichier `docker-compose.yml`.

L'utilisateur peut fournir plusieurs repositories correspondant aux différentes parties de son application.

Exemple :

```text
                 Application Stack
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    Frontend         Backend       Database
    Repository       Repository
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                Docker Network
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
          Front      Back        DB
```

ValaDeploy automatise alors notamment :

* la création et la liaison du réseau Docker ;
* la création des conteneurs ;
* les connexions entre services ;
* le montage des volumes ;
* le routage via Traefik ;
* la configuration nécessaire aux communications entre composants.

L'objectif est de permettre de déployer une architecture composée de plusieurs services sans demander à l'utilisateur de construire manuellement toute la configuration Docker.

---

# 📊 Metrics

ValaDeploy fournit actuellement des métriques d'utilisation des ressources des conteneurs en cours d'exécution.

Les métriques actuellement suivies sont notamment :

* utilisation CPU ;
* utilisation RAM.

Exemple :

```text
Container
   │
   ├── CPU usage
   │
   └── RAM usage
```

Ces données sont utilisées pour afficher l'utilisation des ressources directement dans l'interface ValaDeploy.

> Les métriques actuelles ne constituent pas encore une plateforme complète de monitoring telle que Prometheus/Grafana.

---

# 📜 Logs en temps réel

ValaDeploy permet de consulter les logs des conteneurs depuis l'interface Web.

La communication temps réel utilise **WebSocket**.

```text
Docker Container
       │
       │ logs
       ▼
logs_service
       │
       ▼
WebSocket
       │
       ▼
Frontend
       │
       ▼
Dashboard
```

Cela permet de suivre un déploiement ou le fonctionnement d'une application sans devoir ouvrir une session SSH sur le serveur.

---

# 🔐 Authentification et autorisation

Le backend dispose d'un système d'authentification avec :

* inscription ;
* connexion ;
* authentification JWT ;
* routes protégées ;
* gestion des rôles ;
* utilisateur `admin` ;
* utilisateur `dev`.

Les endpoints protégés utilisent le mécanisme de dépendances de FastAPI afin de récupérer et vérifier l'utilisateur authentifié.

---

# ⚙️ Variables d'environnement

ValaDeploy permet de gérer les variables d'environnement des applications déployées.

L'objectif est de permettre la configuration d'une application sans devoir modifier directement son code source ou se connecter manuellement au serveur.

Exemples :

```text
DATABASE_URL
API_URL
APP_ENV
SECRET_KEY
```

Ces variables peuvent ensuite être injectées dans le conteneur correspondant lors du déploiement.

---

# 🧹 Gestion du cycle de vie

ValaDeploy dispose de services permettant de gérer le cycle de vie des ressources Docker.

Cela comprend notamment :

* déploiement ;
* arrêt ;
* suppression ;
* nettoyage des ressources ;
* gestion des anciens déploiements ;
* conservation de l'historique.

---

# 🗂️ Historique des déploiements

Les déploiements sont enregistrés en base de données.

Cela permet de conserver un historique comprenant notamment les informations relatives aux différents runs de déploiement et à leur état.

L'interface fournit une vue permettant de consulter l'historique.

---

# 🏗️ Architecture

L'architecture globale actuelle est organisée autour de quatre composants principaux :

```text
                         ┌───────────────┐
                         │    Browser    │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │    Traefik    │
                         │ Reverse Proxy │
                         └───────┬───────┘
                                 │
                  ┌──────────────┴──────────────┐
                  │                             │
                  ▼                             ▼
          ┌───────────────┐             ┌───────────────┐
          │    Frontend   │             │    Backend     │
          │   HTML/CSS/JS │◄───────────►│    FastAPI     │
          └───────────────┘             └───────┬───────┘
                                               │
                         ┌─────────────────────┼────────────────────┐
                         │                     │                    │
                         ▼                     ▼                    ▼
                  ┌────────────┐        ┌────────────┐       ┌────────────┐
                  │ PostgreSQL │        │   Docker   │       │    Git     │
                  │            │        │    SDK     │       │ repositories│
                  └────────────┘        └──────┬─────┘       └────────────┘
                                               │
                                               ▼
                                      ┌─────────────────┐
                                      │ Applications    │
                                      │ déployées       │
                                      └────────┬────────┘
                                               │
                                               ▼
                                          ┌─────────┐
                                          │ Traefik │
                                          └─────────┘
```

Traefik constitue donc le point d'entrée HTTP principal.

Il route :

```text
/       → Frontend
/api    → Backend
/app    → Applications déployées
```

La règle de routage exacte des applications dépend de leur configuration et des ports exposés.

---

# 🔄 Workflow complet d'un déploiement

Le workflow principal de ValaDeploy est actuellement :

```text
┌──────────────────┐
│    Git URL       │
└────────┬─────────┘
         ▼
┌──────────────────┐
│   Git Clone      │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Framework        │
│ Detection        │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Build Preparation│
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Dockerfile       │
│ Generation       │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Docker Build     │
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Security Scans   │
│ Trivy + Gitleaks │
└────────┬─────────┘
         ▼
    ┌────┴────┐
    │         │
  BLOCK      ALLOW
    │         │
    │         ▼
    │  ┌───────────────┐
    │  │ Docker Deploy │
    │  └───────┬───────┘
    │          ▼
    │  ┌───────────────┐
    │  │ Network /     │
    │  │ Volumes       │
    │  └───────┬───────┘
    │          ▼
    │  ┌───────────────┐
    │  │    Traefik    │
    │  │    Routing    │
    │  └───────┬───────┘
    │          ▼
    │     Application
    │       running
    │
    ▼
Deployment stopped
```

---

# 🧰 Stack technique

## Backend

| Technologie           | Utilisation                   |
| --------------------- | ----------------------------- |
| Python 3.11+          | Langage principal             |
| FastAPI               | API et backend                |
| SQLAlchemy 2.x        | ORM                           |
| Pydantic 2.x          | Validation et schémas         |
| Alembic               | Migrations de base de données |
| PostgreSQL            | Base de données               |
| Docker SDK for Python | Gestion des ressources Docker |
| GitPython             | Gestion des repositories Git  |
| WebSocket             | Streaming temps réel          |
| JWT                   | Authentification              |
| Argon2id              | Hashage des mots de passe     |

## Frontend

| Technologie  | Utilisation                       |
| ------------ | --------------------------------- |
| HTML5        | Structure des pages               |
| CSS          | Styles                            |
| JavaScript   | Logique côté client et appels API |
| Tailwind CSS | Utilitaires CSS                   |
| WebSocket    | Logs temps réel                   |

## Infrastructure

| Technologie    | Utilisation                                |
| -------------- | ------------------------------------------ |
| Docker         | Conteneurisation et exécution              |
| Docker Compose | Déploiement de l'infrastructure ValaDeploy |
| Traefik        | Reverse proxy et routage                   |
| PostgreSQL     | Persistance                                |
| sslip.io       | Accès local basé sur l'adresse IP          |

## Sécurité

| Technologie | Utilisation                  |
| ----------- | ---------------------------- |
| Trivy       | Analyse des vulnérabilités   |
| Gitleaks    | Détection de secrets         |
| JWT         | Authentification             |
| Argon2id    | Protection des mots de passe |

---

# 📁 Structure du projet

```text
ValaDeploy/
│
├── backend/
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── requirements.txt
│   │
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── routes_auth.py
│   │   │   ├── routes_deployment.py
│   │   │   ├── routes_deploy.py
│   │   │   ├── routes_logs.py
│   │   │   ├── routes_metrics.py
│   │   │   ├── routes_projects.py
│   │   │   ├── routes_security.py
│   │   │   └── routes_stack.py
│   │   │
│   │   ├── core/
│   │   │   ├── boostrap.py
│   │   │   ├── config.py
│   │   │   ├── docker_client.py
│   │   │   ├── exceptions.py
│   │   │   └── security.py
│   │   │
│   │   ├── db/
│   │   │   ├── database.py
│   │   │   └── migrations/
│   │   │       └── versions/
│   │   │
│   │   ├── models/
│   │   │   ├── deployment.py
│   │   │   ├── project.py
│   │   │   └── user.py
│   │   │
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── deployment.py
│   │   │   ├── deploy.py
│   │   │   ├── metrics.py
│   │   │   └── stack_deploy.py
│   │   │
│   │   ├── services/
│   │   │   ├── auth_service.py
│   │   │   ├── build/
│   │   │   │   ├── builder.py
│   │   │   │   ├── detector.py
│   │   │   │   ├── generator.py
│   │   │   │   └── __init__.py
│   │   │   ├── build_preparation.py
│   │   │   ├── build_service.py
│   │   │   ├── cleanup_service.py
│   │   │   ├── container_service.py
│   │   │   ├── deploy_service.py
│   │   │   ├── env_var_service.py
│   │   │   ├── git_service.py
│   │   │   ├── logs_service.py
│   │   │   ├── metrics_service.py
│   │   │   ├── project_service.py
│   │   │   ├── scan_service.py
│   │   │   └── traefik_service.py
│   │   │
│   │   ├── templates/
│   │   │   ├── assets/
│   │   │   ├── laravel.dockerfile
│   │   │   ├── laravel_monolith.dockerfile
│   │   │   ├── node.dockerfile
│   │   │   ├── python.dockerfile
│   │   │   └── react_vite.dockerfile
│   │   │
│   │   └── websockets/
│   │       └── log_stream.py
│   │
│   ├── tests/
│   │   └── test_websocket.html
│   │
│   ├── test_network.py
│   ├── test_extra_network.py
│   └── test_stack.sh
│
├── frontend/
│   ├── assets/
│   │   └── images/
│   ├── components/
│   │   ├── confirm-modal.html
│   │   ├── sidebar.html
│   │   └── toast-container.html
│   │
│   ├── pages/
│   │   ├── account.html
│   │   ├── dashboard.html
│   │   ├── history.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── new-project.html
│   │   ├── new-stack.html
│   │   ├── pipeline.html
│   │   ├── project-detail.html
│   │   ├── register.html
│   │   ├── security.html
│   │   ├── security-details.html
│   │   └── stacks.html
│   │
│   ├── scripts/
│   │   ├── api/
│   │   └── *.js
│   │
│   └── styles/
│       ├── *.css
│       └── *.tailwind.config.js
│
├── infra/
│   ├── docker-compose.yml
│   └── traefik/
│       ├── dynamic_conf.yml
│       └── traefik.yml
│
└── README.md
```

---

# 🚀 Installation

## Prérequis

L'environnement d'exécution nécessite notamment :

* Docker Engine
* Docker Compose
* Git
* une machine Linux recommandée pour l'environnement On-Premise

Le backend et les composants d'infrastructure sont exécutés dans des conteneurs Docker.

---

## 1. Cloner le projet

```bash
git clone https://github.com/Dylan-Best/ValaDeploy.git
cd ValaDeploy
```

---

## 2. Démarrer l'infrastructure

L'ensemble de l'infrastructure principale est défini dans :

```text
infra/docker-compose.yml
```

Démarrer les services :

```bash
cd infra
docker compose up -d
```

Cette configuration démarre les quatre composants principaux :

```text
Traefik
Frontend
Backend
PostgreSQL
```

Vérifier l'état des conteneurs :

```bash
docker compose ps
```

Consulter les logs :

```bash
docker compose logs -f
```

---

# 🗄️ Base de données et migrations

ValaDeploy utilise **PostgreSQL** pour la persistance et **Alembic** pour gérer les migrations.

Les migrations sont situées dans :

```text
backend/app/db/migrations/
```

Les différentes versions du schéma sont conservées dans :

```text
backend/app/db/migrations/versions/
```

Avant toute modification importante du modèle de données, une nouvelle migration Alembic doit être créée.

Exemple :

```bash
alembic revision --autogenerate -m "description"
```

Puis :

```bash
alembic upgrade head
```

> Les commandes Alembic doivent être exécutées dans le contexte où les dépendances et la configuration du backend sont disponibles.

---

# 🖥️ Utilisation

Une fois l'infrastructure démarrée, l'utilisateur accède à l'interface Web de ValaDeploy via le point d'entrée Traefik configuré pour l'environnement.

Le workflow utilisateur principal est :

```text
Login
  │
  ▼
Dashboard
  │
  ├── Create Project
  │       │
  │       ▼
  │    Git URL
  │       │
  │       ▼
  │    Deploy
  │
  ├── Create Stack
  │
  ├── Deployment History
  │
  ├── Security Reports
  │
  └── Account
```

---

# 🔌 API

Le backend FastAPI est organisé par domaines fonctionnels.

```text
app/api/
│
├── routes_auth.py
├── routes_deployment.py
├── routes_deploy.py
├── routes_logs.py
├── routes_metrics.py
├── routes_projects.py
├── routes_security.py
└── routes_stack.py
```

Les principales catégories d'API sont :

| Module         | Responsabilité                              |
| -------------- | ------------------------------------------- |
| Authentication | Inscription, connexion, utilisateur courant |
| Projects       | Gestion des projets                         |
| Deployment     | Gestion des déploiements                    |
| Deploy         | Déclenchement des opérations de déploiement |
| Logs           | Accès aux logs                              |
| Metrics        | CPU / RAM des conteneurs                    |
| Security       | Résultats des scans                         |
| Stack          | Gestion des stacks multi-services           |

La documentation interactive FastAPI peut être utilisée pour explorer les endpoints lorsque le backend est démarré :

```text
/docs
```

et :

```text
/redoc
```

---

# 🔒 Architecture de sécurité

La sécurité est appliquée à plusieurs niveaux.

```text
                  User
                   │
                   ▼
             Authentication
                   │
                   ▼
                 JWT
                   │
                   ▼
            Protected API
                   │
                   ▼
             Deployment
                   │
                   ▼
        ┌────────────────────┐
        │ Security Pipeline  │
        ├────────────────────┤
        │ Trivy              │
        │ Gitleaks           │
        └─────────┬──────────┘
                  │
             Security check
                  │
          ┌───────┴────────┐
          ▼                ▼
        BLOCK             ALLOW
          │                │
          │                ▼
          │             Deploy
          │
          ▼
       Report
```

Le principe est de déplacer une partie des contrôles de sécurité **avant le déploiement**, plutôt que de les réaliser uniquement après mise en production.

---

# 🧪 Tests

Le backend contient également plusieurs éléments permettant de tester les fonctionnalités réseau et WebSocket.

Exemples :

```text
backend/test_network.py
backend/test_extra_network.py
backend/test_stack.sh
backend/tests/test_websocket.html
```

Ces tests servent notamment à vérifier les comportements liés :

* au réseau Docker ;
* aux communications entre conteneurs ;
* aux stacks ;
* au streaming WebSocket.

---

# 📈 État actuel du projet

ValaDeploy a dépassé le stade du simple MVP initial.

Les fonctionnalités actuellement opérationnelles comprennent notamment :

* [x] Authentification et inscription
* [x] JWT et routes protégées
* [x] Gestion des rôles
* [x] Gestion des projets
* [x] Clone Git
* [x] Détection de certains frameworks
* [x] Génération de Dockerfiles
* [x] Build Docker
* [x] Déploiement Docker
* [x] Gestion des variables d'environnement
* [x] Routage Traefik
* [x] Logs temps réel via WebSocket
* [x] Historique des déploiements
* [x] Trivy
* [x] Gitleaks
* [x] Rapports de sécurité
* [x] Metrics CPU / RAM des conteneurs
* [x] Gestion des volumes
* [x] Gestion du réseau entre services
* [x] Cleanup des ressources

### Fonctionnalités encore en évolution

* [ ] Automatisation complète du DNS
* [ ] Scaling plus avancé
* [ ] Amélioration du support multi-services
* [ ] Support de davantage de frameworks
* [ ] Amélioration de la gestion des environnements
* [ ] Renforcement de la gestion des secrets
* [ ] Monitoring plus avancé

---

# 🛣️ Roadmap

Les prochaines évolutions envisagées sont notamment :

### Build & deployment

* [ ] Support de nouveaux frameworks
* [ ] Amélioration de la détection automatique
* [ ] Optimisation des builds
* [ ] Meilleure gestion des erreurs de déploiement

### Networking

* [ ] Automatisation du DNS
* [ ] Amélioration du routage des applications
* [ ] Gestion réseau plus avancée pour les stacks

### Security

* [ ] Amélioration des rapports de sécurité
* [ ] Gestion plus avancée des secrets
* [ ] Renforcement des règles de blocage
* [ ] Extension des contrôles DevSecOps

### Scaling

* [ ] Amélioration du scaling manuel
* [ ] Gestion plus robuste des replicas
* [ ] Amélioration du load balancing
* [ ] Réflexion sur une architecture multi-nœuds

### Observability

* [ ] Métriques plus détaillées
* [ ] Historisation des métriques
* [ ] Monitoring plus complet
* [ ] Alerting

---

# ⚠️ Limitations actuelles

ValaDeploy est actuellement conçu comme une **plateforme On-Premise simplifiée**, et non comme un orchestrateur distribué complet.

Les principales limitations actuelles sont :

* le déploiement repose sur Docker ;
* le fonctionnement est principalement orienté vers un environnement mono-hôte ;
* le DNS n'est pas encore automatisé ;
* la détection automatique ne couvre pas tous les frameworks ;
* les métriques actuelles sont limitées au CPU et à la RAM des conteneurs en fonctionnement ;
* le scaling reste limité et principalement manuel ;
* une stack ValaDeploy ne correspond pas directement à l'exécution d'un fichier `docker-compose.yml` ;
* le support multi-nœuds n'est pas encore implémenté.

Ces limitations constituent également des axes d'évolution du projet.

---

# 🧠 Concepts importants

ValaDeploy repose sur une idée centrale :

> **Le développeur décrit ce qu'il veut déployer ; ValaDeploy s'occupe d'une partie de la complexité infrastructure nécessaire pour l'exécuter.**

L'architecture cherche donc à séparer :

```text
Developer
   │
   │ Application
   ▼
ValaDeploy
   │
   ├── Git
   ├── Build
   ├── Security
   ├── Docker
   ├── Network
   ├── Volumes
   ├── Traefik
   └── Logs / Metrics
          │
          ▼
     Infrastructure
```

L'objectif n'est pas de remplacer tous les outils d'infrastructure, mais de fournir une **couche d'abstraction simple au-dessus de Docker**.

---

# 🎓 Contexte du projet

ValaDeploy est développé comme un projet de **conception et développement d'une Internal Developer Platform On-Premise**.

Le projet explore notamment les problématiques suivantes :

* automatisation du déploiement ;
* conteneurisation ;
* gestion réseau ;
* reverse proxy ;
* sécurité intégrée au pipeline ;
* gestion du cycle de vie des conteneurs ;
* observabilité ;
* abstraction de l'infrastructure ;
* déploiement multi-services.

---

# 👤 Auteur

**Dylan-Best**

Conception & développement de ValaDeploy.

---

# 📄 Licence

Ce projet est distribué sous licence **MIT**.

Voir le fichier [`LICENSE`](LICENSE) pour plus d'informations.

---

<p align="center">
  <strong>ValaDeploy</strong><br>
  Internal Developer Platform — On-Premise
</p>
