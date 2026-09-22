// Comportement de la page Security Report.
//scripts/security-details.js
document.addEventListener('DOMContentLoaded', () => {
    const slug = new URLSearchParams(window.location.search).get('slug') || 'unknown-project';
    const slugEl = document.getElementById('project-slug');
    if (slugEl) slugEl.textContent = slug;

    // Gestion du bouton Re-scan
    const rescanBtn = document.getElementById('rescan-btn');
    if (rescanBtn) {
        rescanBtn.addEventListener('click', () => {
            ValaToast.show({
                type: 'info',
                title: 'Information',
                message: 'This feature is coming soon.',
                duration: 3000
            });
        });
    }

    initUserSession(
        async () => {
            try {
                const report = await getSecurityReport(slug);

                const trivyResult = {
                    severity_count: report.severity_count,
                    blocking: report.fail_reason === 'VULNERABILITY',
                };
                const gitleaksResult = {
                    blocking: report.fail_reason === 'SECRET_LEAK',
                    secret_count: report.secret_count,
                    secret_found: report.secret_found,
                };

                renderSummary(trivyResult, gitleaksResult);
                renderTrivyCounts(trivyResult);
                renderGitleaksResult(gitleaksResult);
            } catch (error) {
                console.error('Erreur chargement rapport de sécurité:', error);
                const badge = document.getElementById('scan-status-badge');
                if (badge) {
                    badge.textContent = 'Loading Error';
                    badge.className = 'flex items-center gap-2 px-4 py-2 border border-error text-error rounded-full font-label-md text-label-md bg-white';
                }
            }
        },
        (error) => {
            console.log('Session invalide ou expirée :', error.message);
            window.location.href = "login.html";
        }
    );
});

// ... (fonctions renderSummary, renderTrivyCounts, renderGitleaksResult inchangées)

function renderSummary(trivyResult, gitleaksResult) {
    const badge = document.getElementById('scan-status-badge');
    const blocked = trivyResult.blocking || gitleaksResult.blocking;

    badge.textContent = blocked ? 'Deployment Blocked' : 'Passed';
    badge.className = blocked
        ? 'flex items-center gap-2 px-4 py-2 border border-error text-error rounded-full font-label-md text-label-md bg-white'
        : 'flex items-center gap-2 px-4 py-2 border border-[#12B76A] text-[#12B76A] rounded-full font-label-md text-label-md bg-white';
}

function renderTrivyCounts(trivyResult) {
    const counts = trivyResult.severity_count || {};
    document.getElementById('count-critical').textContent = counts.CRITICAL || 0;
    document.getElementById('count-high').textContent = counts.HIGH || 0;
    document.getElementById('count-medium').textContent = counts.MEDIUM || 0;
    document.getElementById('count-low').textContent = counts.LOW || 0;
}

function renderGitleaksResult(gitleaksResult) {
    const container = document.getElementById('gitleaks-section');

    if (!gitleaksResult.secret_count) {
        container.innerHTML = `
            <div class="flex items-center gap-2 text-[#12B76A] font-body-sm text-body-sm">
                <span class="material-symbols-outlined text-[18px]">check_circle</span>
                No secrets detected in the repository history.
            </div>`;
        return;
    }

    const secret = gitleaksResult.secret_found;
    const extraNote = gitleaksResult.secret_count > 1
        ? `<p class="font-body-sm text-body-sm text-secondary mt-sm italic">${gitleaksResult.secret_count} secrets detected in total — only the first is shown (backend limitation).</p>`
        : '';

    container.innerHTML = `
        <div class="py-md flex flex-col md:flex-row gap-md md:items-center justify-between">
            <div class="flex-1">
                <div class="flex items-center gap-sm mb-xs">
                    <span class="font-mono-code text-mono-code text-on-surface font-medium">${secret.rule_id}</span>
                    <span class="px-2 py-0.5 border border-outline rounded text-xs font-mono-code text-secondary">${secret.file}</span>
                </div>
                <div class="text-secondary text-sm">${secret.description}</div>
            </div>
            <div class="font-body-sm text-body-sm text-secondary md:text-right">
                <div>Line ${secret.line}</div>
            </div>
        </div>
        ${extraNote}`;
}