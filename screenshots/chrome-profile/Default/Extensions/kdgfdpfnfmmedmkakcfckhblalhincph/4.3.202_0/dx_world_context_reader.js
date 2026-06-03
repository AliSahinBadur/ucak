function handler(event) {
    if (event.source !== window) return;
    if (event.origin !== 'https://chatgpt.com') return;

    const { data } = event;

    if (!data || data.type !== 'DX_GET_WORLD_CONTEXT_DATA') return;

    if (data.message === 'FETCH_CHATGPT_TRAINING_STATUS') {
        const plan = window.__STATSIG__?.firstInstance?._user?.custom?.plan_type;

        if (plan === undefined) {
            window.postMessage(
                {
                    type: 'DX_GET_WORLD_CONTEXT_DATA_RESPONSE',
                    message: 'FETCH_CHATGPT_TRAINING_STATUS_RESPONSE',
                    payload: { error: true },
                },
                event.origin
            );
        } else if (plan === 'team') {
            window.postMessage(
                {
                    type: 'DX_GET_WORLD_CONTEXT_DATA_RESPONSE',
                    message: 'FETCH_CHATGPT_TRAINING_STATUS_RESPONSE',
                    payload: { trainingEnabled: false },
                },
                event.origin
            );
        } else {
            let path = '/backend-api/settings/user';

            const headers = new Headers();
            headers.append('Authorization', data.payload.bearer);
            headers.append('Content-Type', 'application/json');

            fetch(path, {
                method: 'GET',
                signal: AbortSignal.timeout(5000),
                headers,
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(trainingStatus => {
                    window.postMessage(
                        {
                            type: 'DX_GET_WORLD_CONTEXT_DATA_RESPONSE',
                            message: 'FETCH_CHATGPT_TRAINING_STATUS_RESPONSE',
                            payload: { trainingEnabled: trainingStatus.settings?.training_allowed },
                        },
                        event.origin
                    );
                })
                .catch(error => {
                    window.postMessage(
                        {
                            type: 'DX_GET_WORLD_CONTEXT_DATA_RESPONSE',
                            message: 'FETCH_CHATGPT_TRAINING_STATUS_RESPONSE',
                            payload: { error: true },
                        },
                        event.origin
                    );
                    console.error('Error fetching training status data:', error);
                });
        }
    }
}

window.addEventListener('message', handler);
