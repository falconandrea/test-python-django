# Template compilabili

Applicazione Django con backoffice nel Django Admin e frontend autenticato per gestire e compilare i template.

## Avvio con Docker

1. Avvia i servizi: `docker compose up --build`.
2. Crea l'admin iniziale: `docker compose exec web python manage.py createsuperuser`.
3. Apri <http://localhost:8000/admin/>.

I valori predefiniti sono per lo sviluppo locale; `.env.example` elenca le variabili configurabili. Le migrazioni vengono applicate all'avvio e PostgreSQL conserva i dati nel volume `postgres_data`.

## Template e workbook

- I **template** contengono solo la struttura riutilizzabile. Gli admin possono modificarli sempre; non hanno moderatori, utenti o conferma.
- Un admin crea un **workbook** scegliendo nome, template di origine e un moderatore. Blocchi e opzioni Markdown vengono copiati, con nuovi ID, nella struttura indipendente del workbook.
- Le modifiche al template originale vengono incluse solo nei workbook creati successivamente.
- Admin e moderatore assegnato collegano gli utenti con ruolo **user** al workbook. Revocare un’assegnazione conserva le risposte e impedisce l’accesso alla compilazione.
- Il workbook nasce in **bozza**. Il moderatore assegnato può modificarlo e confermarlo; dopo la conferma può consultarlo e gestire utenti e risposte. Gli admin possono modificarne la struttura anche dopo la conferma.
- Gli user vedono e compilano solo i workbook confermati e assegnati al proprio account. Ogni coppia workbook/utente ha una compilazione aggiornabile.
- La sezione **Risposte** nel backoffice mostra le compilazioni dei workbook. I moderatori accedono solo ai propri workbook e alle relative risposte; gli user non accedono al backoffice.

## Frontend

- `/login/`: accesso con le credenziali Django.
- `/`: dashboard dei workbook; gli admin vedono anche i template.
- `/templates/<id>/edit/`: editor del template, riservato agli admin.
- `/workbooks/new/`: creazione di un workbook, riservata agli admin.
- `/workbooks/<id>/edit/`: modifica del workbook o consultazione dopo la conferma per i moderatori.
- `/workbooks/<id>/responses/`: assegnazione degli utenti e lettura delle risposte.
- `/workbooks/<id>/`: compilazione personale, riservata agli user assegnati a un workbook confermato.

Nei blocchi di testo e nelle opzioni checklist si scrive Markdown (`**grassetto**`, elenchi, paragrafi e `[link](https://...)`). Il contenuto viene convertito e sanificato sul server prima della visualizzazione. Ogni opzione si aggiunge e si riordina separatamente.

La migrazione `0008_workbookassignment_and_more` conserva utenti, template, blocchi e opzioni. Rimuove la conferma e le associazioni dei template, eliminando le vecchie assegnazioni e risposte dimostrative. I workbook vengono poi creati esplicitamente dalle strutture esistenti.
