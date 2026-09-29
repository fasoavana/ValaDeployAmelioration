/**
 * Fetches the news and activity feed.
 * @returns {Promise<Array>} List of news items.
 */
async function getNewsFeed() {
    // TODO: Replace with actual API call: const response = await fetch('/api/news'); return await response.json();
    
    // Mock data for demonstration
    return [
        {
            id: "notif-init-902a",
            category: "deployment",
            badge: "✨ Stack Deployment Guide",
            badgeClass: "bg-primary-fixed text-on-primary-fixed",
            statusBadge: "All Services Live",
            statusClass: "text-on-primary-container bg-primary-fixed",
            date: "Just now",
            title: "Woohoo! Your multi-service stack is live and ready 🎉",
            description: "Hi Dylan! Everything built smoothly. Your front-end, API gateway, and internal storage tunnel are provisioned and listening.",
            details: [
                { label: "Frontend App", url: "https://mytest9-front.valadeploy.app", type: "public", action: "Open App" },
                { label: "API Gateway", url: "https://api.mytest9.valadeploy.app/health", type: "ok", action: "View Endpoints" },
                { label: "Database Tunnel", url: "db.valadeploy.internal:5432", type: "pool", action: "Copy Internal Host" }
            ],
            isFeatured: true
        },
        {
            id: "notif-8f2910c",
            category: "deployment",
            badge: "Deployment Notice",
            badgeClass: "bg-tertiary-fixed text-on-tertiary-fixed",
            statusBadge: "3/3 Health Checks Passed",
            statusClass: "text-on-surface-variant bg-surface-container",
            date: "Today at 14:32",
            title: "Deployment completed: auth-service v1.4.0",
            description: "Your container deployment has settled. Access your microservice documentation.",
            details: [
                { label: "Target", value: "auth-service" },
                { label: "Env", value: "production" },
                { label: "Endpoint", value: "auth.valadeploy.app" }
            ],
            isFeatured: false
        },
        {
            id: "notif-sec-418b",
            category: "security",
            badge: "Security Alert",
            badgeClass: "bg-primary-fixed text-on-primary-fixed",
            statusBadge: "Auto-Secured",
            statusClass: "text-on-surface-variant bg-surface-container",
            date: "Yesterday at 09:15",
            title: "Quick Security recommendation for your cluster",
            description: "We noticed port 8080 exposed without TLS encryption on test-service. We automatically provisioned a free Let's Encrypt SSL certificate for you.",
            details: [
                { label: "Rule", value: "TLS-AUTO-V3" },
                { label: "Certificate", value: "Let's Encrypt Wildcard" },
                { label: "Port", value: "8080 → 443" }
            ],
            isFeatured: false
        },
        {
            id: "notif-rel-993d",
            category: "announcement",
            badge: "Release Note",
            badgeClass: "bg-surface-container-highest text-on-surface",
            statusBadge: "v2.4.0 Available",
            statusClass: "text-primary-container bg-primary-fixed",
            date: "Sep 08, 2026",
            title: "What's new in ValaDeploy v2.4: Instant Rollbacks & Traefik v3",
            description: "Zero-downtime rollbacks are now one click away directly from the Pipeline tab. We also upgraded Traefik reverse proxies.",
            details: [
                { label: "Version", value: "v2.4.0-stable" },
                { label: "Components", value: "Traefik v3, OTel Core" },
                { label: "Rollout", value: "Global" }
            ],
            isFeatured: false
        }
    ];
}

async function markNewsAsRead(newsId) {
    // TODO: API call to mark as read
    console.log(`Marked ${newsId} as read`);
}

async function markAllNewsAsRead() {
    // TODO: API call to mark all as read
    console.log("Marked all as read");
}