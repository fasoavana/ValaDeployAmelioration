// new-stack.js
// Gestion du formulaire de création de stack (nouveau projet avec composants)
document.addEventListener('DOMContentLoaded', () => {
    // Initialisation des composants partagés (sidebar, etc.)
    if (typeof loadComponents === 'function') {
        loadComponents();
    }

    // Gestion du sélecteur de composant
    const addBtn = document.getElementById('add-component-btn');
    const picker = document.getElementById('component-picker');

    if (addBtn && picker) {
        addBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleComponentPicker();
        });

        document.addEventListener('click', (e) => {
            if (!picker.contains(e.target) && !addBtn.contains(e.target)) {
                closeComponentPicker();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeComponentPicker();
        });

        picker.querySelectorAll('.component-picker-option').forEach(option => {
            option.addEventListener('click', () => {
                const kind = option.dataset.kind;
                closeComponentPicker();
                addComponent(kind);
            });
        });
    }

    const componentsContainer = document.getElementById('componentsContainer');

    // Délégation d'événements pour les composants et variables d'env
    componentsContainer.addEventListener('click', (e) => {
        // Supprimer un composant
        if (e.target.closest('.remove-component-btn')) {
            const card = e.target.closest('.component-card');
            if (document.querySelectorAll('.component-card').length > 1) {
                card.remove();
                updateConnectors();
            } else {
                if (typeof ValaToast !== 'undefined') {
                    ValaToast.show({
                        type: 'warning',
                        title: 'Action impossible',
                        message: 'A stack must contain at least one component.'
                    });
                } else {
                    alert("A stack must contain at least one component.");
                }
            }
        }

        // Toggle mode variables d'environnement
        if (e.target.closest('.env-mode-toggle')) {
            const btn = e.target.closest('.env-mode-toggle');
            const card = btn.closest('.component-card');
            const mode = btn.dataset.mode;

            // Mettre à jour les boutons actifs
            card.querySelectorAll('.env-mode-toggle').forEach(b => {
                b.classList.remove('text-primary');
                b.classList.add('text-on-surface-variant');
            });
            btn.classList.remove('text-on-surface-variant');
            btn.classList.add('text-primary');

            // Afficher/cacher les sections
            const manualMode = card.querySelector('.env-manual-mode');
            const fileMode = card.querySelector('.env-file-mode');

            if (mode === 'file') {
                manualMode.classList.add('hidden');
                fileMode.classList.remove('hidden');
            } else {
                fileMode.classList.add('hidden');
                manualMode.classList.remove('hidden');
            }
        }

        // Ajouter une variable d'environnement
        if (e.target.closest('.add-env-var-btn')) {
            const card = e.target.closest('.component-card');
            const list = card.querySelector('.env-vars-list');
            const newRow = document.createElement('div');
            newRow.className = 'flex items-center gap-sm env-var-row';
            newRow.innerHTML = `
                <input class="env-key flex-1 h-10 border border-outline-variant rounded px-md font-mono-code text-mono-code bg-surface-container-low text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="CLÉ" type="text"/>
                <span class="text-on-surface-variant font-mono-code">=</span>
                <div class="flex-1 relative">
                    <input class="env-value w-full h-10 border border-outline-variant rounded px-md pr-10 font-mono-code text-mono-code bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="VALEUR" type="password"/>
                    <button type="button" class="absolute right-2 top-2 text-on-surface-variant hover:text-on-surface transition-colors toggle-visibility-btn" title="Afficher/Masquer">
                        <span class="material-symbols-outlined text-[18px]">visibility</span>
                    </button>
                </div>
                <button type="button" class="w-10 h-10 flex-shrink-0 flex items-center justify-center text-on-surface-variant hover:text-error transition-colors border border-transparent hover:border-outline-variant rounded remove-env-var-btn">
                    <span class="material-symbols-outlined text-[18px]">close</span>
                </button>
            `;
            list.appendChild(newRow);
        }

        // Supprimer une variable d'environnement
        if (e.target.closest('.remove-env-var-btn')) {
            e.target.closest('.env-var-row').remove();
        }

        // Basculer la visibilité d'une variable
        if (e.target.closest('.toggle-visibility-btn')) {
            const btn = e.target.closest('.toggle-visibility-btn');
            const input = btn.parentElement.querySelector('.env-value');
            const icon = btn.querySelector('.material-symbols-outlined');

            if (input.type === 'password') {
                input.type = 'text';
                icon.textContent = 'visibility';
                btn.classList.remove('text-on-surface-variant');
                btn.classList.add('text-primary');
            } else {
                input.type = 'password';
                icon.textContent = 'visibility_off';
                btn.classList.remove('text-primary');
                btn.classList.add('text-on-surface-variant');
            }
        }

        // Supprimer le fichier uploadé
        if (e.target.classList.contains('env-file-remove')) {
            const card = e.target.closest('.component-card');
            const fileInput = card.querySelector('.env-file-input');
            const fileInfo = card.querySelector('.env-file-info');
            const filename = card.querySelector('.env-filename-display');

            fileInput.value = '';
            fileInfo.classList.add('hidden');
            filename.textContent = '';
        }
    });

    // Écoute du changement de fichier (se déclenche APRÈS la sélection réelle,
    // contrairement à "click" qui se déclenche à l'ouverture de la boîte de dialogue)
    componentsContainer.addEventListener('change', (e) => {
        if (e.target.classList.contains('env-file-input')) {
            handleEnvFileUpload(e.target);
        }
    });

    // Gestion du drag & drop sur les zones de dépôt de fichier .env
    componentsContainer.addEventListener('dragover', (e) => {
        const dropZone = e.target.closest('.env-file-mode > div');
        if (dropZone) {
            e.preventDefault();
            dropZone.classList.add('border-primary', 'bg-surface-variant');
        }
    });

    componentsContainer.addEventListener('dragleave', (e) => {
        const dropZone = e.target.closest('.env-file-mode > div');
        if (dropZone) {
            dropZone.classList.remove('border-primary', 'bg-surface-variant');
        }
    });

    componentsContainer.addEventListener('drop', (e) => {
        const dropZone = e.target.closest('.env-file-mode > div');
        if (!dropZone) return;
        e.preventDefault();
        dropZone.classList.remove('border-primary', 'bg-surface-variant');

        const file = e.dataTransfer.files[0];
        if (!file) return;

        const fileInput = dropZone.querySelector('.env-file-input');

        // On transfère le fichier déposé vers l'input caché,
        // puis on réutilise la logique d'upload existante
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(file);
        fileInput.files = dataTransfer.files;

        handleEnvFileUpload(fileInput);
    });
});

function toggleComponentPicker() {
    const picker = document.getElementById('component-picker');
    picker.classList.toggle('hidden');
}

function closeComponentPicker() {
    const picker = document.getElementById('component-picker');
    if (picker) picker.classList.add('hidden');
}

function updateConnectors() {
    // Le CSS gère déjà le :last-child, cette fonction est là pour d'éventuels futurs ajustements
}

function addComponent(kind) {
    if (!kind || !['database', 'back', 'front'].includes(kind)) return;

    const container = document.getElementById('componentsContainer');
    const div = document.createElement('div');
    div.className = 'stack-item relative pb-lg component-card';
    div.dataset.kind = kind;

    let innerHTML = '';

    if (kind === 'database') {
        innerHTML = `
            <div class="stack-connector"></div>
            <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-lg md:p-xl relative z-10 hover:border-outline transition-colors">
                <div class="flex items-center gap-md mb-lg border-b border-outline-variant pb-md">
                    <div class="w-8 h-8 rounded bg-surface-variant flex items-center justify-center text-tertiary border border-outline-variant">
                        <span class="material-symbols-outlined text-[18px]">database</span>
                    </div>
                    <input class="component-name font-label-md text-label-md font-bold text-on-surface bg-transparent border-none p-0 focus:ring-0 focus:outline-none w-auto" placeholder="Nom (ex: db)" type="text" value="database" required/>
                    <input type="hidden" class="component-kind" value="database">
                    <button class="ml-auto text-on-surface-variant hover:text-error transition-colors remove-component-btn" type="button"><span class="material-symbols-outlined text-[20px]">delete</span></button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-lg">
                    <div>
                        <label class="block font-label-md text-label-md text-on-surface mb-xs">Image Docker</label>
                        <input class="component-db-image w-full h-10 border border-outline-variant rounded px-md font-mono-code text-body-sm bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="postgres:15-alpine" type="text" required/>
                    </div>
                    <div>
                        <label class="block font-label-md text-label-md text-on-surface mb-xs">Nom du Volume</label>
                        <input class="component-volume-name w-full h-10 border border-outline-variant rounded px-md font-mono-code text-body-sm bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="slug-pgdata" type="text" required/>
                    </div>
                </div>
            </div>`;
    } else {
        const uploadId = `env-file-upload-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        innerHTML = `
            <div class="stack-connector"></div>
            <div class="bg-surface-container-lowest border border-outline-variant rounded-lg p-lg md:p-xl relative z-10 hover:border-outline transition-colors">
                <div class="flex items-center gap-md mb-lg border-b border-outline-variant pb-md">
                    <div class="w-8 h-8 rounded bg-surface-variant flex items-center justify-center text-primary border border-outline-variant">
                        <span class="material-symbols-outlined text-[18px]">${kind === 'front' ? 'web' : 'dns'}</span>
                    </div>
                    <input class="component-name font-label-md text-label-md font-bold text-on-surface bg-transparent border-none p-0 focus:ring-0 focus:outline-none w-auto" placeholder="Nom (ex: back)" type="text" value="${kind}" required/>
                    <input type="hidden" class="component-kind" value="${kind}">
                    <button class="ml-auto text-on-surface-variant hover:text-error transition-colors remove-component-btn" type="button"><span class="material-symbols-outlined text-[20px]">delete</span></button>
                </div>
                <div class="grid grid-cols-1 md:grid-cols-2 gap-lg mb-xl">
                    <div class="md:col-span-2">
                        <label class="block font-label-md text-label-md text-on-surface mb-xs">Repository URL</label>
                        <div class="flex relative">
                            <span class="absolute left-3 top-2.5 text-on-surface-variant"><span class="material-symbols-outlined text-[18px]">link</span></span>
                            <input class="component-repo-url w-full h-10 border border-outline-variant rounded pl-10 pr-md font-body-sm text-body-sm bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="https://github.com/org/repo.git" type="url" required/>
                        </div>
                    </div>
                    <div>
                        <label class="block font-label-md text-label-md text-on-surface mb-xs">Branch</label>
                        <input class="component-branch w-full h-10 border border-outline-variant rounded px-md font-mono-code text-body-sm bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="main" type="text" value="main" required/>
                    </div>
                    <div>
                        <label class="block font-label-md text-label-md text-on-surface mb-xs">Port d'écoute</label>
                        <input class="component-port w-full h-10 border border-outline-variant rounded px-md font-mono-code text-body-sm bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="8080" type="number" required/>
                    </div>
                    <div class="md:col-span-2 flex items-center gap-2 mt-2">
                        <input type="checkbox" class="component-expose-publicly w-4 h-4 text-primary border-outline-variant rounded focus:ring-0" checked>
                        <label class="font-body-sm text-body-sm text-on-surface cursor-pointer select-none">Exposer publiquement via Traefik</label>
                    </div>
                </div>

                <!-- Variables d'environnement avec Toggle Manual/File -->
                <div class="mt-lg pt-lg border-t border-outline-variant">
                    <div class="flex items-center justify-between mb-md">
                        <h4 class="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">Environment Variables</h4>
                        <div class="flex items-center gap-sm">
                            <button type="button" class="env-mode-toggle text-label-md font-label-md text-primary flex items-center gap-1 transition-colors" data-mode="manual">
                                <span class="material-symbols-outlined text-[16px]">edit</span> Manual
                            </button>
                            <span class="text-on-surface-variant">|</span>
                            <button type="button" class="env-mode-toggle text-label-md font-label-md text-on-surface-variant hover:text-on-surface flex items-center gap-1 transition-colors" data-mode="file">
                                <span class="material-symbols-outlined text-[16px]">upload_file</span> .env File
                            </button>
                        </div>
                    </div>

                    <!-- Mode Manuel (par défaut) -->
                    <div class="env-manual-mode">
                        <div class="flex items-center justify-between mb-md">
                            <span class="font-body-sm text-body-sm text-on-surface-variant">Saisie manuelle</span>
                            <button type="button" class="text-label-md font-label-md text-on-surface-variant hover:text-on-surface flex items-center gap-1 transition-colors add-env-var-btn">
                                <span class="material-symbols-outlined text-[16px]">add</span> Ajouter
                            </button>
                        </div>
                        <div class="max-h-64 overflow-y-auto pr-2 space-y-sm env-vars-list"></div>
                    </div>

                    <!-- Mode Fichier (caché par défaut) -->
                    <div class="env-file-mode hidden">
                        <div class="border-2 border-dashed border-outline-variant rounded-lg p-lg text-center hover:border-primary transition-colors bg-surface-container-lowest">
                            <input type="file"
                                   class="env-file-input hidden"
                                   accept=".env,.env.*,text/plain,*/*"
                                   id="${uploadId}"/>
                            <label for="${uploadId}"
                                   class="cursor-pointer flex flex-col items-center gap-sm">
                                <span class="material-symbols-outlined text-[32px] text-on-surface-variant">upload_file</span>
                                <span class="font-label-md text-label-md text-on-surface">Click to upload .env file</span>
                                <span class="font-body-sm text-body-sm text-on-surface-variant">or drag and drop the file here</span>
                            </label>
                            <div class="env-file-info mt-md hidden">
                                <div class="flex items-center justify-center gap-sm text-primary">
                                    <span class="material-symbols-outlined text-[18px]">check_circle</span>
                                    <span class="font-label-md text-label-md env-filename-display"></span>
                                </div>
                                <button type="button" class="mt-sm text-error hover:text-error-container font-body-sm text-body-sm env-file-remove">
                                    Delete File
                                </button>
                            </div>
                        </div>
                        <p class="font-body-sm text-body-sm text-on-surface-variant mt-sm">
                            The file will be analyzed automatically. Expected format : <code class="bg-surface-container-low px-xs rounded">KEY=VALUE</code> per line.
                        </p>
                    </div>
                </div>
            </div>`;
    }

    div.innerHTML = innerHTML;
    const addButton = container.lastElementChild;
    container.insertBefore(div, addButton);
    div.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Gestion de l'upload de fichier .env (appelée sur "change" ou après un drop)
function handleEnvFileUpload(input) {
    const file = input.files[0];
    if (!file) return;

    const card = input.closest('.component-card');
    const fileInfo = card.querySelector('.env-file-info');
    const filename = card.querySelector('.env-filename-display');

    // Validation plus permissive : accepter .env, .env.*, ou tout fichier texte
    const isValidEnvFile = file.name === '.env' ||
                           file.name.startsWith('.env.') ||
                           file.name.endsWith('.env') ||
                           file.type === 'text/plain' ||
                           !file.type; // Les fichiers .env n'ont souvent pas de type MIME

    if (!isValidEnvFile) {
        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'error',
                title: 'Invalid Format',
                message: 'Please select a valid .env file.'
            });
        }
        input.value = '';
        return;
    }

    // Lire le fichier
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const variables = parseEnvFile(content);

        // Remplir automatiquement les variables
        const envList = card.querySelector('.env-vars-list');
        envList.innerHTML = '';

        variables.forEach(({key, value}) => {
            const row = document.createElement('div');
            row.className = 'flex items-center gap-sm env-var-row';
            row.innerHTML = `
                <input class="env-key flex-1 h-10 border border-outline-variant rounded px-md font-mono-code text-mono-code bg-surface-container-low text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="CLÉ" type="text" value="${escapeHtml(key)}"/>
                <span class="text-on-surface-variant font-mono-code">=</span>
                <div class="flex-1 relative">
                    <input class="env-value w-full h-10 border border-outline-variant rounded px-md pr-10 font-mono-code text-mono-code bg-transparent text-on-surface focus:outline-none focus:border-on-surface transition-colors" placeholder="VALEUR" type="password" value="${escapeHtml(value)}"/>
                    <button type="button" class="absolute right-2 top-2 text-on-surface-variant hover:text-on-surface transition-colors toggle-visibility-btn" title="Afficher/Masquer">
                        <span class="material-symbols-outlined text-[18px]">visibility</span>
                    </button>
                </div>
                <button type="button" class="w-10 h-10 flex-shrink-0 flex items-center justify-center text-on-surface-variant hover:text-error transition-colors border border-transparent hover:border-outline-variant rounded remove-env-var-btn">
                    <span class="material-symbols-outlined text-[18px]">close</span>
                </button>
            `;
            envList.appendChild(row);
        });

        // Afficher les informations du fichier
        filename.textContent = file.name;
        fileInfo.classList.remove('hidden');

        // Basculer automatiquement en mode manuel pour voir les variables
        const manualBtn = card.querySelector('.env-mode-toggle[data-mode="manual"]');
        const fileBtn = card.querySelector('.env-mode-toggle[data-mode="file"]');

        manualBtn.classList.remove('text-on-surface-variant');
        manualBtn.classList.add('text-primary');
        fileBtn.classList.remove('text-primary');
        fileBtn.classList.add('text-on-surface-variant');

        card.querySelector('.env-file-mode').classList.add('hidden');
        card.querySelector('.env-manual-mode').classList.remove('hidden');

        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'success',
                title: 'File Imported',
                message: `${variables.length} variable(s) imported from ${file.name}`
            });
        }
    };

    reader.onerror = function() {
        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'error',
                title: 'Reading Error',
                message: 'Unable to read the .env file'
            });
        }
        input.value = '';
    };

    reader.readAsText(file);
}

// Parser un fichier .env
function parseEnvFile(content) {
    const lines = content.split('\n');
    const variables = [];

    lines.forEach(line => {
        line = line.trim();

        // Ignorer les lignes vides et les commentaires
        if (!line || line.startsWith('#')) return;

        // Parser KEY=VALUE
        const match = line.match(/^([^=]+)=(.*)$/);
        if (match) {
            let key = match[1].trim();
            let value = match[2].trim();

            // Supprimer les guillemets si présents
            if ((value.startsWith('"') && value.endsWith('"')) ||
                (value.startsWith("'") && value.endsWith("'"))) {
                value = value.slice(1, -1);
            }

            variables.push({key, value});
        }
    });

    return variables;
}

// Fonction utilitaire pour échapper le HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Gère la soumission du formulaire et construit le payload pour l'API
 */

function formatEnvValue(value) {
    if (/\s/.test(value) && !(value.startsWith('"') && value.endsWith('"'))) {
        // Échappe les guillemets doubles internes avant d'encadrer
        return `"${value.replace(/"/g, '\\"')}"`;
    }
    return value;
}

async function handleStackSubmit(event) {
    event.preventDefault();

    const slug = document.getElementById('stack_slug').value.trim();
    const componentCards = document.querySelectorAll('.component-card');
    const components = [];

    componentCards.forEach(card => {
        const kind = card.querySelector('.component-kind').value;
        const name = card.querySelector('.component-name').value.trim();

        const componentData = {
            name: name,
            kind: kind,
            replica: 1 // Valeur par défaut, à adapter si tu ajoutes un champ replica plus tard
        };

        if (kind === 'database') {
            componentData.db_image = card.querySelector('.component-db-image').value.trim();
            componentData.volume_name = card.querySelector('.component-volume-name').value.trim();
        } else {
            componentData.repo_url = card.querySelector('.component-repo-url').value.trim();
            componentData.branch = card.querySelector('.component-branch').value.trim();
            componentData.port = parseInt(card.querySelector('.component-port').value, 10);
            componentData.expose_publicly = card.querySelector('.component-expose-publicly').checked;

            // CONVERSION : Le backend attend un dictionnaire {"CLÉ": "VALEUR"}, pas un tableau
            const envsVarDict = {};
            card.querySelectorAll('.env-var-row').forEach(row => {
                const key = row.querySelector('.env-key').value.trim();
                const value = row.querySelector('.env-value').value;
                if (key) {
                    envsVarDict[key] = formatEnvValue(value);
                }
            });
            componentData.envs_var = envsVarDict; // Nom exact attendu par le backend
        }

        components.push(componentData);
    });

    const payload = {
        slug: slug,
        components: components
    };

    console.log("Payload à envoyer:", JSON.stringify(payload, null, 2));

    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span> Deploying...`;

    try {
        // Appel à la fonction API que nous venons de créer
        const response = await createStack(payload);

        console.log("Réponse du serveur:", response);
        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'success',
                title: 'Deployment Started',
                message: `The stack "${slug}" is being created.`,
                duration: 3000
            });
        }

        // Petit délai pour laisser l'utilisateur voir le toast avant la redirection
        setTimeout(() => {
            window.location.href = `pipeline.html?project_id=${response.project_id}`;
        }, 500);

    } catch (error) {
        console.error("Erreur de déploiement:", error);
        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'error',
                title: 'Deployment Failed',
                message: error.message || 'An unknown error occurred while creating the stack.',
                duration: 8000
            });
        } else {
            alert(`Deployment Failed: ${error.message}`);
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnText;
    }
}