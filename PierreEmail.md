Bonjour Nabil,
Voici le second envoi en correction selon tes commentaires! Pour l'instant un plus grand historique est conditionné par l'évaluation dans Snowflake par l'équipe de Rania de TIMESHEET_PNC_PNT avec un plus long historique. C'est faisable, on pourra le faire dans un deuxième temps.
Ce qui a été corrigé
•	D2 (plannings) : de vrais blocs avec début et fin réels
•	D3 / D3 legs : un même code de rotation AIMS couvre plusieurs voyages différents. Chaque rotation est donc maintenant identifiée par son code et sa date de début (ex. C0001_20260501).
•	D6 : horodatages complets
•	D7 (paie) : pilotes seulement, codes de paie explicites et montants en dollars.
o	Les drafts sont dans DRAFT_THX (temps et demi, payé en temps double depuis la CC 2026) et DRAFT_T2.
o	La réserve est dans RESERVE_CREDIT.
o	Les primes en devoir sont P10, P30 et P16.
o	Taux appliqués : 240 $/h en temps simple, 480 $/h en temps double.
•	D8 : dates et heures complètes
•	D10 (reconstruit) : noms des passagers supprimés, et toutes les stations sont maintenant des codes aéroport. Le fichier ne contient que des coûts PNT.
•	D11 (nouveau) : 1 020 sessions de formation pour 419 pilotes (PPC, simulateur de qualification de type, CRM, cours récurrents, examens…). 
•	Loi 25 : les crew_id sont anonymisés (P######), avec le même pseudonyme dans tous les fichiers et d'un envoi à l'autre. 
Réponses à tes questions
1.	*Heures _local (D3, D8) : heure locale de l'aéroport du segment, recalculée à partir de l'UTC avec l'heure d'été. Les colonnes d'heure locale d'AIMS appliquaient un décalage fixe et faux, on ne les utilise plus. Dans D2, *_local est l'heure de la base du pilote.
2.	CHV : c'est le crédit horaire régulier, en heures. Il apparaît maintenant avec les autres codes de paie, avec un montant en dollars.
3.	disruption_class (D9) : classe calculée par station et par jour, à partir du retard moyen au départ des vols qui touchent la station : 
o	SEVERE : au moins une annulation, ou un retard moyen d'au moins 45 min ;
o	DISRUPTED : de 20 à 45 min ;
o	NORMAL : de 5 à 20 min ;
o	CALM : sous 5 min.

Dis-moi si ce round te permet de lancer une première simulation!
