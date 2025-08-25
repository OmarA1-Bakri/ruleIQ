#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BACKEND_URL = 'http://localhost:8000';

console.log('🔍 RuleIQ API Connection Deep Analysis\n');
console.log('=' .repeat(80));

// Fetch backend OpenAPI spec
function fetchBackendSpec() {
  try {
    const specJson = execSync(`curl -s ${BACKEND_URL}/openapi.json`, { encoding: 'utf8' });
    return JSON.parse(specJson);
  } catch (error) {
    console.error('❌ Failed to fetch backend OpenAPI spec:', error.message);
    process.exit(1);
  }
}

// Extract API calls from frontend files
function extractFrontendCalls() {
  const apiDir = path.join(process.cwd(), 'frontend/lib/api');
  const files = fs.readdirSync(apiDir).filter(f => f.endsWith('.service.ts'));
  
  const calls = new Map();
  
  files.forEach(file => {
    const filePath = path.join(apiDir, file);
    const content = fs.readFileSync(filePath, 'utf8');
    
    // Pattern to match apiClient method calls
    const pattern = /apiClient\.(get|post|put|patch|delete|request|publicGet|publicPost|publicRequest)<[^>]*>\(['"`]([^'"`]+)['"`]/g;
    
    let match;
    while ((match = pattern.exec(content)) !== null) {
      const method = match[1].toUpperCase();
      const endpoint = match[2];
      
      // Track line number for debugging
      const lineNum = content.substring(0, match.index).split('\n').length;
      
      if (!calls.has(endpoint)) {
        calls.set(endpoint, []);
      }
      
      calls.get(endpoint).push({
        file: file,
        method: method,
        line: lineNum
      });
    }
  });
  
  return calls;
}

// Analyze the connections
function analyzeConnections() {
  console.log('\n📊 Fetching Backend OpenAPI Specification...');
  const spec = fetchBackendSpec();
  
  console.log('\n🔍 Extracting Frontend API Calls...');
  const frontendCalls = extractFrontendCalls();
  
  console.log('\n📈 Analysis Results:\n');
  
  // Get all backend endpoints
  const backendEndpoints = Object.keys(spec.paths);
  
  // Categorize connections
  const results = {
    perfectMatch: [],
    trailingSlashIssue: [],
    prefixIssue: [],
    completelyMissing: [],
    unusedBackend: new Set(backendEndpoints)
  };
  
  // Check each frontend call
  frontendCalls.forEach((locations, endpoint) => {
    // What the frontend actually calls after client.ts transformation
    const actualCall = endpoint.startsWith('/api') ? endpoint : `/api/v1${endpoint}`;
    
    // Check for exact match
    if (backendEndpoints.includes(actualCall)) {
      results.perfectMatch.push({ frontend: endpoint, backend: actualCall, locations });
      results.unusedBackend.delete(actualCall);
    }
    // Check with trailing slash
    else if (backendEndpoints.includes(actualCall + '/')) {
      results.trailingSlashIssue.push({ 
        frontend: endpoint, 
        actualCall: actualCall,
        backend: actualCall + '/', 
        locations 
      });
      results.unusedBackend.delete(actualCall + '/');
    }
    // Check without trailing slash
    else if (actualCall.endsWith('/') && backendEndpoints.includes(actualCall.slice(0, -1))) {
      results.trailingSlashIssue.push({ 
        frontend: endpoint, 
        actualCall: actualCall,
        backend: actualCall.slice(0, -1), 
        locations 
      });
      results.unusedBackend.delete(actualCall.slice(0, -1));
    }
    // Check for similar endpoints (might be parameter mismatch)
    else {
      const baseCall = actualCall.split('?')[0]; // Remove query params
      const similar = backendEndpoints.filter(be => {
        const beBase = be.replace(/{[^}]+}/g, '*'); // Replace path params with *
        const callBase = baseCall.replace(/\/\d+/g, '/*'); // Replace numeric IDs with *
        return beBase === callBase || beBase === callBase + '/';
      });
      
      if (similar.length > 0) {
        results.prefixIssue.push({ 
          frontend: endpoint, 
          actualCall: actualCall,
          similar: similar, 
          locations 
        });
        similar.forEach(s => results.unusedBackend.delete(s));
      } else {
        results.completelyMissing.push({ 
          frontend: endpoint, 
          actualCall: actualCall,
          locations 
        });
      }
    }
  });
  
  // Print results
  console.log(`✅ Perfect Matches: ${results.perfectMatch.length}`);
  if (results.perfectMatch.length > 0 && results.perfectMatch.length <= 20) {
    results.perfectMatch.forEach(m => {
      console.log(`   - ${m.frontend} → ${m.backend}`);
    });
  }
  
  console.log(`\n⚠️  Trailing Slash Issues: ${results.trailingSlashIssue.length}`);
  if (results.trailingSlashIssue.length > 0) {
    console.log('   These would work if we fix the trailing slash:');
    results.trailingSlashIssue.slice(0, 10).forEach(m => {
      console.log(`   - Frontend: ${m.frontend}`);
      console.log(`     Becomes:  ${m.actualCall}`);
      console.log(`     Backend:  ${m.backend}`);
      console.log(`     Used in:  ${m.locations[0].file}:${m.locations[0].line}`);
    });
    if (results.trailingSlashIssue.length > 10) {
      console.log(`   ... and ${results.trailingSlashIssue.length - 10} more`);
    }
  }
  
  console.log(`\n🔧 Path Parameter Issues: ${results.prefixIssue.length}`);
  if (results.prefixIssue.length > 0) {
    console.log('   These need path parameter adjustments:');
    results.prefixIssue.slice(0, 10).forEach(m => {
      console.log(`   - Frontend: ${m.frontend}`);
      console.log(`     Similar:  ${m.similar.join(', ')}`);
    });
    if (results.prefixIssue.length > 10) {
      console.log(`   ... and ${results.prefixIssue.length - 10} more`);
    }
  }
  
  console.log(`\n❌ Completely Missing: ${results.completelyMissing.length}`);
  if (results.completelyMissing.length > 0) {
    console.log('   These frontend calls have no backend equivalent:');
    results.completelyMissing.slice(0, 10).forEach(m => {
      console.log(`   - ${m.frontend} (${m.locations[0].file}:${m.locations[0].line})`);
    });
    if (results.completelyMissing.length > 10) {
      console.log(`   ... and ${results.completelyMissing.length - 10} more`);
    }
  }
  
  console.log(`\n📦 Unused Backend Endpoints: ${results.unusedBackend.size}`);
  if (results.unusedBackend.size > 0 && results.unusedBackend.size <= 20) {
    console.log('   These backend endpoints are not called by frontend:');
    Array.from(results.unusedBackend).slice(0, 20).forEach(endpoint => {
      console.log(`   - ${endpoint}`);
    });
  }
  
  // Generate fix recommendations
  console.log('\n' + '='.repeat(80));
  console.log('\n🛠️  RECOMMENDED FIXES:\n');
  
  if (results.trailingSlashIssue.length > 0) {
    console.log('1. Fix Trailing Slash Issues in Backend:');
    console.log('   Option A: Configure FastAPI to ignore trailing slashes');
    console.log('   Option B: Update frontend calls to include trailing slashes');
    console.log(`   This would immediately fix ${results.trailingSlashIssue.length} connections!\n`);
  }
  
  if (results.prefixIssue.length > 0) {
    console.log('2. Fix Path Parameter Patterns:');
    console.log('   Frontend uses /resource/123 but backend expects /resource/{id}');
    console.log(`   This affects ${results.prefixIssue.length} endpoints\n`);
  }
  
  if (results.completelyMissing.length > 0) {
    console.log('3. Implement Missing Backend Endpoints:');
    console.log(`   ${results.completelyMissing.length} frontend calls have no backend implementation`);
    console.log('   These might be planned features or legacy code\n');
  }
  
  // Calculate connection health score
  const totalFrontendCalls = frontendCalls.size;
  const healthScore = ((results.perfectMatch.length / totalFrontendCalls) * 100).toFixed(1);
  
  console.log('='.repeat(80));
  console.log(`\n📊 CONNECTION HEALTH SCORE: ${healthScore}%`);
  console.log(`\nOnly ${results.perfectMatch.length} out of ${totalFrontendCalls} frontend API calls are properly connected!`);
  
  if (results.trailingSlashIssue.length > 0) {
    const potentialScore = (((results.perfectMatch.length + results.trailingSlashIssue.length) / totalFrontendCalls) * 100).toFixed(1);
    console.log(`\n💡 Quick Win: Fixing trailing slashes would improve score to ${potentialScore}%!`);
  }
  
  // Save detailed report
  const report = {
    timestamp: new Date().toISOString(),
    summary: {
      totalFrontendCalls: totalFrontendCalls,
      totalBackendEndpoints: backendEndpoints.length,
      perfectMatches: results.perfectMatch.length,
      trailingSlashIssues: results.trailingSlashIssue.length,
      pathParameterIssues: results.prefixIssue.length,
      completelyMissing: results.completelyMissing.length,
      unusedBackend: results.unusedBackend.size,
      healthScore: parseFloat(healthScore)
    },
    details: results
  };
  
  fs.writeFileSync('api-connection-report.json', JSON.stringify(report, null, 2));
  console.log('\n📄 Detailed report saved to api-connection-report.json');
}

// Run analysis
analyzeConnections();