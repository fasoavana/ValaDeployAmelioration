// scripts/api/stack.js
// API pour les déploiements de Stacks multi-composants

function createStack(stackData) {
    // stackData = { slug: string, components: Array<{name, kind, repo_url, branch, port, expose_publicly, envs_var, db_image, volume_name}> }
    return fetchWithAutoRefresh(function(token) {
        return fetch('http://app.localhost:8080/api/deploy/stack', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + token
            },
            body: JSON.stringify(stackData)
        })
        .then(handleResponse);
    });
}

// Suppression d'une stack (et de ses composants).
// NOTE: URL supposée en cohérence avec createStack ci-dessus
// ('/api/deploy/stack/{project_id}'). A ajuster si le backend expose
// une route différente (ex: par slug, ou /api/project/{id}).
function deleteStack(projectId) {
    return fetchWithAutoRefresh(function(token) {
        return fetch('http://app.localhost:8080/api/deploy/stack/' + projectId, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + token
            }
        })
        .then(handleResponse);
    });
}

// Note: getStacks() et getStackDetail(projectId) sont déjà dans project.js,
// donc pas besoin de les doubler ici.