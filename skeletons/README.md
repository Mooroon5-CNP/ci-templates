# skeletons — squelettes d'applications CNP

Squelettes minimaux utilisés par le **CNP Portal** quand un utilisateur choisit
« Créer un nouveau dépôt » dans *Déploiements → Nouveau déploiement*.

```
skeletons/
├── _common/        ← fichiers ajoutés à tous les squelettes (README.md…)
├── node/
├── python/
├── go/
├── java/
├── cpp/
└── fullstack/      ← web/ (node) + api/ (python), une seule image
```

Le portail pousse `_common/` puis `<langage>/` dans le nouveau dépôt
(`<langage>/` l'emporte en cas de fichier commun), crée les branches `main` et
`prod`, puis lance l'onboarding habituel. Le portail lit ces fichiers sur la
branche `main` de ce dépôt (même principe que `pipeline.yml@main`).

## Jetons de substitution

| Jeton | Remplacé par |
|---|---|
| `{{APP_NAME}}` | nom de l'application saisi dans le formulaire |
| `{{APP_PORT}}` | port applicatif saisi dans le formulaire |

Aucun autre jeton n'est supporté. Pour tester un squelette en local, remplacez
les deux jetons (`sed -i 's/{{APP_NAME}}/demo/g; s/{{APP_PORT}}/8080/g'`).

## Règles

- **Pas de `.github/workflows/`** dans un squelette : `ci.yml` est posé par l'onboarding du portail (une seule source de vérité).
- Pas de secret, pas de `node_modules`, pas d'artefact de build.
- Chaque squelette doit passer lint, tests, Hadolint, Gitleaks et Trivy du pipeline.
- `/healthz` et `/ready` répondent `200` sur le port `PORT`.
- Un seul niveau de dossiers de premier niveau pour les monorepos (voir README principal, section 9).

## Vérifier un squelette

`python skeletons/verify.py [langage ...] [--port 9090] [--log FICHIER] [--no-scan]` (Docker requis) rend chaque squelette puis
rejoue ce que fait le pipeline sur un dépôt applicatif : le vrai script `detect-stack` de `pipeline.yml`, lint, hadolint,
tests, Gitleaks, Trivy fs, puis `docker build`, démarrage de l'image (`/healthz`, `/ready`, `/`, utilisateur non-root)
et Trivy image. Les tests statiques (`tests/test_skeletons.py`) tournent dans le CI de ce dépôt ; `verify.py` est
à lancer avant de modifier ou d'ajouter un squelette.
