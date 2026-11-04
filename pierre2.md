Objet : CrewSim – données v2 : ce qui manque encore avant l'intégration

Bonjour Pierre,

Merci beaucoup pour le nouvel envoi et pour tes notes. J'ai passé les 11 fichiers dans le chargeur de CrewSim et dans nos contrôles de qualité. C'est une grosse amélioration par rapport au premier envoi.

## Ce qui est bon maintenant

- **Les vrais drafts sont bien dans D6** : 3 127 lignes `reason_code = DRAFT`, pour 526 pilotes. Le statut avant le draft est cohérent (2 701 depuis un jour off, 343 depuis une rotation, le reste depuis réserve, vacances ou formation). C'est exactement ce qu'il nous fallait.
- **Les `crew_id` sont pseudonymisés** (format `P######`), et pareils dans tous les fichiers. Tous les `crew_id` existent dans D1.
- **Tous les `pairing_id` existent dans D3** (sauf 4 dans D4).
- **Les heures UTC / locales sont cohérentes** (−4 h / −5 h avec le changement d'heure), et il n'y a pas de bloc qui finit avant de commencer.
- **Aucune colonne avec des données personnelles.**
- **D9 n'est plus nécessaire** : on calcule maintenant le niveau de perturbation nous-mêmes, avec un modèle de Markov caché (HMM) à partir des autres fichiers. Tu n'as rien à extraire pour D9.

## Ce qui bloque encore l'intégration

**1. La période est trop courte.**
Tous les fichiers couvrent seulement du 1er janvier au 26 août 2026 (8 mois). Pour la saison d'hiver, on a donc seulement janvier à avril 2026, un seul hiver incomplet. Il nous faut idéalement 36 mois (août 2023 à juillet 2026), ou au minimum 24 mois avec deux hivers complets. La même période pour tous les fichiers, s'il te plaît.

**2. D4 (absences) : il manque des colonnes.**
- Colonnes manquantes : `base`, `fleet`, `position`, `duration_days`.
- `notification_ts` est vide pour 284 absences sur 1 518 (19 %). Sans cette heure, on ne peut pas savoir avec combien de préavis l'absence est arrivée.

**3. D5 (call-outs de réserve) : le format a changé.**
- Reçu : `callout_id, crew_id, reserve_date, reserve_call_type, call_ts, report_ts, pairing_id, outcome`
- Attendu : `callout_id, crew_id, call_ts, report_ts, assigned_pairing_id, outcome, base, fleet`

Les nouvelles colonnes `reserve_date` et `reserve_call_type` sont utiles, on peut les garder. Par contre il manque `base` et `fleet`. Pour `outcome`, je reçois `assigned` / `not_called` : est-ce que `not_called` veut dire « en réserve ce jour-là, mais pas appelé » ? Est-ce qu'il existe aussi les cas « refusé » / « no-show » ?

**4. D7 (paie) : le lien entre la paie de draft et la rotation manque.**
- `linked_pairing_id` est vide pour 2 090 lignes `DRAFT_THX` sur 2 834 (74 %), et pour 43 lignes `DRAFT_T2` sur 63.
- Avec la rotation, je retrouve seulement 19 % des drafts de D6 dans la paie. Avec le pilote et la date, je monte à environ 70 %, mais notre seuil de qualité est de 80 %.
- Est-ce que tu peux remplir `linked_pairing_id` pour toutes les lignes `DRAFT_*` ?

## Ce qu'il me faut comprendre (questions)

1. **`DRAFT_THX` ou `DRAFT_T2` ?** Tu m'avais dit que `DRAFT_THX` est payé en temps double (480 $/h) depuis la CC 2026. Alors que représente `DRAFT_T2` (63 lignes) ? Et `OVERTIME_THX` (1 465 lignes), c'est quoi la différence avec `DRAFT_THX` ?
2. **Le montant de `DRAFT_THX`** : la médiane est de 5 899 $ par ligne, donc environ 12 h × 480 $. Est-ce que c'est **toute la paie de la rotation** en temps double, ou seulement la **prime** (la partie en plus du temps simple) ? Pour le coût d'un draft dans la simulation, il me faut la prime seule.
3. **Les autres codes D7** : `CHV`, `T_1_4`, `AJU`, `MIN`, `DMG`, `BME`, `RESERVE_CREDIT`, `DUTY_PREMIUM_P10/P16/P30`. Une ligne d'explication pour chacun serait parfait. Aussi, 663 lignes `CHV` ont un montant négatif : ce sont des corrections ?
4. **`SHORT_NOTICE_COVER` dans D6** (2 757 lignes) : maintenant que les drafts ont leur propre code `DRAFT`, est-ce que `SHORT_NOTICE_COVER` est autre chose ? 124 de ces lignes ont quand même une paie `DRAFT_*`.
5. **D6 `DRAFT`** : 48 lignes n'ont pas de `new_pairing_id` et 6 lignes sont en double (même pilote, même rotation). C'est normal ?
6. **D2 (plannings)** : il y a seulement les bases YUL et YYZ, mais D1 contient aussi des pilotes à YMX, YHZ, YHM, YOW, YVR et PRG. C'est voulu ? Aussi, 99 lignes n'ont pas de `base` / `fleet`, et 1 302 blocs `PAIRING` n'ont pas de `pairing_id`.
7. **Flottes** : les fichiers disent `A321` et `A330`. Est-ce que `A321` mélange les A321ceo et A321neoLR ? Notre périmètre de simulation est l'A321neoLR à YUL, donc c'est important. Et que veulent dire `L15` et `W7S8` (D1) ? La base `PRG` (1 pilote) est une erreur ?
8. **D1** : 764 pilotes sur 1 500 sont `TERMINATED` (51 %). C'est bien l'historique complet, et pas une erreur de filtre ?
9. **D3 legs** : merci pour la nouvelle colonne `deadhead`, on va la garder. Je comprends bien que 1 = le pilote voyage en mise en place, sans heures de vol ?
10. **D8** : la seule raison d'annulation est `NOT_OPERATED_4_1`. Est-ce qu'on peut avoir la vraie cause (météo, équipage, technique, etc.) ?
11. **Règles de la convention (D12)** : pas reçu. Peux-tu me confirmer surtout le préavis minimum pour appeler une réserve **courte (SC)** et **longue (LC)** ? Notre fichier de test dit 2 h et 12 h, et pour l'instant on utilise 14 h pour la LC.

## En résumé

| Priorité | Fichier | À faire |
|---|---|---|
| Bloquant | Tous | Période plus longue (36 mois idéalement, même période partout) |
| Bloquant | D4 | Ajouter `base`, `fleet`, `position`, `duration_days`; remplir `notification_ts` |
| Bloquant | D5 | Ajouter `base`, `fleet` (on peut adapter le reste de notre côté) |
| Bloquant | D7 | Remplir `linked_pairing_id` pour les lignes `DRAFT_*` |
| À clarifier | D7, D6, D1, D2, D8, D12 | Questions 1 à 11 ci-dessus |
| Plus besoin | D9 | Calculé par CrewSim (HMM) |

Pour la suite : je prépare déjà de notre côté le nouveau code `DRAFT` dans D6, la colonne `deadhead` et les nouveaux noms de flotte. Dès que j'ai la période complète et les colonnes de D4, D5 et D7, je relance tous les contrôles.

Si c'est plus simple, on peut faire un appel de 30 minutes pour passer les questions ensemble.

Merci encore pour ton aide !

Bonne journée,
Nabil
