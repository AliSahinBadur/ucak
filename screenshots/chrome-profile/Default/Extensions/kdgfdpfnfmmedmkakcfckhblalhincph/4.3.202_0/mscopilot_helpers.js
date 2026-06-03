(function () {
    const TRUSTED_ORIGINS = ['https://m365.cloud.microsoft', 'https://copilot.microsoft.com'];
    const origin = window.location.origin;

    if (!TRUSTED_ORIGINS.includes(origin)) return;

    const originalSend = WebSocket.prototype.send;
    const recordSeparator = '\x1E';
    const targetSubstring = '"event":"send","conversationId"';

    WebSocket.prototype.send = function (data) {
        originalSend.call(this, data);

        if (typeof data !== 'string') return;
        const hasRecordSeparator = data.includes(recordSeparator);
        const hasTargetSubstring = data.includes(targetSubstring);

        if (!hasRecordSeparator && !hasTargetSubstring) return;

        if (hasRecordSeparator) {
            const substrings = data.split(recordSeparator);

            for (const str of substrings) {
                try {
                    const message = JSON.parse(str);
                    if (!message || typeof message !== 'object') continue;

                    const prompt = message.arguments?.[0]?.message;

                    if (message.target === 'chat' && prompt) {
                        window.postMessage({ type: 'DX_MS_COPILOT_PROMPT', payload: { prompt, accountType: 'work' } }, origin);
                        return;
                    }
                } catch (e) {
                    // Intentionally empty - most fragments aren't valid JSON
                }
            }
        } else if (hasTargetSubstring) {
            try {
                const message = JSON.parse(data);
                if (!message || typeof message !== 'object' || !Array.isArray(message.content) || message.content.length === 0) return;

                const hasValidMessage = message.content.some(msg => msg.type === 'text');
                if (!hasValidMessage) return;

                window.postMessage({ type: 'DX_MS_COPILOT_PROMPT', payload: { prompt: message.content, accountType: 'personal' } }, origin);
            } catch (e) {
                // Intentionally empty - most fragments aren't valid JSON
            }
        }
    };
})();
