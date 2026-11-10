# FrigoLab · Diagnostic frigorifique

Application locale inspirée du parcours de diagnostic de Frigobase. Elle analyse des relevés saisis à la main, affiche les calculs et propose une hypothèse argumentée ou la prochaine mesure pour départager les pannes.

## Démarrer sous Windows

Décompresser l’archive et ouvrir PowerShell dans le dossier FrigoLab. Avec Python 3.11 ou 3.12 installé, lancer les commandes suivantes.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Ouvrir http://localhost:8501 si le navigateur ne s’ouvre pas.

1. Ouvrir **Paramètres du circuit** pour sélectionner le fluide, le mode de saisie et les conditions d’exploitation.
2. Cliquer sur les composants du synoptique, renseigner les mesures disponibles et enregistrer chaque groupe de relevés.
3. Cliquer sur **Analyser les relevés** pour afficher le diagnostic, le prochain contrôle et les calculs.

## Relevés et interprétation

- Indiquer le fluide réel. Saisir les paliers en degrés Celsius ou les pressions en bar. Pour des pressions manométriques, renseigner la pression atmosphérique locale.
- Les pressions sont converties en bar absolus puis en pascals pour CoolProp. Le moteur utilise la rosée pour la surchauffe et la bulle pour le sous-refroidissement.
- Mesurer le frigorigène en sortie d’évaporateur, le liquide en sortie de condenseur **avant le déshydrateur** et les températures d’air à l’entrée. Les sorties d’air, les deux températures au déshydrateur et le test à l’équilibre complètent l’analyse.
- Une case vide demeure une donnée manquante. Le mode froid stabilisé et l’insuffisance de production de froid doivent être confirmés pour appliquer les règles.
- Le profil est pédagogique et couvre la climatisation air-air. Les repères de froid commercial, les systèmes complexes et les conclusions terrain demandent un profil et une validation adaptés.

## Moteur et provenance

`diagnostic_rules.py` expose `Readings`, `calculate()` et `diagnose()`. Les indicateurs contiennent leur valeur, leur unité et leur formule. Le résultat contient l’état de la décision, les hypothèses et le prochain contrôle. Cette séparation permet une intégration au moteur existant.

Repères de cours issus d’*Installations frigorifiques*, p. 18, 24 et 31–33 du PDF, et des *Méthodes de diagnostic des pannes des installations frigorifiques*, p. 3–40 et arbre récapitulatif p. 42. Les tests automatisés utilisent des relevés fictifs pour vérifier les signatures du cours. Les seuils de 2 K pour la chute au déshydrateur et de 0,3 bar pour le test à l’équilibre sont des choix provisoires du prototype. Une température stable au filtre ne prouve pas que toute la ligne est libre. Le test à l’équilibre est limité aux fluides purs et suppose la coexistence du liquide et de la vapeur.

## Vérifier

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```
