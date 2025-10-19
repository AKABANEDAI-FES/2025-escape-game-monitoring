document.addEventListener('DOMContentLoaded', function() {

    const statusText = document.getElementById('status-text');
    const timerText = document.getElementById('timer-text');
    const gameOverMessage = document.getElementById('game-over-message');
    const body = document.body;

    const updateState = async () => {
        try {
            const response = await fetch('/api/gamestate');
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            const state = await response.json();

            // Update text content
            statusText.textContent = state.status;
            timerText.textContent = state.timer;

            // Update background color and game over message
            body.classList.remove('green-bg', 'red-bg', 'game-over-bg');
            gameOverMessage.classList.add('hidden');

            if (state.status === 'GREEN') {
                body.classList.add('green-bg');
            } else if (state.status === 'RED') {
                body.classList.add('red-bg');
            } else if (state.status === 'GAME_OVER') {
                body.classList.add('game-over-bg');
                gameOverMessage.classList.remove('hidden');
            }

        } catch (error) {
            console.error('Failed to fetch game state:', error);
            statusText.textContent = '接続エラー';
        }
    };

    // Update state every 500ms
    setInterval(updateState, 500);
});
