Objet : CrewSim – peut-on exporter directement l'historique des drafts d'AIMS (pour éviter la jointure avec D7)?

Bonjour Pierre,

J'ai une question de fond sur les drafts, qui pourrait nous simplifier la vie à tous les deux et réduire le nombre de fichiers à extraire.

## Le problème actuel

Pour CrewSim, un « draft » est un pilote qui reçoit une rotation à la dernière minute (hors réserve, souvent sur un jour off), à cause d'un trou opérationnel (maladie, annulation, retard, etc.). On en a besoin pour :

- mesurer la **fréquence réelle des drafts** (par pilote, par mois) et la comparer à la simulation;
- connaître le **statut du pilote juste avant le draft** (jour off, réserve SC, réserve LC, …), pour estimer la répartition par niveau (« tier ») des pilotes draftés;
- calibrer **combien coûte un draft**.

Aujourd'hui, on n'a aucun champ qui dit « ceci est un draft ». On doit le reconstruire en croisant :

- **D6** (changements de planning) : lignes `SHORT_NOTICE_COVER` initiées par l'IOC;
- **D7** (paie) : lignes `DRAFT_THX` / `DRAFT_T2`, qui prouvent qu'une prime a été payée.

Cette jointure est fragile, et les chiffres de ce second envoi le montrent :

- D6 a 15 099 lignes `SHORT_NOTICE_COVER`, mais D7 n'a que 1 329 lignes de draft payé. Le délai médian entre le changement et le pairing dans D6 est d'environ 14 jours. Beaucoup de ces lignes sont donc de simples changements de planning, pas des drafts de dernière minute;
- quand je pars de D7, 86 % des drafts payés se retrouvent dans D6, mais l'inverse n'est pas vrai (on ne sait pas lesquelles des 15 099 lignes sont des vrais drafts);
- D7 demande aussi plusieurs codes à expliquer (`T_1_4`, `AJU`, `MIN`, `DMG`, `BME`, `RED_CAP`) et contient 169 montants négatifs.

## L'objectif

**Remplacer la jointure D6 × D7 par un export direct de l'historique des drafts depuis AIMS**, si AIMS le permet. Concrètement :

- on n'aurait plus besoin de D7 pour **identifier** les drafts;
- on n'aurait plus besoin de deviner dans D6 lesquelles sont de vraies urgences;
- on réduirait le travail d'extraction et les risques d'incohérence entre fichiers (période, doublons, `crew_id` absents de D1).

## La question

Est-ce qu'AIMS peut sortir (ou est-ce que quelqu'un à Crew Control / IOC peut sortir) une liste des **assignations faites par le contrôle des opérations sur un pilote non planifié ce jour-là** (donc les drafts)? Par exemple :

- un type d'assignation ou un code d'action dans le journal des modifications (audit log) d'AIMS;
- un rapport « drafts » ou « call-out hors réserve » qu'utilise déjà l'équipe de planification;
- ou, à défaut, un champ dans D6 qui sépare le vrai draft de dernière minute d'un simple changement de planning.

## Le schéma qu'on aimerait recevoir

Un seul fichier, une ligne par draft, par exemple `d12_drafts.csv` :

| Champ | Description | Pourquoi |
|---|---|---|
| `draft_id` | identifiant unique de la ligne | traçabilité |
| `crew_id` | pilote drafté, même pseudonyme `P######` | lien avec D1 |
| `assigned_pairing_id` | rotation assignée, au format code + date (ex. `C0001_20260501`) | lien avec D3, D2 |
| `draft_ts` | date et heure où l'assignation a été faite dans AIMS | délai de préavis |
| `notified_ts` | date et heure où le pilote a été avisé (si distinct) | idem, plus fin |
| `prior_status` | statut avant le draft : `DAY_OFF`, `RESERVE_SC`, `RESERVE_LC`, autre | répartition par tier |
| `initiator` | qui l'a fait : IOC, Crew Control, etc. | filtrage |
| `outcome` | accepté, refusé, annulé | taux d'acceptation |
| `trigger_reason` | cause du trou : maladie, annulation, retard, etc. (si disponible) | lien avec les cascades |
| `base`, `fleet`, `position` | base, flotte et siège du pilote drafté | périmètre de la simulation |
| `credit_hours` ou `pay_multiplier` | heures créditées et multiplicateur (1,5×, 2×) | coût (voir plus bas) |

Les champs `draft_ts`, `assigned_pairing_id`, `prior_status`, `crew_id` sont les obligatoires. Les autres sont des bonus.

## Et le coût? (ce qu'on perdrait sans D7)

D7 sert aussi à calibrer le coût et au backtest V6 (simulation vs vraie paie). Mais tu m'as déjà donné les taux : 240 $/h en temps simple, 480 $/h en temps double, et `DRAFT_THX` payé en temps double depuis la CC 2026. Donc si l'export contient **les heures créditées** (ou le multiplicateur), on peut calculer le coût d'un draft = heures × taux, sans passer par la paie.

Ce qu'on perdrait :

- la validation « ça a vraiment été payé » (le backtest V6 contre la vraie paie);
- les montants réels des ajustements (`AJU`, négatifs, etc.).

Si tu penses que c'est important de garder un D7 minimal (seulement `DRAFT_*` et `RESERVE_CREDIT`, dédupliqué, sans les codes qu'on ne comprend pas), on peut le garder comme **contrôle** et non comme source. Dis-moi ce qui est le plus simple pour toi.

## Même fenêtre pour tous les fichiers

Comme dans mon dernier message, il nous faut la même période pour D2, D3, D4, D6 et D8 et pour ce nouveau fichier de drafts (idéalement 36 mois, sinon le plus long possible), sans la période après la date d'extraction.

## Si ce n'est pas possible

Aucun problème, dans ce cas :

1. on garde D6 × D7 comme source, mais j'aurais besoin d'une règle pour reconnaître un vrai draft dans D6 (délai maximal avant le pairing, champ ou code supplémentaire);
2. et la liste des codes D7 expliquée (`T_1_4`, `AJU`, `MIN`, `DMG`, `BME`, `RED_CAP`).

Un appel de 30 minutes avec quelqu'un de Crew Control qui connaît le fonctionnement des drafts dans AIMS serait peut-être le plus rapide pour trancher.

Merci d'avance, et désolé pour la question de plus!

Cordialement,
Nabil
