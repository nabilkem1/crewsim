# Questions for Pierre - clarifications before CrewSim reads AIMS directly

Two versions below: **section A = French, ready to send**; **section B = English copy** (same numbering). Each question says why we ask and gives a simple default answer where one exists, so a short reply (Oui / Non / "voir fichier") is enough. Priority: **[P1]** = we cannot finish the AIMS extraction or the cost model without it; **[P2]** = improves accuracy; **[P3]** = nice to have.

Context for the sender (not for Pierre): decisions taken 2026-11-03 - snapshot-first, published roster for D2, v3 pseudonym key hosted in `CrewSchedAI.sim`, pilots only (cabin-ready design), extraction SQL kept in the CrewSim repo, window = what AIMS has (reliable from 2024-05-14). The environment we read is the QAS copy of AIMS.

---

# A. Version francaise (a envoyer)

**Objet : CrewSim - questions de clarification avant la lecture directe d'AIMS (QAS)**

Bonjour Pierre,

On passe CrewSim sur une lecture directe de la base AIMS (environnement QAS, lecture seule) avec un instantane (snapshot) fige pour chaque calcul. On a reproduit tes fichiers v3 a partir d'AIMS avec de tres bons ecarts (rotations 99,6-100 %, heures de paie a 0,2 %, call-outs de reserve a +/-2 par mois), mais il reste des points que seul toi (ou les equipes derriere toi) peux trancher. Je les ai classes par theme ; marque [P1] = bloquant. Une reponse courte suffit pour la plupart. Les schemas CSV des fichiers complementaires sont dans le document joint.

## 1. Environnement et acces AIMS
1. **[P1] QAS vs production.** Le serveur est `PPR-MTLSQLAIMS1\AIMS`. Comment QAS est-il alimente (copie de la production, avec quel delai, quelle frequence) ? Nos controles montrent des ecritures du journal jusqu'a aujourd'hui, donc ce n'est pas une copie figee. *Pourquoi :* on doit savoir si ce qu'on valide en QAS sera identique en production. *Reponse simple :* "copie quotidienne / hebdomadaire / en continu".
2. **[P1] Compte de service et acces production.** Qui cree un compte de service (lecture seule) pour CrewSim et qui approuve l'acces a la production le moment venu ? Existe-t-il une copie de lecture (reporting) de la production, ou doit-on extraire hors heures de pointe ? *Pourquoi :* l'instance n'a pas de groupe de disponibilite ; on ne veut pas charger la production.
3. **[P1] Hebergement de la table de pseudonymes.** On veut heberger ta table `aims_crew_id -> crew_id (P######)` dans la base `CrewSchedAI`, schema `sim` (jamais dans le depot de code). Est-ce acceptable pour la Loi 25 / securite, et quel canal securise utilises-tu pour la livrer ? Peux-tu confirmer qu'elle couvre **tous** les equipages (pilotes et PNC), y compris les nouveaux embauches, et comment les nouveaux ids seront ajoutes ? *Pourquoi :* un id non mappe fait echouer l'extraction (on n'invente jamais d'id).
4. **[P2] Que s'est-il passe le 14 mai 2024 dans AIMS ?** A partir de cette date les journaux de modification (`LOG_ROSTER`) existent, la quasi-totalite des vols non annules ont des heures reelles, et les legs de train (SNCF) sont codes autrement ; avant, environ 48 % des vols planifies n'ont pas d'heures reelles. S'agit-il d'une migration / mise a niveau ? Existe-t-il des archives ou sauvegardes du journal avant cette date ? *Pourquoi :* c'est la raison pour laquelle on commence l'historique le 2024-05-14 et pas avant.

## 2. Comment tes fichiers v3 ont ete construits (pour reproduire ou justifier les ecarts)
5. **[P1] D2 - etat du roster.** Ton D2 correspond a quel etat : roster **publie** (a quelle date de publication), roster **actuel**, ou roster a une date donnee ? On trouve environ 10 % de couples pilote-rotation de plus dans ton D2 que dans AIMS (publie ou actuel), sans pouvoir l'expliquer.
6. **[P1] D2 - heures UTC.** Pour les blocs `PAIRING`, `start_utc` semble contenir l'heure **locale** de presentation etiquetee UTC (decalage de 6 h sur 55 % des rotations de janvier 2026 ; correct sur 1,2 %). Peux-tu confirmer ou nous dire comment `start_utc/end_utc` sont calcules ? *Pourquoi :* notre chargeur recree ensuite des chevauchements (367 raccourcis, 1 599 supprimes) a cause de cela.
7. **[P1] D2 - classification des codes d'activite.** Peux-tu nous donner la regle `code AIMS -> block_type` (PAIRING / DAY_OFF / VACATION / RESERVE / TRAINING / SIMULATOR / ABSENCE / OFFICE / OTHER / REST) ? En particulier : quels codes comptent comme **reserve courte (SC)** (AM, PM, AM0, PM0, REA1, PM1, XAM, XPM ?) et quel code est la **reserve longue (LC)** (LCR, depuis mars 2026 ?) ; d'ou vient le bloc `REST`, qui n'existe pas dans AIMS ? Nous avons pre-rempli les 450 codes dans `m01_activity_code_map.prefilled.csv` : il suffit de corriger. *Reponse simple :* "ton fichier pre-rempli + corrections".
8. **[P1] D4 - types d'absence.** Quels codes AIMS donnent `SICK`, `FAMILY`, `INJURY` ? (On observe MAL, CPP5 et quelques petits codes pour SICK ; que sont INV / MARH ? Les congés de plus de 60 jours sont-ils du SICK ?) Comment fusionnes-tu plusieurs codes consecutifs (MAL puis MFIT, etc.) en une seule absence ?
9. **[P1] D4 - `notification_ts`.** Quel evenement represente-t-il (moment ou le planificateur a saisi le code ? heure de notification du pilote ? `ROSTER.NOTDATE/NOTTIME` ?) et dans quel fuseau ? Que signifient exactement les sources `AUCUNE_ROTATION_A_RETIRER` et `INTROUVABLE` ? *Pourquoi :* AIMS permet de fournir un vrai horodatage pour 100 % des absences depuis 2024-03-14 ; on veut etre sur de mesurer la meme chose que toi.
10. **[P2] D5 - issues et horodatages.** Que veut dire `not_called` ? D'ou vient `call_ts` ? Les 238 lignes avec `report_ts` avant `call_ts` viennent-elles d'une jointure ? Existe-t-il un journal des appels (refus, absence, relache) en dehors d'AIMS ?
11. **[P1] D6 - `DRAFT` vs `SHORT_NOTICE_COVER`.** Quelle regle distingue les deux, et quelles sont les autres valeurs (`ROSTER_CHANGE`, `CASCADE_UNCOVERED`, `VOLUNTARY_SWAP`) ? Comment `initiator = IOC` est-il determine (100 % des lignes en v3) ? Les baisses de volume (juin-24, dec-24, juin-25, dec-25, juil/aout-26) viennent-elles de l'extraction ? *Pourquoi :* dans AIMS ces creux n'existent pas ; il n'y a pas de champ "raison", donc on doit reproduire ta regle ou la remplacer par le marqueur `ROSTERDT` (type 21).
12. **[P1] D7 - source et regles.** Ces lignes viennent-elles de Snowflake (`TIMESHEET_PNC_PNT`) ou d'un autre systeme de paie ? Nos controles : les heures de ton D7 collent a la table AIMS `TIMEPNCPNT` a 0,2 %, mais AIMS ne contient **aucun montant en dollars** et seulement 4 mois (juin-sept 2026). Donc :
    - a. Les montants (`amount_cad`, `premium_cad`, `rate_cad`) = heures x taux : quel taux (240 $/h ? par echelon d'anciennete ?) et a partir de quelles dates ?
    - b. `DRAFT_THX` : 150 % (prime = 50 %) ou 200 % ? depuis le 2026-02-01 ? Que represente `DRAFT_T2` ? Comment separes-tu `DRAFT_THX` de `OVERTIME_THX`, et `DRAFT_T2` de `HOLIDAY_T2` ?
    - c. `RESERVE_CREDIT` : AIMS donne 4,00 h (AM/PM depuis 2026-01-06), 3,00 h (LCR depuis 2026-03-01) et 3,33 h (anciens XAM/XPM = 799,20 $). Ton fichier paie 3,33 h jusqu'au 2026-02-28 : quelle est la date d'effet de paie ?
    - d. `AJU`, `DMG`, `BME`, `MIN`, `T_1_4`, `RED_CAP`, `P10/P16/P30` (heures dans AIMS, montants fixes chez toi) : une ligne d'explication par code, et pourquoi ton `AJU` est different (681 h vs 182 h en juillet 2026) ?
    - e. Pourquoi `C_IN` (environ 5 % de `CHV`) est-il exclu ? D'ou viennent les 1 318 montants negatifs de `CHV` ?
    - f. Bornes des periodes de paie (ex. 1-30 janv., 31 janv.-1 mars, 2-31 mars, puis mois civils) : confirmes-tu ?
13. **[P1] D8 - `cancelled`.** Ton `cancelled=1` semble signifier "aucune heure reelle" et non `LEGMAIN.CANCELLED` (en juin 2026, 42 de tes 46 vols annules ont `CANCELLED=0` avec des heures reelles). Confirmes-tu la regle ? Quelle definition d'annulation veux-tu pour CrewSim (annulation decidee a J-2 ou moins, ou toute suppression d'horaire) ?
14. **[P2] D8 - codes de retard.** Quelle regle choisis-tu quand un vol a plusieurs codes IATA (AIMS en a 14 329 de type 89 sur la periode, ton fichier 1 911) ? Retard depart seulement ? Pourquoi un code sur ~49 % des vols en retard alors qu'AIMS en code 100 % ?
15. **[P2] D8 - lignes particulieres.** Peux-tu confirmer que : les lignes origine = destination sont des legs retour (`LEGCD` A-D) ; TRN = trains SNCF ; P295 / PDH4 / 7M8 / W737... sont des avions affretes (ACMI/wet-lease) hors flotte propre ? Doit-on les exclure ?
16. **[P2] D3 - definitions.** `credit_hours` est-il bien la somme des heures bloc planifiees (et non un credit de paie) ? D'ou viennent les decalages de presentation (60 min avant) et de liberation (30 min apres), alors que le code de planification utilise 15 min de debriefing ? Comment determines-tu `fleet_detail` quand une rotation melange A321 et A321neo (118 en janvier) ?
17. **[P2] D1 - source RH.** D'ou viennent `hire_date`, `termination_date`, `employment_status` et `seniority_number` (AIMS n'a que des substituts via la validite des qualifications) ? Que veulent dire `L15` et `W7S8` ? Pourquoi 764 pilotes sur 1 500 sont-ils `TERMINATED` (historique complet voulu ?). Comment `fleet_detail` (A320-200 / A321-200 / neoLR) est-il determine ?
18. **[P2] D11 - formation.** Regle `code AIMS -> session_type` (11 types chez toi), codes de `INITIAL_GROUND` (on en retrouve 728 sessions contre 1 100), regle de fusion des jours consecutifs (ecart de 3 jours ?), intervalles de requalification (PPC : 6 mois dans AIMS, 365 jours chez toi) et source de `reschedule_cost_cad_estimate`.
19. **[P1] D10 - factures.** Source (comptes fournisseurs ?), pourquoi le fichier commence le 2025-06-28, comment une facture est rattachee a un equipage et a une rotation (13,9 % sans `crew_id`, 35 % sans `pairing_id`), comment relier une facture a une reservation AIMS (`HOTAC`), et signification des categories 2, 3 et 5 de `HOTAC`.

## 3. Donnees qui ne sont pas dans AIMS (voir les schemas joints)
20. **[P1] Paie et finance.** Qui, a la paie et aux finances, peut fournir : dictionnaire des codes de paie (F01), registre de paie en dollars (F02), taux et multiplicateurs avec dates d'effet (F03), regles de la convention (F04), coefficients de cout de planification (F06) ? Peux-tu nous mettre en contact (appel de 30 min) ? **Question cle :** le Snowflake (`TIMESHEET_PNC_PNT`) contient-il plus d'historique que les 4 mois d'AIMS ? Dans ton dernier courriel, l'equipe de Rania evaluait un historique plus long.
21. **[P1] Convention collective.** Quelles sont les valeurs confirmees : preavis minimal reserve courte / longue (D5 montre ~10 h et ~46 h en mediane, notre fichier de test dit 2 h et 12 h), garantie par jour, prime de draft, plafonds, blocs proteges (confirmes "aucun"), duree de la convention (2025-05-01 -> 2030-04-30 ?) ?
22. **[P2] Cout des perturbations.** Existe-t-il des couts reels d'annulation et de retard (APPR, prise en charge des passagers, reaccomodement) pour calibrer nos valeurs fictives (25 000 $ par annulation, 55 $/min de retard) ?
23. **[P2] Flotte A321neoLR.** Peux-tu nous fournir la liste des immatriculations neoLR (AIMS a 22 avions de type 32Q) et l'historique de qualification neoLR des pilotes (dans AIMS, tous les pilotes A321 ont les qualifications 321 et 32Q avec les memes dates) ?
24. **[P2] Qui a fait la modification.** Peux-tu nous aider a classer les utilisateurs et programmes AIMS par groupe (IOC, Controle des equipages, Planification, systeme automatique) ? On compte environ 9 programmes (par ex. `MOVEMENT.EXE`) et ~100 utilisateurs actifs sur 100 jours.
25. **[P3] Cause des annulations et des drafts.** Existe-t-il, hors AIMS (journal OCC/IROPS), la cause d'une annulation (meteo, technique, equipage...) et la raison d'un draft (maladie, annulation, retard) ?
26. **[P3] Conventions de presentation.** Heures de presentation / liberation par flotte et groupe, et fenetres horaires des reserves AM/PM (heures de debut et fin).

## 4. Draft : Snowflake `DMT_DRAFTS_PNT_PNC`
27. **[P1] Logique du mart.** Le fichier `DRAFTPNCPNT.sql` utilise `ROSTERDT` (`RECTYPE=21`, `VALUE1` = 15, 16, 19, 20). Peux-tu confirmer ces codes, et nous dire ce que signifient les **autres valeurs de `VALUE1`** (1-14, 17, 18, 21-24, 27) ? Un marqueur "journee" (sans leg, `LEG_FLT=0`) est-il copie sur tous les legs du jour dans Snowflake (on obtient 59 lignes pour 11 marqueurs en janvier 2026) ? Quel est `CREW_CODE` (id AIMS ? autre) ? `15/16` : "a la base / hors base" se rapporte-t-il a la base du pilote ou a celle de la rotation ?
28. **[P2] Statut avant le draft.** 85 % des drafts de pilotes de janvier 2026 viennent de `WFLY` ("willing to fly"), pas de "jour off". Ton `DAY_OFF` inclut-il `WFLY` ? Sinon comment les distingues-tu ?

## 5. Calendrier
29. **[P1] Fichiers minimaux et dates.** Pour demarrer, il nous faut : codes de paie, registre de paie, taux, regles de la convention, coefficients de cout, table de pseudonymes et statut d'emploi (voir tableau de priorites). Quelle date de livraison est realiste pour chacun ? On accepte l'historique qui existe (a partir du 2024-05-14) ; rien avant n'est necessaire.
30. **[P3] Periode de reference.** Souhaites-tu qu'on garde tes fichiers v3 comme jeu de regression (pour comparer avec la lecture AIMS) ? Peux-tu nous dire si une nouvelle version de ces fichiers est prevue ?

Merci beaucoup !
Nabil

---

# B. English copy (same numbering)

**Subject: CrewSim - clarification questions before reading AIMS directly (QAS)**

We are switching CrewSim to read AIMS directly (QAS, read-only) into a frozen snapshot per run. AIMS reproduces your v3 files closely (pairings 99.6-100 %, pay hours within 0.2 %, reserve call-outs +/-2 a month); the points below are what only you (or the teams behind you) can decide. [P1] = blocking.

## 1. AIMS environment and access
1. **[P1] QAS vs production.** Server `PPR-MTLSQLAIMS1\AIMS`. How is QAS fed from production (delay, frequency)? Journal writes are current to today, so it is not a frozen restore. We must know whether what we validate in QAS equals production.
2. **[P1] Service account and production access.** Who creates a read-only service account for CrewSim and who approves production access later? Is there a reporting copy of production, or must we extract off-peak (the instance has no availability group)?
3. **[P1] Pseudonym table hosting.** We want to host your `aims_crew_id -> crew_id (P######)` map in `CrewSchedAI`, schema `sim` (never in the code repository). Acceptable for Law 25 / security? Which secure channel will you use? Does it cover **all** crew (pilots and cabin), including new hires, and how are new ids added? An unmapped id makes the extraction fail; we never invent ids.
4. **[P2] What changed in AIMS on 2024-05-14?** From that date change journals exist, actual times exist for almost all non-cancelled flights, and SNCF train legs are encoded differently; before it ~48 % of scheduled flights have no actual times. A migration/upgrade? Are older journal archives or backups available?

## 2. How your v3 files were built (to reproduce or explain differences)
5. **[P1] D2 roster state.** Is D2 the published roster (which publication date), the current roster, or an as-of roster? Your D2 has ~10 % more crew-pairing pairs than AIMS (published or current) for January 2026, unexplained.
6. **[P1] D2 UTC times.** `PAIRING` blocks seem to hold the local report time labelled UTC (6 h off on 55 % of January 2026 pairings, correct on 1.2 %). Please confirm how `start_utc/end_utc` are computed; our loader then creates overlaps (367 shortened, 1,599 dropped).
7. **[P1] Activity code classification.** The rule AIMS code -> `block_type`; which codes are short-call reserve (AM, PM, AM0, PM0, REA1, PM1, XAM, XPM?) and which is long-call (LCR since March 2026?); where does the `REST` block come from (not in AIMS)? We pre-filled the 450 codes (`m01_activity_code_map.prefilled.csv`): correct it.
8. **[P1] D4 absence types.** Which AIMS codes give SICK, FAMILY, INJURY (we see MAL, CPP5 and small codes for SICK; what are INV / MARH; are >60-day absences SICK)? How are consecutive different sick codes merged into one absence?
9. **[P1] D4 `notification_ts`.** Which event does it record (planner entry time, crew notified time, `ROSTER.NOTDATE/NOTTIME`) and in which time zone? Meaning of the sources `AUCUNE_ROTATION_A_RETIRER` and `INTROUVABLE`? AIMS can give a real timestamp for 100 % of absences since 2024-03-14.
10. **[P2] D5 outcomes and timestamps.** Meaning of `not_called`; source of `call_ts`; are the 238 rows with `report_ts` before `call_ts` join defects? Is there a call log (declined, no-show, released) outside AIMS?
11. **[P1] D6 `DRAFT` vs `SHORT_NOTICE_COVER`.** The rule separating them and the other values (`ROSTER_CHANGE`, `CASCADE_UNCOVERED`, `VOLUNTARY_SWAP`); how `initiator = IOC` (100 % of rows) is decided; are the monthly volume dips an extraction artefact? They do not exist in AIMS, which has no reason field, so we must reproduce your rule or replace it with the `ROSTERDT` type-21 marker.
12. **[P1] D7 source and rules.** From Snowflake `TIMESHEET_PNC_PNT` or a payroll system? Your hours match AIMS `TIMEPNCPNT` within 0.2 %, but AIMS has **no dollar amounts** and only 4 months (June-Sept 2026):
    - a. Rate behind `amount_cad`/`premium_cad`/`rate_cad` (240 $/h? by seniority step?) and effective dates.
    - b. `DRAFT_THX` 150 % (premium = 50 %) or 200 %, from 2026-02-01? What is `DRAFT_T2`? How are `DRAFT_THX` vs `OVERTIME_THX` and `DRAFT_T2` vs `HOLIDAY_T2` separated?
    - c. `RESERVE_CREDIT`: AIMS has 4.00 h (AM/PM since 2026-01-06), 3.00 h (LCR since 2026-03-01), 3.33 h (legacy XAM/XPM = 799.20 $). Your file pays 3.33 h until 2026-02-28: what is the pay effective date?
    - d. `AJU`, `DMG`, `BME`, `MIN`, `T_1_4`, `RED_CAP`, `P10/P16/P30` (hours in AIMS, flat dollars in yours): one line of explanation per code; why is your `AJU` different (681 h vs 182 h in July 2026)?
    - e. Why is `C_IN` (~5 % of `CHV`) excluded? Where do the 1,318 negative `CHV` amounts come from?
    - f. Pay period boundaries (e.g. Jan 1-30, Jan 31-Mar 1, Mar 2-31, then calendar months): confirm.
13. **[P1] D8 `cancelled`.** Your `cancelled=1` appears to mean "no actual times", not `LEGMAIN.CANCELLED` (June 2026: 42 of your 46 cancelled rows have `CANCELLED=0` with actual times). Confirm. Which definition does CrewSim need (decided within 2 days of departure, or any schedule removal)?
14. **[P2] D8 delay codes.** Which rule picks one code when a flight has several IATA codes (AIMS has 14,329 type-89 lines in the period, your file 1,911)? Departure delay only? Why codes on ~49 % of delayed flights when AIMS codes 100 %?
15. **[P2] D8 special rows.** Confirm: origin = destination rows are return legs (`LEGCD` A-D); TRN = SNCF trains; P295 / PDH4 / 7M8 / W737... are wet-lease/ACMI aircraft outside own fleet. Exclude them?
16. **[P2] D3 definitions.** Is `credit_hours` the sum of scheduled block hours (not a pay credit)? Origin of the 60-min report and 30-min release offsets (the planner code uses a 15-min debrief)? How is `fleet_detail` set when a pairing mixes A321 and A321neo (118 in January)?
17. **[P2] D1 HR source.** Source of `hire_date`, `termination_date`, `employment_status`, `seniority_number` (AIMS only offers proxies from qualification validity)? Meaning of `L15` and `W7S8`? Why 764 of 1,500 pilots `TERMINATED` (full history intended)? How is `fleet_detail` (A320-200 / A321-200 / neoLR) set?
18. **[P2] D11 training.** Rule AIMS code -> `session_type` (11 types), the `INITIAL_GROUND` codes (we recover 728 sessions vs 1,100), merge rule for consecutive days (3-day gap?), requalification intervals (PPC: 6 months in AIMS, 365 days in yours), source of `reschedule_cost_cad_estimate`.
19. **[P1] D10 invoices.** Source (accounts payable?), why the file starts on 2025-06-28, how an invoice is linked to a crew member and pairing (13.9 % without `crew_id`, 35 % without `pairing_id`), how to link an invoice to an AIMS booking (`HOTAC`), meaning of `HOTAC` categories 2, 3 and 5.

## 3. Data that is not in AIMS (see the attached schemas)
20. **[P1] Pay and finance.** Who in payroll and finance can provide the pay code dictionary (F01), the pay register in dollars (F02), rates and multipliers with effective dates (F03), agreement rules (F04) and planning cost coefficients (F06)? Can you introduce us (30-minute call)? **Key question:** does Snowflake (`TIMESHEET_PNC_PNT`) hold more history than AIMS's 4 months? Your last email said Rania's team was evaluating a longer history.
21. **[P1] Collective agreement.** Confirmed values: minimum notice for short/long-call reserve (D5 medians ~10 h and ~46 h, our test file says 2 h and 12 h), daily guarantee, draft premium, caps, protected blocks (confirmed "none"), agreement term (2025-05-01 -> 2030-04-30?).
22. **[P2] Disruption costs.** Real costs of cancellations and delays (APPR, passenger care, rebooking) to replace our placeholders (25,000 $ per cancellation, 55 $/min delay)?
23. **[P2] A321neoLR.** The list of neoLR registrations (AIMS has 22 aircraft of type 32Q) and the pilots' neoLR qualification history (in AIMS every A321 pilot holds 321 and 32Q with identical dates).
24. **[P2] Who made the change.** Help classifying AIMS users and programs into groups (IOC, crew control, planning, automatic system): ~9 programs (e.g. `MOVEMENT.EXE`) and ~100 active users over 100 days.
25. **[P3] Causes.** Outside AIMS (OCC/IROPS log), is there a cancellation cause (weather, technical, crew) and a draft trigger (sick call, cancellation, delay)?
26. **[P3] Duty conventions.** Report/release offsets per fleet and crew group, and the AM/PM reserve window times.

## 4. Draft: Snowflake `DMT_DRAFTS_PNT_PNC`
27. **[P1] Mart logic.** `DRAFTPNCPNT.sql` uses `ROSTERDT` (`RECTYPE=21`, `VALUE1` = 15, 16, 19, 20). Confirm these codes and tell us what the **other `VALUE1` values** (1-14, 17, 18, 21-24, 27) mean. Is a day-level marker (no leg, `LEG_FLT=0`) copied to every leg of the day in Snowflake (11 markers give 59 rows in January 2026)? What is `CREW_CODE` (AIMS id or other)? For 15/16, does "at base / out of base" refer to the crew member's base or the pairing's base?
28. **[P2] Status before the draft.** 85 % of January 2026 pilot drafts come from `WFLY` ("willing to fly"), not "day off". Does your `DAY_OFF` include `WFLY`? If not, how do you separate them?

## 5. Schedule
29. **[P1] Minimal files and dates.** To start we need: pay codes, pay register, rates, agreement rules, cost coefficients, pseudonym table, employment status. What delivery date is realistic for each? We accept the history that exists (from 2024-05-14); nothing earlier is required.
30. **[P3] Reference period.** Shall we keep your v3 files as a regression set (to compare with the AIMS read)? Is a new version of those files planned?

