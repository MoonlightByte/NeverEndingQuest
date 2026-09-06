"""Synthetic performance load over the isolated portrait runtime's real routes.

Uses the same current backend for both UI builds to isolate frontend cost.
No engine or provider calls. A test-only endpoint broadcasts 400 long messages
and 80 synthetic NPC records; this is a stress fixture, not real campaign data.
"""
from flask_socketio import SocketIO
from flask import jsonify, request
from ember_portrait_runtime import main

original_run = SocketIO.run

def performance_run(socketio, app, **kwargs):
    stress_party = None
    original_party = socketio.server.handlers['/']['request_party_data']
    def party_request(sid, *args):
        if stress_party is None:
            return original_party(sid, *args)
        socketio.emit('party_data_response', stress_party, to=sid)
    socketio.server.handlers['/']['request_party_data'] = party_request
    @app.before_request
    def clear_stress():
        nonlocal stress_party
        if request.path.startswith('/__parity__/scenario/'):
            stress_party = None
    @app.post('/__performance__/stress')
    def stress():
        nonlocal stress_party
        messages = [{'type': 'narration', 'content': f'Performance passage {i}. ' + 'The ancient forest opens onto a quiet stone courtyard. ' * 35,
                     'message_id': f'perf-{i}'} for i in range(400)]
        people = [{'name': f'Performance Ranger {i}', 'class': 'Ranger', 'level': 3,
                   'hitPoints': {'current': 20, 'maximum': 24}, 'is_present': True} for i in range(80)]
        socketio.emit('cached_messages', messages)
        stress_party = {'members': [], 'location_npcs': people}
        socketio.emit('party_data_response', stress_party)
        return jsonify({'messages': len(messages), 'npcs': len(people)})
    return original_run(socketio, app, **kwargs)

SocketIO.run = performance_run

if __name__ == '__main__':
    main()
