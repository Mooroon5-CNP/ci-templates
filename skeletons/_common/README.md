# {{APP_NAME}}

Application créée depuis le CNP Portal à partir du squelette CNP. Elle suit le
contrat de la plateforme : le pipeline de `Mooroon5-CNP/ci-templates` la
construit, la teste, la scanne puis la déploie.

## Contrat plateforme

| Élément | Valeur |
|---|---|
| Port d'écoute | `{{APP_PORT}}` (variable d'environnement `PORT`, doit rester égal au port déclaré dans le portail et à `EXPOSE` du Dockerfile) |
| Liveness | `GET /healthz` → `200` |
| Readiness | `GET /ready` → `200` |
| Image | `Dockerfile` à la racine, utilisateur non-root (`USER 1000`), `HEALTHCHECK` |
| Pipeline | `.github/workflows/ci.yml`, **posé par le CNP Portal** : ne pas le supprimer |

## Branches

| Branche | Rôle |
|---|---|
| `main` | Développement : chaque push lance la CI puis déploie l'environnement `dev` |
| `prod` | Production : déploiement soumis à validation manuelle |

Travaillez sur une branche `feat/...`, ouvrez une pull request vers `main`,
puis promouvez vers `prod` par pull request `main` → `prod`.

## Bonnes pratiques

- Messages de commit au format *Conventional Commits* (`feat:`, `fix:`, `chore:`…).
- Lint et tests doivent passer en local avant de pousser (voir les commandes du langage).
- Aucun secret dans le dépôt : le pipeline exécute Gitleaks et échoue si un secret est détecté.
- Les dépendances sont scannées (Trivy) : une CVE critique bloque le déploiement.
- Le Dockerfile est vérifié par Hadolint : image de base épinglée, utilisateur non-root.
- Logs structurés sur la sortie standard ; `LOG_LEVEL`, `DD_ENV`, `DD_SERVICE`
  et `DD_VERSION` sont injectés par la plateforme.

## Structure du dépôt

Un seul langage : fichier marqueur à la **racine**. Plusieurs parties (ex. front + back) :
chacune dans son **propre dossier de premier niveau**, avec son fichier marqueur
(`package.json`, `requirements.txt`, `go.mod`, `pom.xml`, `CMakeLists.txt`).
Un dossier imbriqué plus profond n'est pas détecté par la CI.
