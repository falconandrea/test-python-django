(() => {
    function initialize(editor) {
        if (editor.dataset.ready || editor.closest('.empty-form')) return;
        editor.dataset.ready = 'true';
        const input = editor.querySelector('input[type="hidden"]');
        const rows = editor.querySelector('.checklist-editor-rows');
        let options;
        try { options = JSON.parse(input.value || '[]') || []; }
        catch { options = []; }
        if (!Array.isArray(options)) options = [];
        const sync = () => {
            input.value = JSON.stringify(options);
            input.dispatchEvent(new Event('change', { bubbles: true }));
        };
        function draw(focusIndex) {
            rows.replaceChildren();
            options.forEach((option, index) => {
                const row = document.createElement('div');
                row.className = 'checklist-editor-option';
                const label = document.createElement('label');
                label.textContent = `Opzione ${index + 1} — Markdown`;
                const textarea = document.createElement('textarea');
                textarea.id = `${input.id}_option_${index}`;
                label.htmlFor = textarea.id;
                textarea.rows = 5;
                textarea.value = typeof option.text === 'string' ? option.text : '';
                textarea.placeholder = 'Testo in **grassetto**\n\nAltro paragrafo con [un link](https://...)';
                textarea.addEventListener('input', () => { option.text = textarea.value; sync(); });
                const actions = document.createElement('div');
                actions.className = 'checklist-editor-actions';
                function button(text, disabled, action) {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.textContent = text;
                    button.disabled = disabled;
                    button.addEventListener('click', action);
                    actions.append(button);
                }
                button('Sposta su', index === 0, () => {
                    [options[index - 1], options[index]] = [options[index], options[index - 1]];
                    sync(); draw(index - 1);
                });
                button('Sposta giù', index === options.length - 1, () => {
                    [options[index + 1], options[index]] = [options[index], options[index + 1]];
                    sync(); draw(index + 1);
                });
                button('Elimina', false, () => { options.splice(index, 1); sync(); draw(); });
                row.append(label, textarea, actions);
                rows.append(row);
                if (focusIndex === index) textarea.focus();
            });
        }
        editor.querySelector('.checklist-add').addEventListener('click', () => {
            options.push({ id: null, text: '' });
            sync(); draw(options.length - 1);
        });
        const blockRow = editor.closest('tr');
        const kind = blockRow?.querySelector('select[name$="-kind"]');
        if (kind) {
            const toggle = () => { editor.hidden = kind.value !== 'checklist'; };
            kind.addEventListener('change', toggle);
            toggle();
        }
        draw();
    }
    const scan = () => document.querySelectorAll('.checklist-editor').forEach(initialize);
    document.addEventListener('DOMContentLoaded', scan);
    document.addEventListener('formset:added', scan);
})();
