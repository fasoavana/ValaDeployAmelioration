// scripts/vuln-render.js
// Rendu formaté d'une liste de vulnérabilités critiques (format scan_service.py),
// groupées par patchable / non-patchable. Utilisé par le popup de confirmation
// et par la future page de détail sécurité. N'a pas de HTML propre : il remplit
// un container déjà présent dans la page appelante.

function renderVulnerabilityList(containerEl, vulnerabilities) {
    if (!containerEl) return;

    if (!vulnerabilities || vulnerabilities.length === 0) {
        containerEl.innerHTML = '<p class="text-secondary text-body-sm italic">Aucune vulnérabilité critique.</p>';
        return;
    }

    const patchable = vulnerabilities.filter(v => v.fixed);
    const notPatchable = vulnerabilities.filter(v => !v.fixed);

    const renderCard = (v) => `
        <div class="border border-outline-variant rounded-lg p-md bg-surface-container-lowest">
            <div class="flex items-center justify-between gap-sm mb-xs">
                <span class="font-mono-code text-label-sm text-primary-orange">${escapeHtml(v.id || 'CVE-INCONNU')}</span>
                <span class="font-label-sm text-label-sm px-sm py-xs rounded-full ${v.fixed ? 'bg-[#12B76A]/10 text-[#12B76A]' : 'bg-red-500/10 text-red-500'}">
                    ${v.fixed ? 'Patch disponible' : 'Pas de patch'}
                </span>
            </div>
            <p class="font-body-sm text-body-sm text-on-surface mb-xs">${escapeHtml(v.title || 'Sans titre')}</p>
            <div class="flex flex-wrap gap-md font-mono-code text-label-sm text-secondary">
                <span><strong class="text-on-surface">Package:</strong> ${escapeHtml(v.package || '—')}</span>
                <span><strong class="text-on-surface">Installée:</strong> ${escapeHtml(v.installed_version || '—')}</span>
                ${v.fixed ? `<span><strong class="text-on-surface">Corrigée:</strong> ${escapeHtml(v.fixed_version)}</span>` : ''}
            </div>
        </div>
    `;

    let html = '';

    if (patchable.length > 0) {
        html += `
            <div class="mb-lg">
                <h4 class="font-label-md text-label-md text-[#12B76A] uppercase tracking-wider mb-sm flex items-center gap-xs">
                    <span class="material-symbols-outlined text-[18px]">build</span>
                    Patchables (${patchable.length})
                </h4>
                <div class="space-y-sm">${patchable.map(renderCard).join('')}</div>
            </div>
        `;
    }

    if (notPatchable.length > 0) {
        html += `
            <div>
                <h4 class="font-label-md text-label-md text-red-500 uppercase tracking-wider mb-sm flex items-center gap-xs">
                    <span class="material-symbols-outlined text-[18px]">block</span>
                    Sans correctif (${notPatchable.length})
                </h4>
                <div class="space-y-sm">${notPatchable.map(renderCard).join('')}</div>
            </div>
        `;
    }

    containerEl.innerHTML = html;
}

// Fallback local si escapeHtml n'est pas déjà défini globalement par pipeline.js
if (typeof escapeHtml === 'undefined') {
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}