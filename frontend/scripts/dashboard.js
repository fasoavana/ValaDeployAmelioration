// api/dashboard.js
// Loading projects, pagination, filtering and deletion


document.addEventListener('DOMContentLoaded', () => {
    initUserSession(
        async (user) => {
            const fullnameEl = document.getElementById('user-fullname');
            if (fullnameEl) fullnameEl.textContent = user.full_name;

            try {
                const projects = await getProjects();
                renderProjects(projects);
            } catch (error) {
                console.error('Error loading projects:', error);

                if (typeof ValaToast !== 'undefined') {
                    ValaToast.show({
                        type: 'error',
                        title: 'Error loading projects',
                        message: error.message || 'Impossible to load projects.',
                        duration: 6000
                    });
                }
                const tbody = document.getElementById('projects-table-body');
                if (tbody) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="5" class="py-lg text-center text-on-surface-variant">
                                Impossible to display projects at the moment.
                            </td>
                        </tr>
                    `;
                }
            }

            // Charge les stats dashboard séparément (ne bloque pas l'affichage des projets)
            try {
                const stats = await getDashboardStats();
                renderDashboardStats(stats);
            } catch (error) {
                console.error('Error loading dashboard stats:', error);
            }
        },
        (error) => {
            console.log('Invalid or expired session :', error.message);
            window.location.href = "login.html";
        }
    );
});

// --- État en mémoire ---
let allProjects = [];       // liste complète (source de vérité pour stats/filtrage)
let visibleProjects = [];   // liste après filtrage texte
let currentPage = 1;
const PAGE_SIZE = 10;

// Palette de badges avatar (douce, pas de gris "excel") — choisie cycliquement selon le nom du projet
const AVATAR_PALETTE = [
    { bg: 'bg-primary-container/15', text: 'text-primary' },
    { bg: 'bg-tertiary-container/15', text: 'text-tertiary' },
    { bg: 'bg-[#12B76A]/15', text: 'text-[#12B76A]' },
    { bg: 'bg-surface-container-high', text: 'text-on-surface' },
];

function getAvatarStyle(slug) {
    const str = slug || '?';
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function renderProjects(projects) {
    allProjects = projects;
    visibleProjects = projects;
    currentPage = 1;

    renderCurrentPage();
    updateStats(allProjects);
    setupProjectFilter();
    setupPagination();
}

// --- Pagination ---
function getTotalPages() {
    return Math.max(1, Math.ceil(visibleProjects.length / PAGE_SIZE));
}

function getPageSlice() {
    const start = (currentPage - 1) * PAGE_SIZE;
    return visibleProjects.slice(start, start + PAGE_SIZE);
}

function renderCurrentPage() {
    const totalPages = getTotalPages();
    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const pageItems = getPageSlice();
    renderTable(pageItems, visibleProjects.length === 0);

    const start = visibleProjects.length === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
    const end = Math.min(currentPage * PAGE_SIZE, visibleProjects.length);
    updateShowingCount(start, end, visibleProjects.length);
    updatePageIndicator(currentPage, totalPages);
    updatePaginationButtons(currentPage, totalPages);
}

function setupPagination() {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    if (!prevBtn || !nextBtn) return;

    if (!prevBtn.dataset.bound) {
        prevBtn.dataset.bound = 'true';
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage -= 1;
                renderCurrentPage();
            }
        });
    }

    if (!nextBtn.dataset.bound) {
        nextBtn.dataset.bound = 'true';
        nextBtn.addEventListener('click', () => {
            if (currentPage < getTotalPages()) {
                currentPage += 1;
                renderCurrentPage();
            }
        });
    }
}

function updatePaginationButtons(page, totalPages) {
    const prevBtn = document.getElementById('prev-page');
    const nextBtn = document.getElementById('next-page');
    if (prevBtn) prevBtn.disabled = page <= 1;
    if (nextBtn) nextBtn.disabled = page >= totalPages;
}

function updatePageIndicator(page, totalPages) {
    const el = document.getElementById('page-indicator');
    if (el) el.textContent = `Page ${page} of ${totalPages}`;
}

// --- Rendu du tableau ---
function renderTable(projects, isTrulyEmpty) {
    const tbody = document.getElementById('projects-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (projects.length === 0) {
        if (isTrulyEmpty) {
            tbody.innerHTML = `
                <tr id="empty-row">
                    <td colspan="5" class="py-xl text-center text-secondary">
                        <span class="material-symbols-outlined text-4xl block mb-sm">folder_open</span>
                        <p>No projects at the moment</p>
                        <a href="new-project.html" class="inline-block mt-md px-lg py-sm bg-primary-container text-on-primary rounded-lg hover:opacity-90 transition-all duration-150 active:scale-[0.97]">
                            Create your first project
                        </a>
                    </td>
                </tr>
            `;
        } else {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="py-xl text-center text-secondary">
                        <span class="material-symbols-outlined text-4xl block mb-sm">search_off</span>
                        <p>No projects match your search</p>
                    </td>
                </tr>
            `;
        }
        return;
    }

    projects.forEach(project => {
        const row = createProjectRow(project);
        tbody.appendChild(row);
    });
}

function setupProjectFilter() {
    const input = document.getElementById('project-filter');
    if (!input || input.dataset.bound) return;
    input.dataset.bound = 'true';

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        visibleProjects = query
            ? allProjects.filter(p => (p.slug || '').toLowerCase().includes(query))
            : allProjects;

        currentPage = 1;
        renderCurrentPage();
    });
}

function createProjectRow(project) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-surface-container-low transition-colors duration-150 group project-row';
    row.dataset.projectId = project.id;

    // Déterminer le statut et la couleur
    const statusConfig = getStatusConfig(project.status);

    // URL du service (si running)
    const url = project.status === 'running'
        ? `${project.slug}.sslip.io`
        : 'not yet deployed';

    const initial = (project.slug || '?').charAt(0).toUpperCase();
    const avatar = getAvatarStyle(project.slug);
    const commitShort = project.commit_hash ? project.commit_hash.substring(0, 7) : '—';

    row.innerHTML = `
        <td class="py-md px-lg">
            <div class="flex items-center gap-md">
                <div class="w-9 h-9 rounded-lg ${avatar.bg} ${avatar.text} flex items-center justify-center font-label-md text-label-md font-semibold shrink-0 transition-transform duration-150 group-hover:scale-105">
                    ${initial}
                </div>
                <div>
                    <div class="font-label-md text-label-md text-on-surface font-semibold">${project.slug}</div>
                    <div class="font-body-sm text-body-sm text-secondary">${url}</div>
                </div>
            </div>
        </td>
        <td class="py-md px-lg">
            <div class="status-badge ${statusConfig.class}">
                <div class="status-dot"></div>
                <span class="font-label-sm text-label-sm">${statusConfig.label}</span>
            </div>
        </td>
        <td class="py-md px-lg font-mono-code text-mono-code text-secondary">${commitShort}</td>
        <td class="py-md px-lg text-secondary">
            <span class="inline-flex items-center gap-xs">
                <span class="w-[6px] h-[6px] rounded-full bg-secondary inline-block"></span>
                ${project.replica || 1}
            </span>
        </td>
        <td class="py-md px-lg text-right">
            <div class="flex items-center justify-end gap-sm">
                <button type="button"
                    class="delete-project-btn text-secondary hover:text-error opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all duration-150 inline-flex items-center justify-center w-8 h-8 rounded-lg hover:bg-error-container/40"
                    data-project-id="${project.id}"
                    data-project-slug="${project.slug}"
                    title="Supprimer le projet"
                    aria-label="Supprimer le projet ${project.slug}">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
                <a href="project-detail.html?slug=${project.slug}"
                   class="text-on-surface hover:text-primary transition-colors inline-flex items-center gap-xs">
                    <span class="font-label-md text-label-md">View</span>
                    <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
                </a>
            </div>
        </td>
    `;

    const deleteBtn = row.querySelector('.delete-project-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            handleDeleteProject(project);
        });
    }

    return row;
}

async function handleDeleteProject(project) {
    const confirmed = await ValaModal.confirm({
        title: "Delete Project",
        message: `Permanently delete the project "${project.slug}" ? This action is irreversible and will delete all associated data.`,
        confirmLabel: "Delete",
        cancelLabel: "Cancel",
        variant: "danger"
    });
    if (!confirmed) return;

    try {
        if (typeof deleteProject !== 'function') {
            throw new Error('Project deletion is not yet available.');
        }

        await deleteProject(project.id);

        // Mise à jour de l'état local
        allProjects = allProjects.filter(p => p.id !== project.id);
        visibleProjects = visibleProjects.filter(p => p.id !== project.id);

        renderCurrentPage();
        updateStats(allProjects);

        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'success',
                title: 'Project deleted',
                message: `The project "${project.slug}" has been deleted successfully.`,
                duration: 4000
            });
        }
    } catch (error) {
        console.error('Error deleting project:', error);
        if (typeof ValaToast !== 'undefined') {
            ValaToast.show({
                type: 'error',
                title: 'Deletion impossible',
                message: error.message || 'An error occurred while deleting the project.',
                duration: 6000
            });
        }
    }
}

function getStatusConfig(status) {
    const configs = {
        'running': {
            label: 'Running',
            class: 'status-running'
        },
        'stopped': {
            label: 'Stopped',
            class: 'status-stopped'
        },
        'building': {
            label: 'Building',
            class: 'status-building'
        },
        'failed': {
            label: 'Failed',
            class: 'status-error'
        }
    };
    return configs[status] || {
        label: status || 'Unknown',
        class: 'status-created'
    };
}

function updateStats(projects) {
    // Total projets
    const totalEl = document.getElementById('total-projects');
    if (totalEl) totalEl.textContent = projects.length;

    // Badge count dans l'onglet "Projects"
    const totalBadgeEl = document.getElementById('total-projects-badge');
    if (totalBadgeEl) totalBadgeEl.textContent = projects.length;

    // Conteneurs en cours d'exécution (projets avec status 'running')
    const runningEl = document.getElementById('running-containers');
    if (runningEl) {
        const runningCount = projects.filter(p => p.status === 'running').length;
        runningEl.textContent = runningCount;
    }
}

function updateShowingCount(start, end, total) {
    const el = document.getElementById('showing-count');
    if (!el) return;
    if (total === 0) {
        el.textContent = 'Showing 0 of 0 projects';
    } else {
        el.textContent = `Showing ${start}–${end} of ${total} projects`;
    }
}

function renderDashboardStats(stats) {
    // Pourcentage d'échecs dus à des vulnérabilités critiques
    const vulnsEl = document.getElementById('critical-vulns');
    if (vulnsEl) vulnsEl.textContent = stats.critical_vuln_percentage + '%';
}