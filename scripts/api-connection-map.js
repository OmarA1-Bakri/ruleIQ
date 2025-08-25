#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

// Configuration
const FRONTEND_BASE = path.join(__dirname, '..', 'frontend');
const HOOKS_DIR = path.join(FRONTEND_BASE, 'lib', 'tanstack-query', 'hooks');
const API_SERVICES_DIR = path.join(FRONTEND_BASE, 'lib', 'api');
const OUTPUT_FILE = path.join(__dirname, '..', 'api-connection-map.html');
const BACKEND_URL = 'http://localhost:8000';

// Store discovered connections
const connections = {
  frontend: {},
  backend: {},
  mappings: []
};

// Color coding for status
const STATUS_COLORS = {
  connected: '#10b981',    // green
  mismatched: '#f59e0b',   // yellow
  missing: '#ef4444',      // red
  unused: '#6b7280'        // gray
};

// Extract API calls from TypeScript/JavaScript files
function extractApiCalls(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const apiCalls = [];
    
    // Match apiClient.get/post/put/delete patterns
    const apiClientPattern = /apiClient\.(get|post|put|patch|delete|request)<[^>]*>\(['"`]([^'"`]+)['"`]/g;
    let match;
    while ((match = apiClientPattern.exec(content)) !== null) {
      apiCalls.push({
        method: match[1].toUpperCase(),
        path: match[2],
        line: content.substring(0, match.index).split('\n').length
      });
    }
    
    // Match fetch patterns
    const fetchPattern = /fetch\(['"`]([^'"`]+)['"`].*method:\s*['"`](GET|POST|PUT|PATCH|DELETE)['"`]/g;
    while ((match = fetchPattern.exec(content)) !== null) {
      apiCalls.push({
        method: match[2],
        path: match[1].replace('${API_BASE_URL}', '').replace('http://localhost:8000', ''),
        line: content.substring(0, match.index).split('\n').length
      });
    }
    
    return apiCalls;
  } catch (error) {
    console.error(`Error reading ${filePath}: ${error.message}`);
    return [];
  }
}

// Scan hook files
function scanHooks() {
  console.log('📚 Scanning frontend hooks...');
  
  try {
    const hookFiles = fs.readdirSync(HOOKS_DIR)
      .filter(file => file.endsWith('.ts') || file.endsWith('.tsx'));
    
    hookFiles.forEach(file => {
      const filePath = path.join(HOOKS_DIR, file);
      const content = fs.readFileSync(filePath, 'utf8');
      
      // Extract hook names and their corresponding service calls
      const hookPattern = /export\s+function\s+(use\w+)/g;
      let match;
      
      while ((match = hookPattern.exec(content)) !== null) {
        const hookName = match[1];
        
        // Find what service this hook uses
        const servicePattern = new RegExp(`${hookName}[\\s\\S]*?(\\w+Service)\\.(\\w+)\\(`);
        const serviceMatch = content.match(servicePattern);
        
        if (serviceMatch) {
          connections.frontend[hookName] = {
            file: file,
            service: serviceMatch[1],
            method: serviceMatch[2]
          };
        }
      }
    });
    
    console.log(`  Found ${Object.keys(connections.frontend).length} hooks`);
  } catch (error) {
    console.error('Error scanning hooks:', error);
  }
}

// Scan API service files
function scanServices() {
  console.log('🔍 Scanning API services...');
  
  try {
    const serviceFiles = fs.readdirSync(API_SERVICES_DIR)
      .filter(file => file.endsWith('.service.ts') || file.endsWith('.ts'));
    
    serviceFiles.forEach(file => {
      const filePath = path.join(API_SERVICES_DIR, file);
      const apiCalls = extractApiCalls(filePath);
      
      apiCalls.forEach(call => {
        const key = `${file}:${call.method}:${call.path}`;
        connections.frontend[key] = {
          file: file,
          method: call.method,
          path: call.path,
          line: call.line
        };
      });
    });
    
    console.log(`  Found ${Object.keys(connections.frontend).length} total API calls`);
  } catch (error) {
    console.error('Error scanning services:', error);
  }
}

// Fetch backend OpenAPI spec
async function fetchBackendSpec() {
  console.log('🌐 Fetching backend OpenAPI spec...');
  
  try {
    // Try using curl as a fallback
    const { execSync } = require('child_process');
    const specJson = execSync(`curl -s ${BACKEND_URL}/openapi.json`, { encoding: 'utf8' });
    const spec = JSON.parse(specJson);
    
    // Extract all paths
    Object.entries(spec.paths || {}).forEach(([path, methods]) => {
      Object.entries(methods).forEach(([method, details]) => {
        if (['get', 'post', 'put', 'patch', 'delete'].includes(method.toLowerCase())) {
          connections.backend[`${method.toUpperCase()}:${path}`] = {
            path: path,
            method: method.toUpperCase(),
            summary: details.summary || '',
            tags: details.tags || []
          };
        }
      });
    });
    
    console.log(`  Found ${Object.keys(connections.backend).length} backend endpoints`);
  } catch (error) {
    console.error('Error fetching OpenAPI spec:', error.message);
    console.log('  Continuing without backend spec...');
  }
}

// Create connection mappings
function createMappings() {
  console.log('🔗 Creating connection mappings...');
  
  // Map frontend calls to backend endpoints
  Object.entries(connections.frontend).forEach(([key, frontend]) => {
    if (!frontend.path) return;
    
    // Normalize path (remove /api/v1 prefix if present)
    let normalizedPath = frontend.path;
    if (normalizedPath.startsWith('/api/v1')) {
      normalizedPath = normalizedPath.substring(7);
    } else if (!normalizedPath.startsWith('/')) {
      normalizedPath = '/' + normalizedPath;
    }
    
    // Try to find matching backend endpoint
    const backendKey = `${frontend.method || 'GET'}:/api/v1${normalizedPath}`;
    const backendAltKey = `${frontend.method || 'GET'}:${normalizedPath}`;
    
    let status = 'missing';
    let backendMatch = null;
    
    if (connections.backend[backendKey]) {
      status = 'connected';
      backendMatch = connections.backend[backendKey];
      connections.backend[backendKey].used = true;
    } else if (connections.backend[backendAltKey]) {
      status = 'connected';
      backendMatch = connections.backend[backendAltKey];
      connections.backend[backendAltKey].used = true;
    } else {
      // Check for partial match (might be parameterized route)
      const pathPattern = normalizedPath.replace(/\/\d+/g, '/{id}').replace(/\/[\w-]+$/g, '/{id}');
      const possibleKeys = [
        `${frontend.method || 'GET'}:/api/v1${pathPattern}`,
        `${frontend.method || 'GET'}:${pathPattern}`
      ];
      
      for (const testKey of possibleKeys) {
        if (connections.backend[testKey]) {
          status = 'connected';
          backendMatch = connections.backend[testKey];
          connections.backend[testKey].used = true;
          break;
        }
      }
    }
    
    connections.mappings.push({
      frontend: key,
      frontendDetails: frontend,
      backend: backendMatch,
      status: status
    });
  });
  
  // Find unused backend endpoints
  Object.entries(connections.backend).forEach(([key, backend]) => {
    if (!backend.used) {
      connections.mappings.push({
        frontend: null,
        frontendDetails: null,
        backend: backend,
        status: 'unused'
      });
    }
  });
  
  console.log(`  Created ${connections.mappings.length} mappings`);
}

// Generate HTML report
function generateHTML() {
  console.log('📝 Generating HTML report...');
  
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RuleIQ API Connection Map</title>
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      padding: 20px;
    }
    
    .container {
      max-width: 1400px;
      margin: 0 auto;
      background: white;
      border-radius: 12px;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
      overflow: hidden;
    }
    
    .header {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 30px;
      text-align: center;
    }
    
    .header h1 {
      font-size: 2rem;
      margin-bottom: 10px;
    }
    
    .stats {
      display: flex;
      justify-content: center;
      gap: 40px;
      margin-top: 20px;
    }
    
    .stat {
      text-align: center;
    }
    
    .stat-value {
      font-size: 2rem;
      font-weight: bold;
    }
    
    .stat-label {
      font-size: 0.9rem;
      opacity: 0.9;
    }
    
    .filters {
      padding: 20px 30px;
      background: #f8f9fa;
      display: flex;
      gap: 20px;
      align-items: center;
      border-bottom: 1px solid #e5e7eb;
    }
    
    .filter-btn {
      padding: 8px 16px;
      border: 2px solid #e5e7eb;
      background: white;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }
    
    .filter-btn:hover {
      background: #f3f4f6;
    }
    
    .filter-btn.active {
      background: #667eea;
      color: white;
      border-color: #667eea;
    }
    
    .search-box {
      flex: 1;
      padding: 8px 16px;
      border: 2px solid #e5e7eb;
      border-radius: 6px;
      font-size: 14px;
    }
    
    .connections {
      padding: 30px;
    }
    
    .connection-grid {
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: 20px;
      align-items: stretch;
    }
    
    .column {
      background: #f8f9fa;
      border-radius: 8px;
      padding: 20px;
    }
    
    .column-title {
      font-weight: bold;
      font-size: 1.1rem;
      margin-bottom: 15px;
      color: #374151;
    }
    
    .connection-row {
      display: contents;
    }
    
    .connection-row:hover .endpoint-card {
      transform: translateY(-2px);
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .endpoint-card {
      background: white;
      padding: 12px;
      border-radius: 6px;
      margin-bottom: 10px;
      border: 1px solid #e5e7eb;
      transition: all 0.2s;
      cursor: pointer;
    }
    
    .endpoint-method {
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: bold;
      margin-right: 8px;
    }
    
    .method-GET { background: #d1fae5; color: #065f46; }
    .method-POST { background: #dbeafe; color: #1e40af; }
    .method-PUT { background: #fed7aa; color: #92400e; }
    .method-PATCH { background: #fef3c7; color: #92400e; }
    .method-DELETE { background: #fee2e2; color: #991b1b; }
    
    .endpoint-path {
      font-family: 'Courier New', monospace;
      font-size: 13px;
      color: #4b5563;
      word-break: break-all;
    }
    
    .endpoint-file {
      font-size: 11px;
      color: #9ca3af;
      margin-top: 4px;
    }
    
    .status-indicator {
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }
    
    .status-line {
      width: 100px;
      height: 2px;
      position: relative;
    }
    
    .status-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      position: absolute;
      top: -5px;
      left: 44px;
    }
    
    .status-connected { background: ${STATUS_COLORS.connected}; }
    .status-mismatched { background: ${STATUS_COLORS.mismatched}; }
    .status-missing { background: ${STATUS_COLORS.missing}; }
    .status-unused { background: ${STATUS_COLORS.unused}; }
    
    .legend {
      padding: 20px 30px;
      background: #f8f9fa;
      border-top: 1px solid #e5e7eb;
      display: flex;
      justify-content: center;
      gap: 30px;
    }
    
    .legend-item {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    
    .legend-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }
    
    .empty-state {
      text-align: center;
      padding: 40px;
      color: #6b7280;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>🔗 API Connection Map</h1>
      <p>Frontend-Backend Endpoint Connections for RuleIQ</p>
      <div class="stats">
        <div class="stat">
          <div class="stat-value" id="stat-connected">0</div>
          <div class="stat-label">Connected</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="stat-missing">0</div>
          <div class="stat-label">Missing</div>
        </div>
        <div class="stat">
          <div class="stat-value" id="stat-unused">0</div>
          <div class="stat-label">Unused</div>
        </div>
      </div>
    </div>
    
    <div class="filters">
      <button class="filter-btn active" onclick="filterConnections('all')">All</button>
      <button class="filter-btn" onclick="filterConnections('connected')">✅ Connected</button>
      <button class="filter-btn" onclick="filterConnections('missing')">❌ Missing</button>
      <button class="filter-btn" onclick="filterConnections('unused')">🔄 Unused</button>
      <input type="text" class="search-box" placeholder="Search endpoints..." onkeyup="searchConnections(this.value)">
    </div>
    
    <div class="connections">
      <div class="connection-grid" id="connections-grid">
        <!-- Connections will be inserted here -->
      </div>
    </div>
    
    <div class="legend">
      <div class="legend-item">
        <div class="legend-dot status-connected"></div>
        <span>Connected & Working</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot status-mismatched"></div>
        <span>Path Mismatch</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot status-missing"></div>
        <span>Not Connected</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot status-unused"></div>
        <span>Unused Backend</span>
      </div>
    </div>
  </div>
  
  <script>
    const connections = ${JSON.stringify(connections.mappings, null, 2)};
    let currentFilter = 'all';
    
    function renderConnections(filter = 'all', search = '') {
      const grid = document.getElementById('connections-grid');
      grid.innerHTML = '';
      
      // Add column headers
      grid.innerHTML = \`
        <div class="column">
          <div class="column-title">Frontend (Hooks/Services)</div>
        </div>
        <div></div>
        <div class="column">
          <div class="column-title">Backend Endpoints</div>
        </div>
      \`;
      
      let stats = { connected: 0, missing: 0, unused: 0 };
      
      const filtered = connections.filter(conn => {
        if (filter !== 'all' && conn.status !== filter) return false;
        
        if (search) {
          const searchLower = search.toLowerCase();
          const frontendMatch = conn.frontendDetails && (
            conn.frontend.toLowerCase().includes(searchLower) ||
            (conn.frontendDetails.path && conn.frontendDetails.path.toLowerCase().includes(searchLower))
          );
          const backendMatch = conn.backend && (
            conn.backend.path.toLowerCase().includes(searchLower) ||
            conn.backend.summary.toLowerCase().includes(searchLower)
          );
          return frontendMatch || backendMatch;
        }
        
        return true;
      });
      
      if (filtered.length === 0) {
        grid.innerHTML += \`
          <div class="empty-state" style="grid-column: 1 / -1;">
            No connections found matching your criteria
          </div>
        \`;
        return;
      }
      
      filtered.forEach(conn => {
        stats[conn.status === 'mismatched' ? 'missing' : conn.status]++;
        
        const frontendCard = conn.frontendDetails ? \`
          <div class="endpoint-card">
            <div>
              <span class="endpoint-method method-\${conn.frontendDetails.method || 'GET'}">\${conn.frontendDetails.method || 'HOOK'}</span>
              <span class="endpoint-path">\${conn.frontendDetails.path || conn.frontend}</span>
            </div>
            <div class="endpoint-file">\${conn.frontendDetails.file || ''}</div>
          </div>
        \` : '<div></div>';
        
        const statusIndicator = \`
          <div class="status-indicator">
            <div class="status-line status-\${conn.status}">
              <div class="status-dot status-\${conn.status}"></div>
            </div>
          </div>
        \`;
        
        const backendCard = conn.backend ? \`
          <div class="endpoint-card">
            <div>
              <span class="endpoint-method method-\${conn.backend.method}">\${conn.backend.method}</span>
              <span class="endpoint-path">\${conn.backend.path}</span>
            </div>
            <div class="endpoint-file">\${conn.backend.summary || conn.backend.tags.join(', ') || ''}</div>
          </div>
        \` : '<div></div>';
        
        grid.innerHTML += frontendCard + statusIndicator + backendCard;
      });
      
      // Update stats
      document.getElementById('stat-connected').textContent = stats.connected;
      document.getElementById('stat-missing').textContent = stats.missing;
      document.getElementById('stat-unused').textContent = stats.unused;
    }
    
    function filterConnections(filter) {
      currentFilter = filter;
      document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
      });
      event.target.classList.add('active');
      renderConnections(filter);
    }
    
    function searchConnections(value) {
      renderConnections(currentFilter, value);
    }
    
    // Initial render
    renderConnections();
  </script>
</body>
</html>`;
  
  fs.writeFileSync(OUTPUT_FILE, html);
  console.log(`✅ HTML report generated: ${OUTPUT_FILE}`);
}

// Main execution
async function main() {
  console.log('🚀 Starting API Connection Mapping...\n');
  
  // Scan frontend
  scanHooks();
  scanServices();
  
  // Fetch backend spec
  await fetchBackendSpec();
  
  // Create mappings
  createMappings();
  
  // Generate report
  generateHTML();
  
  console.log('\n✨ Done! Open api-connection-map.html in your browser to view the connections.');
}

// Run if executed directly
if (require.main === module) {
  main().catch(console.error);
}

module.exports = { extractApiCalls, scanHooks, scanServices };