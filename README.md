# Template compilabili

Applicazione Django con backoffice nel Django Admin e una pagina pubblica distinta per compilare i template tramite link.

## Avvio con Docker

1. Avvia i servizi: `docker compose up --build`.
2. Crea l'admin iniziale: `docker compose exec web python manage.py createsuperuser`.
3. Apri <http://localhost:8000/admin/>.

I valori predefiniti sono per lo sviluppo locale; `.env.example` elenca le variabili configurabili. Le migrazioni vengono applicate all'avvio e PostgreSQL conserva i dati nel volume `postgres_data`.

## Flusso nel Django Admin

- L'admin crea utenti moderatori dalla sezione **Utenti**. I moderatori accedono allo stesso `/admin/`.
- L'admin crea un template e assegna uno o più moderatori. Un moderatore vede e modifica solo i template assegnati.
- I blocchi si aggiungono nella pagina del template. Il campo **Ordine** usa numeri crescenti; per una checklist, inserisci una voce per riga nel campo **Voci checklist**.
- L'azione **Conferma e blocca i template selezionati** rende immutabile la struttura. **Duplica i template selezionati** crea copie in bozza e mantiene i moderatori assegnati.
- Da **Risposte** si crea un link nominato per ogni persona: ogni riga rappresenta una persona e la sua compilazione. Aprendo la riga si vedono insieme le risposte, raggruppate per blocco; dalla lista si può chiudere o riattivare il link. Un link chiuso mostra una pagina informativa e non accetta altre modifiche.
- Chi riceve il link non ha un account: vede il contenuto e può modificare solo checklist e campi di testo. Ogni link conserva la propria compilazione.

Nei blocchi di testo l'admin scrive Markdown (ad esempio `# Titolo`, `**grassetto**`, elenchi e `[link](https://...)`). Il Markdown viene convertito e sanificato sul server prima di essere mostrato all'utente. I vecchi contenuti HTML dei blocchi vengono convertiti in Markdown dalla migrazione.
