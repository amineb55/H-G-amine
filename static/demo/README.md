# Exemple de démonstration

`chantier-exemple.jpg` est la photo chargée par le bouton « Essayer avec un
exemple » de la page d'accueil, pour qu'un visiteur puisse tester le service
sans fournir sa propre image.

Le fichier doit être un **JPEG réel** : la page l'envoie en déclarant
`image/jpeg`, et le moteur d'analyse reçoit ce type. Un fichier PNG renommé en
`.jpg` déclarerait un type qui ne correspond pas à son contenu.

Pour le remplacer, gardez le même nom et le même emplacement — aucun
changement de code n'est nécessaire :

```bash
python - <<'PY'
from PIL import Image
Image.open("votre-photo.png").convert("RGB").save(
    "static/demo/chantier-exemple.jpg", format="JPEG", quality=90, optimize=True)
PY
```
