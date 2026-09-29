// scripts/api/pipeline.js

function getPipelineStatus(projectId) {
    return fetchWithAutoRefresh(function(token) {
        // Timestamp unique pour empêcher le cache du navigateur
        const timestamp = new Date().getTime();
        
        return fetch('http://app.localhost:8080/api/deploy/' + projectId + '/pipeline?t=' + timestamp, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + token,
                // En-têtes HTTP pour forcer le non-cache
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        }).then(handleResponse);
    });
}

function cancelBuild(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch('http://app.localhost:8080/api/deploy/' + projectId + '/cancel', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        }).then(handleResponse);
    });
}

function retryBuild(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch('http://app.localhost:8080/api/deploy/' + projectId + '/retry', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        }).then(handleResponse);
    });
}