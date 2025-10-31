document.addEventListener('DOMContentLoaded', function() {

    const INTERVAL_DURATION_MS = 5000;

    const modeText = document.getElementById('mode');
    const gameOverMessage = document.getElementById('game-over-message');
    const restartButton = document.getElementById('restart-button');
    const penaltyText = document.getElementById('penalty-text');
    const body = document.body;

    let localTimer = null;
    let lastMode = null;
    let audioContextUnlocked = false; // 🔒 音声許可フラグ

    // --- 音声再生 ---
    const audio = new Audio('/static/sounds/attention.mp3');

    function playAttentionSound() {
        if (!audioContextUnlocked) {
            console.warn('ユーザー操作前のため音声を再生できません');
            return;
        }
        audio.currentTime = 0;
        audio.play().catch(err => console.warn('音声再生エラー:', err));
        setTimeout(() => {
            audio.pause();
            audio.currentTime = 0;
        }, 4000);
    }

    // --- 初回クリックで音声再生を許可 ---
    document.addEventListener('click', () => {
        if (!audioContextUnlocked) {
            audio.play().then(() => {
                audio.pause();
                audio.currentTime = 0;
                audioContextUnlocked = true; // ✅ 許可完了
                console.log('音声再生が許可されました');
            }).catch(err => console.warn('音声初期化エラー:', err));
        }
    });

    // --- 以下は既存のゲームロジック ---
    const setServerMode = async (mode) => {
        try {
            await fetch('/api/setmode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode }),
            });
        } catch (error) {
            console.error(`Failed to set mode to ${mode}:`, error);
        }
    };

    const restartGame = async () => {
        try {
            await fetch('/api/start', { method: 'POST' });
        } catch (error) {
            console.error('Failed to restart game:', error);
        }
    };

    function startIntervalTimer(currentMode) {
        if (localTimer) return;
        let mode = currentMode;
        localTimer = setInterval(() => {
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
                    startIntervalTimer(serverState.mode);

                    if (serverState.mode === 'RED' && lastMode !== 'RED') {
                        playAttentionSound();
                    }
                    break;

                case 'GAME_OVER':
                    body.classList.add('game-over-bg');
                    gameOverMessage.classList.remove('hidden');
                    stopIntervalTimer();
                    break;

                default:
                    body.classList.add('idle-bg');
                    gameOverMessage.classList.add('hidden');
                    stopIntervalTimer();
                    break;
            }

            if (serverState.penalty_flash) {
                body.classList.add('penalty-flash');
                penaltyText.classList.add('show');

                setTimeout(() => {
                    body.classList.remove('penalty-flash');
                    penaltyText.classList.remove('show');
                }, 1000);
            }

            lastMode = serverState.mode;

        } catch (error) {
            console.error('Failed to fetch game state:', error);
            modeText.textContent = '接続エラー';
        }
    };

    restartButton.addEventListener('click', restartGame);
    setInterval(updateStateFromServer, 500);
    updateStateFromServer();
});
