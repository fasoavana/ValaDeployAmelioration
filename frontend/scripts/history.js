// scripts/history.js

let currentProjectId = null;
let currentProjectSlug = null;

document.addEventListener('DOMContentLoaded', () => {
    initUserSession(
        async () => {
            const params = new URLSearchParams(window.location.search);
            currentProjectId = params.get('project_id');

            if (!currentProjectId) {
                showFatalError('Aucun projet spécifié (paramètre project_id manquant).');
                return;
            }

            // Récupérer le nom du projet pour l'afficher dans le header (optionnel, via l'API projets)
            // Pour l'instant, on affiche juste l'ID ou on le récupère via l'historique
            await loadHistory();
        },
        (error) => {
            console.log('Session invalide ou expirée :', error.message);
            window.location.href = "login.html";
        }
    );
});

async function loadHistory() {
    const container = document.getElementById('history-container');
    const loadingEl = document.getElementById('history-loading');
    const emptyEl = document.getElementById('history-empty');
    const tableEl = document.getElementById('history-table');

    if (loadingEl) loadingEl.style.display = 'flex';
    if (tableEl) tableEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'none';

    try {
        const history = await getDeploymentHistory(currentProjectId);
        
        if (loadingEl) loadingEl.style.display = 'none';

        if (!history || history.length === 0) {
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }

        // Mise à jour du titre avec le slug du premier élément (ils ont tous le même)
        if (history.length > 0 && history[0].project) {
            currentProjectSlug = history[0].project.slug; // Si ton schéma renvoie le slug, sinon on garde l'ID
            document.getElementById('page-project-name').textContent = `Projet #${currentProjectId}`;
        }

        const tbody = document.getElementById('history-tbody');
        tbody.innerHTML = history.map(run => renderRunRow(run)).join('');
        
        if (tableEl) tableEl.style.display = 'table';

    } catch (error) {
        console.error('Erreur de chargement de l\'historique:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        showFatalError('Impossible de charger l\'historique des déploiements.');
    }
}

function renderRunRow(run) {
    const statusConfig = getStatusConfig(run.status);
    const triggerLabel = run.trigger === 'webhook' ? 'Webhook GitHub' : 'Manuel';
    const duration = formatDuration(run.started_at, run.finished_at);
    const dateStr = new Date(run.started_at).toLocaleString('fr-FR', {
        day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });

    return `
        <tr class="border-b border-subtle hover:bg-surface-container-low transition-colors">
            <td class="px-lg py-md font-mono-code text-label-sm text-secondary">#${run.id}</td>
            <td class="px-lg py-md font-body-sm text-body-sm text-on-surface">${dateStr}</td>
            <td class="px-lg py-md">
                <span class="inline-flex items-center gap-xs px-sm py-xs rounded-full bg-surface-container-highest font-label-sm text-label-sm text-secondary">
                    <span class="material-symbols-outlined" style="font-size: 14px;">
                        ${run.trigger === 'webhook' ? 'webhook' : 'touch_app'}
                    </span>
                    ${triggerLabel}
                </span>
            </td>
            <td class="px-lg py-md">
                <span class="inline-flex items-center gap-xs px-sm py-xs rounded-full font-label-sm text-label-sm" 
                      style="background-color: ${statusConfig.bg}; color: ${statusConfig.color}; border: 1px solid ${statusConfig.border};">
                    <span class="material-symbols-outlined" style="font-size: 14px;">${statusConfig.icon}</span>
                    ${statusConfig.label}
                </span>
            </td>
            <td class="px-lg py-md font-mono-code text-label-sm text-secondary">
                ${run.commit_hash ? run.commit_hash.substring(0, 7) : '—'}
            </td>
            <td class="px-lg py-md font-body-sm text-body-sm text-on-surface">
                ${duration}
            </td>
            <td class="px-lg py-md text-right">
                <button onclick="viewRunLogs(${run.id})" 
                        class="inline-flex items-center gap-xs px-md py-sm rounded-DEFAULT border border-subtle bg-white text-primary-dark font-label-sm text-label-sm hover:bg-surface-variant transition-colors">
                    <span class="material-symbols-outlined" style="font-size: 16px;">receipt_long</span>
                    Logs
                </button>
            </td>
        </tr>
    `;
}

function getStatusConfig(status) {
    const lowerStatus = status.toLowerCase();
    const configs = {
        pending:   { label: 'En attente', icon: 'schedule', color: '#5e5e5e', bg: 'rgba(94, 94, 94, 0.1)', border: 'rgba(94, 94, 94, 0.2)' },
        cloning:   { label: 'Clonage', icon: 'cloud_download', color: '#1d4ed8', bg: 'rgba(29, 78, 216, 0.1)', border: 'rgba(29, 78, 216, 0.2)' },
        building:  { label: 'Build', icon: 'construction', color: '#d97706', bg: 'rgba(217, 119, 6, 0.1)', border: 'rgba(217, 119, 6, 0.2)' },
        scanning:  { label: 'Scan Sécurité', icon: 'security', color: '#7c3aed', bg: 'rgba(124, 58, 237, 0.1)', border: 'rgba(124, 58, 237, 0.2)' },
        deploying: { label: 'Déploiement', icon: 'rocket_launch', color: '#ff5c00', bg: 'rgba(255, 92, 0, 0.1)', border: 'rgba(255, 92, 0, 0.2)' },
        success:   { label: 'Succès', icon: 'check_circle', color: '#12b76a', bg: 'rgba(18, 183, 106, 0.1)', border: 'rgba(18, 183, 106, 0.2)' },
        failed:    { label: 'Échec', icon: 'error', color: '#ba1a1a', bg: 'rgba(186, 26, 26, 0.1)', border: 'rgba(186, 26, 26, 0.2)' }
    };
    return configs[lowerStatus] || configs.pending;
}

function formatDuration(startedAt, finishedAt) {
    if (!startedAt || !finishedAt) return '—';
    const start = new Date(startedAt).getTime();
    const end = new Date(finishedAt).getTime();
    const diffSeconds = Math.floor((end - start) / 1000);
    
    if (diffSeconds < 60) return `${diffSeconds}s`;
    const minutes = Math.floor(diffSeconds / 60);
    const seconds = diffSeconds % 60;
    return `${minutes}m ${seconds}s`;
}

function viewRunLogs(runId) {
    // Pour l'instant, on affiche un toast. 
    // Tu pourras plus tard ouvrir une modale ou rediriger vers une page de détail des logs.
    ValaToast.show({ 
        type: 'info', 
        title: 'Run\'s logs #' + runId, 
        message: 'Fonctionnalité d\'affichage détaillé des logs en cours d\'intégration.' 
    });
    
    // Exemple de redirection future :
    // window.location.href = `run-logs.html?project_id=${currentProjectId}&run_id=${runId}`;
}

function showFatalError(message) {
    const container = document.getElementById('history-container');
    if (container) {
        container.innerHTML = `
            <div class="flex flex-col items-center justify-center py-20 text-center">
                <span class="material-symbols-outlined text-6xl text-error mb-md">error_outline</span>
                <h3 class="font-headline-sm text-headline-sm text-on-surface mb-xs">Error</h3>
                <p class="font-body-md text-body-md text-secondary max-w-md">${escapeHtml(message)}</p>
                <a href="stacks.html" class="mt-lg inline-flex items-center gap-xs px-lg py-sm bg-primary-orange text-white rounded-DEFAULT font-label-md hover:opacity-90 transition-opacity">
                    Back to Projects
                </a>
            </div>
        `;
    }
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}