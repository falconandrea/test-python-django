document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('block-forms');
    const total = document.getElementById('id_blocks-TOTAL_FORMS');
    document.getElementById('add-block').addEventListener('click', () => {
        const index = Number(total.value);
        const wrapper = document.createElement('div');
        wrapper.innerHTML = document.getElementById('empty-block-form').innerHTML.replaceAll('__prefix__', String(index));
        const row = wrapper.firstElementChild;
        const positions = Array.from(container.querySelectorAll('input[name$="-position"]'), field => Number(field.value) || 0);
        row.querySelector('input[name$="-position"]').value = positions.length ? Math.max(...positions) + 1 : 0;
        container.append(row);
        total.value = index + 1;
        document.dispatchEvent(new CustomEvent('formset:added'));
        row.querySelector('input[name$="-title"]').focus();
    });
});
