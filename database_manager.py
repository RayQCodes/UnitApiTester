#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading

class WeatherTestDatabase:
    def __init__(self, db_path: str = "weather_tests.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Test sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    target_url TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    total_tests INTEGER DEFAULT 0,
                    passed_tests INTEGER DEFAULT 0,
                    failed_tests INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running',
                    config TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Individual test results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    city TEXT NOT NULL,
                    test_type TEXT NOT NULL,
                    passed BOOLEAN NOT NULL,
                    api_endpoint TEXT,
                    status_code INTEGER,
                    response_time_ms REAL,
                    response_data TEXT,
                    errors TEXT,
                    validation_results TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES test_sessions (session_id)
                )
            ''')
            
            # API endpoints performance tracking
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS endpoint_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    endpoint TEXT NOT NULL,
                    avg_response_time REAL,
                    success_rate REAL,
                    total_requests INTEGER DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # City test statistics
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS city_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    city TEXT NOT NULL UNIQUE,
                    total_tests INTEGER DEFAULT 1,
                    success_count INTEGER DEFAULT 0,
                    avg_response_time REAL,
                    last_tested TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON test_results(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_city ON test_results(city)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON test_results(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_endpoint ON endpoint_performance(endpoint)')
            
            conn.commit()
    
    def create_test_session(self, session_id: str, target_url: str, config: Dict) -> bool:
        """Create a new test session"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO test_sessions 
                        (session_id, target_url, start_time, config, status)
                        VALUES (?, ?, ?, ?, 'running')
                    ''', (session_id, target_url, datetime.now(), json.dumps(config)))
                    conn.commit()
                    return True
            except sqlite3.IntegrityError:
                return False
    
    def update_test_session(self, session_id: str, **kwargs) -> bool:
        """Update test session with new data"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    set_clauses = []
                    values = []
                    
                    for key, value in kwargs.items():
                        if key in ['end_time', 'total_tests', 'passed_tests', 'failed_tests', 'status']:
                            set_clauses.append(f"{key} = ?")
                            values.append(value)
                    
                    if set_clauses:
                        values.append(session_id)
                        query = f"UPDATE test_sessions SET {', '.join(set_clauses)} WHERE session_id = ?"
                        cursor.execute(query, values)
                        conn.commit()
                        return cursor.rowcount > 0
                    return False
            except Exception:
                return False
    
    def save_test_result(self, session_id: str, result: Dict[str, Any]) -> bool:
        """Save individual test result"""
        with self.lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO test_results 
                        (session_id, city, test_type, passed, api_endpoint, status_code, 
                         response_time_ms, response_data, errors, validation_results, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        session_id,
                        result.get('city', ''),
                        result.get('test_type', ''),
                        result.get('passed', False),
                        result.get('api_endpoint'),
                        result.get('status_code'),
                        result.get('response_time_ms'),
                        json.dumps(result.get('response_data')),
                        json.dumps(result.get('errors', [])),
                        json.dumps(result.get('validation_results', {})),
                        result.get('timestamp', datetime.now().isoformat())
                    ))
                    
                    # Update endpoint performance
                    self._update_endpoint_performance(cursor, result)
                    
                    # Update city statistics
                    self._update_city_stats(cursor, result)
                    
                    conn.commit()
                    return True
            except Exception as e:
                print(f"Error saving test result: {e}")
                return False
    
    def _update_endpoint_performance(self, cursor, result: Dict):
        """Update endpoint performance statistics"""
        endpoint = result.get('api_endpoint')
        if not endpoint:
            return
        
        response_time = result.get('response_time_ms', 0)
        is_success = result.get('passed', False)
        
        cursor.execute('''
            SELECT avg_response_time, success_rate, total_requests 
            FROM endpoint_performance 
            WHERE endpoint = ?
        ''', (endpoint,))
        
        existing = cursor.fetchone()
        
        if existing:
            avg_time, success_rate, total_requests = existing
            new_total = total_requests + 1
            new_avg_time = ((avg_time * total_requests) + response_time) / new_total
            new_success_rate = ((success_rate * total_requests) + (1 if is_success else 0)) / new_total
            
            cursor.execute('''
                UPDATE endpoint_performance 
                SET avg_response_time = ?, success_rate = ?, total_requests = ?, last_updated = ?
                WHERE endpoint = ?
            ''', (new_avg_time, new_success_rate, new_total, datetime.now(), endpoint))
        else:
            cursor.execute('''
                INSERT INTO endpoint_performance 
                (endpoint, avg_response_time, success_rate, total_requests)
                VALUES (?, ?, ?, 1)
            ''', (endpoint, response_time, 1.0 if is_success else 0.0))
    
    def _update_city_stats(self, cursor, result: Dict):
        """Update city testing statistics"""
        city = result.get('city')
        if not city:
            return
        
        response_time = result.get('response_time_ms', 0)
        is_success = result.get('passed', False)
        
        cursor.execute('''
            SELECT total_tests, success_count, avg_response_time 
            FROM city_stats 
            WHERE city = ?
        ''', (city,))
        
        existing = cursor.fetchone()
        
        if existing:
            total_tests, success_count, avg_response_time = existing
            new_total = total_tests + 1
            new_success_count = success_count + (1 if is_success else 0)
            new_avg_time = ((avg_response_time * total_tests) + response_time) / new_total
            
            cursor.execute('''
                UPDATE city_stats 
                SET total_tests = ?, success_count = ?, avg_response_time = ?, last_tested = ?
                WHERE city = ?
            ''', (new_total, new_success_count, new_avg_time, datetime.now(), city))
        else:
            cursor.execute('''
                INSERT INTO city_stats 
                (city, total_tests, success_count, avg_response_time)
                VALUES (?, 1, ?, ?)
            ''', (city, 1 if is_success else 0, response_time))
    
    def get_test_sessions(self, limit: int = 50) -> List[Dict]:
        """Get recent test sessions"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM test_sessions 
                ORDER BY start_time DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_session_results(self, session_id: str) -> List[Dict]:
        """Get all results for a specific session"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM test_results 
                WHERE session_id = ? 
                ORDER BY timestamp DESC
            ''', (session_id,))
            
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                # Parse JSON fields
                for field in ['response_data', 'errors', 'validation_results']:
                    if result[field]:
                        try:
                            result[field] = json.loads(result[field])
                        except json.JSONDecodeError:
                            result[field] = None
                results.append(result)
            
            return results
    
    def get_city_performance(self) -> List[Dict]:
        """Get performance statistics for all cities"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT city, total_tests, success_count, avg_response_time, last_tested,
                       ROUND((success_count * 100.0 / total_tests), 2) as success_rate
                FROM city_stats 
                ORDER BY total_tests DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_endpoint_performance(self) -> List[Dict]:
        """Get performance statistics for all endpoints"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT endpoint, 
                       ROUND(avg_response_time, 2) as avg_response_time,
                       ROUND(success_rate * 100, 2) as success_rate_percent,
                       total_requests, last_updated
                FROM endpoint_performance 
                ORDER BY total_requests DESC
            ''')
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_test_history(self, days: int = 30) -> List[Dict]:
        """Get test history for the last N days"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT DATE(timestamp) as test_date,
                       COUNT(*) as total_tests,
                       SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as passed_tests,
                       AVG(response_time_ms) as avg_response_time
                FROM test_results 
                WHERE timestamp >= datetime('now', '-{} days')
                GROUP BY DATE(timestamp)
                ORDER BY test_date DESC
            '''.format(days))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_data(self, days: int = 90) -> int:
        """Clean up test data older than specified days"""
        with self.lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get old session IDs
                cursor.execute('''
                    SELECT session_id FROM test_sessions 
                    WHERE start_time < datetime('now', '-{} days')
                '''.format(days))
                
                old_sessions = [row[0] for row in cursor.fetchall()]
                
                # Delete old test results
                cursor.execute('''
                    DELETE FROM test_results 
                    WHERE timestamp < datetime('now', '-{} days')
                '''.format(days))
                
                results_deleted = cursor.rowcount
                
                # Delete old sessions
                cursor.execute('''
                    DELETE FROM test_sessions 
                    WHERE start_time < datetime('now', '-{} days')
                '''.format(days))
                
                sessions_deleted = cursor.rowcount
                
                conn.commit()
                return results_deleted + sessions_deleted
    
    def export_data(self, session_id: Optional[str] = None) -> Dict:
        """Export test data to JSON format"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if session_id:
                # Export specific session
                cursor.execute('SELECT * FROM test_sessions WHERE session_id = ?', (session_id,))
                sessions = [dict(row) for row in cursor.fetchall()]
                
                cursor.execute('SELECT * FROM test_results WHERE session_id = ?', (session_id,))
                results = [dict(row) for row in cursor.fetchall()]
            else:
                # Export all data
                cursor.execute('SELECT * FROM test_sessions ORDER BY start_time DESC')
                sessions = [dict(row) for row in cursor.fetchall()]
                
                cursor.execute('SELECT * FROM test_results ORDER BY timestamp DESC')
                results = [dict(row) for row in cursor.fetchall()]
            
            return {
                'export_timestamp': datetime.now().isoformat(),
                'sessions': sessions,
                'results': results
            }