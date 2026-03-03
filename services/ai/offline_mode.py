"""
from __future__ import annotations

# Constants
MAX_RETRIES = 3


Offline Mode Management for AI Services

Provides comprehensive offline capabilities when AI services are unavailable,
including local response generation, offline assessment tools, and
synchronization when services return.
"""
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from services.ai.fallback_system import FallbackResponse


class OfflineMode(Enum):
    """Offline operating modes"""
    DISABLED = 'disabled'
    BASIC = 'basic'
    ENHANCED = 'enhanced'
    FULL = 'full'


@dataclass
class OfflineRequest:
    """Represents a request made while offline"""
    id: str
    operation: str
    context: Dict[str, Any]
    timestamp: datetime
    user_id: Optional[str] = None
    status: str = 'pending'
    priority: int = 1


@dataclass
class OfflineCapability:
    """Describes what's available in offline mode"""
    operation: str
    available: bool
    degradation_level: str
    description: str
    alternatives: List[str] = field(default_factory=list)


class OfflineDatabase:
    """Local SQLite database for offline operation"""

    def __init__(self, db_path: Optional[str]=None) ->None:
        if db_path is None:
            try:
                from config.ai_config import ai_config
                db_path = ai_config.get_offline_config().get('database_path',
                    'data/offline_ai.db')
            except ImportError:
                db_path = 'data/offline_ai.db'
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        self._initialize_database()

    def _initialize_database(self) ->None:
        """Initialize the offline database schema"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_requests (
                    id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    context TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    user_id TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                )
            """
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS cached_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    response TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_used TEXT DEFAULT CURRENT_TIMESTAMP,
                    use_count INTEGER DEFAULT 0,
                    UNIQUE(operation, context_hash),
                )
            """
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_type TEXT NOT NULL,
                    subtype TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(template_type, subtype),
                )
            """
                )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS service_status (
                    service_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    last_check TEXT NOT NULL,
                    consecutive_failures INTEGER DEFAULT 0,
                    last_success TEXT,
                )
            """
                )
            conn.commit()
            self.logger.info('Offline database initialized')

    def store_offline_request(self, request: OfflineRequest) ->None:
        """Store a request made while offline"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO offline_requests                (id, operation, context, timestamp, user_id, status, priority)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
                , (request.id, request.operation, json.dumps(request.
                context), request.timestamp.isoformat(), request.user_id,
                request.status, request.priority))
            conn.commit()

    def get_pending_requests(self) ->List[OfflineRequest]:
        """Get all pending offline requests"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, operation, context, timestamp, user_id, status, priority
                FROM offline_requests                WHERE status = 'pending'
                ORDER BY priority DESC, timestamp ASC
            """
                )
            requests = []
            for row in cursor.fetchall():
                requests.append(OfflineRequest(id=row[0], operation=row[1],
                    context=json.loads(row[2]), timestamp=datetime.
                    fromisoformat(row[3]), user_id=row[4], status=row[5],
                    priority=row[6]))
            return requests

    def update_request_status(self, request_id: str, status: str) ->None:
        """Update the status of an offline request"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE offline_requests
                SET status = ?                WHERE id = ?
            """
                , (status, request_id))
            conn.commit()

    def store_cached_response(self, operation: str, context_hash: str,
        response: str, confidence: float) ->None:
        """Store a cached response for offline use"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO cached_responses                (operation, context_hash, response, confidence, last_used, use_count)
                VALUES (?, ?, ?, ?, ?, COALESCE((SELECT use_count FROM cached_responses WHERE operation = ? AND context_hash = ?), 0) + 1)
            """
                , (operation, context_hash, response, confidence, datetime.
                now().isoformat(), operation, context_hash))
            conn.commit()

    def get_cached_response(self, operation: str, context_hash: str
        ) ->Optional[Tuple[str, float]]:
        """Get a cached response for offline use"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT response, confidence
                FROM cached_responses
                WHERE operation = ? AND context_hash = ?
            """
                , (operation, context_hash))
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    """
                    UPDATE cached_responses
                    SET last_used = ?, use_count = use_count + 1
                    WHERE operation = ? AND context_hash = ?
                """
                    , (datetime.now().isoformat(), operation, context_hash))
                conn.commit()
                return result[0], result[1]
            return None


class OfflineAssessmentTools:
    """Provides offline assessment capabilities"""

    def __init__(self) ->None:
        self.logger = logging.getLogger(__name__)
        self.frameworks = self._initialize_frameworks()

    def _initialize_frameworks(self) ->Dict[str, Dict[str, Any]]:
        """Initialize offline framework assessment tools"""
        return {'gdpr': {'name': 'General Data Protection Regulation',
            'basic_questions': [
            'Do you process personal data of EU residents?',
            'Have you identified your lawful basis for processing?',
            'Do you have procedures for data subject rights?',
            'Have you appointed a Data Protection Officer (if required)?',
            'Do you have data breach notification procedures?',
            'Have you conducted Privacy Impact Assessments where required?',
            'Do you have appropriate technical and organizational measures?',
            'Have you reviewed your data sharing agreements?'], 'scoring':
            {'high_risk': '0-3 yes answers', 'medium_risk':
            '4-6 yes answers', 'low_risk': '7-8 yes answers'}}, 'iso27001':
            {'name': 'ISO 27001 Information Security', 'basic_questions': [
            'Do you have a documented information security policy?',
            'Have you conducted an information security risk assessment?',
            'Do you maintain an asset inventory?',
            'Do you have access control procedures?',
            'Are software and systems regularly updated?',
            'Do you have incident response procedures?',
            'Is security awareness training provided to staff?',
            'Do you regularly monitor and review security controls?'],
            'scoring': {'high_risk': '0-3 yes answers', 'medium_risk':
            '4-6 yes answers', 'low_risk': '7-8 yes answers'}}, 'general':
            {'name': 'General Compliance Assessment', 'basic_questions': [
            'Do you have documented compliance policies?',
            'Are staff trained on relevant regulations?',
            'Do you regularly assess compliance risks?',
            'Are compliance responsibilities clearly assigned?',
            'Do you have incident reporting procedures?',
            'Is compliance monitoring performed regularly?',
            'Are third-party relationships managed for compliance?',
            'Do you maintain compliance documentation?'], 'scoring': {
            'high_risk': '0-3 yes answers', 'medium_risk':
            '4-6 yes answers', 'low_risk': '7-8 yes answers'}}}

    def get_basic_assessment(self, framework: str='general') ->Dict[str, Any]:
        """Get basic offline assessment for a framework"""
        framework_data = self.frameworks.get(framework.lower(), self.
            frameworks['general'])
        return {'framework': framework_data['name'], 'assessment_type':
            'basic_offline', 'questions': framework_data['basic_questions'],
            'scoring_guide': framework_data['scoring'], 'instructions':
            """
This is a basic offline assessment. Answer each question with 'Yes' or 'No':
- Count your 'Yes' answers
- Use the scoring guide to determine your risk level
- For detailed recommendations, use the full online assessment when available
            """
            , 'limitations': ['Simplified assessment - not comprehensive',
            'No personalized recommendations',
            'Limited to basic compliance areas', 'Results are indicative only']
            }

    def calculate_basic_score(self, framework: str, yes_answers: int) ->Dict[
        str, Any]:
        """Calculate basic assessment score"""
        framework_data = self.frameworks.get(framework.lower(), self.
            frameworks['general'])
        total_questions = len(framework_data['basic_questions'])
        if yes_answers <= MAX_RETRIES:
            risk_level = 'high_risk'
            risk_description = 'High risk - immediate attention required'
        elif yes_answers <= 6:
            risk_level = 'medium_risk'
            risk_description = 'Medium risk - improvements needed'
        else:
            risk_level = 'low_risk'
            risk_description = 'Low risk - maintain current practices'
        return {'framework': framework_data['name'], 'total_questions':
            total_questions, 'yes_answers': yes_answers, 'score_percentage':
            yes_answers / total_questions * 100, 'risk_level': risk_level,
            'risk_description': risk_description, 'next_steps': self.
            _get_basic_recommendations(risk_level), 'assessment_date':
            datetime.now().isoformat(), 'assessment_type': 'basic_offline'}

    def _get_basic_recommendations(self, risk_level: str) ->List[str]:
        """Get basic recommendations based on risk level"""
        recommendations = {'high_risk': [
            'Prioritize establishing basic compliance documentation',
            'Seek expert consultation immediately',
            'Implement fundamental security controls',
            'Schedule comprehensive compliance assessment'], 'medium_risk':
            ['Review and strengthen existing policies',
            'Enhance staff training programs',
            'Improve monitoring and reporting procedures',
            'Consider expert review of current practices'], 'low_risk': [
            'Maintain current good practices',
            'Continue regular monitoring and updates',
            'Stay informed of regulatory changes',
            'Conduct periodic comprehensive reviews']}
        return recommendations.get(risk_level, recommendations['medium_risk'])


class OfflineModeManager:
    """
    Comprehensive offline mode management system
    """

    def __init__(self, mode: OfflineMode=OfflineMode.ENHANCED) ->None:
        self.mode = mode
        self.database = OfflineDatabase()
        self.assessment_tools = OfflineAssessmentTools()
        self.logger = logging.getLogger(__name__)
        self.offline_stats = {'requests_served': 0, 'cache_hits': 0,
            'template_uses': 0, 'assessment_completions': 0}
        self.service_status = {'ai_service': False, 'last_check': datetime.
            now(), 'consecutive_failures': 0}

    def is_offline_mode_active(self) ->bool:
        """Check if offline mode is currently active"""
        return not self.service_status['ai_service'
            ] and self.mode != OfflineMode.DISABLED

    def get_offline_capabilities(self) ->List[OfflineCapability]:
        """Get list of available offline capabilities"""
        capabilities = []
        if self.mode == OfflineMode.DISABLED:
            return capabilities
        capabilities.append(OfflineCapability(operation='basic_assessment',
            available=True, degradation_level='major', description=
            'Simplified compliance assessment with basic scoring',
            alternatives=[
            'Use online comprehensive assessment when available']))
        if self.mode in [OfflineMode.ENHANCED, OfflineMode.FULL]:
            capabilities.extend([OfflineCapability(operation=
                'assessment_help', available=True, degradation_level=
                'minor', description=
                'Static guidance templates for common frameworks',
                alternatives=['Contact support for personalized guidance']),
                OfflineCapability(operation='cached_responses', available=
                True, degradation_level='minor', description=
                'Previously generated responses for similar contexts',
                alternatives=['Request fresh analysis when online'])])
        if self.mode == OfflineMode.FULL:
            capabilities.extend([OfflineCapability(operation=
                'request_queuing', available=True, degradation_level='none',
                description=
                'Queue requests for processing when service returns',
                alternatives=[]), OfflineCapability(operation=
                'offline_reporting', available=True, degradation_level=
                'minor', description='Generate basic compliance reports',
                alternatives=['Use advanced reporting when online'])])
        return capabilities

    def handle_offline_request(self, operation: str, context: Dict[str, Any
        ], user_id: Optional[str]=None) ->FallbackResponse:
        """Handle a request when in offline mode"""
        if self.mode == OfflineMode.DISABLED:
            raise Exception('Offline mode is disabled')
        self.offline_stats['requests_served'] += 1
        if self.mode in [OfflineMode.ENHANCED, OfflineMode.FULL]:
            cached_response = self._get_cached_response(operation, context)
            if cached_response:
                self.offline_stats['cache_hits'] += 1
                return cached_response
        if operation == 'basic_assessment':
            return self._handle_basic_assessment(context)
        elif operation == 'assessment_help':
            return self._handle_assessment_help(context)
        elif operation in ['assessment_analysis', 'assessment_recommendations'
            ]:
            return self._handle_complex_operation(operation, context, user_id)
        else:
            return self._handle_unknown_operation(operation, context)

    def _get_cached_response(self, operation: str, context: Dict[str, Any]
        ) ->Optional[FallbackResponse]:
        """Get cached response if available"""
        context_hash = self._generate_context_hash(context)
        cached = self.database.get_cached_response(operation, context_hash)
        if cached:
            response_text, confidence = cached
            return FallbackResponse(content=response_text, confidence=
                confidence, source='offline_cache', metadata={'operation':
                operation, 'cache_hit': True, 'offline_mode': True})
        return None

    def _handle_basic_assessment(self, context: Dict[str, Any]
        ) ->FallbackResponse:
        """Handle basic assessment request"""
        framework = context.get('framework', 'general')
        yes_answers = context.get('yes_answers')
        if yes_answers is not None:
            result = self.assessment_tools.calculate_basic_score(framework,
                yes_answers)
            self.offline_stats['assessment_completions'] += 1
            content = f"""**Basic {result['framework']} Assessment Results**

**Score:** {result['score_percentage']:.1f}% ({result['yes_answers']}/{result['total_questions']} criteria met)
**Risk Level:** {result['risk_description']}

**Immediate Next Steps:**
{chr(10).join(f'• {rec}' for rec in result['next_steps'])}

*Note: This is a simplified offline assessment. For comprehensive analysis and personalized recommendations, please use the full online assessment when available.*"""
        else:
            assessment = self.assessment_tools.get_basic_assessment(framework)
            content = f"""**{assessment['framework']} - Basic Assessment**

{assessment['instructions']}

**Assessment Questions:**
{chr(10).join(f'{i + 1}. {q}' for i, q in enumerate(assessment['questions']))}

**Scoring Guide:**
{chr(10).join(f'• {level}: {desc}' for level, desc in assessment['scoring_guide'].items())}

**Limitations:**
{chr(10).join(f'• {limitation}' for limitation in assessment['limitations'])}"""
        return FallbackResponse(content=content, confidence=0.7, source=
            'offline_assessment', metadata={'framework': framework,
            'offline_mode': True, 'assessment_type': 'basic'})

    def _handle_assessment_help(self, context: Dict[str, Any]
        ) ->FallbackResponse:
        """Handle assessment help request"""
        from services.ai.fallback_system import get_fallback_system
        fallback_system = get_fallback_system()
        self.offline_stats['template_uses'] += 1
        return fallback_system.get_fallback_response('assessment_help', context
            )

    def _handle_complex_operation(self, operation: str, context: Dict[str,
        Any], user_id: Optional[str]) ->FallbackResponse:
        """Handle complex operations that require queuing"""
        if self.mode == OfflineMode.FULL:
            request_id = (
                f"offline_{operation}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                ,)
            offline_request = OfflineRequest(id=request_id, operation=
                operation, context=context, timestamp=datetime.now(),
                user_id=user_id, priority=3 if 'critical' in context else 2)
            self.database.store_offline_request(offline_request)
            content = f"""**Request Queued for Processing**

Your {operation.replace('_', ' ')} request has been queued and will be processed automatically when AI services are restored.

**Request ID:** {request_id}
**Estimated Processing:** When services return online
**Priority:** {'High' if offline_request.priority >= MAX_RETRIES else 'Standard'}

You will be notified when the analysis is complete. In the meantime, you can:
• Use the basic assessment tools available offline
• Review static guidance templates
• Contact support for urgent assistance"""
            return FallbackResponse(content=content, confidence=0.9, source
                ='offline_queue', metadata={'request_id': request_id,
                'queued': True, 'offline_mode': True})
        else:
            return FallbackResponse(content=
                f"The {operation.replace('_', ' ')} service is currently unavailable offline. Please try again when AI services are restored, or use the basic assessment tools available."
                , confidence=0.5, source='offline_unavailable', metadata={
                'offline_mode': True, 'operation': operation})

    def _handle_unknown_operation(self, operation: str, context: Dict[str, Any]
        ) ->FallbackResponse:
        """Handle unknown operations"""
        return FallbackResponse(content=
            f'The {operation} operation is not available in offline mode. Please try again when AI services are restored.'
            , confidence=0.3, source='offline_unavailable', metadata={
            'offline_mode': True, 'operation': operation})

    def _generate_context_hash(self, context: Dict[str, Any]) ->str:
        """Generate a hash for context to use as cache key"""
        import hashlib
        key_elements = []
        for key in sorted(context.keys()):
            if key in ['framework', 'business_type', 'complexity', 'industry']:
                key_elements.append(f'{key}:{context[key]}')
        context_string = '|'.join(key_elements)
        # Use SHA-256 instead of MD5 for security compliance, truncated for cache key compatibility
        return hashlib.sha256(context_string.encode()).hexdigest()[:16]

    def sync_offline_requests(self) ->Dict[str, Any]:
        """Synchronize queued offline requests when service returns"""
        if self.service_status['ai_service']:
            pending_requests = self.database.get_pending_requests()
            return {'pending_requests': len(pending_requests),
                'sync_status': 'ready', 'high_priority_requests': len([r for
                r in pending_requests if r.priority >= MAX_RETRIES]),
                'oldest_request': min((r.timestamp for r in
                pending_requests), default=None)}
        return {'sync_status': 'service_unavailable'}

    def update_service_status(self, ai_service_available: bool) ->None:
        """Update the status of AI services"""
        self.service_status['last_check'] = datetime.now()
        if ai_service_available:
            if not self.service_status['ai_service']:
                self.logger.info('AI service restored - exiting offline mode')
                sync_status = self.sync_offline_requests()
                if sync_status['pending_requests'] > 0:
                    self.logger.info('Syncing %s offline requests' %
                        sync_status['pending_requests'])
            self.service_status['ai_service'] = True
            self.service_status['consecutive_failures'] = 0
        else:
            if self.service_status['ai_service']:
                self.logger.warning(
                    'AI service unavailable - entering offline mode')
            self.service_status['ai_service'] = False
            self.service_status['consecutive_failures'] += 1

    def get_offline_status(self) ->Dict[str, Any]:
        """Get comprehensive offline mode status"""
        return {'offline_mode': self.mode.value, 'is_active': self.
            is_offline_mode_active(), 'service_status': self.service_status
            .copy(), 'capabilities': [cap.__dict__ for cap in self.
            get_offline_capabilities()], 'statistics': self.offline_stats.
            copy(), 'pending_requests': len(self.database.
            get_pending_requests())}


_offline_manager: Optional[OfflineModeManager] = None


def get_offline_manager(mode: OfflineMode=OfflineMode.ENHANCED
    ) ->OfflineModeManager:
    """Get global offline mode manager instance"""
    global _offline_manager
    if _offline_manager is None:
        _offline_manager = OfflineModeManager(mode)
    return _offline_manager


def reset_offline_manager() ->None:
    """Reset global offline manager (for testing)"""
    global _offline_manager
    _offline_manager = None
