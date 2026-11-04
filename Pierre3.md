Objet : CrewSim – données v3 : on a adapté notre code pour les charger, il reste quelques points bloquants

Bonjour Pierre,

Merci pour la v3. C'est une vraie amélioration : les `crew_id` et les `pairing_id` se retrouvent presque partout, les rotations sont maintenant partagées entre CA et FO, D8 couvre tous les jours à YUL et YYZ, les annulations existent et D6 contient les `DRAFT`.

Pour ne pas t'attendre, **on a adapté CrewSim pour qu'il lise tes fichiers tels quels**. Les 11 fichiers se chargent, la calibration tourne et une simulation complète s'exécute sur tes données. Mais certains problèmes ne peuvent pas être contournés côté code : je ne veux pas les cacher, donc ils sont écrits dans nos rapports (section « Limitations ») et listés plus bas.

## Ce qu'on a adapté de notre côté (rien à faire pour toi)

- **Colonnes en plus** (`fleet_detail`, `delay_subcode`, `delay_description`, `hours`, `rate_cad`, `premium_cad`, etc.) : ignorées. On lit `deadhead` (D3) et `notification_source` (D4) quand elles sont là. Les deadheads comptent comme du temps de service, pas comme du vol.
- **Flotte** : `A321neoLR` n'existe pas dans D1/D2/D4 (tout est `A321`; un seul FO actif à YUL a `fleet_detail = A321neoLR`). Le périmètre passe automatiquement à `A321` quand D1 en contient plus : 151 pilotes actifs YUL/FO.
- **Codes de paie de draft** : `DRAFT_THX` et `DRAFT_T2`. Côté D6 on accepte `DRAFT` **et** `SHORT_NOTICE_COVER`. Résultat : 4 122 drafts reconstitués, rappel D7→D6 de 86 %.
- **Période** : on commence au 1er mai 2024 (voir le point 2 plus bas).
- **Bloc `ABSENCE`** (D2), `OFFICE` et `OTHER` : acceptés comme « indisponible ».
- **`notification_ts` vide** : on suppose que l'absence a été signalée à 00 h 00 le premier jour. Les lignes ne sont pas perdues, mais le préavis est inconnu pour elles.
- **Lignes D8 où origine = destination** : retirées avant tout calcul (voir le point 3).
- **D9** : pas nécessaire. **D12** : pas reçu; on utilise le fichier de notre jeu de test, qui correspond à ce qu'on croit être la convention. Les valeurs à confirmer sont à la fin.

## Ce qui bloque encore (par ordre de priorité)

**1. Il faut plus d'historique.** Tes fichiers vont du 24 avril 2024 au 31 août 2026 (28 mois). Avec une fenêtre d'ajustement et une fenêtre de validation, **chacune ne contient qu'un seul hiver complet** (déc. 2024 – avr. 2025 et déc. 2025 – avr. 2026). Le modèle d'hiver s'ajuste donc sur 151 jours seulement; le test de stabilité (1 seul des 8 essais EM converge au même optimum) et le critère BIC (qui préfère 2 régimes au lieu de 4) le confirment. Idéalement août 2023 → août 2026, au minimum décembre 2023 → avril 2024 de plus, avec **la même période pour tous les fichiers**.

**2. D8 – première semaine inutilisable (23-30 avril 2024).** 1 801 des 2 286 vols d'avril 2024 (79 %) sont marqués `cancelled = 1`, et il y a environ 310 lignes par jour au lieu de 70 à partir du 1er mai. On dirait des vols seulement planifiés. Peux-tu refaire cette semaine ou confirmer ce qu'elle contient ?

**3. D8 – lignes bizarres.**
- 708 lignes ont `origin = destination` (dont 246 annulées). Exemple : TS250 du 2025-10-24, trois lignes : YUL→CDG (retard 80 min), YUL→YUL (retard 0) et YUL→YUL (annulé).
- 469 lignes répétées (même vol, même date, même origine, même destination).
- Les annulations : `NOT_OPERATED_4_1` pour 2 610 sur 2 617. Peux-tu nous donner la vraie cause (météo, équipage, technique, ...) ? Depuis mai 2024, 510 des 816 annulations partent d'une escale; dans notre fenêtre d'ajustement il n'y en a que **29** au départ de YUL/YYZ, trop peu pour que le modèle apprenne quelque chose.
- Flottes `TRN`, `P295`, `7M8`, `PDH4`, `343C`, `332C`, `W737` : 368 départs de YUL/YYZ. Ce sont des vols hors exploitation (formation, ferry, charters) ?

**4. D4 – absences.**
- `notification_ts` est vide pour 824 des 5 816 lignes (14 %) : `AUCUNE_ROTATION_A_RETIRER` (650) et `INTROUVABLE` (174). Et 65 lignes ont une notification **après** le premier jour de l'absence. Peux-tu retrouver ces heures ?
- 1 145 lignes (20 %) n'ont pas de `affected_pairing_id`, et 3 pairings sont datés de septembre 2026 (ex. `C0136_20260911`), après la fin de l'extraction.
- **Seulement 12 des 4 671 absences avec rotation retrouvent cette rotation dans le roster D2 du même pilote.** La rotation a sans doute été retirée de son roster au moment de l'absence. Sans le roster publié *avant* l'absence, on ne peut pas reconstruire la fraction historique de réserves éligibles : notre contrôle V3 échoue (0 événement exploitable).
- 56 absences `SICK` durent plus de 60 jours (jusqu'à 779). Ce sont des congés enregistrés comme maladie ? On compte aussi 142 `FAMILY` et 3 `INJURY` : on les garde comme appels maladie ?
- Notre contrôle de liaison D4 → D3 donne 80,3 % (seuil 95 %).

**5. D7 – paie.**
- `DRAFT_THX` est payé à 360 $/h (150 % de 240 $/h) et `premium_cad` en est le tiers (120 $/h). Dans ton dernier courriel, on parlait de temps double à 480 $/h. Lequel est correct ? Et que représente `DRAFT_T2` (56 lignes, à 480 $/h) ?
- `RESERVE_CREDIT` : 14 594 lignes de 3,33 h × 240 $ = 799,20 $. Est-ce bien la garantie de réserve par jour ? Est-elle différente entre courte et longue durée ? Notre fichier de test dit 250 $ / 180 $.
- Il n'y a aucun code pour l'utilisation d'une réserve (la réserve qui vole est payée `CHV` comme n'importe quel vol) : peut-on la séparer ?
- Les autres codes : `CHV` (dont 1 318 montants négatifs), `T_1_4`, `MIN`, `AJU`, `BME`, `DMG`, `OVERTIME_THX`, `HOLIDAY_T2`, `DUTY_PREMIUM_P10/P16/P30`. Une ligne d'explication pour chacun nous permet de les rattacher à la simulation.
- 13 `linked_pairing_id` n'existent pas dans D3 (rotations de septembre 2026), et 67 lignes ont un `crew_id` absent de D1 (2 pilotes).

**6. D6 – volume irrégulier.** Le nombre de changements par mois est d'environ 2 600 à 5 000, mais **seulement 1 000 à 1 700 en juin 2024, décembre 2024, juin 2025, décembre 2025, juillet 2026 et août 2026**. Les extractions sont-elles incomplètes ces mois-là ? Et quelle est la différence entre `SHORT_NOTICE_COVER` et `DRAFT` ? Seulement 29,5 % des lignes urgentes de D6 ont une paie de draft dans D7.

**7. D5 – réserves.**
- Les seules issues sont `assigned` et `not_called` : pas de `released`, `no-show` ni `declined` ? On les lit comme 0 %, ce qui est faux par construction.
- Pour 238 des 4 236 appels `assigned`, `report_ts` est **avant** `call_ts` (228 sont des courts appels). 217 ont plus de 72 h d'écart. Et 503 courts appels ont moins de 2 h de préavis. Peux-tu vérifier ?

**8. D1 / D2 – flottes.** D1 donne à 85 FO actifs de YUL `fleet_detail = A320-200` et à 65 `A321-200` (1 seul `A321neoLR`); D2, pour la même cellule YUL/A321/FO, compte 190 pilotes en `A321-200` et 12 en `A321neoLR`. Les deux fichiers ne disent pas la même chose. Peux-tu nous donner l'historique de qualification par sous-flotte (neoLR en particulier) ? Notre périmètre cible est l'A321neoLR; tant qu'on n'a pas cela, on simule l'ensemble des A321. Aussi : 11 pilotes actifs YUL/YYZ n'ont aucune ligne dans D2.

**9. D3 – rotations.** 4 163 legs (3,2 %) n'ont pas d'heures (dep/arr) et 2 842 rotations (6,2 %) ont une flotte `UNKNOWN`. Nos seuils sont de 98 % pour les deux.

**10. D10 – factures.** 13,9 % des factures (982) n'ont pas de `crew_id`, 35 % pas de `pairing_id`, et le fichier ne commence qu'au 28 juin 2025.

**11. D2 – chevauchements.** Notre chargeur a dû réconcilier des blocs qui se chevauchent dans la fenêtre de gabarit (20 mars → 1er mai 2026) : 367 raccourcis et 1 599 supprimés, pour 135 pilotes sur 151. Est-ce attendu ?

## Convention (D12) : ce qu'il nous faut confirmer

On utilise notre fichier de test. Les éléments suivants sont **encore des valeurs de test, pas des faits d'Air Transat** :

| Champ | Valeur actuelle | Ce que disent tes données |
|---|---|---|
| `drafting.premium_pct` | 200 | THX : 150 % du taux (prime = 50 %); T2 : 200 % |
| `reserve.guarantee_per_day_cad` | courte 250 $, longue 180 $ | `RESERVE_CREDIT` ≈ 799 $ par jour (3,33 h × 240 $) |
| `reserve.notice_hours` | courte 2 h, longue 12 h | D5 : longue médiane ≈ 46 h; courte médiane ≈ 10 h (données à vérifier, point 7) |
| `term` | 2025-05-01 → 2030-04-30 | à confirmer |

CrewSim n'utilise pas D12 directement (les coûts et les préavis sont dans notre configuration), mais ces chiffres décident du coût d'un draft et d'une réserve : sans eux, les résultats ne sont pas des résultats Air Transat.

## En résumé

| Priorité | Fichier | À faire |
|---|---|---|
| Bloquant | Tous | Historique plus long (au moins déc. 2023 → avr. 2024 de plus), même période partout |
| Bloquant | D8 | Refaire ou expliquer le 23-30 avril 2024; lignes origine = destination; vraie cause des annulations |
| Bloquant | D4 / D2 | Roster publié avant l'absence (ou le lien absence → rotation); `notification_ts` manquants |
| Bloquant | D7 | Sens de `DRAFT_THX` / `DRAFT_T2` (360 $/h ou 480 $/h ?), `RESERVE_CREDIT`, autres codes |
| Important | D6, D5 | Mois à faible volume dans D6; `call_ts` / `report_ts` incohérents dans D5; issues manquantes |
| Important | D1 / D2 | Historique des sous-flottes (neoLR) |
| À clarifier | D3, D10, D2 | Legs sans heures, flotte `UNKNOWN`, factures sans `crew_id`, chevauchements |
| À fournir | D12 | Valeurs de la convention (tableau ci-dessus) |
| Plus besoin | D9 | Calculé par CrewSim |

Je peux te montrer le rapport « Limitations » qu'on génère à chaque chargement; si c'est plus simple, un appel de 30 minutes suffit pour passer les points ensemble.

Merci encore pour ton aide !

Bonne journée,
Nabil
