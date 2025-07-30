#!/usr/bin/env python3
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import threading
import time
import uuid
import os
from datetime import datetime
from weather_api_tester import WeatherAPITester
# Import database only if file exists, otherwise use simplified version
try:
    from database_manager import WeatherTestDatabase
    db = WeatherTestDatabase()
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    db = None
import json
import random

app = Flask(__name__)
CORS(app)

# Global test state
test_state = {
    'running': False,
    'current_test': '',
    'progress': 0,
    'total': 0,
    'passed': 0,
    'failed': 0,
    'results': [],
    'start_time': None,
    'end_time': None,
    'target_url': 'http://localhost:5000',
    'session_id': None
}

current_tester = None

@app.route('/')
def index():
    return send_from_directory('.', 'test_interface.html')

@app.route('/<path:filename>')
def static_files(filename):
    try:
        return send_from_directory('.', filename)
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/test/start', methods=['POST'])
def start_tests():
    global test_state, current_tester
    
    if test_state['running']:
        return jsonify({'error': 'Tests already running'}), 400
    
    config = request.get_json() or {}
    target_url = config.get('target_url', 'http://localhost:5000')
    num_valid = config.get('num_valid', 20)
    num_invalid = config.get('num_invalid', 10)
    num_edge = config.get('num_edge', 8)
    delay = config.get('delay', 0.1)
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Create session in database if available
    if DATABASE_AVAILABLE and db:
        session_config = {
            'num_valid': num_valid,
            'num_invalid': num_invalid,
            'num_edge': num_edge,
            'delay': delay
        }
        db.create_test_session(session_id, target_url, session_config)
    
    test_state.update({
        'running': True,
        'current_test': 'Initializing...',
        'progress': 0,
        'total': num_valid + num_invalid + num_edge,
        'passed': 0,
        'failed': 0,
        'results': [],
        'start_time': datetime.now().isoformat(),
        'end_time': None,
        'target_url': target_url,
        'session_id': session_id
    })
    
    current_tester = WeatherAPITester(target_url)
    thread = threading.Thread(
        target=run_test_suite_background,
        args=(current_tester, session_id, num_valid, num_invalid, num_edge, delay)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'message': 'Tests started',
        'total': test_state['total'],
        'target_url': target_url,
        'session_id': session_id
    })

@app.route('/api/test/stop', methods=['POST'])
def stop_tests():
    global test_state
    test_state['running'] = False
    test_state['end_time'] = datetime.now().isoformat()
    test_state['current_test'] = 'Stopped by user'
    
    # Update session in database if available
    if DATABASE_AVAILABLE and db and test_state['session_id']:
        db.update_test_session(
            test_state['session_id'],
            end_time=test_state['end_time'],
            status='stopped',
            total_tests=test_state['progress'],
            passed_tests=test_state['passed'],
            failed_tests=test_state['failed']
        )
    
    return jsonify({'message': 'Tests stopped'})

@app.route('/api/test/status')
def get_test_status():
    return jsonify(test_state)

@app.route('/api/test/single', methods=['POST'])
def test_single():
    data = request.get_json()
    target_url = data.get('target_url', 'http://localhost:5000')
    city = data.get('city', 'London')
    
    # Create a single test session if database available
    session_id = str(uuid.uuid4())
    config = {'type': 'single_test', 'city': city}
    
    if DATABASE_AVAILABLE and db:
        db.create_test_session(session_id, target_url, config)
    
    tester = WeatherAPITester(target_url)
    result = tester.test_api_endpoint(city, 'manual')
    
    # Save result to database if available
    if DATABASE_AVAILABLE and db:
        db.save_test_result(session_id, result)
        
        # Complete the session
        db.update_test_session(
            session_id,
            end_time=datetime.now().isoformat(),
            status='completed',
            total_tests=1,
            passed_tests=1 if result['passed'] else 0,
            failed_tests=0 if result['passed'] else 1
        )
    
    return jsonify(result)

@app.route('/api/test/results/download')
def download_results():
    if not test_state['results'] and not test_state['session_id']:
        return jsonify({'error': 'No results available'}), 400
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"test_results_{timestamp}.json"
    
    # Export from database if available and session exists
    if DATABASE_AVAILABLE and db and test_state['session_id']:
        results_data = db.export_data(test_state['session_id'])
    else:
        results_data = {
            'test_info': {
                'target_url': test_state['target_url'],
                'total_tests': test_state['total'],
                'passed': test_state['passed'],
                'failed': test_state['failed'],
                'start_time': test_state['start_time'],
                'end_time': test_state['end_time']
            },
            'results': test_state['results']
        }
    
    with open(filename, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    return send_from_directory('.', filename, as_attachment=True)

# Database-related endpoints (only if database is available)

@app.route('/api/history/sessions')
def get_test_sessions():
    if not DATABASE_AVAILABLE or not db:
        return jsonify({'error': 'Database not available'}), 503
    
    limit = request.args.get('limit', 20, type=int)
    sessions = db.get_test_sessions(limit)
    return jsonify(sessions)

@app.route('/api/history/session/<session_id>')
def get_session_results(session_id):
    if not DATABASE_AVAILABLE or not db:
        return jsonify({'error': 'Database not available'}), 503
    
    results = db.get_session_results(session_id)
    return jsonify(results)

@app.route('/api/analytics/cities')
def get_city_analytics():
    if not DATABASE_AVAILABLE or not db:
        return jsonify([])  # Return empty array if no database
    
    city_stats = db.get_city_performance()
    return jsonify(city_stats)

@app.route('/api/analytics/endpoints')
def get_endpoint_analytics():
    if not DATABASE_AVAILABLE or not db:
        return jsonify([])  # Return empty array if no database
    
    endpoint_stats = db.get_endpoint_performance()
    return jsonify(endpoint_stats)

@app.route('/api/analytics/history')
def get_test_history():
    if not DATABASE_AVAILABLE or not db:
        return jsonify([])  # Return empty array if no database
    
    days = request.args.get('days', 30, type=int)
    history = db.get_test_history(days)
    return jsonify(history)

@app.route('/api/data/cleanup', methods=['POST'])
def cleanup_old_data():
    if not DATABASE_AVAILABLE or not db:
        return jsonify({'error': 'Database not available'}), 503
    
    days = request.json.get('days', 90) if request.json else 90
    deleted_count = db.cleanup_old_data(days)
    return jsonify({'message': f'Deleted {deleted_count} old records'})

@app.route('/api/data/export')
def export_all_data():
    if not DATABASE_AVAILABLE or not db:
        return jsonify({'error': 'Database not available'}), 503
    
    export_data = db.export_data()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"weather_test_data_export_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    return send_from_directory('.', filename, as_attachment=True)

def run_test_suite_background(tester, session_id, num_valid, num_invalid, num_edge, delay):
    global test_state
    
    try:
        # Test valid cities
        test_state['current_test'] = 'Testing valid cities...'
        valid_cities = random.sample(tester.valid_cities, min(num_valid, len(tester.valid_cities)))
        
        for i, city in enumerate(valid_cities):
            if not test_state['running']:
                break
                
            test_state['current_test'] = f'Testing valid city: {city}'
            result = tester.test_api_endpoint(city, 'valid')
            
            # Save to database if available
            if DATABASE_AVAILABLE and db:
                db.save_test_result(session_id, result)
            
            test_state['results'].append(result)
            test_state['progress'] += 1
            
            if result['passed']:
                test_state['passed'] += 1
            else:
                test_state['failed'] += 1
                
            time.sleep(delay)
        
        # Test invalid inputs
        test_state['current_test'] = 'Testing invalid inputs...'
        invalid_cities = random.sample(tester.invalid_cities, min(num_invalid, len(tester.invalid_cities)))
        
        for city in invalid_cities:
            if not test_state['running']:
                break
                
            test_state['current_test'] = f'Testing invalid input: {city}'
            result = tester.test_api_endpoint(city, 'invalid')
            
            # Save to database if available
            if DATABASE_AVAILABLE and db:
                db.save_test_result(session_id, result)
            
            test_state['results'].append(result)
            test_state['progress'] += 1
            
            if result['passed']:
                test_state['passed'] += 1
            else:
                test_state['failed'] += 1
                
            time.sleep(delay)
        
        # Test edge cases
        test_state['current_test'] = 'Testing edge cases...'
        edge_cities = random.sample(tester.edge_cases, min(num_edge, len(tester.edge_cases)))
        
        for city in edge_cities:
            if not test_state['running']:
                break
                
            test_state['current_test'] = f'Testing edge case: {city}'
            result = tester.test_api_endpoint(city, 'edge_case')
            
            # Save to database if available
            if DATABASE_AVAILABLE and db:
                db.save_test_result(session_id, result)
            
            test_state['results'].append(result)
            test_state['progress'] += 1
            
            if result['passed']:
                test_state['passed'] += 1
            else:
                test_state['failed'] += 1
                
            time.sleep(delay)
        
        # Complete the session
        test_state['running'] = False
        test_state['end_time'] = datetime.now().isoformat()
        test_state['current_test'] = 'Tests completed!'
        
        # Update session in database if available
        if DATABASE_AVAILABLE and db:
            db.update_test_session(
                session_id,
                end_time=test_state['end_time'],
                status='completed',
                total_tests=test_state['progress'],
                passed_tests=test_state['passed'],
                failed_tests=test_state['failed']
            )
        
    except Exception as e:
        test_state['running'] = False
        test_state['current_test'] = f'Error: {str(e)}'
        
        # Update session with error if database available
        if DATABASE_AVAILABLE and db and session_id:
            db.update_test_session(
                session_id,
                end_time=datetime.now().isoformat(),
                status='error',
                total_tests=test_state['progress'],
                passed_tests=test_state['passed'],
                failed_tests=test_state['failed']
            )

if __name__ == '__main__':
    # Get port from environment variable for Railway deployment
    port = int(os.environ.get('PORT', 5001))
    
    print("🧪 Weather API Testing Server Starting...")
    if DATABASE_AVAILABLE:
        print("💾 Database: SQLite with full analytics support")
    else:
        print("⚠️  Database: In-memory only (database_manager.py not found)")
    print(f"📊 Dashboard: http://0.0.0.0:{port}")
    print("🎯 Default target: http://localhost:5000")
    print("="*50)
    
    # Use production settings for Railway
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=port)