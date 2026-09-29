// scripts/security-details.js
// Security Report page: works for a single project AND for a stack

const COUNT_SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
const SEVERITIES = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'];
const SEV_RANK = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3, UNKNOWN: 4 };

// Severity pills (design only)
const SEV_PILL = 'inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold tracking-wide uppercase border';
const SEV_CLASS = {
    CRITICAL: `${SEV_PILL} bg-red-50 text-red-700 border-red-200/70`,
    HIGH: `${SEV_PILL} bg-orange-50 text-orange-700 border-orange-200/70`,
    MEDIUM: `${SEV_PILL} bg-amber-50 text-amber-700 border-amber-200/70`,
    LOW: `${SEV_PILL} bg-slate-50 text-slate-600 border-slate-200`,
    UNKNOWN: `${SEV_PILL} bg-slate-50 text-slate-500 border-slate-200`,
};

// Scan status badge (design only)
const BADGE_BASE = 'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border';
const BADGE_OK = `${BADGE_BASE} bg-emerald-50 text-emerald-700 border-emerald-200/80`;
const BADGE_ERR = `${BADGE_BASE} bg-red-50 text-red-700 border-red-200/80`;

let showAllSeverities = false;   // default: only CRITICAL + HIGH are listed

const esc = (s) => String(s ?? '').replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function comingSoon() {
    ValaToast.show({
        type: 'info',
        title: 'Coming soon',
        message: 'This feature is coming soon.',
        duration: 3000
    });
}

document.addEventListener('DOMContentLoaded', () => {
    const params = new URLSearchParams(window.location.search);
    const slug = params.get('slug') || 'unknown-project';
    const slugEl = document.getElementById('project-slug');
    if (slugEl) slugEl.textContent = slug;

    document.getElementById('rescan-btn')?.addEventListener('click', comingSoon);
    document.getElementById('autofix-btn')?.addEventListener('click', comingSoon);

    initUserSession(
        async () => {
            try {
                const report = await getSecurityReport(slug);
                const wantedComponent = params.get('component') || report.focus;

                if (slugEl) slugEl.textContent = report.slug;
                renderSummary(report);
                renderComponents(report, wantedComponent);
            } catch (error) {
                console.error('Error loading security report:', error);
                const badge = document.getElementById('scan-status-badge');
                if (badge) {
                    badge.textContent = 'Loading Error';
                    badge.className = BADGE_ERR;
                }
            }
        },
        (error) => {
            console.log('Invalid or expired session:', error.message);
            window.location.href = "login.html";
        }
    );
});

function renderSummary(report) {
    const badge = document.getElementById('scan-status-badge');
    const blocked = !!report.blocked;

    badge.innerHTML = blocked
        ? '<span class="material-symbols-outlined text-[14px]">block</span> Deployment Blocked'
        : '<span class="material-symbols-outlined text-[14px]">check</span> Passed';
    badge.className = blocked ? BADGE_ERR : BADGE_OK;
}

// Single project: no tabs. Stack: one tab per component.
function renderComponents(report, wanted) {
    const tabs = document.getElementById('component-tabs');
    const comps = report.components;

    if (!report.is_stack) {
        tabs.classList.add('hidden');
        renderComponent(comps[0]);
        return;
    }

    let active = comps.find(c => c.name === wanted) || comps[0];

    const draw = () => {
        tabs.innerHTML = comps.map(c => {
            const total = SEVERITIES.reduce((n, s) => n + ((c.severity_count || {})[s] || 0), 0);
            const on = c.name === active.name;
            return `<button data-name="${esc(c.name)}" type="button"
                class="px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-colors ${on
                    ? 'bg-slate-900 text-white border-transparent'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900'}">
                ${esc(c.name)} <span class="font-mono opacity-70">(${total})</span></button>`;
        }).join('');

        tabs.querySelectorAll('button').forEach(b => b.addEventListener('click', () => {
            active = comps.find(c => c.name === b.dataset.name);
            draw();
            renderComponent(active);
        }));
    };

    tabs.classList.remove('hidden');
    draw();
    renderComponent(active);
}

function renderComponent(c) {
    renderCounts(c.severity_count || {});
    renderVulnDetails(c.vulnerabilities || {}, c.severity_count || {});
    renderGitleaksResult(c);
}

function renderCounts(counts) {
    COUNT_SEVERITIES.forEach(s => {
        const el = document.getElementById(`count-${s.toLowerCase()}`);
        if (el) el.textContent = counts[s] || 0;
    });
}

// ---------------------------------------------------------------- //
// Vulnerabilities: grouped by origin, then by package
// ---------------------------------------------------------------- //

// Flat list from the {SEVERITY: [...]} dict. Old scans have no "origin" -> "system".
function flatten(grouped) {
    return SEVERITIES.flatMap(s => (grouped[s] || []).map(v => ({
        ...v,
        severity: v.severity || s,
        origin: v.origin || 'system',
    })));
}

function groupByPackage(vulns) {
    const map = new Map();
    vulns.forEach(v => {
        const key = v.package || 'unknown';
        if (!map.has(key)) {
            map.set(key, { name: key, vulns: [], worst: 'UNKNOWN', installed: v.installed_version, fixedVersions: new Set() });
        }
        const p = map.get(key);
        p.vulns.push(v);
        if (SEV_RANK[v.severity] < SEV_RANK[p.worst]) p.worst = v.severity;
        if (v.fixed_version) p.fixedVersions.add(v.fixed_version);
    });

    return [...map.values()]
        .map(p => ({
            ...p,
            // highest version fixes all issues of the package
            fixed: [...p.fixedVersions]
                .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
                .pop() || null,
        }))
        .sort((a, b) => SEV_RANK[a.worst] - SEV_RANK[b.worst] || b.vulns.length - a.vulns.length);
}

function cveRow(v) {
    return `
        <div class="py-2.5 flex flex-col md:flex-row md:items-start md:justify-between gap-1 md:gap-4">
            <div class="min-w-0">
                <div class="flex items-center gap-2">
                    <span class="font-mono text-xs font-semibold text-orange-600">${esc(v.id)}</span>
                    <span class="${SEV_CLASS[v.severity]}">${esc(v.severity)}</span>
                </div>
                <div class="text-slate-500 text-xs mt-1">${esc(v.title || 'No description available')}</div>
            </div>
            ${v.fixed_version ? `
            <div class="font-mono text-xs text-slate-500 shrink-0 md:text-right">
                ${esc(v.installed_version || '')} → <span class="font-semibold text-emerald-700">${esc(v.fixed_version)}</span>
            </div>` : ''}
        </div>`;
}

function packageRow(p, showFix) {
    const n = p.vulns.length;
    return `
        <details data-pkg class="group/pkg">
            <summary class="w-full grid grid-cols-12 items-center px-4 py-3.5 text-left hover:bg-slate-50/80 transition-colors cursor-pointer list-none [&::-webkit-details-marker]:hidden">
                <div class="col-span-5 sm:col-span-4 flex items-center gap-2.5 min-w-0">
                    <span class="material-symbols-outlined text-[16px] text-slate-400 transition-transform duration-200 group-open/pkg:rotate-90">chevron_right</span>
                    <span class="font-mono text-sm font-semibold text-slate-800 truncate" title="${esc(p.vulns[0].target || '')}">${esc(p.name)}</span>
                </div>
                <div class="col-span-3 sm:col-span-3">
                    <span class="${SEV_CLASS[p.worst]}">${esc(p.worst)}</span>
                </div>
                <div class="col-span-4 sm:col-span-5 text-right flex items-center justify-end gap-3 font-mono text-xs">
                    <span class="text-slate-500 font-sans text-xs hidden sm:inline">${n} issue${n > 1 ? 's' : ''}</span>
                    ${showFix && p.fixed ? `
                    <span class="text-slate-400">${esc(p.installed || '')}</span>
                    <span class="text-slate-400">→</span>
                    <span class="font-semibold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-100">${esc(p.fixed)}</span>` : ''}
                </div>
            </summary>
            <!-- UX: max height + internal scroll so long CVE lists don't push the page -->
            <div class="bg-slate-50/60 px-6 py-2 border-t border-slate-100 divide-y divide-slate-200/60 max-h-72 overflow-y-auto">
                ${p.vulns.map(cveRow).join('')}
            </div>
        </details>`;
}

function section({ title, subtitle, packages, showFix }) {
    const body = packages.length
        ? packages.map(p => packageRow(p, showFix)).join('')
        : `<div class="px-4 py-4 text-sm text-slate-500">No critical or high issues here.</div>`;
    return `
        <div class="space-y-3 mb-10">
            <div>
                <h3 class="text-xl font-bold tracking-tight text-slate-900">${esc(title)}</h3>
                <p class="text-xs text-slate-500 mt-0.5">${esc(subtitle)}</p>
            </div>
            <div>
                <div class="grid grid-cols-12 px-4 py-2 text-[11px] font-semibold tracking-wider uppercase text-slate-400 border-b border-slate-200">
                    <div class="col-span-5 sm:col-span-4">Package</div>
                    <div class="col-span-3 sm:col-span-3">Severity</div>
                    <div class="col-span-4 sm:col-span-5 text-right">Recommended Fix</div>
                </div>
                <div class="divide-y divide-slate-100 bg-white rounded-xl border border-slate-200/70 shadow-sm overflow-hidden">${body}</div>
            </div>
        </div>`;
}

function renderVulnDetails(grouped, counts) {
    const el = document.getElementById('vuln-details');
    const all = flatten(grouped);

    const fixSystem = all.filter(v => v.fixed && v.origin === 'system');
    const fixApp = all.filter(v => v.fixed && v.origin === 'app');
    const noFix = all.filter(v => !v.fixed);

    // Verdict cards (always count everything)
    document.getElementById('verdict-system').textContent = fixSystem.length;
    document.getElementById('verdict-app').textContent = fixApp.length;
    document.getElementById('verdict-nofix').textContent = noFix.length;

    const total = SEVERITIES.reduce((n, s) => n + (counts[s] || 0), 0);
    if (total === 0) {
        el.innerHTML = `
            <div class="bg-emerald-50/70 border border-emerald-200/60 rounded-xl p-4 flex items-center gap-3.5">
                <div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 text-emerald-600">
                    <span class="material-symbols-outlined text-[18px]">check</span>
                </div>
                <p class="text-sm font-semibold text-emerald-950">No vulnerabilities found.</p>
            </div>`;
        return;
    }

    // Default view: CRITICAL + HIGH only
    const visible = v => showAllSeverities || SEV_RANK[v.severity] <= SEV_RANK.HIGH;
    const hiddenCount = all.filter(v => !visible(v)).length;

    let html = '';
    if (fixSystem.length) {
        html += section({
            title: 'System packages',
            subtitle: 'Come from the base image, not from your code. Updating the image fixes them.',
            packages: groupByPackage(fixSystem.filter(visible)),
            showFix: true,
        });
    }
    if (fixApp.length) {
        html += section({
            title: 'Your application dependencies',
            subtitle: 'Come from your project. A newer version of each package fixes the issue.',
            packages: groupByPackage(fixApp.filter(visible)),
            showFix: true,
        });
    }
    if (noFix.length) {
        html += `
            <details class="group/nofix mb-10">
                <summary class="cursor-pointer list-none [&::-webkit-details-marker]:hidden flex items-center gap-2 text-sm font-semibold text-slate-500 hover:text-slate-700 transition-colors">
                    <span class="material-symbols-outlined text-[16px] text-slate-400 transition-transform duration-200 group-open/nofix:rotate-90">chevron_right</span>
                    No fix available yet (${noFix.length}) — nothing to do for now
                </summary>
                <div class="mt-3 divide-y divide-slate-100 bg-white rounded-xl border border-slate-200/70 shadow-sm overflow-hidden opacity-80">
                    ${groupByPackage(noFix).map(p => packageRow(p, false)).join('')}
                </div>
            </details>`;
    }

    if (hiddenCount > 0 || showAllSeverities) {
        html += `
            <div class="pt-2 text-center">
                <button id="toggle-severities" type="button"
                    class="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold text-orange-600 hover:text-orange-700 hover:bg-orange-50/60 transition-colors">
                    ${showAllSeverities ? 'Show only critical & high issues' : `Show ${hiddenCount} medium, low & unknown issues`}
                    <span class="material-symbols-outlined text-[16px]">${showAllSeverities ? 'expand_less' : 'expand_more'}</span>
                </button>
            </div>`;
    }

    // Older scans only stored CRITICAL details: warn until the project is redeployed
    if (SEVERITIES.some(s => (counts[s] || 0) > (grouped[s] || []).length)) {
        html += `<p class="text-xs text-slate-500 italic text-center mt-4">
            Some issues are only counted. Redeploy the project to get the full detailed list.</p>`;
    }

    el.innerHTML = html;

    // UX: only one package open at a time, and keep the opened one in view
    const pkgDetails = el.querySelectorAll('details[data-pkg]');
    pkgDetails.forEach(d => d.addEventListener('toggle', () => {
        if (!d.open) return;
        pkgDetails.forEach(o => { if (o !== d) o.open = false; });
        d.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }));

    document.getElementById('toggle-severities')?.addEventListener('click', () => {
        showAllSeverities = !showAllSeverities;
        renderVulnDetails(grouped, counts);
    });
}

// ---------------------------------------------------------------- //
// Secrets (Gitleaks)
// ---------------------------------------------------------------- //
function renderGitleaksResult(c) {
    const container = document.getElementById('gitleaks-section');

    if (!c.secret_count) {
        container.innerHTML = `
            <div class="bg-emerald-50/70 border border-emerald-200/60 rounded-xl p-4 flex items-center justify-between gap-4">
                <div class="flex items-center gap-3.5">
                    <div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center shrink-0 text-emerald-600">
                        <span class="material-symbols-outlined text-[18px]">check</span>
                    </div>
                    <p class="text-sm font-semibold text-emerald-950">No secrets detected in the repository history.</p>
                </div>
                <span class="text-xs font-mono text-emerald-700/80 bg-emerald-100/60 px-2.5 py-1 rounded">Clean</span>
            </div>`;
        return;
    }

    const secret = c.secret_found || {};
    const extraNote = c.secret_count > 1
        ? `<p class="text-xs text-slate-500 mt-3 italic">${c.secret_count} secrets detected in total — only the first is shown (backend limitation).</p>`
        : '';

    container.innerHTML = `
        <div class="bg-red-50/70 border border-red-200/60 rounded-xl p-4 flex flex-col md:flex-row gap-3 md:items-center justify-between">
            <div class="flex items-start gap-3.5 min-w-0">
                <div class="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center shrink-0 text-red-600">
                    <span class="material-symbols-outlined text-[18px]">key</span>
                </div>
                <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2 mb-1">
                        <span class="font-mono text-sm font-semibold text-red-950">${esc(secret.rule_id)}</span>
                        <span class="px-2 py-0.5 bg-white border border-red-200/70 rounded text-xs font-mono text-slate-600">${esc(secret.file)}</span>
                    </div>
                    <div class="text-xs text-red-800/90">${esc(secret.description)}</div>
                </div>
            </div>
            <div class="text-xs font-mono text-red-700/80 bg-red-100/60 px-2.5 py-1 rounded shrink-0 self-start md:self-center">
                Line ${esc(secret.line)}
            </div>
        </div>
        ${extraNote}`;
}