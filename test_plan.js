        async function submitToolkitHomebrewRetryFromPacket(jobId) {
            renderHomebrewUploadStatus('info', 'Starting build from normalized packet...');
            try {
                const response = await fetch(`/api/toolkit/homebrew/jobs/${jobId}/retry-from-packet`, {
                    method: 'POST'
                });
                const payload = await response.json();
                if (!response.ok || payload.status !== 'success') {
                    renderHomebrewUploadStatus('error', 'Retry from packet failed.', JSON.stringify(payload, null, 2));
                    return;
                }
                renderHomebrewUploadStatus('success', 'Retry from packet started successfully.', JSON.stringify(payload.job, null, 2));
                await pollToolkitHomebrewJob(jobId);
            } catch (err) {
                renderHomebrewUploadStatus('error', `Retry request failed: ${err.message}`);
            }
        }
