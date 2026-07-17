#!/usr/bin/env python3
"""
Web Interface for Module Builder
Provides a standalone web UI for creating new game modules with real-time progress tracking
"""

import os
import sys
import json
import random
import socket
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.generators.module_builder import ModuleBuilder, BuilderConfig
from core.generators.module_stitcher import list_available_modules
from utils.enhanced_logger import info, error, debug, set_script_name

# Setup logging
set_script_name('module_builder_web')

# Initialize Flask app
app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.config['SECRET_KEY'] = os.urandom(24).hex()
CORS(app)

# Initialize SocketIO with long polling as fallback
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global variable to track current build
current_build = {
    'active': False,
    'thread': None,
    'cancelled': False
}

def find_free_port():
    """Find a random available port"""
    # Try random ports in the 7000-9000 range
    for _ in range(100):
        port = random.randint(7000, 9000)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('', port))
                return port
            except:
                continue
    # Fallback to any available port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

class ModuleBuilderWithProgress(ModuleBuilder):
    """Extended ModuleBuilder with progress reporting"""
    
    def __init__(self, config, progress_callback=None):
        super().__init__(config)
        self.progress_callback = progress_callback
        self.current_stage = 0
        self.stages = [
            "Initializing module builder",
            "Generating base module structure",
            "Creating NPCs",
            "Building monsters",
            "Designing areas",
            "Generating plots and quests",
            "Creating location connections",
            "Finalizing module data",
            "Saving module files"
        ]
    
    def report_progress(self, stage_index=None, message="", sub_progress=None):
        """Report progress to callback if available"""
        if stage_index is not None:
            self.current_stage = stage_index
        
        if self.progress_callback:
            progress_data = {
                'stage': self.current_stage,
                'total_stages': len(self.stages),
                'stage_name': self.stages[min(self.current_stage, len(self.stages)-1)],
                'message': message,
                'percentage': (self.current_stage / len(self.stages)) * 100
            }
            
            if sub_progress is not None:
                progress_data['sub_progress'] = sub_progress
            
            self.progress_callback(progress_data)
    
    def build_module(self, concept):
        """Override build_module to add progress reporting"""
        try:
            self.report_progress(0, "Starting module generation...")
            
            # Stage 1: Base structure
            self.report_progress(1, "Creating module foundation...")
            result = super().build_module(concept)
            
            # Note: We'll need to add more granular progress calls 
            # within the actual module_builder.py methods
            
            self.report_progress(8, "Module generation complete!")
            return result
            
        except Exception as e:
            error(f"Module build error: {e}")
            if self.progress_callback:
                self.progress_callback({
                    'error': str(e),
                    'stage': self.current_stage,
                    'stage_name': self.stages[self.current_stage]
                })
            raise

def build_module_thread(module_name, narrative, num_areas, locations_per_area, socket_id):
    """Thread function to build module without blocking"""
    global current_build
    
    try:
        info(f"Starting module build: {module_name} with {num_areas} areas, {locations_per_area} locations per area")
        
        # Create progress callback
        def progress_callback(data):
            if current_build['cancelled']:
                raise Exception("Build cancelled by user")
            
            # Emit progress update to specific client
            socketio.emit('module_progress', data, room=socket_id)
        
        # Build the module
        progress_callback({'stage': 0, 'total_stages': 9, 'stage_name': 'Initializing', 'percentage': 0})
        
        # Call the actual builder (we'll need to modify module_builder.py to report progress)
        from core.generators.module_builder import ai_driven_module_creation
        
        # Create parameters for AI-driven creation
        params = {
            'narrative': narrative,
            'module_name': module_name,
            'num_areas': num_areas,
            'locations_per_area': locations_per_area,
        }

        # Execute module creation
        success, created_name = ai_driven_module_creation(
            params,
            progress_callback=progress_callback,
            policy="toolkit",
        )
        
        if success:
            # Emit completion
            socketio.emit('module_complete', {
                'success': True,
                'module_name': created_name,
                'message': f"Module '{created_name}' created successfully!"
            }, room=socket_id)
            info(f"Module '{created_name}' created successfully")
        else:
            raise Exception("Module creation failed")
            
    except Exception as e:
        error(f"Module build thread error: {traceback.format_exc()}")
        
        error_message = str(e) if str(e) != "Build cancelled by user" else "Module generation cancelled"
        
        socketio.emit('module_error', {
            'error': error_message,
            'traceback': traceback.format_exc() if not current_build['cancelled'] else None
        }, room=socket_id)
    
    finally:
        current_build['active'] = False
        current_build['thread'] = None
        current_build['cancelled'] = False

@app.route('/')
def index():
    """Serve the module builder interface"""
    return render_template('module_builder.html')

@app.route('/api/status')
def get_status():
    """Get current build status"""
    return jsonify({
        'active': current_build['active'],
        'timestamp': datetime.now().isoformat()
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    info(f"Client connected: {request.sid}")
    emit('connected', {'message': 'Connected to Module Builder'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    info(f"Client disconnected: {request.sid}")

@socketio.on('start_build')
def handle_start_build(data):
    """Start building a new module"""
    global current_build
    
    if current_build['active']:
        emit('module_error', {'error': 'A module build is already in progress'})
        return
    
    module_name = data.get('module_name', '').strip()
    narrative = data.get('narrative', '').strip()
    num_areas = data.get('num_areas', 3)
    locations_per_area = data.get('locations_per_area', 5)
    
    if not module_name or not narrative:
        emit('module_error', {'error': 'Module name and narrative are required'})
        return
    
    # Start build in background thread
    current_build['active'] = True
    current_build['cancelled'] = False
    current_build['thread'] = threading.Thread(
        target=build_module_thread,
        args=(module_name, narrative, num_areas, locations_per_area, request.sid)
    )
    current_build['thread'].start()
    
    emit('build_started', {'message': f'Starting build of module: {module_name}'})

@socketio.on('cancel_build')
def handle_cancel_build():
    """Cancel the current build"""
    global current_build
    
    if current_build['active']:
        current_build['cancelled'] = True
        emit('build_cancelled', {'message': 'Cancelling module generation...'})
        info("Module build cancelled by user")
    else:
        emit('module_error', {'error': 'No active build to cancel'})

@socketio.on('ping')
def handle_ping():
    """Handle ping to keep connection alive"""
    emit('pong')

@socketio.on('request_module_list')
def handle_request_module_list():
    """Handles client request to get the list of available modules."""
    try:
        # Call the function from module_stitcher to get the module data
        # This function reads world_registry.json and formats the data
        modules = list_available_modules()
        
        # Send the module list back to the client
        emit('module_list_response', modules)
        info(f"Sent module list with {len(modules)} modules to client")
        
    except Exception as e:
        error(f"Error handling request_module_list: {e}")
        # If something goes wrong, send back an empty list
        emit('module_list_response', [])

def main():
    """Main entry point"""
    port = find_free_port()
    
    print("\n" + "="*60)
    print("MODULE BUILDER WEB INTERFACE")
    print("="*60)
    print(f"Starting server on port {port}...")
    print(f"Open your browser to: http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    # Auto-launch browser after a short delay
    def open_browser():
        import time
        time.sleep(1.5)  # Wait for server to start
        webbrowser.open(f'http://localhost:{port}')
    
    browser_thread = threading.Thread(target=open_browser)
    browser_thread.daemon = True
    browser_thread.start()
    
    try:
        socketio.run(app, host='0.0.0.0', port=port, debug=False)
    except KeyboardInterrupt:
        print("\nShutting down Module Builder...")
    except Exception as e:
        print(f"Server error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
