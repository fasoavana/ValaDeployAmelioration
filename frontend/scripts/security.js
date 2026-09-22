// scripts/security.js
// Liste globale des projets avec leur statut de sécurité

let allReports = [];

document.addEventListener('DOMContentLoaded', () => {
    initUserSession(
        async () => {
            try {
                const reports = await getSecurityList();
                renderSecurityTable(reports);
            } catch (error) {
                console.error('Erreur chargement rapports de sécurité:', error);
                // Notification d'erreur
                ValaToast.show({ type: 'error', title: 'Loading Error', message: 'Impossible to load security reports at the moment.' });
                document.getElementById('security-table-body').innerHTML = `
                    <tr><td colspan="6" class="py-lg text-center text-on-surface-variant">
                        Impossible to load security data at the moment.
                    </td></tr>`;
            }
        },
        (error) => {
            console.log('Session invalide ou expirée :', error.message);
            window.location.href = "login.html";
        }
    );
});

function renderSecurityTable(reports) {
    allReports = reports;
    renderRows(reports);
    updateSecurityStats(reports);
    updateShowingCount(reports.length, reports.length);
    setupSecurityFilter();
}

function renderRows(reports) {
    const tbody = document.getElementById('security-table-body');
    tbody.innerHTML = '';

    if (reports.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="6" class="py-xl text-center text-secondary">
                <span class="material-symbols-outlined text-4xl block mb-sm">folder_open</span>
                No projects yet.
            </td></tr>`;
        return;
    }

    reports.forEach(report => {
        tbody.appendChild(createSecurityRow(report));
    });
}

function setupSecurityFilter() {
    const input = document.getElementById('security-filter');
    if (!input || input.dataset.bound) return;
    input.dataset.bound = 'true';

    input.addEventListener('input', () => {
        const query = input.value.trim().toLowerCase();
        const filtered = query
            ? allReports.filter(r => (r.slug || '').toLowerCase().includes(query))
            : allReports;

        renderRows(filtered);
        updateShowingCount(filtered.length, allReports.length);
    });
}

function updateSecurityStats(reports) {
    const totalEl = document.getElementById('sec-total-projects');
    if (totalEl) totalEl.textContent = reports.length;

    const blockedEl = document.getElementById('sec-blocked-count');
    if (blockedEl) {
        const blockedCount = reports.filter(r => r.fail_reason === 'VULNERABILITY' || r.fail_reason === 'SECRET_LEAK').length;
        blockedEl.textContent = blockedCount;
    }

    const criticalEl = document.getElementById('sec-critical-total');
    if (criticalEl) {
        const criticalTotal = reports.reduce((sum, r) => sum + (r.critical_vuln_count || 0), 0);
        criticalEl.textContent = criticalTotal;
    }

    const secretsEl = document.getElementById('sec-secrets-total');
    if (secretsEl) {
        const secretsTotal = reports.reduce((sum, r) => sum + (r.secret_count || 0), 0);
        secretsEl.textContent = secretsTotal;
    }
}

function updateShowingCount(shown, total) {
    const el = document.getElementById('sec-showing-count');
    if (el) el.textContent = `Showing ${shown} of ${total} projects`;
}

// Palette d'avatars — même logique que dashboard.js pour rester cohérent visuellement
const AVATAR_PALETTE = [
    { bg: 'bg-primary-container/15', text: 'text-primary' },
    { bg: 'bg-[#0096fd]/15', text: 'text-[#0096fd]' },
    { bg: 'bg-[#12B76A]/15', text: 'text-[#12B76A]' },
    { bg: 'bg-surface-container-high', text: 'text-on-surface' },
];

function getAvatarStyle(slug) {
    const str = slug || '?';
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function createSecurityRow(report) {
    const row = document.createElement('tr');
    row.className = 'hover:bg-surface-container-low transition-colors group';

    const blocked = report.fail_reason === 'VULNERABILITY' || report.fail_reason === 'SECRET_LEAK';
    const scanBadge = blocked
        ? `<span class="scan-badge scan-badge-blocked">
               <span class="material-symbols-outlined text-[14px]">gpp_bad</span>
               Blocked
           </span>`
        : `<span class="scan-badge scan-badge-passed">
               <span class="material-symbols-outlined text-[14px]">verified_user</span>
               Passed
           </span>`;

    const deployStatus = getStatusConfig(report.status);
    const initial = (report.slug || '?').charAt(0).toUpperCase();
    const avatar = getAvatarStyle(report.slug);

    row.innerHTML = `
        <td class="py-md px-lg">
            <div class="flex items-center gap-md">
                <div class="w-9 h-9 rounded-lg ${avatar.bg} ${avatar.text} flex items-center justify-center font-label-md text-label-md font-semibold shrink-0">
                    ${initial}
                </div>
                <div class="font-mono-code text-mono-code font-semibold text-on-surface">${report.slug}</div>
            </div>
        </td>
        <td class="py-md px-lg">
            <div class="status-badge ${deployStatus.class}">
                <div class="status-dot"></div>
                <span class="font-label-sm text-label-sm">${deployStatus.label}</span>
            </div>
        </td>
        <td class="py-md px-lg font-label-md text-label-md ${report.critical_vuln_count > 0 ? 'severity-stat-critical font-semibold' : 'text-secondary'}">${report.critical_vuln_count}</td>
        <td class="py-md px-lg font-label-md text-label-md ${report.secret_count > 0 ? 'severity-stat-critical font-semibold' : 'text-secondary'}">${report.secret_count}</td>
        <td class="py-md px-lg">${scanBadge}</td>
        <td class="py-md px-lg text-right">
            <a href="security-details.html?slug=${report.slug}"
               class="text-on-surface hover:text-primary transition-colors inline-flex items-center gap-xs">
                <span class="font-label-md text-label-md">Report</span>
                <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
            </a>
        </td>
    `;
    return row;
}

// Réutilise le même mapping que dashboard.js (dupliqué ici volontairement,
// les deux fichiers sont chargés sur des pages différentes)
function getStatusConfig(status) {
    const configs = {
        'running': { label: 'Running', class: 'status-running' },
        'stopped': { label: 'Stopped', class: 'status-stopped' },
        'building': { label: 'Building', class: 'status-building' },
        'failed': { label: 'Failed', class: 'status-error' }
    };
    return configs[status] || { label: status || 'Unknown', class: 'status-created' };
}