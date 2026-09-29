document.addEventListener('DOMContentLoaded', () => {
    let allNews = [];
    let currentFilter = 'all';

    // Initialize
    loadNewsFeed();
    setupEventListeners();

    async function loadNewsFeed() {
        const container = document.getElementById('news-feed-container');
        const loading = document.getElementById('news-loading');
        
        try {
            allNews = await getNewsFeed();
            loading.style.display = 'none';
            updateFilterCounts();
            renderFeed();
        } catch (error) {
            console.error('Error loading news:', error);
            loading.innerHTML = `
                <div class="py-lg text-center text-on-surface-variant">
                    <span class="material-symbols-outlined text-4xl block mb-sm text-error">error</span>
                    Unable to load updates at the moment.
                </div>
            `;
        }
    }

    function updateFilterCounts() {
        const counts = { all: allNews.length, deployment: 0, security: 0, announcement: 0 };
        allNews.forEach(item => {
            if (counts[item.category] !== undefined) counts[item.category]++;
        });

        document.querySelectorAll('.filter-pill').forEach(btn => {
            const filter = btn.getAttribute('data-filter');
            const countSpan = btn.querySelector('span');
            if (countSpan) countSpan.textContent = `(${counts[filter]})`;
        });
    }

    function renderFeed() {
        const container = document.getElementById('news-feed-container');
        // Keep the loading div hidden, clear the rest
        const loading = document.getElementById('news-loading');
        container.innerHTML = '';
        container.appendChild(loading);

        const filteredNews = currentFilter === 'all' 
            ? allNews 
            : allNews.filter(item => item.category === currentFilter);

        if (filteredNews.length === 0) {
            container.innerHTML += `
                <div class="py-xl text-center text-secondary">
                    <span class="material-symbols-outlined text-4xl block mb-sm">inbox</span>
                    <p>No updates match this filter.</p>
                </div>
            `;
            return;
        }

        filteredNews.forEach(item => {
            container.appendChild(createNewsCard(item));
        });
    }

    function createNewsCard(item) {
        const article = document.createElement('article');
        // NOTE: 'border-l-4 border-primary-container' a été supprimé ici comme demandé
        article.className = `feed-item relative overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm hover:shadow-md transition-shadow p-lg md:p-xl flex flex-col gap-md ${item.isFeatured ? 'bg-surface-container-low/50' : ''}`;
        article.dataset.category = item.category;
        article.dataset.id = item.id;

        let detailsHtml = '';
        if (item.isFeatured && item.details) {
            detailsHtml = `<div class="grid grid-cols-1 md:grid-cols-3 gap-md relative my-xs">
                ${item.details.map((detail, index) => `
                    <div class="p-md rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors flex flex-col justify-between gap-md">
                        <div class="flex flex-col gap-xs">
                            <div class="flex items-center justify-between">
                                <span class="font-label-sm text-label-sm text-secondary uppercase font-semibold">${detail.label}</span>
                                <span class="inline-flex items-center gap-1 text-[11px] font-mono-code ${detail.type === 'public' ? 'text-on-surface-variant bg-surface-container-highest' : detail.type === 'ok' ? 'text-on-primary-container bg-primary-fixed' : 'text-on-tertiary-container bg-tertiary-fixed'} px-xs py-0.5 rounded-full">
                                    <span class="w-1.5 h-1.5 rounded-full ${detail.type === 'public' ? 'bg-tertiary-container' : detail.type === 'ok' ? 'bg-primary-container' : 'bg-tertiary'}"></span>
                                    ${detail.type === 'public' ? 'Public' : detail.type === 'ok' ? '200 OK' : 'Pool Active'}
                                </span>
                            </div>
                            <div class="font-mono-code text-mono-code text-on-surface break-all font-medium text-[13px]">${detail.url}</div>
                        </div>
                        <div class="flex items-center gap-xs">
                            ${detail.action.includes('Copy') 
                                ? `<button class="w-full inline-flex items-center justify-center gap-1 px-sm py-xs rounded-lg bg-surface-container-high hover:bg-surface-dim text-on-surface font-label-sm text-label-sm transition-colors" onclick="copyToClipboard('${detail.url}', this)"><span class="material-symbols-outlined text-[16px]">key</span><span class="">${detail.action}</span></button>`
                                : `<a class="flex-1 inline-flex items-center justify-center gap-1 px-sm py-xs rounded-lg ${detail.type === 'ok' ? 'bg-surface-container-high hover:bg-surface-dim' : 'bg-primary-container text-on-primary hover:opacity-95'} font-label-sm text-label-sm transition-colors" href="${detail.url}" target="_blank"><span class="">${detail.action}</span><span class="material-symbols-outlined text-[16px]">${detail.type === 'ok' ? 'arrow_forward' : 'open_in_new'}</span></a>
                                   <button class="inline-flex items-center justify-center p-xs rounded-lg bg-surface-container-high hover:bg-surface-dim text-on-surface transition-colors" onclick="copyToClipboard('${detail.url}', this)" title="Copy"><span class="material-symbols-outlined text-[18px]">content_copy</span></button>`
                            }
                        </div>
                    </div>
                `).join('')}
            </div>`;
        } else if (!item.isFeatured && item.details) {
            detailsHtml = `<div class="p-sm rounded-lg bg-surface-container-low flex flex-wrap items-center justify-between gap-sm">
                <div class="flex flex-wrap items-center gap-md">
                    ${item.details.map(d => `
                        <div class="flex items-center gap-xs font-mono-code text-[12px]">
                            <span class="text-secondary">${d.label}:</span>
                            <span class="text-on-surface font-medium">${d.value}</span>
                        </div>
                    `).join('')}
                </div>
                <button class="inline-flex items-center gap-xs text-[12px] font-mono-code text-secondary hover:text-on-surface transition-colors" onclick="copyToClipboard('${item.details[0].value}', this)">
                    <span class="material-symbols-outlined text-[15px]">content_copy</span>
                    <span class="">Copy ${item.details[0].label}</span>
                </button>
            </div>`;
        }

        article.innerHTML = `
            ${item.isFeatured ? '<div class="absolute -right-16 -top-16 w-64 h-64 rounded-full bg-gradient-to-br from-primary-fixed/30 via-primary-container/10 to-transparent pointer-events-none"></div>' : ''}
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-xs relative">
                <div class="flex flex-wrap items-center gap-sm">
                    <span class="px-sm py-0.5 rounded-full ${item.badgeClass} font-label-sm text-[11px] font-semibold tracking-wide inline-flex items-center gap-xs">
                        ${item.category === 'deployment' && item.isFeatured ? '<span class="w-2 h-2 rounded-full bg-primary-container animate-ping"></span>' : ''}
                        ${item.badge}
                    </span>
                    <span class="font-mono-code text-mono-code text-secondary text-[12px]">${item.date}</span>
                </div>
                <div class="flex items-center gap-sm">
                    <span class="inline-flex items-center gap-1 font-mono-code text-[11px] ${item.statusClass} px-xs py-0.5 rounded-full font-medium">
                        ${item.category === 'security' ? '<span class="material-symbols-outlined text-[13px]">shield</span>' : '<span class="w-1.5 h-1.5 rounded-full bg-current"></span>'}
                        ${item.statusBadge}
                    </span>
                    <span class="font-mono-code text-[11px] text-secondary">ID: ${item.id}</span>
                </div>
            </div>
            <div class="flex flex-col gap-xs relative">
                <h3 class="font-headline-md text-headline-md text-on-surface tracking-tight">${item.title}</h3>
                <p class="font-body-md text-body-md text-on-surface-variant max-w-3xl">${item.description}</p>
            </div>
            ${detailsHtml}
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-md pt-xs relative">
                <div class="flex flex-wrap items-center gap-sm">
                    <button class="inline-flex items-center gap-xs px-md py-xs rounded-lg bg-primary-container hover:opacity-95 text-on-primary font-label-sm text-label-sm transition-opacity shadow-sm" onclick="handlePrimaryAction('${item.id}')">
                        <span class="">${item.isFeatured ? 'Open Stack' : item.category === 'security' ? 'Check SSL Certificate' : 'Read Guide'}</span>
                        <span class="material-symbols-outlined text-[16px]">${item.isFeatured ? 'open_in_new' : 'arrow_right_alt'}</span>
                    </button>
                    ${!item.isFeatured ? `<button class="inline-flex items-center gap-xs px-md py-xs rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md transition-colors" onclick="handleSecondaryAction('${item.id}')"><span class="material-symbols-outlined text-[16px]">${item.category === 'security' ? 'shield' : 'history'}</span><span class="">${item.category === 'security' ? 'Security Dashboard' : 'Changelog'}</span></button>` : ''}
                </div>
                <div class="flex items-center gap-md">
                    ${item.isFeatured ? `<button class="font-label-md text-label-md text-secondary hover:text-on-surface transition-colors inline-flex items-center gap-xs" onclick="dismissCard('${item.id}')"><span class="material-symbols-outlined text-[16px]">visibility_off</span><span class="">Dismiss guide</span></button>` : ''}
                    <button class="font-label-md text-label-md text-secondary hover:text-on-surface transition-colors inline-flex items-center gap-xs" onclick="markAsRead('${item.id}', this)">
                        <span class="material-symbols-outlined text-[16px]">mark_email_read</span>
                        <span class="">Mark as read</span>
                    </button>
                </div>
            </div>
        `;

        return article;
    }

    function setupEventListeners() {
        // Filter pills
        document.querySelectorAll('.filter-pill').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.filter-pill').forEach(b => {
                    b.classList.remove('bg-on-surface', 'text-surface-container-lowest', 'active-pill');
                    b.classList.add('bg-surface-container-low', 'text-secondary');
                });
                btn.classList.add('bg-on-surface', 'text-surface-container-lowest', 'active-pill');
                btn.classList.remove('bg-surface-container-low', 'text-secondary');

                currentFilter = btn.getAttribute('data-filter');
                renderFeed();
            });
        });

        // Mark all as read
        document.getElementById('mark-all-read-btn').addEventListener('click', async () => {
            await markAllNewsAsRead();
            const btn = document.getElementById('mark-all-read-btn');
            btn.innerHTML = '<span class="material-symbols-outlined text-[18px]">check</span><span>Done</span>';
            btn.classList.add('opacity-70', 'cursor-default');
            
            document.querySelectorAll('.feed-item').forEach(item => {
                item.classList.add('opacity-70');
            });
            
            if (typeof ValaToast !== 'undefined') {
                ValaToast.show({ type: 'success', title: 'Success', message: 'All updates marked as read.', duration: 3000 });
            }
        });
    }

    // Global functions for inline onclick handlers
    window.copyToClipboard = function(text, btnElement) {
        navigator.clipboard.writeText(text).then(() => {
            const originalHTML = btnElement.innerHTML;
            btnElement.innerHTML = '<span class="material-symbols-outlined text-[18px] text-tertiary">check</span><span class="">Copied!</span>';
            if (typeof ValaToast !== 'undefined') {
                ValaToast.show({ type: 'success', title: 'Copied', message: 'Content copied to clipboard.', duration: 2000 });
            }
            setTimeout(() => {
                btnElement.innerHTML = originalHTML;
            }, 1800);
        });
    };

    window.dismissCard = function(id) {
        const card = document.querySelector(`.feed-item[data-id="${id}"]`);
        if (card) {
            card.classList.add('dismissed');
            setTimeout(() => {
                card.style.display = 'none';
            }, 200);
        }
    };

    window.markAsRead = async function(id, btnElement) {
        await markNewsAsRead(id);
        const card = document.querySelector(`.feed-item[data-id="${id}"]`);
        if (card) {
            card.classList.add('opacity-70');
        }
        btnElement.innerHTML = '<span class="material-symbols-outlined text-[16px]">check</span><span class="">Read</span>';
        btnElement.classList.add('text-tertiary', 'cursor-default');
        btnElement.onclick = null;
    };

    window.handlePrimaryAction = function(id) {
        // Placeholder for primary action logic
        console.log('Primary action for', id);
    };

    window.handleSecondaryAction = function(id) {
        // Placeholder for secondary action logic
        console.log('Secondary action for', id);
    };
});