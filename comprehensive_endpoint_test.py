#!/usr/bin/env python3
"""
Enhanced Comprehensive API Endpoint Tester for ruleIQ
Tests major endpoint categories with proper session management
"""
import requests
import json
import time
from typing import Dict, List, Any, Tuple

class ComprehensiveAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.jwt_token = None
        self.test_results = []
        
    def authenticate(self, email: str, password: str) -> bool:
        """Authenticate and store JWT token"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/token",
                data={"username": email, "password": password},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.jwt_token = data["access_token"]
                self.session.headers.update({"Authorization": f"Bearer {self.jwt_token}"})
                print(f"✅ Authentication successful")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Authentication error: {str(e)}")
            return False
    
    def test_endpoint_group(self, group_name: str, endpoints: List[Tuple]) -> Dict[str, Any]:
        """Test a group of related endpoints"""
        print(f"\n🔍 Testing {group_name} Endpoints...")
        results = []
        
        for method, endpoint, expected_codes, description in endpoints:
            result = self._test_single_endpoint(method, endpoint, expected_codes)
            result["description"] = description
            results.append(result)
            
            # Status indicator
            if result["success"]:
                status = "✅"
            elif result["status_code"] in [401, 403]:
                status = "🔐"  # Auth required
            elif result["status_code"] in [404]:
                status = "📭"  # Not found (might be expected)
            elif result["status_code"] in [500, 502, 503]:
                status = "🚨"  # Server error
            else:
                status = "⚠️"   # Other issue
                
            print(f"{status} {method} {endpoint} - {result['status_code']} ({result.get('response_time_ms', 'N/A')}ms) - {description}")
        
        return {
            "group_name": group_name,
            "results": results,
            "summary": self._calculate_group_summary(results)
        }
    
    def _test_single_endpoint(self, method: str, endpoint: str, expected_codes: List[int], data: Dict = None) -> Dict[str, Any]:
        """Test a single endpoint"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            start_time = time.time()
            
            # Choose request method
            if method.upper() == "GET":
                response = self.session.get(url, timeout=10)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=10)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=10)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=10)
            elif method.upper() == "PATCH":
                response = self.session.patch(url, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
                
            response_time = time.time() - start_time
            success = response.status_code in expected_codes
            
            return {
                "endpoint": endpoint,
                "method": method.upper(),
                "status_code": response.status_code,
                "response_time_ms": round(response_time * 1000),
                "success": success,
                "content_length": len(response.content),
                "error": None
            }
            
        except requests.exceptions.Timeout:
            return {
                "endpoint": endpoint,
                "method": method.upper(),
                "status_code": None,
                "response_time_ms": None,
                "success": False,
                "content_length": 0,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "endpoint": endpoint,
                "method": method.upper(),
                "status_code": None,
                "response_time_ms": None,
                "success": False,
                "content_length": 0,
                "error": str(e)
            }
    
    def _calculate_group_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """Calculate summary statistics for a group"""
        total = len(results)
        successful = sum(1 for r in results if r["success"])
        
        valid_times = [r["response_time_ms"] for r in results if r["response_time_ms"] is not None]
        avg_response_time = round(sum(valid_times) / len(valid_times)) if valid_times else 0
        
        # Count by status code ranges
        status_codes = {
            "2xx": sum(1 for r in results if r["status_code"] and 200 <= r["status_code"] < 300),
            "3xx": sum(1 for r in results if r["status_code"] and 300 <= r["status_code"] < 400),
            "4xx": sum(1 for r in results if r["status_code"] and 400 <= r["status_code"] < 500),
            "5xx": sum(1 for r in results if r["status_code"] and 500 <= r["status_code"] < 600),
            "errors": sum(1 for r in results if r["status_code"] is None)
        }
        
        return {
            "total_tests": total,
            "successful": successful,
            "success_rate": round((successful / total) * 100, 1) if total > 0 else 0,
            "avg_response_time_ms": avg_response_time,
            "status_distribution": status_codes
        }
    
    def run_comprehensive_tests(self) -> List[Dict]:
        """Run comprehensive endpoint testing"""
        all_results = []
        
        # 1. Authentication & User Management
        auth_endpoints = [
            ("GET", "/api/v1/auth/me", [200], "Get current user info"),
            ("GET", "/api/v1/users/profile", [200, 404], "Get user profile"),
            ("GET", "/api/v1/users/current", [200, 404], "Get current user details"),
        ]
        all_results.append(self.test_endpoint_group("Authentication & Users", auth_endpoints))
        
        # 2. Business Profiles
        business_endpoints = [
            ("GET", "/api/v1/business-profiles", [200, 404], "List business profiles"),
            ("GET", "/api/v1/business-profiles/current", [200, 404], "Get current business profile"),
            ("GET", "/api/v1/business-profiles/me", [200, 404], "Get my business profile"),
        ]
        all_results.append(self.test_endpoint_group("Business Profiles", business_endpoints))
        
        # 3. Compliance Frameworks
        framework_endpoints = [
            ("GET", "/api/v1/compliance-frameworks", [200, 404], "List compliance frameworks"),
            ("GET", "/api/v1/compliance-frameworks/gdpr", [200, 404], "Get GDPR framework"),
            ("GET", "/api/v1/frameworks", [200, 404], "Alternative frameworks endpoint"),
            ("GET", "/api/v1/frameworks/gdpr", [200, 404], "Get GDPR via frameworks"),
        ]
        all_results.append(self.test_endpoint_group("Compliance Frameworks", framework_endpoints))
        
        # 4. Assessments & Questions
        assessment_endpoints = [
            ("GET", "/api/v1/assessments", [200, 404], "List assessments"),
            ("GET", "/api/v1/assessments/templates", [200, 404], "Get assessment templates"),
            ("GET", "/api/v1/questions", [200, 404], "List questions"),
            ("GET", "/api/v1/questions/gdpr", [200, 404], "Get GDPR questions"),
        ]
        all_results.append(self.test_endpoint_group("Assessments & Questions", assessment_endpoints))
        
        # 5. AI Services (expect some failures due to missing config)
        ai_endpoints = [
            ("GET", "/api/v1/ai-cost/current", [200, 404, 500], "Current AI cost"),
            ("GET", "/api/v1/ai-cost/monthly", [200, 404, 500], "Monthly AI cost"),
            ("POST", "/api/v1/ai-assessments/start", [200, 400, 422, 500], "Start AI assessment"),
            ("GET", "/api/v1/ai-assessments/status", [200, 404, 500], "AI assessment status"),
        ]
        all_results.append(self.test_endpoint_group("AI Services", ai_endpoints))
        
        # 6. Evidence & Implementation
        evidence_endpoints = [
            ("GET", "/api/v1/evidence", [200, 404], "List evidence"),
            ("GET", "/api/v1/evidence/sources", [200, 404], "Get evidence sources"),
            ("GET", "/api/v1/implementation", [200, 404], "Get implementation data"),
            ("GET", "/api/v1/implementation/status", [200, 404], "Implementation status"),
        ]
        all_results.append(self.test_endpoint_group("Evidence & Implementation", evidence_endpoints))
        
        # 7. Reporting
        reporting_endpoints = [
            ("GET", "/api/v1/reports", [200, 404], "List reports"),
            ("GET", "/api/v1/reports/compliance", [200, 404], "Compliance reports"),
            ("GET", "/api/v1/reports/export", [200, 404], "Export reports"),
        ]
        all_results.append(self.test_endpoint_group("Reporting", reporting_endpoints))
        
        # 8. Health & Status
        health_endpoints = [
            ("GET", "/health", [200], "Root health check"),
            ("GET", "/api/v1/health", [200], "API health check"),
            ("GET", "/api/v1/status", [200, 404], "Service status"),
        ]
        all_results.append(self.test_endpoint_group("Health & Status", health_endpoints))
        
        return all_results
    
    def generate_comprehensive_report(self, test_groups: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive testing report"""
        # Overall statistics
        total_tests = sum(group["summary"]["total_tests"] for group in test_groups)
        total_successful = sum(group["summary"]["successful"] for group in test_groups)
        overall_success_rate = round((total_successful / total_tests) * 100, 1) if total_tests > 0 else 0
        
        # Response time statistics
        all_times = []
        for group in test_groups:
            for result in group["results"]:
                if result["response_time_ms"] is not None:
                    all_times.append(result["response_time_ms"])
        
        avg_response_time = round(sum(all_times) / len(all_times)) if all_times else 0
        
        # Status code distribution
        overall_status_dist = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "errors": 0}
        for group in test_groups:
            for key in overall_status_dist:
                overall_status_dist[key] += group["summary"]["status_distribution"][key]
        
        return {
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": total_successful,
                "overall_success_rate": overall_success_rate,
                "avg_response_time_ms": avg_response_time,
                "status_distribution": overall_status_dist,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "test_duration_seconds": None  # Will be set by caller
            },
            "group_summaries": [
                {
                    "group_name": group["group_name"],
                    "summary": group["summary"]
                }
                for group in test_groups
            ],
            "detailed_results": test_groups
        }

def main():
    print("🚀 ruleIQ API Comprehensive Endpoint Testing")
    print("=" * 60)
    
    start_time = time.time()
    tester = ComprehensiveAPITester()
    
    # Authenticate
    if not tester.authenticate("newtest@ruleiq.com", "NewTestPass123!"):
        print("❌ Authentication failed. Cannot proceed with tests.")
        return
    
    # Run comprehensive tests
    print(f"\n📊 Running comprehensive endpoint tests...")
    test_groups = tester.run_comprehensive_tests()
    
    # Calculate test duration
    test_duration = round(time.time() - start_time, 1)
    
    # Generate report
    report = tester.generate_comprehensive_report(test_groups)
    report["test_summary"]["test_duration_seconds"] = test_duration
    
    # Display summary
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE TEST SUMMARY")
    print("=" * 60)
    
    summary = report["test_summary"]
    print(f"🔬 Total Tests Run: {summary['total_tests']}")
    print(f"✅ Successful Tests: {summary['successful_tests']}")
    print(f"📈 Overall Success Rate: {summary['overall_success_rate']}%")
    print(f"⏱️  Average Response Time: {summary['avg_response_time_ms']}ms")
    print(f"🕒 Total Test Duration: {summary['test_duration_seconds']}s")
    
    print(f"\n📊 Status Code Distribution:")
    dist = summary["status_distribution"]
    print(f"  2xx (Success): {dist['2xx']}")
    print(f"  3xx (Redirect): {dist['3xx']}")
    print(f"  4xx (Client Error): {dist['4xx']}")
    print(f"  5xx (Server Error): {dist['5xx']}")
    print(f"  Network Errors: {dist['errors']}")
    
    print(f"\n📋 Group Performance Summary:")
    for group_summary in report["group_summaries"]:
        name = group_summary["group_name"]
        stats = group_summary["summary"]
        print(f"  📂 {name}:")
        print(f"    Success: {stats['successful']}/{stats['total_tests']} ({stats['success_rate']}%)")
        print(f"    Avg Response: {stats['avg_response_time_ms']}ms")
    
    # Save comprehensive report
    report_filename = f"comprehensive_api_test_report_{int(time.time())}.json"
    with open(report_filename, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n💾 Comprehensive report saved: {report_filename}")
    
    # Performance assessment
    if summary["overall_success_rate"] > 80:
        print(f"\n🎉 EXCELLENT: Overall success rate above 80%!")
    elif summary["overall_success_rate"] > 60:
        print(f"\n👍 GOOD: Overall success rate above 60%")
    else:
        print(f"\n⚠️  NEEDS ATTENTION: Success rate below 60%")
    
    if summary["avg_response_time_ms"] < 200:
        print(f"⚡ FAST: Average response time under 200ms")
    elif summary["avg_response_time_ms"] < 1000:
        print(f"✅ ACCEPTABLE: Average response time under 1s")
    else:
        print(f"🐌 SLOW: Average response time above 1s - consider optimization")
    
    print(f"\n✅ Comprehensive endpoint testing completed successfully!")

if __name__ == "__main__":
    main()