document.addEventListener('DOMContentLoaded', function() {

    const INTERVAL_DURATION_MS = 5000; // 5 seconds for GREEN/RED cycle

    const modeText = document.getElementById('mode');
    const gameOverMessage = document.getElementById('game-over-message');
    const restartButton = document.getElementById('restart-button');
    const penaltyText = document.getElementById('penalty-text');
    const idleButton = document.getElementById('idle-button');
    const body = document.body;

    let localTimer = null;

    // --- API Functions ---

    const setServerMode = async (mode) => {
        try {
            await fetch('/api/setmode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: mode }),
            });
        } catch (error) {
            console.error(`Failed to set mode to ${mode}:`, error);
        }
    };

    const restartGame = async () => {
        try {
            // This just tells the server to go into GREEN mode.
            // The polling logic will then pick it up and start the timer.
            await fetch('/api/start', { method: 'POST' });
        } catch (error) {
            console.error('Failed to restart game:', error);
        }
    };

    // --- Timer Logic ---

    function startIntervalTimer(currentMode) {
        if (localTimer) return; // Timer is already running

        let mode = currentMode;
        
        localTimer = setInterval(() => {
            // This client takes responsibility for toggling the state
            mode = mode === 'GREEN' ? 'RED' : 'GREEN';
            setServerMode(mode);
        }, INTERVAL_DURATION_MS);
    }

    function stopIntervalTimer() {
        if (localTimer) {
            clearInterval(localTimer);
            localTimer = null;
        }
    }

    // --- UI Update Logic ---

    const updateStateFromServer = async () => {
        try {
            const response = await fetch('/api/gamestate');
            if (!response.ok) throw new Error('Network response was not ok');
            
            const serverState = await response.json();

            modeText.textContent = serverState.mode;
            body.classList.remove('green-bg', 'red-bg', 'game-over-bg', 'idle-bg');

            switch (serverState.mode) {
                case 'GREEN':
                case 'RED':
                    body.classList.add(serverState.mode === 'GREEN' ? 'green-bg' : 'red-bg');
                    gameOverMessage.classList.add('hidden');
                    startIntervalTimer(serverState.mode); // Start the timer if game is active
                    break;
                case 'GAME_OVER':
                    body.classList.add('game-over-bg');
                    gameOverMessage.classList.remove('hidden');
                    stopIntervalTimer();
                    break;
                default: // IDLE
                    body.classList.add('idle-bg');
                    gameOverMessage.classList.add('hidden');
                    stopIntervalTimer();
                    break;
            }

            // Handle penalty flash
            if (serverState.penalty_flash) {
                body.classList.add('penalty-flash');
                penaltyText.classList.add('show');

                setTimeout(() => {
                    body.classList.remove('penalty-flash');
                    penaltyText.classList.remove('show');
                }, 1000);
            }

        } catch (error) {
            console.error('Failed to fetch game state:', error);
            modeText.textContent = '接続エラー';
        }
    };

    // --- Event Listeners ---
    restartButton.addEventListener('click', restartGame);
    idleButton.addEventListener('click', () => {
        stopIntervalTimer();
        setServerMode('IDLE');
    });

    // --- Initial Setup ---
    setInterval(updateStateFromServer, 500); 
    updateStateFromServer();
});
