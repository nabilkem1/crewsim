# CrewSim – Analyse des données réelles Air Transat

**Destinataire :** Pierre · **Date :** octobre 2026 · **Objet :** qualité des fichiers CSV de
`real_data/` et corrections à faire dans les scripts d'extraction.

**Conclusion : les données ne sont pas encore prêtes à être injectées dans CrewSim.**
Ce document liste, fichier par fichier, le problème constaté et la correction attendue.
Il est écrit pour être donné directement à Claude pour corriger les scripts à la source.

## Résumé

| Fichier | Lignes réelles | Lignes mock | Période réelle | Statut chargeur |
|---|---|---|---|---|
| D1 crew_master | 1 500 | 2 019 | – | ✅ se charge (à corriger) |
| D2 rosters | 51 055 | 207 179 | juin–août 2026 (3 mois) | ❌ refusé – blocs de 0 min, pas de RESERVE |
| D3 pairings | 3 059 | 115 332 | déc. 2025–oct. 2026 | ✅ se charge (à corriger) |
| D3 pairing_legs | 43 631 | 481 136 | – | ❌ refusé – heures sans date |
| D4 absences | 1 527 | 7 903 | juin–août 2026 (3 mois) | ✅ se charge – heures générées |
| D5 reserve_callouts | 1 098 | 5 411 | 24 juin–31 juil. 2026 | ✅ se charge – heures générées |
| D6 schedule_changes | 6 554 | 3 169 | mai–août 2026 | ❌ refusé – horodatages mal formatés |
| D7 pay_register | 9 183 | 8 004 | mai–sept. 2026 | ✅ se charge – codes de paie inutilisables |
| D8 flight_movements | 22 421 | 67 368 | déc. 2025–oct. 2026 | ❌ refusé – colonnes, heures, pas d'annulations |
| D9 station_days | 8 962 | 62 354 | déc. 2025–oct. 2026 | ✅ se charge (à vérifier) |
| D10 positioning_invoices | 29 831 | 753 | mai 2025–août 2026 | ❌ refusé – noms de passagers |
| D11 training_sessions | – | 5 340 | – | ❗ manquant |
| D12 agreement_rules | – | yaml | – | ❗ manquant |

Le corpus mock couvre **36 mois** (août 2023 – juillet 2026). Les données réelles couvrent
**3 mois** pour les plannings et les absences, ce qui est trop court pour calibrer le modèle.

## 1. Règles générales (pour tous les fichiers)

1. **Format CSV :**
   - UTF-8 (sans BOM si possible), séparateur virgule, une ligne d'en-tête.
   - Une cellule vide veut dire « pas de valeur ». Ne pas écrire `NULL`, `nan` ou `0` pour dire « inconnu ».
2. **Colonnes :**
   - Exactement les colonnes listées pour chaque fichier, ni plus ni moins. L'ordre n'a pas d'importance.
   - Les colonnes en plus font échouer le chargement. Si une colonne en plus est utile, on peut en parler, mais elle ne doit pas être dans le fichier principal.
3. **Dates et heures :**
   - Date : `YYYY-MM-DD` (exemple : `2026-06-03`).
   - Date + heure : `YYYY-MM-DDTHH:MM`, toujours avec 2 chiffres pour l'heure et les minutes (exemple : `2026-05-28T04:08`, et **pas** `2026-05-28T4:08`). Pas de secondes, pas de `Z`.
   - **Jamais une heure seule** (`03:43`), jamais une heure négative (`-2:50`), jamais `24:05`. Un vol qui arrive après minuit doit porter la date du lendemain.
   - Les colonnes `*_utc` sont en UTC. Les colonnes `*_local` sont en heure locale de la station concernée. Merci de confirmer la convention (voir les questions à la fin).
4. **Vie privée (Loi 25) – très important :**
   - **`crew_id` ne doit pas être le matricule.** Aujourd'hui ce sont les vrais numéros d'employé (`312673`, `1912`…). Il faut un pseudonyme stable, par exemple `P` + un numéro, ou un hash salé. Le même employé doit avoir **le même pseudonyme dans tous les fichiers** D1 à D11. La table de correspondance reste chez toi et ne doit pas m'être envoyée.
   - Aucun nom de personne, ni de passager ni d'équipage, et aucune adresse, aucun courriel, aucun téléphone, aucune date de naissance.
5. **Période :**
   - Aujourd'hui, les plannings (D2) et les absences (D4) couvrent seulement juin à août 2026 (3 mois). C'est trop court pour calibrer le modèle, et il n'y a aucun mois d'hiver.
   - **Idéal :** août 2023 à juillet 2026 (36 mois), pour **tous** les fichiers D2 à D10, sur la même période.
   - **Minimum :** 24 mois consécutifs, avec au moins deux hivers complets (décembre à avril).
6. **Cohérence entre fichiers :**
   - Chaque `crew_id` de D2, D4, D5, D6, D7, D10 et D11 doit exister dans D1. Aujourd'hui, seulement **34 %** des `crew_id` de D7 sont dans D1.
   - Chaque `pairing_id` utilisé dans D2, D4, D5, D7 et D10 doit exister dans D3.
7. **Codes avion :** utiliser les mêmes codes partout : `A320-200`, `A321-200`, `A321neoLR`, `A330-200`, `A330-300`. Pas de `UNKNOWN`, pas de `L15` ou `W7S8` (si ce ne sont pas des avions, merci de m'expliquer ce que c'est).

---

## 2. Retour fichier par fichier

### D1 – `d1_crew_master.csv` ✅ se charge (1 500 lignes, mock : 2 019)
Colonnes attendues : `crew_id, base, crew_group, position, fleet, fleet_family, qual_valid_from, qual_valid_to, seniority_number, employment_status, hire_date, termination_date`

À corriger :
- `crew_id` : pseudonymiser (règle 4).
- `fleet` : enlever ou expliquer `L15` et `W7S8`. `fleet_family` est vide pour 2,7 % des lignes : merci de le remplir.
- 51 % des pilotes sont `TERMINATED`. C'est OK si c'est voulu (historique), mais merci de confirmer. Valeurs acceptées pour `employment_status` : `ACTIVE, INACTIVE, TERMINATED, LONG_TERM_ABSENCE, MANAGEMENT_OR_INSTRUCTOR, INITIAL_TRAINING, FLEET_TRANSITION`.
- `hire_date = 1980-01-01` apparaît une fois : est-ce une valeur par défaut ? Si oui, mettre la vraie date, ou laisser la cellule vide.
- **Question de périmètre :** seulement **3 FO actifs** sur YUL / A321neoLR, contre 112 dans le mock. Les gros groupes sont YUL A320-200 (276) et A330-300 (104). Est-ce correct ? Ça va probablement changer le périmètre de la simulation.

### D2 – `d2_rosters.csv` ❌ refusé (51 055 lignes, mock : 207 179) – **le plus important**
Colonnes attendues : `crew_id, base, fleet, position, block_type, start_utc, end_utc, start_local, end_local, pairing_id, reserve_call_type`

Problèmes :
- 3 colonnes en trop : `block_plan_hours`, `block_act_hours`, `delay_min`. Il faut les enlever.
- **Tous les blocs durent 0 minute.** Sur les 51 055 lignes, `start == end` à `00:00`, et l'heure UTC est égale à l'heure locale. Exemple : `DAY_OFF, 2026-06-03T00:00, 2026-06-03T00:00`.
- **Aucun bloc `RESERVE`** (mock : 25 577), et `reserve_call_type` est vide à 100 %. Sans les blocs de réserve, le simulateur n'a aucune capacité de réserve.

Correction attendue :
- **Une ligne par bloc réel**, avec le vrai début et la vraie fin. Exemples :
  - une rotation de 4 jours = 1 ligne de `PAIRING` du début du premier service à la fin du dernier ;
  - une période de réserve = 1 ligne `RESERVE` avec ses heures exactes.
- Ce n'est **pas** une ligne par jour à minuit.
- `start_utc/end_utc` en UTC, et `start_local/end_local` en heure locale de la base, donc avec le décalage horaire (à YUL, l'été : local = UTC − 4 h).
- `block_type` dans : `PAIRING, RESERVE, DAY_OFF, VACATION, TRAINING, SIMULATOR, REST, DEADHEAD`.
- `reserve_call_type` = `SC` (court préavis) ou `LC` (long préavis) pour **chaque** ligne `RESERVE`, et vide pour les autres types.
- `pairing_id` rempli pour chaque `PAIRING`, et il doit exister dans D3. Aujourd'hui, 1 seul identifiant manque.
- `fleet` et `base` sont vides sur 0,2 % des lignes : merci de les remplir.

### D3 – `d3_pairings.csv` ✅ se charge (3 059 lignes, mock : 115 332)
Colonnes attendues : `pairing_id, base, fleet, position_complement, duty_periods, credit_hours, layover_stations, start_date, days`

À corriger :
- `base` a 30 valeurs (MAN, DUB…). Ce doit être la **base de l'équipage** (YUL, YYZ, YVR…), pas l'escale.
- `fleet = UNKNOWN` existe : il faut mettre le vrai type avion.
- `position_complement` : utiliser le format `CA:1,FO:1` (comme dans le mock), et non `1CM2PO`. Merci aussi de me donner la correspondance des codes CM, PO, SP, DV, AB.
- `credit_hours` monte jusqu'à 849,94 (3 rotations au-dessus de 200 h). C'est sûrement une erreur d'unité (minutes ?). Merci de vérifier.
- Le nombre de rotations (3 059 pour ~10 mois) semble faible par rapport à 51 000 lignes de planning. Est-ce un extrait partiel ?

### D3 legs – `d3_pairing_legs.csv` ❌ refusé (43 631 lignes, mock : 481 136)
Colonnes attendues : `pairing_id, duty_period, leg_seq, flight_no, origin, destination, report_local, dep_local, arr_local, release_local, block_hours`

Problèmes :
- `report_local`, `dep_local`, `arr_local` et `release_local` sont des **heures sans date** (`03:43`). 1 057 valeurs sont négatives ou ≥ 24:00, et 8 955 vols « arrivent avant de partir ».
- `report_local == dep_local` sur **toutes** les lignes : il n'y a pas de temps de présentation avant le vol. Même chose pour `arr_local == release_local`.
- Exemple incohérent : `B012B` YUL→YYZ part à 03:43 et arrive à 03:44, mais `block_hours = 7.42`.
- `leg_seq` monte jusqu'à 156 : c'est sûrement une erreur.
- `block_hours` est vide sur 27 % des lignes.

Correction attendue :
- Date + heure complète, `YYYY-MM-DDTHH:MM`, en heure locale de l'aéroport du segment.
- Un vrai `report_local` (présentation, environ 1 h avant le départ) et un vrai `release_local` (environ 30 min après l'arrivée), venant du système de planification.
- `leg_seq` qui recommence à 1 à chaque `duty_period`.
- `block_hours` rempli, et cohérent avec `arr − dep`.

### D4 – `d4_absences.csv` ✅ se charge (1 527 lignes, mock : 7 903)
Colonnes attendues : `absence_id, crew_id, notification_ts, absence_start, absence_end, duration_days, absence_type, affected_pairing_id, base, fleet, position`

À corriger :
- **`notification_ts` est toujours `12:00`.** C'est une valeur générée. Il faut la vraie heure à laquelle l'absence a été annoncée. C'est essentiel pour calculer le préavis.
- Période : seulement juin à août 2026. Il faut la même longue période que D2 (règle 5).
- `absence_type` : seulement `SICK` et `FAMILY`. Existe-t-il d'autres types (`INJURY`…) ? Si oui, merci de les inclure.
- Merci de confirmer si `absence_end` est inclusive (dernier jour d'absence) ou exclusive (jour du retour).

### D5 – `d5_reserve_callouts.csv` ✅ se charge (1 098 lignes, mock : 5 411)
Colonnes attendues : `callout_id, crew_id, call_ts, report_ts, assigned_pairing_id, outcome, base, fleet`

À corriger :
- **`call_ts` est toujours `00:00` et `report_ts` toujours `02:30`.** Ce sont des valeurs générées. Il faut la vraie heure de l'appel et la vraie heure de présentation.
- `outcome` est toujours `assigned`. Il faut aussi les cas `released` et `no-show`.
- `fleet` est seulement A330. Il faut les appels de réserve de toutes les flottes.
- Période : seulement 24 juin au 31 juillet 2026. Il faut la même période que D2.
- `assigned_pairing_id` est vide à 85 % : il faut le remplir quand l'appel a donné une rotation.

### D6 – `d6_schedule_changes.csv` ❌ refusé (6 554 lignes, mock : 3 169)
Colonnes attendues : `change_id, crew_id, change_ts, old_block_type, new_block_type, new_pairing_id, reason_code, initiator`

Problèmes et corrections :
- **47 % des `change_ts` sont mal formatés :**
  - heure sur 1 chiffre : `2026-05-28T4:08` doit devenir `2026-05-28T04:08` ;
  - heure absente : `2026-06-15T`. Il faut l'heure réelle.
- `new_pairing_id` est vide à 100 %. Pour un `SHORT_NOTICE_COVER`, il faut le `pairing_id` de la rotation couverte (qui doit exister dans D3).
- `reason_code` et `initiator` ont seulement 2 valeurs et 1 valeur. Sont-ce les vrais codes du système, ou un remappage ? Merci de m'envoyer la liste des codes d'origine avec leur signification.

### D7 – `d7_pay_register.csv` ✅ se charge (9 183 lignes, mock : 8 004)
Colonnes attendues : `crew_id, pay_period, pay_code, amount_cad, duty_date, linked_pairing_id`

À corriger :
- `pay_code` contient seulement `CHV` et `DOUBLE_TIME`. CrewSim a besoin de distinguer au minimum :
  - la **prime de draft** (rappel sur jour de congé) ;
  - la **garantie de réserve** ;
  - l'**utilisation de réserve**.
  Merci d'envoyer les vrais codes de paie avec une table « code → signification ».
- `amount_cad` a une moyenne de 64 $ et un maximum de 133 $. Ça ressemble à des **heures** ou à un taux, pas à des montants en dollars. Merci de vérifier l'unité : on attend des dollars canadiens.
- Seulement 34 % des `crew_id` existent dans D1 (règle 6).
- `linked_pairing_id` est vide à 92 %, et une valeur bizarre existe : `G575G`. Il faut lier la ligne à la rotation quand c'est possible.

### D8 – `d8_flight_movements.csv` ❌ refusé (22 421 lignes, mock : 67 368)
Colonnes attendues : `flight_no, date, origin, destination, fleet, sched_dep_local, sched_arr_local, actual_dep_local, actual_arr_local, delay_minutes, iata_delay_code, cancelled, cancel_reason`

Problèmes et corrections :
- **Colonne manquante `delay_minutes`** (elle s'appelle `delay_dep_min`). Il faut la renommer et confirmer sa définition : retard au départ = départ réel − départ prévu, en minutes. Les valeurs négatives (10 216 vols partis en avance) : merci de mettre `0` dans `delay_minutes`.
- 8 colonnes en trop à enlever : `block_act_min, block_plan_min, deadhead, delay_dep_min, delay_desc, delay_subcode, delay_sys_min, pairing_planned`.
- `sched_dep_local` et `sched_arr_local` sont des heures seules, dont 3 565 négatives (`-2:50`, `-1:-5`). Ça ressemble à une conversion de fuseau horaire ratée. Il faut une date + heure complète, en heure locale de l'aéroport.
- `actual_dep_local` et `actual_arr_local` sont **vides à 100 %**. Il faut les heures réelles.
- **Aucun vol annulé** (`cancelled = 0` partout, `cancel_reason` vide). Le mock a environ 1 % d'annulations. Il faut inclure les vols annulés avec `cancelled = 1` et une raison (`WEATHER`, `CREW`, `TECHNICAL`…).

### D9 – `d9_station_days.csv` ✅ se charge (8 962 lignes, mock : 62 354)

> **Mise à jour (F-42) : D9 n'est plus nécessaire.** Le régime de chaque jour (CALM / NORMAL /
> DISRUPTED / SEVERE) est maintenant **calculé** par un modèle de Markov caché à partir de D8 (retards,
> annulations), D4 (absences) et D2 (équipages en service). Tu n'as donc pas à nous expliquer ni à
> produire `disruption_class`. Si vous tenez un journal opérationnel des perturbations (météo, ATC,
> IROPS), tu peux l'envoyer comme D9 : il servira seulement à **vérifier** nos étiquettes calculées.
> Ce qui devient important : **D8 doit couvrir chaque jour, à chaque base** (départs, retards en minutes,
> vols annulés).

Colonnes attendues (si fourni) : `station, date, disruption_class, season, intensity_multiplier`

À vérifier (seulement si D9 est fourni pour contrôle) :
- **Comment `disruption_class` est-il calculé ?** C'est la variable la plus importante pour le modèle. Par exemple, YUL n'a que 3 jours `SEVERE` sur 299, contre 130 sur 1 075 dans le mock. Si c'est une règle maison, merci de m'envoyer la règle.
- Valeurs acceptées : `CALM, NORMAL, DISRUPTED, SEVERE`. `season` dans `winter_sun` (déc.–avr.), `summer_atlantic` (juin–sept.), `shoulder` (mai, oct., nov.).
- `intensity_multiplier` a 1.5 en plus des valeurs du mock. C'est OK si c'est voulu.
- Période : même longue période que D2.

### D10 – `d10_positioning_invoices.csv` ❌ refusé (29 831 lignes, mock : 753)
Colonnes attendues : `date, station, cost_type, amount_cad, crew_id, pairing_id`

Problèmes et corrections :
- **`passenger_name` est présent (environ 24 000 noms). Il faut le supprimer à la source**, c'est une donnée personnelle (Loi 25). Le chargeur refuse le fichier pour cette raison.
- 6 autres colonnes en trop à enlever : `travel_date, merchant, routing, currency_local, match_type, pairing_match`.
- `amount_cad` : il y a une facture à **157 964,74 $**, à vérifier. Merci aussi de confirmer que tous les montants sont bien **convertis en CAD** (le fichier contient des codes de devise EUR, GBP, USD, MAD, MXN).
- `crew_id` est vide à 47 % et `pairing_id` à 97 %. Il faut les remplir au maximum, en utilisant le pseudonyme de la règle 4.
- `cost_type` dans : `DEADHEAD, HOTEL, TRANSPORT`. C'est OK aujourd'hui.

### D11 – `d11_training_sessions.csv` ❗ manquant
Colonnes attendues : `crew_id, session_type, start_date, end_date, requalification_deadline, reschedule_cost_cad_estimate`
- `session_type` : `GROUND` ou `SIM`.
- Si `reschedule_cost_cad_estimate` n'existe pas dans vos systèmes, laisser la cellule vide.

### D12 – `d12_agreement_rules.yaml` ❗ manquant
C'est le résumé des règles de la convention collective ALPA. Je peux t'envoyer notre version de test pour que tu (ou les Relations de travail) corrigiez les valeurs, surtout :
- le préavis de réserve court/long (on a 2 h et 12 h) ;
- la garantie par jour de réserve ;
- le % de prime de draft.

---

## 3. Questions (réponse rapide suffisante)
1. Les heures `*_local` de D3 et D8 : heure locale **de l'aéroport du segment**, ou de la base ?
2. Que veut dire `CHV` dans D7 ?
3. ~~Comment est calculé `disruption_class` (D9) ?~~ Plus nécessaire (le régime est calculé). À la place : avez-vous un journal des perturbations (météo / ATC / IROPS) pour contrôler nos étiquettes ?
4. `absence_end` (D4) : inclusive ou exclusive ?
5. Que sont `L15` et `W7S8` (D1) ?
6. Peut-on avoir 36 mois d'historique (août 2023 à juillet 2026) ?

---

## 4. Script de vérification (à lancer avant l'envoi)

Le script est aussi joint au mail : **`verifier_corpus.py`** (à utiliser plutôt que de copier le code depuis le PDF, pour garder l'indentation).

Python standard, sans aucune librairie à installer. Le lancer dans le dossier des CSV : `python verifier_corpus.py`. Il doit afficher `OK` pour chaque fichier.

```python
import csv, re, sys
from pathlib import Path

D, DT = r"^\d{4}-\d{2}-\d{2}$", r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"
S = {
 "d1_crew_master": {"crew_id":"s","base":"s","crew_group":"s","position":"s","fleet":"s","fleet_family":"s","qual_valid_from":D,"qual_valid_to":D,"seniority_number":"i","employment_status":"s","hire_date":D,"termination_date":D},
 "d2_rosters": {"crew_id":"s","base":"s","fleet":"s","position":"s","block_type":"s","start_utc":DT,"end_utc":DT,"start_local":DT,"end_local":DT,"pairing_id":"s","reserve_call_type":"s"},
 "d3_pairings": {"pairing_id":"s","base":"s","fleet":"s","position_complement":"s","duty_periods":"i","credit_hours":"f","layover_stations":"s","start_date":D,"days":"i"},
 "d3_pairing_legs": {"pairing_id":"s","duty_period":"i","leg_seq":"i","flight_no":"s","origin":"s","destination":"s","report_local":DT,"dep_local":DT,"arr_local":DT,"release_local":DT,"block_hours":"f"},
 "d4_absences": {"absence_id":"s","crew_id":"s","notification_ts":DT,"absence_start":D,"absence_end":D,"duration_days":"i","absence_type":"s","affected_pairing_id":"s","base":"s","fleet":"s","position":"s"},
 "d5_reserve_callouts": {"callout_id":"s","crew_id":"s","call_ts":DT,"report_ts":DT,"assigned_pairing_id":"s","outcome":"s","base":"s","fleet":"s"},
 "d6_schedule_changes": {"change_id":"s","crew_id":"s","change_ts":DT,"old_block_type":"s","new_block_type":"s","new_pairing_id":"s","reason_code":"s","initiator":"s"},
 "d7_pay_register": {"crew_id":"s","pay_period":"s","pay_code":"s","amount_cad":"f","duty_date":D,"linked_pairing_id":"s"},
 "d8_flight_movements": {"flight_no":"s","date":D,"origin":"s","destination":"s","fleet":"s","sched_dep_local":DT,"sched_arr_local":DT,"actual_dep_local":DT,"actual_arr_local":DT,"delay_minutes":"i","iata_delay_code":"s","cancelled":"i","cancel_reason":"s"},
 "d9_station_days": {"station":"s","date":D,"disruption_class":"s","season":"s","intensity_multiplier":"f"},
 "d10_positioning_invoices": {"date":D,"station":"s","cost_type":"s","amount_cad":"f","crew_id":"s","pairing_id":"s"},
 "d11_training_sessions": {"crew_id":"s","session_type":"s","start_date":D,"end_date":D,"requalification_deadline":D,"reschedule_cost_cad_estimate":"f"},
}
BANNED = {"name","full_name","first_name","last_name","passenger_name","passenger","pax_name","email","phone","dob","date_of_birth","address","employee_number","ssn","sin"}
ids = {}
for name, schema in S.items():
    p = Path(f"{name}.csv")
    if not p.exists():
        print(f"{name}: MANQUANT"); continue
    err = []
    with p.open(encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh); cols = set(r.fieldnames or [])
        if b := {c for c in cols if c.strip().lower() in BANNED}: err.append(f"colonnes interdites {sorted(b)}")
        if cols != set(schema): err.append(f"manquantes={sorted(set(schema)-cols)} en trop={sorted(cols-set(schema))}")
        n = zero = num_ids = 0
        for row in r:
            n += 1
            for c, k in schema.items():
                v = (row.get(c) or "").strip()
                if not v: continue
                bad = (k in (D, DT) and not re.match(k, v)) or (k == "i" and not re.match(r"^-?\d+$", v)) \
                      or (k == "f" and not re.match(r"^-?\d+(\.\d+)?$", v))
                if bad and len(err) < 8: err.append(f"ligne {n+1} {c}={v!r}")
            if "crew_id" in schema and re.match(r"^\d+$", row.get("crew_id") or ""): num_ids += 1
            if name == "d2_rosters" and row.get("start_utc") == row.get("end_utc"): zero += 1
        if num_ids: err.insert(0, f"{num_ids} crew_id numériques (matricules ?) – pseudonymiser")
        if zero: err.append(f"{zero} blocs D2 de durée 0")
    if name == "d2_rosters":
        with p.open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not any(x["block_type"] == "RESERVE" for x in rows): err.append("aucun bloc RESERVE")
    print(f"{name}: {'OK' if not err else 'ERREURS'} ({n} lignes)")
    for e in err: print("   -", e)
```
