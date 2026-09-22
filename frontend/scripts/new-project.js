// api/new-project.js
// Gestion du formulaire de création de projet

document.addEventListener('DOMContentLoaded', async () => {
    // Vérifie la session avant d'afficher le formulaire.
    // Réutilise getProjects() qui passe déjà par fetchWithAutoRefresh
    // (donc essaie le refresh token avant d'abandonner).
    try {
        await getProjects();
    } catch (err) {
        console.warn('Session invalide, redirection vers login:', err);
        window.location.href = 'login.html';
        return; // stoppe l'exécution, n'initialise rien du formulaire
    }

    setupSlugPreview();
    setupEnvVarRows();
    setupFormSubmit();
});


// --- Aperçu du sous-domaine (slug -> nom.ip-serveur.sslip.io), reflète RG-05 ---
function slugify(text) {
    return text
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9-]+/g, '-')
        .replace(/-+/g, '-')
        .replace(/^-|-$/g, '');
}

// Détermine le vrai identifiant serveur à afficher dans l'aperçu, avec repli
// sur le placeholder si aucune config n'est disponible côté client.
function getServerHost() {
    if (window.ValaConfig && window.ValaConfig.serverIp) {
        return window.ValaConfig.serverIp;
    }
    const host = window.location.hostname;
    if (host && host !== 'localhost' && host !== '127.0.0.1') {
        return host;
    }
    return '<server-ip>';
}

function renderSlugPreview(rawValue) {
    const preview = document.getElementById('slug-preview');
    if (!preview) return;
    const slug = slugify(rawValue || '') || 'your-project';
    preview.textContent = `${slug}.${getServerHost()}.sslip.io`;
}

function setupSlugPreview() {
    const nameInput = document.getElementById('projectName');
    if (!nameInput) return;

    // Synchronise l'aperçu dès le chargement avec le vrai slug/host,
    // au lieu de laisser le texte statique par défaut.
    renderSlugPreview(nameInput.value);

    nameInput.addEventListener('input', () => {
        renderSlugPreview(nameInput.value);
    });
}

// --- Lignes de variables d'environnement dynamiques ---
function createEnvVarRow() {
    const row = document.createElement('div');
    row.className = 'flex gap-sm items-center env-var-row env-var-row-enter';
    row.innerHTML = `
        <div class="flex-1 flex rounded-lg border border-outline-variant field-wrap overflow-hidden">
            <input class="env-key w-1/3 bg-surface-container-low border-0 border-r border-outline-variant px-md py-sm font-mono-code text-body-sm text-on-surface focus:ring-0" placeholder="KEY" type="text">
            <input class="env-value flex-1 bg-transparent border-0 px-md py-sm font-mono-code text-body-sm text-on-surface focus:ring-0" placeholder="VALUE" type="text">
        </div>
        <div class="flex items-center gap-xs px-sm">
            <input class="env-secret rounded border-outline-variant text-primary focus:ring-primary" type="checkbox">
            <label class="font-label-md text-label-md text-on-surface-variant">Secret</label>
        </div>
        <button class="remove-env-var p-xs text-on-surface-variant hover:text-error transition-colors duration-200" type="button">
            <span class="material-symbols-outlined text-[20px]">delete</span>
        </button>
    `;

    // Bascule le type de l'input VALUE en "password" quand "Secret" est coché
    const secretCheckbox = row.querySelector('.env-secret');
    const valueInput = row.querySelector('.env-value');
    secretCheckbox.addEventListener('change', () => {
        valueInput.type = secretCheckbox.checked ? 'password' : 'text';
    });

    row.querySelector('.remove-env-var').addEventListener('click', () => row.remove());

    // Retire la classe d'entrée après l'animation pour ne pas la rejouer
    requestAnimationFrame(() => {
        requestAnimationFrame(() => row.classList.remove('env-var-row-enter'));
    });

    return row;
}

function setupEnvVarRows() {
    const container = document.getElementById('env-vars-container');
    const addButton = document.getElementById('add-env-var');
    if (!container || !addButton) return;

    // Ajouter une ligne vide par défaut si le conteneur est vide
    if (container.children.length === 0) {
        container.appendChild(createEnvVarRow());
    }

    addButton.addEventListener('click', () => {
        container.appendChild(createEnvVarRow());
    });
}

function collectEnvVars() {
    const rows = document.querySelectorAll('.env-var-row');
    const envVars = {};
    rows.forEach((row) => {
        const key = row.querySelector('.env-key').value.trim();
        const value = row.querySelector('.env-value').value;
        if (key) envVars[key] = value;
    });
    return envVars;
}

// --- Libellés lisibles pour chaque statut backend ---
const STATUS_LABELS = {
    building: 'Build running...',
    running: 'DDeployment successful!',
    stopped: 'Project stopped',
    failed: 'Deployment failed',
};

function updateSubmitButton(submitBtn, status) {
    const label = STATUS_LABELS[status] || `${status}...`;
    submitBtn.innerHTML = `
        <span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
        ${label}
    `;
}

// --- Polling du statut jusqu'à succès ou échec ---
async function pollDeployStatus(projectId, submitBtn, { intervalMs = 2000, timeoutMs = 5 * 60 * 1000 } = {}) {
    const start = Date.now();

    while (true) {
        if (Date.now() - start > timeoutMs) {
            throw new Error('The deployment is taking too long. Check the project status later.');
        }

        const status = await getDeployStatus(projectId);
        updateSubmitButton(submitBtn, status.status);

        if (status.status === 'running') {
            return status;
        }
        if (status.status === 'failed') {
            throw new Error(status.error_message || 'The deployment failed.');
        }

        // "building" (ou autre état intermédiaire) -> on repoll
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
}

// --- Soumission du formulaire ---
function setupFormSubmit() {
    const form = document.querySelector('form');
    const submitBtn = form?.querySelector('button[type="submit"]');
    if (!form || !submitBtn) return;

    form.addEventListener('submit', async (event) => {
        event.preventDefault();

        // 1. Récupérer les données du formulaire
        const projectName = document.getElementById('projectName')?.value.trim();
        const gitUrl = document.getElementById('gitUrl')?.value.trim();
        const branch = document.getElementById('branch')?.value.trim() || 'main';
        const replicas = parseInt(document.getElementById('replicas')?.value, 10) || 1;
        const portValue = document.getElementById('port')?.value;
        const port = portValue ? parseInt(portValue, 10) : null;

        // 2. Validation basique
        if (!projectName) {
            ValaToast.show({ type: 'warning', title: 'Field required', message: 'The project name is required.' });
            return;
        }
        if (!gitUrl) {
            ValaToast.show({ type: 'warning', title: 'Field required', message: 'The Git repository URL is required.' });
            return;
        }

        // 3. Construire le payload
        const payload = {
            slug: slugify(projectName),
            repo_url: gitUrl,
            branch: branch,
            replica: replicas,
            port: port,
            envs_var: collectEnvVars(),
        };

        console.log('Payload prêt pour /deploy :', payload);

        // 4. Sauvegarder le texte original du bouton pour le restaurer
        const originalText = submitBtn.innerHTML;

        // 5. Désactiver le bouton pendant l'appel
        submitBtn.disabled = true;
        submitBtn.innerHTML = `
            <span class="material-symbols-outlined text-[18px] animate-spin">progress_activity</span>
            Envoi de la demande...
        `;

        try {
            // 6. Lancer le déploiement (réponse immédiate: { project_id, status: "building" })
            const created = await createProject(payload);
            console.log('Déploiement lancé, project_id =', created.project_id);

            // 7. Poller jusqu'à succès ou échec, en mettant à jour le bouton
            await pollDeployStatus(created.project_id, submitBtn);

            // 8. Rediriger vers le dashboard une fois RUNNING
            window.location.href = 'dashboard.html';

        } catch (error) {
            console.error('Erreur lors du déploiement:', error);

            // Afficher une erreur plus parlante
            const errorMessage = error.message || 'An unknown error occurred during deployment.';
            if (typeof ValaToast !== 'undefined') {
                ValaToast.show({
                    type: 'error',
                    title: 'Deployment Failed',
                    message: errorMessage,
                    duration: 8000 // Plus long pour une erreur
                });
            } else {
                alert(errorMessage); // Fallback de sécurité si le toast n'est pas chargé
            }

            // 9. Réactiver le bouton
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
    });
}