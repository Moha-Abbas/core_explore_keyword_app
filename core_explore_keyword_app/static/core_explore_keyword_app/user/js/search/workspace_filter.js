// Filter by Workspace: type-to-search + chips, same interaction pattern as
// the Visualization page's workspace selector. Selecting/removing a chip
// only updates the hidden #id_workspaces field - it takes effect on the next
// Search click, same as the Filter by Test pills.
$(document).ready(function () {
    var dataEl = document.getElementById('ek-workspace-data');
    var hiddenInput = document.getElementById('id_workspaces');
    var wrapper = document.getElementById('ek-workspace-tags');
    if (!dataEl || !hiddenInput || !wrapper) return;

    var allWorkspaces = JSON.parse(dataEl.textContent || '[]');
    var chips = document.getElementById('ek-workspace-chips');
    var search = document.getElementById('ek-workspace-search');
    var optionsList = document.getElementById('ek-workspace-options');
    var clearAllBtn = document.getElementById('ek-workspace-clear');

    var selectedIds = (hiddenInput.value || '')
        .split(',')
        .map(function (id) { return id.trim(); })
        .filter(function (id) { return id; });

    function findWorkspace(id) {
        for (var i = 0; i < allWorkspaces.length; i++) {
            if (String(allWorkspaces[i].id) === id) return allWorkspaces[i];
        }
        return null;
    }

    function syncHiddenInput() {
        hiddenInput.value = selectedIds.join(',');
    }

    function updateClearAllVisibility() {
        if (clearAllBtn) clearAllBtn.classList.toggle('show', selectedIds.length > 0);
    }

    function renderChips() {
        chips.innerHTML = '';
        selectedIds.forEach(function (id) {
            var ws = findWorkspace(id);
            if (!ws) return;
            var chip = document.createElement('span');
            chip.className = 'ek-ws-tag-chip' + (ws.is_pseudo ? ' ek-ws-tag-chip-pseudo' : '');
            chip.setAttribute('data-ws-id', id);
            chip.title = ws.title;
            var text = document.createElement('span');
            text.className = 'ek-ws-tag-chip-text';
            text.textContent = ws.title;
            chip.appendChild(text);
            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.setAttribute('aria-label', 'Remove ' + ws.title);
            removeBtn.innerHTML = '&times;';
            removeBtn.addEventListener('click', function () { removeWorkspace(id); });
            chip.appendChild(removeBtn);
            chips.appendChild(chip);
        });
        updateClearAllVisibility();
    }

    function closeOptions() {
        optionsList.style.display = 'none';
        optionsList.innerHTML = '';
    }

    function renderOptions(query) {
        var q = (query || '').trim().toLowerCase();
        var matches = allWorkspaces.filter(function (ws) {
            return selectedIds.indexOf(String(ws.id)) === -1 &&
                ws.title.toLowerCase().indexOf(q) !== -1;
        });

        optionsList.innerHTML = '';
        if (!matches.length) {
            var empty = document.createElement('div');
            empty.className = 'ek-ws-tag-empty';
            empty.textContent = 'No workspaces found';
            optionsList.appendChild(empty);
            optionsList.style.display = 'block';
            return;
        }
        matches.forEach(function (ws) {
            var opt = document.createElement('div');
            opt.className = 'ek-ws-tag-option' + (ws.is_pseudo ? ' ek-ws-tag-option-pseudo' : '');
            opt.textContent = ws.title + (ws.is_public ? ' (Public)' : '');
            opt.addEventListener('click', function () { addWorkspace(ws); });
            optionsList.appendChild(opt);
        });
        optionsList.style.display = 'block';
    }

    function addWorkspace(ws) {
        selectedIds.push(String(ws.id));
        search.value = '';
        closeOptions();
        renderChips();
        syncHiddenInput();
        search.focus();
    }

    function removeWorkspace(id) {
        selectedIds = selectedIds.filter(function (w) { return w !== id; });
        renderChips();
        syncHiddenInput();
    }

    search.addEventListener('input', function () { renderOptions(this.value); });
    search.addEventListener('focus', function () { renderOptions(this.value); });
    search.addEventListener('click', function () { renderOptions(this.value); });
    search.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeOptions();
            this.blur();
        } else if (e.key === 'Backspace' && !this.value && selectedIds.length) {
            removeWorkspace(selectedIds[selectedIds.length - 1]);
        }
    });
    document.addEventListener('click', function (e) {
        if (!wrapper.contains(e.target)) closeOptions();
    });
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', function () {
            selectedIds = [];
            renderChips();
            syncHiddenInput();
        });
    }

    renderChips();
});
