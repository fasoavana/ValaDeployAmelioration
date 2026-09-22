// scripts/stacks.js
// Chargement des stacks et affichage en accordéon (cartes) avec composants dépliables.

// Etat local : la liste des stacks chargées, pour recalculer les stats après suppression
// sans devoir refetch le serveur.

// traduire en anglais sauf les commentaires 
let loadedStacks = [];

// Cache des détails déjà chargés, pour ne pas re-fetch à chaque toggle
const componentDetailCache = {};

document.addEventListener('DOMContentLoaded', () => {
    initUserSession(
        async (user) => {
            const fullnameEl = document.getElementById('user-fullname');
            if (fullnameEl) fullnameEl.textContent = user.full_name;

            try {
                const stacks = await getStacks();
                loadedStacks = stacks;
                renderStacks(stacks);
            } catch (error) {
                console.error('Erreur chargement stacks:', error);
                ValaToast.show({ type: 'error', title: 'Error', message: 'Unable to fetch the list of stacks.' });
                const loadingState = document.getElementById('loading-state');
                if (loadingState) {
                    loadingState.innerHTML = `
                        <div class="py-lg text-center text-on-surface-variant">
                            Unable to display stacks at the moment.
                        </div>
                    `;
                }
            }
        },
        (error) => {
            console.log('Session invalide ou expirée :', error.message);
            window.location.href = "login.html";
        }
    );
});

function renderStacks(stacks) {
    const container = document.getElementById('stacks-list');
    const loadingState = document.getElementById('loading-state');
    const emptyState = document.getElementById('empty-state');
    if (!container) return;

    // Nettoyage : on retire uniquement les cartes déjà rendues (pas les states)
    container.querySelectorAll('.stack-card').forEach(el => el.remove());
    if (loadingState) loadingState.style.display = 'none';

    if (stacks.length === 0) {
        if (emptyState) emptyState.style.display = '';
        updateStackStats(stacks);
        return;
    }

    if (emptyState) emptyState.style.display = 'none';

    stacks.forEach(stack => {
        const card = createStackCard(stack);
        container.appendChild(card);
    });

    updateStackStats(stacks);
}

function createStackCard(stack) {
    const statusConfig = getStatusConfig(stack.status);
    const createdDate = stack.created_at ? new Date(stack.created_at) : null;
    const dateStr = createdDate ? createdDate.toLocaleDateString('fr-FR') : 'Date inconnue';
    const initial = (stack.slug || '?').charAt(0).toUpperCase();
    const avatar = getAvatarStyle(stack.slug);

    const article = document.createElement('article');
    article.className = 'stack-card bg-surface-container-lowest border border-outline-variant/50 rounded-xl overflow-hidden';
    article.dataset.projectId = stack.project_id;
    article.dataset.slug = stack.slug;
    article.dataset.expanded = 'false';

    article.innerHTML = `
        <div class="stack-card-header px-lg py-md flex items-center justify-between cursor-pointer bg-surface hover:bg-surface-container-low transition-colors">
            <div class="flex items-center gap-lg min-w-0">
                <span class="material-symbols-outlined stack-toggle-icon text-secondary text-[20px]">chevron_right</span>
                <div class="w-9 h-9 rounded-lg ${avatar.bg} ${avatar.text} flex items-center justify-center font-label-md text-label-md font-semibold shrink-0">
                    ${initial}
                </div>
                <div class="min-w-0">
                    <h3 class="stack-name font-mono-code text-[15px] font-bold text-on-surface truncate">${escapeHtml(stack.slug)}</h3>
                    <p class="font-body-sm text-body-sm text-secondary">Created on ${dateStr}</p>
                </div>
            </div>
            <div class="flex items-center gap-xl shrink-0">
                <div class="status-badge ${statusConfig.class}">
                    <div class="status-dot"></div>
                    <span class="font-label-sm text-label-sm">${statusConfig.label}</span>
                </div>
                <div class="font-body-sm text-body-sm text-secondary w-28 text-right hidden sm:block">
                    ${stack.component_count} component${stack.component_count > 1 ? 's' : ''}
                </div>
                 <!-- Bouton Pipeline -->
                <button class="stack-pipeline-btn text-secondary hover:text-primary p-xs rounded hover:bg-primary-container/30 transition-colors" title="View pipeline" aria-label="Pipeline of ${escapeHtml(stack.slug)}">
                    <span class="material-symbols-outlined text-[20px]">account_tree</span>
                </button>
                <button class="stack-delete-btn text-secondary hover:text-error p-xs rounded hover:bg-error-container/30" title="Supprimer la stack" aria-label="Supprimer ${escapeHtml(stack.slug)}">
                    <span class="material-symbols-outlined text-[20px]">delete</span>
                </button>
            </div>
        </div>
        <div class="stack-card-body border-t border-outline-variant/50 bg-surface-container-low" id="components-${stack.project_id}" hidden>
            <div class="py-md px-lg text-center text-secondary text-body-sm">
                <span class="material-symbols-outlined text-[18px] animate-spin align-middle">progress_activity</span>
                Loading components...
            </div>
        </div>
    `;

    const header = article.querySelector('.stack-card-header');
    header.addEventListener('click', () => toggleStackDetail(stack.project_id));

    attachDeleteHandler(article, stack);

    // Gestionnaire pour le bouton Pipeline
    const pipelineBtn = article.querySelector('.stack-pipeline-btn');
    if (pipelineBtn) {
        pipelineBtn.addEventListener('click', (event) => {
            event.stopPropagation(); // Empêche d'ouvrir/fermer l'accordéon
            window.location.href = `pipeline.html?project_id=${stack.project_id}&back_to=stacks.html`;
        });
    }

    return article;
}

async function toggleStackDetail(projectId) {
    const article = document.querySelector(`.stack-card[data-project-id="${projectId}"]`);
    if (!article) return;

    const body = article.querySelector('.stack-card-body');
    const stackSlug = article.dataset.slug;
    const isOpen = article.dataset.expanded === 'true';

    if (isOpen) {
        article.dataset.expanded = 'false';
        body.hidden = true;
        return;
    }

    article.dataset.expanded = 'true';
    body.hidden = false;

    // Chargement paresseux : on ne fetch le détail qu'au premier dépliage
    if (!componentDetailCache[projectId]) {
        try {
            const detail = await getStackDetail(projectId);
            componentDetailCache[projectId] = detail;
        } catch (error) {
            ValaToast.show({ type: 'error', title: 'Error', message: 'Unable to load component details.' });
            body.innerHTML = `
                <div class="py-md px-lg text-center text-on-surface-variant text-body-sm">
                    Error loading components.
                </div>
            `;
            return;
        }
    }

    renderComponents(projectId, componentDetailCache[projectId], stackSlug);
}


function renderComponents(projectId, detail, stackSlug) {
    const container = document.getElementById(`components-${projectId}`);
    if (!container) return;

    const components = detail.components || [];
    if (components.length === 0) {
        container.innerHTML = `<div class="py-md px-lg text-center text-secondary text-body-sm">No components available.</div>`;
        return;
    }

    const rows = components.map(c => {
        const statusConfig = getStatusConfig(c.status);
        
        // On garde kindLabel uniquement pour la logique interne (icônes, couleurs)
        const kindLabel = (c.kind || '').replace('ComponentKind.', '').toLowerCase();
        const iconStyle = getComponentIconStyle(kindLabel);
        
        // On utilise le vrai slug du composant s'il existe
        const componentSlug = c.slug || `${stackSlug}-${kindLabel}`;
        
        const isFailed = c.status === 'failed';
        const componentId = c.id;
        const projectSlug = stackSlug;

        return `
            <div class="component-row group flex items-center justify-between bg-surface-container-lowest border border-outline-variant/50 rounded-lg p-sm">
                <div class="flex items-center gap-md min-w-0">
                    <div class="component-icon-box ${iconStyle.bg} ${iconStyle.color}">
                        <span class="material-symbols-outlined text-[18px]">${getComponentIcon(kindLabel)}</span>
                    </div>
                    <span class="font-mono-code text-mono-code truncate" title="${escapeHtml(componentSlug)}">
                        ${escapeHtml(c.name)}
                    </span>
                    <!-- Affichage du vrai slug du composant au lieu du label générique (back, front, database) -->
                    <span class="component-kind-pill font-mono-code text-xs text-secondary" title="Slug: ${escapeHtml(componentSlug)}">
                        ${escapeHtml(c.slug || kindLabel)}
                    </span>
                </div>
                <div class="flex items-center gap-md shrink-0">
                    ${c.error_message ? `<span class="text-body-sm text-error truncate max-w-[220px]" title="${escapeHtml(c.error_message)}">${escapeHtml(c.error_message)}</span>` : ''}
                    <div class="status-badge ${statusConfig.class}">
                        <div class="status-dot"></div>
                        <span class="font-label-sm text-label-sm">${statusConfig.label}</span>
                    </div>
                    <a href="project-detail.html?slug=${encodeURIComponent(projectSlug)}&component_id=${componentId}"
                    class="component-view-link text-secondary hover:text-on-surface inline-flex items-center gap-xs">
                        <span class="font-label-sm text-label-sm">View</span>
                        <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
                    </a>
                </div>
            </div>
            ${isFailed ? `
            <div class="pl-sm">
                <a href="project-detail.html?slug=${encodeURIComponent(componentSlug)}#logs"
                   class="view-logs-link inline-flex items-center gap-xs text-primary font-label-sm text-label-sm hover:underline">
                    <span class="material-symbols-outlined text-[16px]">terminal</span>
                    View Build Logs
                </a>
            </div>` : ''}
        `;
    }).join('');

    container.innerHTML = `<div class="px-lg py-md space-y-sm">${rows}</div>`;
}

function attachDeleteHandler(article, stack) {
    const btn = article.querySelector('.stack-delete-btn');
    if (!btn) return;

    btn.addEventListener('click', async (event) => {
        event.stopPropagation();

        const confirmed = await ValaModal.confirm({
            title: "Delete Stack",
            message: `Permanently delete the stack "${stack.slug}" ? This action is irreversible and will delete all associated containers and configurations.`,
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            variant: "danger"
        });
        
        if (!confirmed) return;

        btn.disabled = true;
        btn.classList.add('opacity-50');

        try {
            await deleteStack(stack.project_id);

            article.remove();
            delete componentDetailCache[stack.project_id];
            loadedStacks = loadedStacks.filter(s => s.project_id !== stack.project_id);

            updateStackStats(loadedStacks);

            ValaToast.show({ type: 'success', title: 'Stack deleted', message: `The stack "${stack.slug}" and its containers have been deleted.` });

            const emptyState = document.getElementById('empty-state');
            if (loadedStacks.length === 0 && emptyState) {
                emptyState.style.display = '';
            }
        } catch (error) {
            ValaToast.show({ type: 'error', title: 'Error deleting stack', message: error.message || 'Unable to delete the stack.' });
            btn.disabled = false;
            btn.classList.remove('opacity-50');
        }
    });
}

// Palette d'avatars — même logique que dashboard.js/security.js pour rester cohérent visuellement
const AVATAR_PALETTE = [
    { bg: 'bg-primary-container/15', text: 'text-primary' },
    { bg: 'bg-[#0096fd]/15', text: 'text-[#0096fd]' },
    { bg: 'bg-[#12B76A]/15', text: 'text-[#12B76A]' },
    { bg: 'bg-surface-container-high', text: 'text-on-surface' },
];

function hashString(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return Math.abs(hash);
}

function getAvatarStyle(slug) {
    return AVATAR_PALETTE[hashString(slug || '?') % AVATAR_PALETTE.length];
}

function getComponentIcon(kindLabel) {
    const icons = {
        'database': 'database',
        'postgres': 'database',
        'db': 'database',
        'backend': 'api',
        'api': 'api',
        'frontend': 'web',
        'web': 'web'
    };
    return icons[kindLabel] || 'deployed_code';
}

// Couleur par type de composant : les types connus ont une couleur fixe et
// reconnaissable, les types inconnus piochent dans une palette de secours
// (au lieu de tomber systématiquement sur du gris neutre).
const COMPONENT_COLOR_MAP = {
    'database': { bg: 'bg-[#a73a00]/8', color: 'text-[#a73a00]' },
    'postgres': { bg: 'bg-[#a73a00]/8', color: 'text-[#a73a00]' },
    'db': { bg: 'bg-[#a73a00]/8', color: 'text-[#a73a00]' },
    'backend': { bg: 'bg-[#12B76A]/10', color: 'text-[#12B76A]' },
    'api': { bg: 'bg-[#12B76A]/10', color: 'text-[#12B76A]' },
    'frontend': { bg: 'bg-[#0096fd]/10', color: 'text-[#0096fd]' },
    'web': { bg: 'bg-[#0096fd]/10', color: 'text-[#0096fd]' },
};

const COMPONENT_COLOR_FALLBACK = [
    { bg: 'bg-[#8e51ff]/10', color: 'text-[#8e51ff]' }, // violet — ex. worker, queue
    { bg: 'bg-[#e0a300]/12', color: 'text-[#a3760a]' }, // ambre — ex. cache
    { bg: 'bg-[#ff5c8a]/10', color: 'text-[#c2185b]' }, // rose — ex. storage
    { bg: 'bg-surface-container-high', color: 'text-secondary' }, // gris — défaut ultime
];

function getComponentIconStyle(kindLabel) {
    if (COMPONENT_COLOR_MAP[kindLabel]) return COMPONENT_COLOR_MAP[kindLabel];
    return COMPONENT_COLOR_FALLBACK[hashString(kindLabel || '?') % COMPONENT_COLOR_FALLBACK.length];
}

function getStatusConfig(status) {
    const configs = {
        'running': { label: 'Running', class: 'status-running' },
        'stopped': { label: 'Stopped', class: 'status-stopped' },
        'building': { label: 'Building', class: 'status-building' },
        'failed': { label: 'Failed', class: 'status-error' }
    };
    return configs[status] || { label: status || 'Unknown', class: 'status-created' };
}

function updateStackStats(stacks) {
    const totalEl = document.getElementById('total-stacks');
    if (totalEl) totalEl.textContent = stacks.length;

    const runningEl = document.getElementById('running-stacks');
    if (runningEl) runningEl.textContent = stacks.filter(s => s.status === 'running').length;

    const failedEl = document.getElementById('failed-stacks');
    if (failedEl) failedEl.textContent = stacks.filter(s => s.status === 'failed').length;
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}