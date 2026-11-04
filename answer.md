Bonjour Pierre,

Merci beaucoup pour ce deuxième envoi et pour tes réponses. J'ai chargé les 12 fichiers dans le système et j'ai passé nos contrôles de qualité. Voici mon retour.

**Réponse courte : on ne peut pas encore lancer une première simulation.** Le format est bon, mais il reste des problèmes de contenu et de période couverte. Je te les explique ci-dessous. Certains problèmes sont aussi de notre côté, je les corrige.

## Ce qui est bon

- Les 12 fichiers se chargent sans erreur de format.
- Les `crew_id` (P######) sont les mêmes dans tous les fichiers, sans orphelin. Aucune colonne avec des noms. Merci pour la Loi 25.
- D3 : les identifiants (code + date) sont uniques, et chaque leg a son entête.
- D2 : les blocs ont de vraies durées, l'heure locale est correcte, et on a bien les réserves SC/LC.
- D7 : les codes sont explicites et les montants sont cohérents avec 240 $/h et 480 $/h.
- D10 et D11 : c'est conforme à ce que tu décris (pas de noms de passagers, 1 020 sessions pour 419 pilotes).

## Ce qui bloque

**1. La période couverte n'est pas la même selon les fichiers.**

| Fichier | Période |
|---|---|
| D2 (plannings) | 1er avril au ~12 juin |
| D4 (absences) | 1er juin au 31 août |
| D6 / D7 | mi-mai à fin août / début septembre |
| D8 (vols opérés) | 17 décembre au 31 août |

Les trois fichiers D2, D4 et D8 se recoupent sur environ 12 jours seulement. Pour calibrer, il nous faut au minimum une même fenêtre pour tous les fichiers, et idéalement 36 mois (au moins trois saisons).

**2. Les derniers jours semblent coupés (date d'extraction).**
- D8 : tous les vols de septembre et octobre (2 244 vols) n'ont pas d'heures réelles et ont `delay_minutes = 0`. Ce sont des vols seulement planifiés. Ils ressemblent à des journées parfaites, et ça fausse le modèle.
- D2 : après le 12 juin, le nombre de pairings tombe de ~113 par jour à 2. Il semble que les blocs ont été coupés à la fin de la période.

**3. D8 : aucune annulation.** Les 22 421 vols ont `cancelled = 0`, et `iata_delay_code` est vide partout. Est-ce que les vols annulés ont été exclus de l'extraction? Pour ta règle D9 (SEVERE = au moins une annulation), c'est aussi un problème.

**4. D4 (absences).**
- Environ 27 % des lignes sont des doublons exacts (1 527 lignes, 1 112 uniques). Une même absence apparaît jusqu'à 36 fois.
- `notification_ts` est toujours 12:00.
- Il y a seulement SICK et FAMILY (pas INJURY).
- `affected_pairing_id` est le code de rotation sans la date (ex. `G0025`), donc le lien avec D3 donne 0 %. Même chose dans D5.
- D4 commence le 1er juin, alors que D2 a des blocs `SICK` en avril et mai. Quelle est la source de vérité pour les absences maladie : D4 ou les blocs `SICK` de D2? Sur la période commune, les deux ne donnent pas les mêmes chiffres.

**5. D6 / D7 (drafts).**
- D6 contient 15 099 lignes `SHORT_NOTICE_COVER`, mais D7 a seulement 1 329 lignes de draft payé (`DRAFT_THX`, `DRAFT_T2`). Quand je pars de D7, 86 % des drafts payés sont retrouvés dans D6, ce qui est bien. Mais D6 contient beaucoup de changements normaux de planning (délai médian d'environ 14 jours avant le pairing).
- Comment reconnaître un vrai draft de dernière minute dans D6? Est-ce qu'il y a un autre champ ou une règle de délai?
- Dans D6, 222 `new_pairing_id` ont un autre format (ex. `TS18@2026-05-18`).

**6. D3 (legs).**
- Environ 30 % des legs ont `block_hours` à 0 ou vide.
- 1 055 legs n'ont pas d'heures, ce qui touche 548 pairings.
- Il y a des legs de 1 minute (ex. YUL → YYZ) et 739 pairings avec la flotte `UNKNOWN`.

**7. D1 / D2 (équipages et flottes).**
- Dans D1, il y a seulement 1 pilote ACTIF sur A321neoLR à YUL, position FO.
- La flotte de D1 est différente de celle de D2 pour 365 pilotes sur 725 (ex. 248 pilotes A320-200 volent sur A321-200 dans D2).
- Quelle flotte est la bonne : D1 ou D2? Est-ce que A321-200 et A321neoLR ont la même qualification? Si oui, on peut faire un groupe « A321 » (environ 138 FO à YUL, dont 16 en réserve).

**8. D2 : types de blocs et chevauchements.**
- `SICK` (4 429), `OTHER` (1 168) et `OFFICE` (1 001) ne sont pas dans notre liste. Que veulent dire `OTHER` et `OFFICE`?
- On a 500 blocs qui se chevauchent pour le même pilote (dont 204 pairing sur pairing).

**9. Autres points, plus petits.**
- D5 : tous les `outcome` sont `assigned`, `call_ts` est toujours à 00:00 et `report_ts` est toujours +2h30. Est-ce une valeur par défaut? Existe-t-il de vraies heures d'appel?
- D7 : peux-tu expliquer les codes `T_1_4`, `AJU`, `MIN`, `DMG`, `BME` et `RED_CAP`? Il y a aussi 169 montants négatifs (ajustements?).
- D8 : la colonne `date` semble être la date UTC pour environ 24 % des vols (elle est différente de la date locale du départ prévu). Peux-tu confirmer?
- D10 : 8 % de lignes en double, et `crew_id` vide pour 21 % des lignes.

## Tes trois réponses

1. **Heures locales** : c'est clair, merci. Il reste seulement la question sur `date` dans D8.
2. **CHV** : c'est clair. On ne l'utilise pas pour la validation des coûts, mais les autres codes D7 nous manquent (voir plus haut).
3. **D9** : la règle est claire. Je vais garder D9 comme contrôle seulement, car elle est calculée à partir de D8, et beaucoup de journées de station ont seulement 1 ou 2 vols.

## Ce que je demande

1. Un nouvel envoi avec une même période pour D2, D3, D4, D6, D7 et D8 (idéalement 36 mois, sinon le plus long possible), et sans la période après la date d'extraction.
2. D4 sans doublons, avec les vraies heures de notification et la date dans les identifiants de pairing (D4 et D5).
3. Une réponse sur les annulations dans D8.
4. Tes réponses aux questions sur D4 / D2 `SICK`, D6 (drafts), la flotte de référence et les codes D7.
5. Les heures manquantes et `block_hours` corrigés dans D3.

## De notre côté

Je corrige aussi chez nous : le contrôle de couverture D8 (il compte des bases de pilotes terminés), les codes de paie des drafts (ils sont codés en dur), et la lecture de D2 (les types de blocs inconnus sont ignorés sans message). Je choisis aussi le périmètre de départ (groupe A321 à YUL) et les fenêtres de calibration.

Si c'est plus simple, on peut en parler 30 minutes en visio. Merci encore pour ton travail, on avance bien.

Cordialement,
Nabil
