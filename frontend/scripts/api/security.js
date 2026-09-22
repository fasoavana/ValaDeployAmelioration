// scripts/api/security.js
// Appel à l'API du rapport de sécurité d'un projet

function getSecurityList() {
    return fetchWithAutoRefresh(accessToken =>
        fetch(`http://app.localhost:8080/api/security`, {
            method: "GET",
            headers: { "Authorization": "Bearer " + accessToken }
        }).then(handleResponse)
    );
}

function getSecurityReport(slug) {
    return fetchWithAutoRefresh(accessToken =>
        fetch(`http://app.localhost:8080/api/security/${slug}`, {
            method: "GET",
            headers: {
                "Authorization": "Bearer " + accessToken
            }
        }).then(handleResponse)
    );
}