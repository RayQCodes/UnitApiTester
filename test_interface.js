class WeatherAPITestDashboard {
    constructor() {
        this.baseURL = window.location.origin;
        this.isRunning = false;
        this.statusInterval = null;
        this.allResults = [];
        
        this.initializeElements();
        this.bindEvents();
        this.addLog('info', 'Dashboard initialized with database support');
    }

    initializeElements() {
        this.targetURL = document.getElementById('target-url');
        this.validCities = document.getElementById('valid-cities');
        this.invalidCities = document.getElementById('invalid-cities');
        this.edgeCases = document.getElementById('edge-cases');
        this.delay = document.getElementById('delay');
        this.singleCity = document.getElementById('single-city');

        this.testSingleBtn = document.getElementById('test-single-btn');
        this.runTestsBtn = document.getElementById('run-tests-btn');
        this.stopTestsBtn = document.getElementById('stop-tests-btn');
        this.clearResultsBtn = document.getElementById('clear-results-btn');
        this.downloadResultsBtn = document.getElementById('download-results-btn');
        this.refreshHistoryBtn = document.getElementById('refresh-history-btn');
        this.exportAllBtn = document.getElementById('export-all-btn');

        this.testStatus = document.getElementById('test-status');
        this.testProgress = document.getElementById('test-progress');
        this.testsPassed = document.getElementById('tests-passed');
        this.testsFailed = document.getElementById('tests-failed');
        this.progressBar = document.getElementById('progress-bar');
        this.currentTest = document.getElementById('current-test');

        this.resultsContainer = document.getElementById('results-container');
        this.filterResults = document.getElementById('filter-results');
        this.logContainer = document.getElementById('log-container');
        this.historyContainer = document.getElementById('history-container');
        this.cityAnalytics = document.getElementById('city-analytics');
        this.endpointAnalytics = document.getElementById('endpoint-analytics');
        this.historyTrends = document.getElementById('history-trends');
    }

    bindEvents() {
        this.testSingleBtn.addEventListener('click', () => this.testSingleCity());
        this.runTestsBtn.addEventListener('click', () => this.runTestSuite());
        this.stopTestsBtn.addEventListener('click', () => this.stopTests());
        this.clearResultsBtn.addEventListener('click', () => this.clearResults());
        this.downloadResultsBtn.addEventListener('click', () => this.downloadResults());
        this.refreshHistoryBtn.addEventListener('click', () => this.loadTestHistory());
        this.exportAllBtn.addEventListener('click', () => this.exportAllData());
        this.filterResults.addEventListener('change', () => this.filterResultsDisplay());

        this.singleCity.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.testSingleCity();
            }
        });
    }

    async testSingleCity() {
        const city = this.singleCity.value.trim();
        const targetURL = this.targetURL.value.trim();

        if (!city) {
            this.addLog('error', 'Please enter a city name');
            return;
        }

        this.addLog('info', `Testing single city: ${city}`);
        this.testSingleBtn.disabled = true;

        try {
            const response = await fetch(`${this.baseURL}/api/test/single`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    target_url: targetURL,
                    city: city
                })
            });

            const result = await response.json();
            this.addResult(result);
            this.addLog(result.passed ? 'success' : 'error', 
                       `Single test ${result.passed ? 'PASSED' : 'FAILED'}: ${city} (saved to database)`);

        } catch (error) {
            this.addLog('error', `Single test failed: ${error.message}`);
        } finally {
            this.testSingleBtn.disabled = false;
        }
    }

    async runTestSuite() {
        const config = {
            target_url: this.targetURL.value.trim(),
            num_valid: parseInt(this.validCities.value),
            num_invalid: parseInt(this.invalidCities.value),
            num_edge: parseInt(this.edgeCases.value),
            delay: parseFloat(this.delay.value)
        };
        
        this.addLog('info', `Starting test suite: ${config.num_valid + config.num_invalid + config.num_edge} total tests`);
        
        try {
            const response = await fetch(`${this.baseURL}/api/test/start`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            const result = await response.json();
            
            if (response.ok) {
                this.isRunning = true;
                this.updateUIForRunningTests();
                this.startStatusPolling();
                this.addLog('success', `Test suite started: ${result.total} tests queued (Session: ${result.session_id})`);
            } else {
                this.addLog('error', `Failed to start tests: ${result.error}`);
            }

        } catch (error) {
            this.addLog('error', `Failed to start test suite: ${error.message}`);
        }
    }

    async stopTests() {
        try {
            const response = await fetch(`${this.baseURL}/api/test/stop`, {
                method: 'POST'
            });

            if (response.ok) {
                this.addLog('info', 'Test suite stopped by user (results saved to database)');
                this.isRunning = false;
                this.updateUIForStoppedTests();
            }

        } catch (error) {
            this.addLog('error', `Failed to stop tests: ${error.message}`);
        }
    }

    updateUIForRunningTests() {
        this.runTestsBtn.disabled = true;
        this.stopTestsBtn.disabled = false;
        this.testStatus.textContent = 'Running';
        this.testStatus.style.color = '#ffa726';
    }

    updateUIForStoppedTests() {
        this.runTestsBtn.disabled = false;
        this.stopTestsBtn.disabled = true;
        this.testStatus.textContent = 'Completed';
        this.testStatus.style.color = '#4caf50';
        
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    }

    startStatusPolling() {
        this.statusInterval = setInterval(async () => {
            try {
                const response = await fetch(`${this.baseURL}/api/test/status`);
                const status = await response.json();
                
                this.updateStatusDisplay(status);
                
                if (!status.running && this.isRunning) {
                    this.isRunning = false;
                    this.updateUIForStoppedTests();
                    this.addLog('success', `Test suite completed: ${status.passed} passed, ${status.failed} failed (all results saved to database)`);
                }

            } catch (error) {
                this.addLog('error', `Status polling error: ${error.message}`);
            }
        }, 1000);
    }

    updateStatusDisplay(status) {
        const progressPercent = status.total > 0 ? (status.progress / status.total) * 100 : 0;
        this.progressBar.style.width = `${progressPercent}%`;
        this.testProgress.textContent = `${status.progress}/${status.total}`;
        
        this.testsPassed.textContent = status.passed;
        this.testsFailed.textContent = status.failed;
        
        this.currentTest.textContent = status.current_test || 'No tests running';
        
        if (status.results && status.results.length > this.allResults.length) {
            const newResults = status.results.slice(this.allResults.length);
            newResults.forEach(result => this.addResult(result));
        }
    }

    // Database-related methods

    async loadTestHistory() {
        this.addLog('info', 'Loading test history from database...');
        try {
            const response = await fetch(`${this.baseURL}/api/history/sessions?limit=20`);
            const sessions = await response.json();
            this.displayHistory(sessions);
            this.addLog('success', `Loaded ${sessions.length} test sessions from database`);
        } catch (error) {
            this.addLog('error', `Failed to load history: ${error.message}`);
            this.historyContainer.innerHTML = '<div class="no-results"><p>Failed to load test history.</p></div>';
        }
    }

    displayHistory(sessions) {
        if (sessions.length === 0) {
            this.historyContainer.innerHTML = '<div class="no-results"><p>No test sessions found in database.</p></div>';
            return;
        }

        this.historyContainer.innerHTML = '';
        
        sessions.forEach(session => {
            const sessionElement = this.createHistoryElement(session);
            this.historyContainer.appendChild(sessionElement);
        });
    }

    createHistoryElement(session) {
        const div = document.createElement('div');
        div.className = 'history-item';
        
        const startTime = new Date(session.start_time).toLocaleString();
        const duration = session.end_time ? 
            Math.round((new Date(session.end_time) - new Date(session.start_time)) / 1000) + 's' : 
            'Running...';
        
        div.innerHTML = `
            <div class="history-header">
                <span class="history-title">${session.target_url}</span>
                <span class="history-status ${session.status}">${session.status.toUpperCase()}</span>
            </div>
            <div class="result-details">
                <div class="result-detail">
                    <strong>Started:</strong> ${startTime}
                </div>
                <div class="result-detail">
                    <strong>Duration:</strong> ${duration}
                </div>
                <div class="result-detail">
                    <strong>Tests:</strong> ${session.total_tests}
                </div>
                <div class="result-detail">
                    <strong>Passed:</strong> ${session.passed_tests}
                </div>
                <div class="result-detail">
                    <strong>Failed:</strong> ${session.failed_tests}
                </div>
            </div>
        `;
        
        div.addEventListener('click', () => this.loadSessionDetails(session.session_id));
        
        return div;
    }

    async loadSessionDetails(sessionId) {
        try {
            const response = await fetch(`${this.baseURL}/api/history/session/${sessionId}`);
            const results = await response.json();
            
            // Switch to testing tab and show results
            showTab('testing');
            this.allResults = results;
            this.displayAllResults();
            this.addLog('info', `Loaded ${results.length} results from session ${sessionId}`);
            
        } catch (error) {
            this.addLog('error', `Failed to load session details: ${error.message}`);
        }
    }

    async loadAnalytics() {
        this.addLog('info', 'Loading analytics from database...');
        try {
            const [cityResponse, endpointResponse, historyResponse] = await Promise.all([
                fetch(`${this.baseURL}/api/analytics/cities`),
                fetch(`${this.baseURL}/api/analytics/endpoints`),
                fetch(`${this.baseURL}/api/analytics/history?days=30`)
            ]);
            
            const cityStats = await cityResponse.json();
            const endpointStats = await endpointResponse.json();
            const historyData = await historyResponse.json();
            
            this.displayCityAnalytics(cityStats);
            this.displayEndpointAnalytics(endpointStats);
            this.displayHistoryTrends(historyData);
            
            this.addLog('success', 'Analytics loaded successfully');
        } catch (error) {
            this.addLog('error', `Failed to load analytics: ${error.message}`);
        }
    }

    displayCityAnalytics(cityStats) {
        if (cityStats.length === 0) {
            this.cityAnalytics.innerHTML = '<div class="no-results">No city data available.</div>';
            return;
        }

        this.cityAnalytics.innerHTML = '';
        
        cityStats.slice(0, 10).forEach(city => {
            const cityElement = document.createElement('div');
            cityElement.className = 'analytics-item';
            cityElement.innerHTML = `
                <span><strong>${city.city}</strong></span>
                <span class="analytics-value">${city.success_rate}% (${city.total_tests} tests)</span>
            `;
            this.cityAnalytics.appendChild(cityElement);
        });
    }

    displayEndpointAnalytics(endpointStats) {
        if (endpointStats.length === 0) {
            this.endpointAnalytics.innerHTML = '<div class="no-results">No endpoint data available.</div>';
            return;
        }

        this.endpointAnalytics.innerHTML = '';
        
        endpointStats.forEach(endpoint => {
            const endpointElement = document.createElement('div');
            endpointElement.className = 'analytics-item';
            const endpointName = endpoint.endpoint.split('/').pop() || 'Unknown';
            endpointElement.innerHTML = `
                <span><strong>${endpointName}</strong><br><small>${endpoint.avg_response_time}ms avg</small></span>
                <span class="analytics-value">${endpoint.success_rate_percent}%</span>
            `;
            this.endpointAnalytics.appendChild(endpointElement);
        });
    }

    displayHistoryTrends(historyData) {
        if (historyData.length === 0) {
            this.historyTrends.innerHTML = '<div class="no-results">No historical data available.</div>';
            return;
        }

        this.historyTrends.innerHTML = '';
        
        historyData.forEach(day => {
            const dayElement = document.createElement('div');
            dayElement.className = 'analytics-item';
            const successRate = day.total_tests > 0 ? Math.round((day.passed_tests / day.total_tests) * 100) : 0;
            dayElement.innerHTML = `
                <span><strong>${day.test_date}</strong><br><small>${day.total_tests} tests</small></span>
                <span class="analytics-value">${successRate}% success</span>
            `;
            this.historyTrends.appendChild(dayElement);
        });
    }

    async exportAllData() {
        try {
            this.addLog('info', 'Exporting all data from database...');
            const link = document.createElement('a');
            link.href = `${this.baseURL}/api/data/export`;
            link.download = `weather_test_data_export_${new Date().toISOString().split('T')[0]}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.addLog('success', 'Data export initiated');
        } catch (error) {
            this.addLog('error', `Export failed: ${error.message}`);
        }
    }

    // Enhanced existing methods

    displayAllResults() {
        this.resultsContainer.innerHTML = '';
        if (this.allResults.length === 0) {
            this.resultsContainer.innerHTML = '<div class="no-results"><p>No test results to display.</p></div>';
            return;
        }
        
        this.allResults.forEach(result => {
            this.displayResult(result);
        });
    }

    addResult(result) {
        this.allResults.push(result);
        this.displayResult(result);
        this.scrollResultsToBottom();
    }

    displayResult(result) {
        const resultElement = this.createResultElement(result);
        
        const filter = this.filterResults.value;
        if (filter === 'all' || 
            (filter === 'passed' && result.passed) || 
            (filter === 'failed' && !result.passed)) {
            
            const noResults = this.resultsContainer.querySelector('.no-results');
            if (noResults) {
                noResults.remove();
            }
            
            this.resultsContainer.appendChild(resultElement);
        }
    }

    createResultElement(result) {
        const div = document.createElement('div');
        div.className = `result-item ${result.passed ? 'passed' : 'failed'}`;
        
        const statusText = result.passed ? 'PASSED' : 'FAILED';
        
        div.innerHTML = `
            <div class="result-header">
                <span class="result-city">${result.city}</span>
                <span class="result-status ${result.passed ? 'passed' : 'failed'}">${statusText}</span>
            </div>
            <div class="result-details">
                <div class="result-detail">
                    <strong>Type:</strong> ${result.test_type}
                </div>
                <div class="result-detail">
                    <strong>Status:</strong> ${result.status_code || 'N/A'}
                </div>
                <div class="result-detail">
                    <strong>Time:</strong> ${result.response_time_ms}ms
                </div>
                <div class="result-detail">
                    <strong>Endpoint:</strong> ${result.api_endpoint ? result.api_endpoint.split('/').pop() : 'None'}
                </div>
                ${result.errors && result.errors.length > 0 ? `
                <div class="result-detail" style="grid-column: 1 / -1;">
                    <strong>Errors:</strong> ${result.errors.join('; ')}
                </div>
                ` : ''}
            </div>
        `;
        
        return div;
    }

    filterResultsDisplay() {
        const filter = this.filterResults.value;
        this.resultsContainer.innerHTML = '';
        
        const filteredResults = this.allResults.filter(result => {
            if (filter === 'all') return true;
            if (filter === 'passed') return result.passed;
            if (filter === 'failed') return !result.passed;
            return true;
        });
        
        if (filteredResults.length === 0) {
            this.resultsContainer.innerHTML = '<div class="no-results"><p>No results match the current filter.</p></div>';
        } else {
            filteredResults.forEach(result => {
                this.resultsContainer.appendChild(this.createResultElement(result));
            });
        }
    }

    clearResults() {
        this.allResults = [];
        this.resultsContainer.innerHTML = '<div class="no-results"><p>No test results yet. Run a test to see results here.</p></div>';
        this.addLog('info', 'Results cleared from display (database records preserved)');
        
        this.testsPassed.textContent = '0';
        this.testsFailed.textContent = '0';
        this.testProgress.textContent = '0/0';
        this.progressBar.style.width = '0%';
    }

    async downloadResults() {
        if (this.allResults.length === 0) {
            this.addLog('error', 'No results to download');
            return;
        }

        try {
            const response = await fetch(`${this.baseURL}/api/test/results/download`);
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `test_results_${new Date().toISOString().split('T')[0]}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.addLog('success', 'Results downloaded successfully');
            } else {
                this.addLog('error', 'Failed to download results');
            }
        } catch (error) {
            this.addLog('error', `Download error: ${error.message}`);
        }
    }

    scrollResultsToBottom() {
        this.resultsContainer.scrollTop = this.resultsContainer.scrollHeight;
    }

    addLog(type, message) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.textContent = `[${timestamp}] ${message}`;
        
        this.logContainer.appendChild(logEntry);
        this.logContainer.scrollTop = this.logContainer.scrollHeight;
        
        const logEntries = this.logContainer.querySelectorAll('.log-entry');
        if (logEntries.length > 50) {
            logEntries[0].remove();
        }
    }
}

// Global tab switching function
function showTab(tabName) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Remove active class from all tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(`${tabName}-tab`).classList.add('active');
    
    // Find and activate the corresponding tab button
    const tabs = document.querySelectorAll('.tab');
    if (tabName === 'testing') tabs[0].classList.add('active');
    else if (tabName === 'history') tabs[1].classList.add('active');
    else if (tabName === 'analytics') tabs[2].classList.add('active');
    
    // Load data for specific tabs
    if (tabName === 'history' && window.testDashboard) {
        window.testDashboard.loadTestHistory();
    } else if (tabName === 'analytics' && window.testDashboard) {
        window.testDashboard.loadAnalytics();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.testDashboard = new WeatherAPITestDashboard();
});