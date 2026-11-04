**Objet : CrewSim – retour sur les données réelles Air Transat (corrections à faire dans les scripts d'extraction)**

**Pièces jointes :** `pierre_analyse_donnees_reelles.pdf`, `verifier_corpus.py`

Bonjour Pierre,

Merci beaucoup pour l'envoi des données réelles, c'est un très bon début ! J'ai tout analysé avec le chargeur (loader) de CrewSim, en comparant fichier par fichier avec notre corpus de test (mock).

Le résultat : **pour l'instant, on ne peut pas encore injecter les données dans CrewSim.**
- 5 fichiers sont refusés par le chargeur, et 2 fichiers manquent.
- Plusieurs fichiers qui se chargent contiennent des valeurs générées (des « placeholders »), et pas les vraies valeurs. Le simulateur donnerait alors des résultats faux sans aucun message d'erreur.

**Merci de regarder la pièce jointe pour l'analyse détaillée.** Le PDF donne, pour chaque fichier, les colonnes attendues, le problème constaté (avec des exemples et des chiffres) et la correction à faire. Tu peux le donner directement à Claude pour corriger les scripts à la source.

Les points les plus importants :
1. **D2 (plannings)** : tous les blocs durent 0 minute (début = fin à minuit), et il n'y a aucun bloc `RESERVE`. C'est le fichier le plus important pour le simulateur.
2. **Période** : plannings et absences sur seulement 3 mois (juin–août 2026). Il faudrait idéalement 36 mois (août 2023 – juillet 2026), ou au minimum 24 mois avec deux hivers complets.
3. **Vie privée (Loi 25)** : les `crew_id` sont les vrais matricules, et D10 contient les noms des passagers. Il faut pseudonymiser les `crew_id` (le même pseudonyme dans tous les fichiers) et supprimer les noms.
4. **Heures** : D3 et D8 ont des heures sans date, parfois négatives. Dans D4 et D5, les heures sont générées (toujours 12:00, 00:00, 02:30).
5. **D7 (paie)** : les codes `CHV` et `DOUBLE_TIME` ne permettent pas de retrouver les primes de draft et de réserve.

Le script `verifier_corpus.py` (Python standard, rien à installer) vérifie les fichiers. Il suffit de le lancer dans le dossier des CSV avec `python verifier_corpus.py` : il doit afficher `OK` pour chaque fichier avant l'envoi.

J'ai aussi quelques questions rapides :
1. Les heures `*_local` de D3 et D8 : heure locale **de l'aéroport du segment**, ou de la base ?
2. Que veut dire `CHV` dans D7 ?
3. ~~Comment est calculé `disruption_class` (D9) ?~~ Plus nécessaire : le régime est maintenant calculé par un modèle de Markov caché à partir de D8/D4/D2. À la place : avez-vous un journal des perturbations (météo / ATC / IROPS) pour contrôler nos étiquettes ?
4. `absence_end` (D4) : inclusive ou exclusive ?
5. Que sont `L15` et `W7S8` (D1) ?
6. Peut-on avoir 36 mois d'historique (août 2023 à juillet 2026) ?

Si c'est plus simple, on peut faire un appel de 30 minutes pour passer les questions ensemble. Encore merci pour ce gros travail, on est vraiment proches !

Bonne journée,
[Ton prénom]
