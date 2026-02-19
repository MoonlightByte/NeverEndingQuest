# Exit/Enter GUI Button Implementation Plan

## Overview

This document outlines a two-phase implementation for adding Exit/Enter functionality to the NeverEndingQuest web interface. The goal is to allow users to stop and start the game server from the GUI without requiring terminal interaction.

**Core Design Principles:**
- No Python watcher processes ( Phase 1 )
- Graceful shutdown of all Python processes
- No arbitrary script execution from browser (security hardening)
- Clean UX with no duplicate browser windows or narration

---

## Phase 1: Exit Only (Recommended - Immediate Implementation)

### Objective
Enable GUI button to gracefully stop ALL Python processes (web server + game loop) from the browser, returning the terminal to a clean state without requiring Ctrl+C.

### User Experience
1. User clicks "Exit" button in pinned browser tab
2. Server acknowledges exit gracefully
3. All Python processes stop cleanly
4. Terminal shows "Shutting down NeverEndingQuest Web Interface..."
5. User must manually restart with `python run_web.py` when ready

### Technical Implementation

#### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│ Browser Tab (Pinned)                                       │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Exit Button (GUI)                                   │  │
│  │  - Click triggers user_exit socket event            │  │
│  │  - Waits for exit_acknowledged                     │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ socket.emit('user_exit')
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ web/web_interface.py (Flask-SocketIO Server)               │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ handle_user_exit()                                 │  │
│  │  1. Emit exit_acknowledged to client              │  │
│  │  2. Signal game loop to quit (queue marker)       │  │
│  │  3. Stop SocketIO server                          │  │
│  │  4. Exit process with code 91                     │  │
│  └─────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ os._exit(91)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│ run_web.py (Launcher)                                     │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Main loop                                           │  │
│  │  - Detects exit code 91                            │  │
│  │  - Prints shutdown message                         │  │
│  │  - Does NOT restart (breaks loop)                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

#### File Changes

**1. web/web_interface.py**

Add graceful shutdown handler:

```python
# Near handle_user_exit() around line 2656
@socketio.on('user_exit')
def handle_user_exit():
    """Handle intentional user exit - graceful shutdown of all processes"""
    try:
        print("INFO: User has initiated exit from the game")
        emit('exit_acknowledged', {'message': 'Exit acknowledged'})
        
        # Phase 1: Graceful full shutdown
        # Step 1: Signal game loop to stop (if running)
        _signal_game_loop_shutdown()
        
        # Step 2: Give a moment for cleanup
        import time
        time.sleep(0.5)
        
        # Step 3: Stop SocketIO server
        socketio.stop()
        
        # Step 4: Exit with dedicated code so launcher knows this was intentional
        print("INFO: Server shutdown complete. Exiting process.")
        os._exit(91)  # 91 = intentional user shutdown
        
    except Exception as e:
        print(f"ERROR handling user exit: {e}")
        # Force exit even on error
        os._exit(91)

def _signal_game_loop_shutdown():
    """Signal the game loop to quit gracefully"""
    global game_thread
    # If game thread is running, we can't directly stop it
    # but the socket disconnect will cause WebInput to return
    # The game loop will exit on next input attempt
    pass
```

**2. run_web.py**

Handle exit code 91 as intentional shutdown:

```python
# Around line 108-127 in main()
while True:
    try:
        result = subprocess.run([sys.executable, "web/web_interface.py"])
        
        # Check exit codes
        if result.returncode == 0:
            # Restart (used by restore/reset actions)
            print("\n[RESTART] Server shutdown detected. Restarting in 2 seconds...")
            time.sleep(2)
            continue
        elif result.returncode == 91:
            # Phase 1: Intentional user shutdown - DO NOT RESTART
            print("\nShutting down NeverEndingQuest Web Interface...")
            break
        else:
            # Error or unexpected exit
            print(f"\n[ERROR] Server exited with code {result.returncode}")
            break
            
    except KeyboardInterrupt:
        print("\nShutting down NeverEndingQuest Web Interface...")
        break
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
```

**3. web/templates/game_interface.html**

Update exit button to wait for acknowledgment:

```javascript
// Around line 8465-8507
function exitGame() {
    const confirmExit = confirm('Are you sure you want to exit the game?');
    
    if (confirmExit) {
        if (connected) {
            // Emit exit event and wait for acknowledgment
            socket.emit('user_exit');
            
            // Show waiting message
            const exitMessage = document.createElement('div');
            exitMessage.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background-color: #2c2c2c;
                border: 2px solid #8B0000;
                padding: 30px;
                border-radius: 10px;
                text-align: center;
                z-index: 10000;
            `;
            exitMessage.innerHTML = `
                <h2 style="color: #FFA500;">Shutting Down...</h2>
                <p>Server is stopping. Please wait.</p>
            `;
            document.body.appendChild(exitMessage);
            
            // Disable input
            document.getElementById('user-input').disabled = true;
            document.getElementById('send-button').disabled = true;
        }
    }
}

// Handle the acknowledgment
socket.on('exit_acknowledged', function(data) {
    console.log('Exit acknowledged:', data.message);
    // Server will stop - no further action needed from client
});
```

#### Verification Checklist
- [ ] Click Exit in GUI
- [ ] Confirmation dialog appears
- [ ] After confirmation, server stops gracefully
- [ ] Terminal shows "Shutting down NeverEndingQuest Web Interface..."
- [ ] No Python processes remain running
- [ ] Manual restart with `python run_web.py` works correctly

#### Key Behaviors Preserved
- Reset action (`os._exit(0)`) still triggers restart
- Restore action (`os._exit(0)`) still triggers restart
- Ctrl+C in terminal still works
- Multiple connected clients handled correctly

---

## Phase 2: Full Exit/Enter Toggle (Future Implementation)

### Objective
Enable true Exit/Enter toggle where user can restart the server from the GUI after clicking Exit, without manual terminal interaction.

### User Experience
1. User clicks "Exit" in pinned tab
2. All Python processes stop gracefully
3. Button changes to "Enter"
4. User clicks "Enter"
5. Server restarts, tab reconnects automatically

### Technical Architecture

**Core Constraint:** Without a watcher process, the browser cannot start a dead Python server. Phase 2 requires a minimal always-on controller.

#### Option A: Persistent Launcher with Control API (Recommended)

```
┌─────────────────────────────────────────────────────────────┐
│ run_web.py (Persistent Supervisor - Always Running)        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Flask Control API (localhost only)                  │  │
│  │  GET  /control/status   -> {running: bool}         │  │
│  │  POST /control/start   -> starts child process     │  │
│  │  POST /control/stop    -> stops child gracefully   │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────┐  │
│  │ Child Process Manager                               │  │
│  │  - Popen for web_interface.py                      │  │
│  │  - Watchdog thread for health monitoring           │  │
│  │  - Graceful restart on child exit                  │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         │                                 │
    ┌────▼────┐                     ┌────▼────┐
    │ Running │                     │ Stopped │
    └────┬────┘                     └────┬────┘
         │                                │
         │  POST /control/stop            │  POST /control/start
         ▼                                ▼
    ┌────┐                          ┌────┐
    │Stop│                          │Start│
    └────┘                          └────┘
```

#### Option B: Native OS Helper (More Complex)

- macOS: LaunchAgent (plist in ~/Library/LaunchAgents/)
- Windows: Task Scheduler or small native helper app
- Pros: System-level reliability
- Cons: Cross-platform complexity, installation required

#### Implementation Steps (Phase 2)

**1. run_web.py - Persistent Supervisor Mode**

```python
# New: Supervisor mode keeps running even when child exits
class ServerSupervisor:
    def __init__(self):
        self.process = None
        self.control_port = 12580  # Dedicated localhost port
    
    def start_child(self):
        """Start web_interface.py as child process"""
        self.process = subprocess.Popen(
            [sys.executable, "web/web_interface.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    
    def stop_child(self):
        """Gracefully stop child process"""
        if self.process:
            # Send termination request via socket first
            # Then monitor and kill if needed
            self.process.terminate()
            self.process.wait(timeout=5)
    
    def run_control_api(self):
        """Run Flask control API on separate thread"""
        # Minimal Flask app for /control/* endpoints
        pass
```

**2. Security Hardening**

```python
# Control API must be secured
@app.route('/control/start', methods=['POST'])
def control_start():
    # Security checks
    if request.remote_addr != '127.0.0.1':
        return 'Forbidden', 403
    
    # CSRF protection
    if request.headers.get('X-CSRF-Token') != get_csrf_token():
        return 'Invalid token', 403
    
    # Fixed command only (no arbitrary execution)
    supervisor.start_child()
    return {'status': 'started'}
```

**3. GUI Updates**

```javascript
// Toggle button state
let serverRunning = true;

function exitGame() {
    if (serverRunning) {
        // Stop server
        fetch('/control/stop', {method: 'POST', 
            headers: {'X-CSRF-Token': getCsrfToken()}})
            .then(() => {
                serverRunning = false;
                document.getElementById('exit-button').textContent = 'Enter';
            });
    } else {
        // Start server
        fetch('/control/start', {method: 'POST',
            headers: {'X-CSRF-Token': getCsrfToken()}})
            .then(() => {
                serverRunning = true;
                document.getElementById('exit-button').textContent = 'Exit';
                // Reconnect socket
                socket.connect();
            });
    }
}
```

#### Browser Tab Reconnection

- On "Enter" click: POST to `/control/start`
- After start: SocketIO auto-reconnects to new server
- No new browser window opened (existing tab reconnects)

#### Duplicate Prevention

- Supervisor tracks child process PID
- If multiple tabs connect, all receive same broadcasts
- Optional: Add tab identity to prevent duplicate TTS

---

## Comparison Matrix

| Feature | Phase 1 | Phase 2 |
|---------|---------|---------|
| Exit from GUI | Yes | Yes |
| Enter from GUI | No (manual restart) | Yes |
| No watcher process | Yes | No |
| Security complexity | Low | Medium |
| Code changes | Minimal | Moderate |
| Browser window handling | N/A | No duplicates |

---

## Risks and Mitigations

### Phase 1 Risks
1. **User confusion** - Button always says "Exit", never changes
   - *Mitigation:* Add tooltip "Stop server (restart manually)"

2. **Race condition** - User clicks Exit while game processing
   - *Mitigation:* Server waits briefly, game loop exits on next input

### Phase 2 Risks
1. **Security** - Localhost API could be exploited
   - *Mitigation:* Strict localhost-only binding, CSRF tokens

2. **Tab duplication** - Multiple restarts open new windows
   - *Mitigation:* Suppress browser auto-open on controlled restart

3. **Watcher reliability** - Supervisor could crash
   - *Mitigation:* Add health monitoring, auto-restart supervisor

---

## Implementation Order

1. **Phase 1** (Immediate):
   - Modify `handle_user_exit()` in web_interface.py
   - Update exit code handling in run_web.py  
   - Update exit button JavaScript in game_interface.html
   - Test graceful shutdown

2. **Phase 2** (Future):
   - Design supervisor architecture
   - Implement control API in run_web.py
   - Add security hardening
   - Update GUI toggle logic
   - Test restart flow

---

## References

- Current exit button: `web/templates/game_interface.html:4520`
- Current exit handler: `web/web_interface.py:2656`
- Current launcher: `run_web.py:108-127`
- SocketIO events: `web/templates/game_interface.html:8465-8507`
