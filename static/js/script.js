document.addEventListener('DOMContentLoaded', function() {

    const statusText = document.getElementById('status-text');
    const totalTimeText = document.getElementById('total-time-text');
    const intervalTimerText = document.getElementById('interval-timer-text');
    const gameOverMessage = document.getElementById('game-over-message');
    const gameOverText = gameOverMessage.querySelector('p'); // The paragraph inside the message div
    const restartButton = document.getElementById('restart-button');
    const body = document.body;

    // Restart button logic
    restartButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/restart', { method: 'POST' });
            if (!response.ok) {
                throw new Error('Failed to restart the game');
            }
            // Hide the game over message and let the regular polling update the UI
            gameOverMessage.classList.add('hidden');
        } catch (error) {
            console.error('Restart failed:', error);
        }
    });

    const updateState = async () => {
        try {
            const response = await fetch('/api/gamestate');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const state = await response.json();

            // Update text content
            statusText.textContent = state.mode;
            totalTimeText.textContent = state.total_time;
            intervalTimerText.textContent = state.interval_timer;

            // Update background color and game over message
            body.classList.remove('green-bg', 'red-bg', 'game-over-bg');
            gameOverMessage.classList.add('hidden');

            if (state.mode === 'GREEN') {
                body.classList.add('green-bg');
            } else if (state.mode === 'RED') {
                body.classList.add('red-bg');
            } else if (state.mode === 'GAME_OVER') {
                body.classList.add('game-over-bg');
                gameOverText.textContent = `最終スコア: ${state.total_time}秒`; // Update with final score
                gameOverMessage.classList.remove('hidden');
            }

            // Handle penalty flash
            if (state.penalty_flash) {
                body.classList.add('penalty-flash');
                // Remove the class after the animation completes
                setTimeout(() => {
                    body.classList.remove('penalty-flash');
                }, 500); // Corresponds to animation duration
            }

        } catch (error) {
            console.error('Failed to fetch game state:', error);
            statusText.textContent = '接続エラー';
        }
    };

    // Update state every 500ms
    setInterval(updateState, 500);
});
