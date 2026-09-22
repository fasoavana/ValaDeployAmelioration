// scripts/pipeline.js

// ==========================================================
// ÉTAT GLOBAL
// ==========================================================
let currentRunId = null;
let currentSlug = null;
let currentProjectId = null;

// ==========================================================
// INITIALISATION / ORCHESTRATION (ajouté)
// ==========================================================
document.addEventListener('DOMContentLoaded', () => {
    initUserSession(
        async () => {
            const params = new URLSearchParams(window.location.search);
            currentProjectId = params.get('project_id'); // peut être null -> vue globale tous projets
            const runId = params.get('run_id'); // permet d'arriver directement sur un run précis via l'URL

            if (runId) {
                await openRunDetails(runId);
            } else {
                await loadHistoryList();
            }
        },
        (error) => {
            console.log('Session invalide ou expirée :', error.message);
            window.location.href = "login.html";
        }
    );

    const backBtn = document.getElementById('back-to-history-btn');
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            // On coupe proprement le websocket/polling en cours avant de quitter la vue détails
            if (typeof disconnectWebSocket === 'function') disconnectWebSocket();
            if (typeof stopPollingForRun === 'function') stopPollingForRun();

            document.getElementById('details-view').classList.add('hidden');
            document.getElementById('history-view').classList.remove('hidden');

            // On rafraîchit la liste au retour, au cas où le statut d'un run a changé
            loadHistoryList();
        });
    }

    const cancelBtn = document.getElementById('cancel-btn');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', async () => {
            if (!currentProjectId) return;
            cancelBtn.disabled = true;
            try {
                await cancelBuild(currentProjectId);
                ValaToast.show({ type: 'info', title: 'Cancellation Requested', message: 'The build will be cancelled.' });
            } catch (error) {
                console.error("Erreur lors de l'annulation :", error);
                ValaToast.show({ type: 'error', title: 'Error', message: "Impossible to cancel the build." });
                cancelBtn.disabled = false;
            }
        });
    }

    const retryBtn = document.getElementById('retry-btn');
    if (retryBtn) {
        retryBtn.addEventListener('click', async () => {
            if (!currentProjectId) return;
            try {
                const run = await retryBuild(currentProjectId);
                ValaToast.show({ type: 'success', title: 'Build Retried', message: 'A new run has started.' });
                if (run && run.id) {
                    await openRunDetails(run.id);
                }
            } catch (error) {
                console.error("Erreur lors du retry :", error);
                ValaToast.show({ type: 'error', title: 'Error', message: 'Impossible to retry the build.' });
            }
        });
    }
});

async function loadHistoryList() {
    const loadingEl = document.getElementById('history-loading');
    const emptyEl = document.getElementById('history-empty');
    const listEl = document.getElementById('history-list');
    const slugEl = document.getElementById('history-project-slug');

    if (loadingEl) loadingEl.style.display = 'flex';
    if (listEl) listEl.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'none';

    const isGlobalView = !currentProjectId;

    try {
        // Vue globale (sidebar, sans project_id) -> tous les runs, tous projets
        // Vue par projet (venu de stacks.html avec ?project_id=...) -> historique d'un seul projet
        const history = isGlobalView
            ? await getAllDeployments()
            : await getDeploymentHistory(currentProjectId);

        if (loadingEl) loadingEl.style.display = 'none';

        if (!history || history.length === 0) {
            if (emptyEl) emptyEl.style.display = 'flex';
            return;
        }

        if (slugEl) {
            if (isGlobalView) {
                slugEl.textContent = 'All Projects';
            } else {
                currentSlug = (history[0].project_slug) || (history[0].project && history[0].project.slug) || null;
                slugEl.textContent = currentSlug || `#${currentProjectId}`;
            }
        }

        if (listEl) {
            listEl.innerHTML = history.map(run => renderHistoryItem(run, isGlobalView)).join('');
            listEl.style.display = 'flex';
        }

    } catch (error) {
        console.error('Erreur de chargement de l\'historique:', error);
        if (loadingEl) loadingEl.style.display = 'none';
        showHistoryError('Impossible de charger l\'historique des déploiements.');
    }
}

function renderHistoryItem(run, showProject) {
    const status = run.status ? run.status.toLowerCase() : 'pending';
    const triggerLabel = run.trigger === 'webhook' ? 'Webhook GitHub' : 'Manuel';
    const commit = run.commit_hash ? `#${run.commit_hash.substring(0, 7)}` : '—';
    const dateStr = run.started_at
        ? new Date(run.started_at).toLocaleString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
        : '—';
    const projectLabel = showProject
        ? `<span class="font-label-sm text-label-sm text-primary-dark font-semibold shrink-0">${escapeHtml(run.project_slug || run.project_name || ('#' + run.project_id))}</span>`
        : '';

    // En vue globale, on doit garder le project_id de CE run (pas currentProjectId, qui est null)
    return `
        <button onclick="openRunDetails(${run.id}, ${run.project_id})"
                class="text-left border border-outline-variant rounded-lg p-md flex items-center justify-between gap-md hover:border-primary-orange transition-colors bg-surface-container-lowest">
            <div class="flex items-center gap-md min-w-0">
                <span class="font-mono-code text-label-sm text-secondary shrink-0">#${run.id}</span>
                ${projectLabel}
                <span class="font-body-sm text-body-sm text-on-surface truncate">${dateStr}</span>
                <span class="font-label-sm text-label-sm text-secondary shrink-0">${triggerLabel}</span>
            </div>
            <div class="flex items-center gap-md shrink-0">
                <span class="font-mono-code text-label-sm text-secondary">${commit}</span>
                <span class="font-label-sm text-label-sm px-sm py-xs rounded-full bg-surface-container-highest">${status}</span>
            </div>
        </button>
    `;
}

async function openRunDetails(runId, projectId) {
    // projectId permet d'ouvrir un run depuis la vue globale, où currentProjectId est null
    const targetProjectId = projectId || currentProjectId;
    try {
        const run = await getDeploymentRunDetails(targetProjectId, runId);
        currentProjectId = targetProjectId; // pour que cancel/retry visent le bon projet
        showDetailsView(run);
    } catch (error) {
        console.error("Erreur lors du chargement du run :", error);
        ValaToast.show({ type: 'error', title: 'Error', message: 'Impossible to load the details of this run.' });
    }
}

function showHistoryError(message) {
    const listEl = document.getElementById('history-list');
    const emptyEl = document.getElementById('history-empty');
    if (emptyEl) emptyEl.style.display = 'none';
    if (listEl) {
        listEl.innerHTML = `<p class="text-error font-body-md text-body-md">${escapeHtml(message)}</p>`;
        listEl.style.display = 'flex';
    }
}

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ==========================================================
// FONCTIONS MANQUANTES DE log.js (ajoutées ici)
// log.js ne fait que le websocket brut (connectLogsWebSocket),
// il n'y avait aucune fonction de rendu -> elles n'existaient nulle part.
// ==========================================================

const TERMINAL_STATUSES = ['success', 'failed', 'cancelled'];
const CANCEL_BTN_DEFAULT_HTML = `
    <span class="material-symbols-outlined text-[18px]">stop_circle</span>
    Cancel Build
`;

const STATUS_BADGE_CONFIG = {
    pending:   { label: 'En attente',    dot: '#5e5e5e', text: '#5e5e5e', bg: 'rgba(94, 94, 94, 0.1)',   border: 'rgba(94, 94, 94, 0.2)' },
    cloning:   { label: 'Clonage',       dot: '#1d4ed8', text: '#1d4ed8', bg: 'rgba(29, 78, 216, 0.1)',  border: 'rgba(29, 78, 216, 0.2)' },
    building:  { label: 'Build',         dot: '#d97706', text: '#d97706', bg: 'rgba(217, 119, 6, 0.1)',  border: 'rgba(217, 119, 6, 0.2)' },
    scanning:  { label: 'Scan Sécurité', dot: '#7c3aed', text: '#7c3aed', bg: 'rgba(124, 58, 237, 0.1)', border: 'rgba(124, 58, 237, 0.2)' },
    deploying: { label: 'Déploiement',   dot: '#ff5c00', text: '#ff5c00', bg: 'rgba(255, 92, 0, 0.1)',   border: 'rgba(255, 92, 0, 0.2)' },
    success:   { label: 'Succès',        dot: '#12b76a', text: '#12b76a', bg: 'rgba(18, 183, 106, 0.1)', border: 'rgba(18, 183, 106, 0.2)' },
    failed:    { label: 'Échec',         dot: '#ba1a1a', text: '#ba1a1a', bg: 'rgba(186, 26, 26, 0.1)',  border: 'rgba(186, 26, 26, 0.2)' },
    cancelled: { label: 'Annulé',        dot: '#5e5e5e', text: '#5e5e5e', bg: 'rgba(94, 94, 94, 0.1)',   border: 'rgba(94, 94, 94, 0.2)' }
};

function renderStatusBadge(status) {
    const badge = document.getElementById('pipeline-status-badge');
    if (!badge) return;
    const key = status ? status.toLowerCase() : 'pending';
    const config = STATUS_BADGE_CONFIG[key] || STATUS_BADGE_CONFIG.pending;

    badge.style.backgroundColor = config.bg;
    badge.style.borderColor = config.border;

    const dotEl = badge.querySelector('span.w-2');
    if (dotEl) dotEl.style.backgroundColor = config.dot;

    const labelEl = badge.querySelector('span.font-label-sm');
    if (labelEl) {
        labelEl.textContent = config.label;
        labelEl.style.color = config.text;
    }
}

function appendLog(line) {
    const body = document.getElementById('terminal-body');
    if (!body) return;
    const lineEl = document.createElement('div');
    lineEl.textContent = line; // textContent = pas d'injection HTML, safe par défaut
    lineEl.className = 'whitespace-pre-wrap break-words';
    body.appendChild(lineEl);
    body.scrollTop = body.scrollHeight;
}

const PIPELINE_STEP_ORDER = ['cloning', 'building', 'scanning', 'deploying'];

function getStatusForStep(currentStatus, stepKey) {
    if (currentStatus === 'success') return 'done';

    if (TERMINAL_STATUSES.includes(currentStatus)) {
        // Le backend ne renvoie qu'un statut global ('failed'/'cancelled'), pas l'étape
        // exacte où ça s'est arrêté. On affiche donc tout comme terminé, sauf la
        // dernière étape marquée en erreur. À affiner si le backend expose un jour
        // un champ "failed_step".
        return stepKey === PIPELINE_STEP_ORDER[PIPELINE_STEP_ORDER.length - 1] ? 'error' : 'done';
    }

    const currentIndex = PIPELINE_STEP_ORDER.indexOf(currentStatus);
    const stepIndex = PIPELINE_STEP_ORDER.indexOf(stepKey);
    if (currentIndex === -1) return 'pending'; // ex: statut 'pending'
    if (stepIndex < currentIndex) return 'done';
    if (stepIndex === currentIndex) return 'active';
    return 'pending';
}

function getStepIconMarkup(status) {
    switch (status) {
        case 'done':
            return `<span class="material-symbols-outlined text-[20px]" style="color:#12b76a;">check_circle</span>`;
        case 'active':
            return `<span class="material-symbols-outlined text-[20px] animate-spin" style="color:#ff5c00;">progress_activity</span>`;
        case 'error':
            return `<span class="material-symbols-outlined text-[20px]" style="color:#ba1a1a;">cancel</span>`;
        default:
            return `<span class="material-symbols-outlined text-[20px] text-outline-variant">radio_button_unchecked</span>`;
    }
}

function getStepFooterMarkup(step) {
    if (step.status === 'active') {
        return `<span class="font-label-sm text-label-sm text-primary-orange mt-1">En cours...</span>`;
    }
    if (step.status === 'error') {
        return `<span class="font-label-sm text-label-sm text-error mt-1">Échec</span>`;
    }
    return '';
}

// ---------- WebSocket + polling ----------

let currentLogsWs = null;
let currentPollingInterval = null;

function connectWebSocket(slug) {
    disconnectWebSocket(); // évite les connexions dupliquées si on rouvre un run

    currentLogsWs = connectLogsWebSocket(slug, null, currentAccessToken, {
        onOpen: () => console.log('[DEBUG] WebSocket logs connecté pour', slug),
        onMessage: (data) => appendLog(data),
        onClose: () => console.log('[DEBUG] WebSocket logs fermé'),
        onTokenExpired: (newToken) => {
            // Le token a été rafraîchi pendant le stream -> on reconnecte avec le nouveau
            connectWebSocket(slug);
        },
        onError: (err) => console.error('[DEBUG] Erreur WebSocket logs :', err)
    });
}

function disconnectWebSocket() {
    if (currentLogsWs) {
        currentLogsWs.close();
        currentLogsWs = null;
    }
}

function startPollingForRun(runId) {
    stopPollingForRun();
    currentPollingInterval = setInterval(async () => {
        try {
            const run = await getDeploymentRunDetails(currentProjectId, runId);
            renderStatusBadge(run.status);
            renderStepsForRun(run);
            renderActions({
                status: run.status,
                project: {
                    slug: currentSlug,
                    live_url: (run.status.toLowerCase() === 'success' && currentSlug) ? `http://${currentSlug}.localhost` : null
                }
            });

            if (TERMINAL_STATUSES.includes(run.status.toLowerCase())) {
                stopPollingForRun();
                disconnectWebSocket();
            }
        } catch (error) {
            console.error('[DEBUG] Erreur de polling :', error);
        }
    }, 5000);
}

function stopPollingForRun() {
    if (currentPollingInterval) {
        clearInterval(currentPollingInterval);
        currentPollingInterval = null;
    }
}

// ==========================================================
// RENDU DE LA VUE DÉTAILS (existant, inchangé)
// ==========================================================
function showDetailsView(run) {
    console.log("[DEBUG] 1. Début de showDetailsView pour le run:", run.id);

    const historyView = document.getElementById('history-view');
    const detailsView = document.getElementById('details-view');
    console.log("[DEBUG] 2. Éléments HTML trouvés ? historyView:", !!historyView, "detailsView:", !!detailsView);

    if (historyView) {
        historyView.classList.add('hidden');
        console.log("[DEBUG] 3. history-view masqué (class 'hidden' ajoutée)");
    }
    if (detailsView) {
        detailsView.classList.remove('hidden');
        console.log("[DEBUG] 4. details-view affiché (class 'hidden' retirée)");
    }

    currentRunId = run.id;
    currentSlug = run.project_slug || currentSlug;
    console.log("[DEBUG] 5. currentSlug défini à:", currentSlug);

    // Mise à jour sécurisée des éléments du DOM
    const slugEl = document.getElementById('pipeline-slug');
    if (slugEl) { slugEl.textContent = currentSlug || 'Projet inconnu'; console.log("[DEBUG] 6. Slug affiché"); }

    const envEl = document.getElementById('pipeline-environment');
    if (envEl) { envEl.textContent = 'local'; console.log("[DEBUG] 7. Env affiché"); }

    const commitEl = document.getElementById('pipeline-commit');
    if (commitEl) { commitEl.textContent = run.commit_hash ? `#${run.commit_hash.substring(0, 7)}` : '—'; console.log("[DEBUG] 8. Commit affiché"); }

    const triggerEl = document.getElementById('pipeline-trigger');
    if (triggerEl) { triggerEl.textContent = run.trigger === 'webhook' ? 'Webhook GitHub' : 'Manuel'; console.log("[DEBUG] 9. Trigger affiché"); }

    const titleEl = document.getElementById('terminal-title');
    if (titleEl) { titleEl.textContent = `Build Log - Run #${run.id}`; console.log("[DEBUG] 10. Titre terminal mis à jour"); }

    console.log("[DEBUG] 11. Appel de renderStatusBadge...");
    renderStatusBadge(run.status);

    // Terminal
    console.log("[DEBUG] 12. Mise à jour du terminal...");
    const body = document.getElementById('terminal-body');
    if (body) {
        body.innerHTML = '';
        if (run.logs) {
            run.logs.split('\n').forEach(line => {
                if (line.trim()) appendLog(line);
            });
            console.log("[DEBUG] 13. Logs historiques injectés");
        } else {
            appendLog("[INFO] Aucun log détaillé disponible pour ce run historique.");
        }
    }

    console.log("[DEBUG] 14. Appel de renderStepsForRun...");
    renderStepsForRun(run);

    console.log("[DEBUG] 15. Appel de renderActions...");
    renderActions({
        status: run.status,
        project: {
            slug: currentSlug,
            live_url: (run.status.toLowerCase() === 'success' && currentSlug) ? `http://${currentSlug}.localhost` : null
        }
    });

    console.log("[DEBUG] 16. Fin de showDetailsView. Vérification du statut terminal...");
    const isTerminal = ['success', 'failed', 'cancelled'].includes(run.status.toLowerCase());
    if (!isTerminal) {
        if (!currentSlug) {
            appendLog("\n[ERREUR SYSTÈME] Impossible de connecter les logs en temps réel : identifiant du projet manquant.");
        } else {
            console.log("[DEBUG] 17. Démarrage du WebSocket et du polling...");
            connectWebSocket(currentSlug);
            startPollingForRun(run.id);
        }
    } else {
        console.log("[DEBUG] 17. Run terminé, pas de WebSocket nécessaire.");
    }
    console.log("[DEBUG] 18. showDetailsView terminé avec succès.");
}

function renderStepsForRun(run) {
    console.log("[DEBUG] renderStepsForRun appelé avec status:", run.status);
    const status = run.status ? run.status.toLowerCase() : 'pending';
    const steps = [
        { label: "Clone Repository", description: "Cloning the repository", status: getStatusForStep(status, 'cloning') },
        { label: "Build Docker Image", description: "Building the Docker image", status: getStatusForStep(status, 'building') },
        { label: "Security Scan", description: "Scanning for security vulnerabilities", status: getStatusForStep(status, 'scanning') },
        { label: "Deploy to Traefik", description: "Deploying to Traefik", status: getStatusForStep(status, 'deploying') }
    ];

    const container = document.getElementById('pipeline-steps');
    if (!container) {
        console.error("[DEBUG] ERREUR CRITIQUE : L'élément 'pipeline-steps' est introuvable dans le HTML !");
        return;
    }

    try {
        container.innerHTML = steps.map(step => `
            <div class="pipeline-step" data-status="${step.status}">
                <div class="step-icon">
                    ${getStepIconMarkup(step.status)}
                </div>
                <div class="flex flex-col pt-xs min-w-0">
                    <span class="pipeline-step-title font-label-md text-label-md text-on-surface" data-status="${step.status}">${escapeHtml(step.label)}</span>
                    <span class="font-body-sm text-body-sm text-secondary mt-1">${escapeHtml(step.description || '')}</span>
                    ${getStepFooterMarkup(step)}
                </div>
            </div>
        `).join('');
        console.log("[DEBUG] renderStepsForRun terminé avec succès.");
    } catch (e) {
        console.error("[DEBUG] Erreur lors du rendu des étapes:", e);
    }
}

function renderActions(data) {
    console.log("[DEBUG] renderActions appelé avec status:", data.status);
    const cancelBtn = document.getElementById('cancel-btn');
    const retryBtn = document.getElementById('retry-btn');
    const viewLiveBtn = document.getElementById('view-live-btn');
    const isRunning = !TERMINAL_STATUSES.includes(data.status.toLowerCase());

    if (cancelBtn) {
        cancelBtn.style.display = isRunning ? '' : 'none';
        if (isRunning) {
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = CANCEL_BTN_DEFAULT_HTML;
        }
    }
    if (retryBtn) {
        retryBtn.style.display = (data.status.toLowerCase() === 'failed' || data.status.toLowerCase() === 'cancelled') ? '' : 'none';
    }
    if (viewLiveBtn) {
        const liveUrl = data.project && data.project.live_url;
        if (data.status.toLowerCase() === 'success' && liveUrl) {
            viewLiveBtn.style.display = '';
            viewLiveBtn.href = liveUrl;
        } else {
            viewLiveBtn.style.display = 'none';
        }
    }
    console.log("[DEBUG] renderActions terminé avec succès.");
}