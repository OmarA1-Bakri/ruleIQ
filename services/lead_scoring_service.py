"""
LeadScoringService - Behavioral analytics and lead scoring engine.

Handles comprehensive lead scoring based on:
1. Assessment engagement patterns
2. Answer quality and completeness
3. Time spent and interaction depth
4. Conversion probability calculation
5. Behavioral event tracking and analytics

Integrates with:
- LeadScoringEvent model for event storage
- AssessmentLead for score updates
- Redis for real-time scoring cache
- Analytics pipeline for conversion insights
"""

import requests
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from database import AssessmentLead, LeadScoringEvent, FreemiumAssessmentSession, ConversionEvent
from config.logging_config import get_logger
from config.cache import get_cache_manager

logger = get_logger(__name__)

# Constants
HTTP_OK = 200
DEFAULT_TIMEOUT = 30
DEFAULT_LIMIT = 100
DEFAULT_RETRIES = 5
MAX_RETRIES = 3


class LeadScoringService:
    """
    Advanced lead scoring service for freemium assessment funnel.

    Implements behavioral analytics, engagement tracking, and
    conversion probability prediction based on user interactions.
    """

    def __init__(self, db_session) -> None:
        self.db = db_session
        self.cache_manager = None
        self.SCORING_RULES = {
            "assessment_start": {"base_score": 15, "category": "engagement"},
            "question_answered": {
                "base_score": 5,
                "category": "assessment",
                "multiplier_field": "answer_quality",
            },
            "assessment_complete": {"base_score": 25, "category": "conversion"},
            "results_viewed": {"base_score": 20, "category": "conversion"},
            "lead_capture": {"base_score": 10, "category": "conversion"},
            "lead_return": {"base_score": 5, "category": "engagement"},
            "email_open": {"base_score": 2, "category": "engagement"},
            "email_click": {"base_score": 8, "category": "engagement"},
            "consultation_booked": {"base_score": 50, "category": "conversion"},
            "trial_signup": {"base_score": 75, "category": "conversion"},
            "demo_requested": {"base_score": 40, "category": "conversion"},
            "pricing_viewed": {"base_score": 15, "category": "intent"},
            "deep_engagement": {"base_score": 12, "category": "engagement"},
            "repeat_visitor": {"base_score": 8, "category": "engagement"},
            "social_share": {"base_score": 6, "category": "engagement"},
            "unsubscribe": {"base_score": -10, "category": "disengagement"},
            "spam_complaint": {"base_score": -25, "category": "disengagement"},
        }
        self.LEAD_QUALIFICATION_THRESHOLDS = {"hot": 75, "warm": 50, "qualified": 25, "cold": 0}

    async def track_event(
        self,
        lead_id: uuid.UUID,
        event_type: str,
        event_category: str,
        event_action: str,
        score_impact: Optional[int] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        page_url: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> LeadScoringEvent:
        """
        Track a lead scoring event and update lead score.

        Args:
            lead_id: UUID of the lead
            event_type: Type of event (assessment_start, question_answered, etc.)
            event_category: Category (engagement, conversion, assessment)
            event_action: Specific action taken
            score_impact: Manual score override (optional)
            session_id: Assessment session ID (optional)
            metadata: Additional event metadata
            page_url: Page where event occurred
            user_agent: User agent string

        Returns:
            LeadScoringEvent: Created event record
        """
        try:
            logger.info("Tracking event for lead %s: %s" % (lead_id, event_type))
            if score_impact is None:
                score_impact = self._calculate_event_score(event_type, metadata or {})
            event_data = {
                "lead_id": lead_id,
                "event_type": event_type,
                "event_category": event_category,
                "event_action": event_action,
                "score_impact": score_impact,
                "event_metadata": metadata or {},
                "page_url": page_url,
                "user_agent": user_agent,
                "created_at": datetime.now(timezone.utc),
            }
            if session_id:
                if isinstance(session_id, str):
                    try:
                        event_data["session_id"] = uuid.UUID(session_id)
                    except ValueError:
                        logger.warning("Invalid session_id format: %s" % session_id)
                else:
                    event_data["session_id"] = session_id
            event = LeadScoringEvent(**event_data)
            self.db.add(event)
            await self._update_lead_score(lead_id, score_impact, event_type)
            if self.cache_manager:
                await self._update_cached_metrics(lead_id, event_type, score_impact)
            await self.db.commit()
            await self.db.refresh(event)
            logger.info(
                "Event tracked successfully: %s, score impact: %s" % (event.id, score_impact)
            )
            return event
        except (KeyError, IndexError) as e:
            logger.error("Error tracking event: %s" % str(e))
            await self.db.rollback()
            raise

    async def calculate_lead_score(self, lead_id: uuid.UUID) -> Dict[str, Any]:
        """
        Calculate comprehensive lead score based on all tracked events.

        Args:
            lead_id: UUID of the lead to score

        Returns:
            Dict containing detailed scoring breakdown
        """
        try:
            logger.info("Calculating comprehensive score for lead: %s" % lead_id)
            from sqlalchemy import select, desc

            result = await self.db.execute(
                select(LeadScoringEvent)
                .where(LeadScoringEvent.lead_id == lead_id)
                .order_by(desc(LeadScoringEvent.created_at))
            )
            events = result.scalars().all()
            if not events:
                return {
                    "total_score": 0,
                    "lead_status": "cold",
                    "conversion_probability": 0.0,
                    "last_activity": None,
                    "event_breakdown": {},
                }
            score_breakdown = {
                "engagement": 0,
                "assessment": 0,
                "conversion": 0,
                "intent": 0,
                "advocacy": 0,
            }
            total_score = 0
            event_counts = {}
            for event in events:
                category = event.event_category or "engagement"
                score_impact = event.score_impact or 0
                if category in score_breakdown:
                    score_breakdown[category] += score_impact
                total_score += score_impact
                event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
            total_score = self._apply_time_decay(events, total_score)
            conversion_probability = self._calculate_conversion_probability(
                total_score, event_counts, events
            )
            lead_status = self._determine_lead_status(total_score)
            engagement_metrics = self._calculate_engagement_metrics(events)
            result = {
                "total_score": total_score,
                "lead_status": lead_status,
                "conversion_probability": conversion_probability,
                "last_activity": events[0].created_at if events else None,
                "event_breakdown": score_breakdown,
                "event_counts": event_counts,
                "engagement_metrics": engagement_metrics,
                "scoring_factors": {
                    "recency": engagement_metrics["days_since_last_activity"],
                    "frequency": len(events),
                    "engagement_depth": engagement_metrics["avg_session_duration"],
                    "conversion_indicators": event_counts.get("results_viewed", 0),
                },
            }
            logger.info(
                "Score calculated: %s (%s) for lead %s" % (total_score, lead_status, lead_id)
            )
            return result
        except (requests.RequestException, Exception, KeyError) as e:
            logger.error("Error calculating lead score: %s" % str(e))
            raise

    async def get_lead_analytics(self, lead_id: uuid.UUID, days_back: int = 30) -> Dict[str, Any]:
        """
        Get comprehensive analytics for a specific lead.

        Args:
            lead_id: UUID of the lead
            days_back: Number of days to include in analysis

        Returns:
            Dict containing detailed lead analytics
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            from sqlalchemy import select, desc, and_

            lead_result = await self.db.execute(
                select(AssessmentLead).where(AssessmentLead.id == lead_id)
            )
            lead = lead_result.scalar_one_or_none()
            if not lead:
                raise ValueError(f"Lead not found: {lead_id}")
            events_result = await self.db.execute(
                select(LeadScoringEvent)
                .where(
                    and_(
                        LeadScoringEvent.lead_id == lead_id,
                        LeadScoringEvent.created_at >= cutoff_date,
                    )
                )
                .order_by(desc(LeadScoringEvent.created_at))
            )
            events = events_result.scalars().all()
            sessions_result = await self.db.execute(
                select(FreemiumAssessmentSession)
                .where(FreemiumAssessmentSession.lead_id == lead_id)
                .order_by(desc(FreemiumAssessmentSession.created_at))
            )
            sessions = sessions_result.scalars().all()
            analytics = {
                "lead_info": {
                    "id": str(lead.id),
                    "email": lead.email,
                    "created_at": lead.created_at.isoformat(),
                    "lead_score": lead.lead_score,
                    "lead_status": lead.lead_status,
                    "last_activity_at": lead.last_activity_at.isoformat()
                    if lead.last_activity_at
                    else None,
                },
                "activity_summary": {
                    "total_events": len(events),
                    "unique_event_types": len(set(e.event_type for e in events)),
                    "assessment_sessions": len(sessions),
                    "completed_assessments": len(
                        [s for s in sessions if s.completion_status == "completed"]
                    ),
                    "days_active": len(set(e.created_at.date() for e in events)),
                },
                "engagement_patterns": self._analyze_engagement_patterns(events),
                "conversion_journey": self._analyze_conversion_journey(events, sessions),
                "behavioral_insights": self._generate_behavioral_insights(events, lead),
                "next_best_actions": self._suggest_next_actions(events, sessions, lead),
            }
            return analytics
        except (Exception, KeyError, IndexError) as e:
            logger.error("Error getting lead analytics: %s" % str(e))
            raise

    async def get_cohort_analytics(
        self, start_date: datetime, end_date: datetime, cohort_type: str = "weekly"
    ) -> Dict[str, Any]:
        """
        Get cohort analysis for leads acquired in a time period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period
            cohort_type: Type of cohort (daily, weekly, monthly)

        Returns:
            Dict containing cohort analytics
        """
        try:
            logger.info("Generating cohort analytics from %s to %s" % (start_date, end_date))
            from sqlalchemy import select, and_

            leads_result = await self.db.execute(
                select(AssessmentLead).where(
                    and_(
                        AssessmentLead.created_at >= start_date,
                        AssessmentLead.created_at <= end_date,
                    )
                )
            )
            leads = leads_result.scalars().all()
            if not leads:
                return {"message": "No leads found in specified period"}
            lead_ids = [lead.id for lead in leads]
            events_result = await self.db.execute(
                select(LeadScoringEvent)
                .where(LeadScoringEvent.lead_id.in_(lead_ids))
                .order_by(LeadScoringEvent.created_at)
            )
            events = events_result.scalars().all()
            try:
                conversions_result = await self.db.execute(
                    select(ConversionEvent).where(ConversionEvent.lead_id.in_(lead_ids))
                )
                conversions = conversions_result.scalars().all()
            except Exception:
                conversions = []
            cohort_metrics = {
                "cohort_size": len(leads),
                "acquisition_period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                    "type": cohort_type,
                },
                "engagement_metrics": {
                    "leads_with_events": len(set(e.lead_id for e in events)),
                    "total_events": len(events),
                    "avg_events_per_lead": len(events) / len(leads) if leads else 0,
                    "assessment_starts": len(
                        [e for e in events if e.event_type == "assessment_start"]
                    ),
                    "assessment_completions": len(
                        [e for e in events if e.event_type == "assessment_complete"]
                    ),
                },
                "conversion_metrics": {
                    "total_conversions": len(conversions),
                    "conversion_rate": len(conversions) / len(leads) if leads else 0,
                    "avg_time_to_conversion": self._calculate_avg_conversion_time(
                        leads, conversions
                    ),
                    "conversion_by_type": self._group_conversions_by_type(conversions),
                },
                "lead_distribution": self._calculate_lead_status_distribution(leads),
                "retention_analysis": self._calculate_retention_metrics(leads, events),
            }
            return cohort_metrics
        except (Exception, KeyError, IndexError) as e:
            logger.error("Error generating cohort analytics: %s" % str(e))
            raise

    def _calculate_event_score(self, event_type: str, metadata: Dict[str, Any]) -> int:
        """Calculate score impact for an event type."""
        scoring_rule = self.SCORING_RULES.get(event_type, {"base_score": 5})
        base_score = scoring_rule["base_score"]
        multiplier = 1.0
        if "answer_quality" in metadata:
            quality = metadata["answer_quality"]
            multiplier *= {"high": 1.5, "medium": 1.0, "low": 0.7}.get(quality, 1.0)
        if "time_spent_seconds" in metadata:
            time_spent = metadata["time_spent_seconds"]
            if time_spent > 120:
                multiplier *= 1.2
            elif time_spent < DEFAULT_TIMEOUT:
                multiplier *= 0.8
        if "confidence" in metadata:
            confidence = metadata["confidence"]
            multiplier *= {"high": 1.3, "medium": 1.0, "low": 0.8}.get(confidence, 1.0)
        return int(base_score * multiplier)

    async def _update_lead_score(
        self, lead_id: uuid.UUID, score_impact: int, event_type: str
    ) -> None:
        """Update lead score and status based on new event."""
        from sqlalchemy import select

        result = await self.db.execute(select(AssessmentLead).where(AssessmentLead.id == lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            return
        lead.lead_score = (lead.lead_score or 0) + score_impact
        lead.last_activity_at = datetime.now(timezone.utc)
        new_status = self._determine_lead_status(lead.lead_score)
        if new_status != lead.lead_status:
            lead.lead_status = new_status
            logger.info("Lead %s status updated to: %s" % (lead_id, new_status))

    async def _update_cached_metrics(
        self, lead_id: uuid.UUID, event_type: str, score_impact: int
    ) -> None:
        """Update cached metrics for real-time analytics."""
        try:
            if not self.cache_manager:
                self.cache_manager = await get_cache_manager()
            cache_key = f"lead_score:{lead_id}"
            await self.cache_manager.increment(cache_key, score_impact)
            event_key = f"lead_events:{lead_id}:{event_type}"
            await self.cache_manager.increment(event_key, 1)
        except (ValueError, TypeError) as e:
            logger.warning("Failed to update cached metrics: %s" % str(e))

    def _apply_time_decay(self, events: List[LeadScoringEvent], total_score: int) -> int:
        """Apply time-based decay to older events."""
        now = datetime.now(timezone.utc)
        adjusted_score = 0
        for event in events:
            days_ago = (now - event.created_at).days
            if days_ago <= 7:
                decay_factor = 1.0
            elif days_ago <= DEFAULT_TIMEOUT:
                decay_factor = 0.9
            else:
                decay_factor = 0.7
            adjusted_score += int((event.score_impact or 0) * decay_factor)
        return adjusted_score

    def _calculate_conversion_probability(
        self, total_score: int, event_counts: Dict[str, int], events: List[LeadScoringEvent]
    ) -> float:
        """Calculate conversion probability based on scoring factors."""
        if total_score >= HTTP_OK:
            base_prob = 0.8
        elif total_score >= 150:
            base_prob = 0.6
        elif total_score >= DEFAULT_LIMIT:
            base_prob = 0.4
        elif total_score >= 50:
            base_prob = 0.2
        else:
            base_prob = 0.05
        probability = base_prob
        if event_counts.get("results_viewed", 0) > 0:
            probability *= 1.5
        if event_counts.get("pricing_viewed", 0) > 0:
            probability *= 1.3
        if event_counts.get("demo_requested", 0) > 0:
            probability *= 2.0
        unique_days = len(set(e.created_at.date() for e in events))
        if unique_days > MAX_RETRIES:
            probability *= 1.2
        return min(probability, 1.0)

    def _determine_lead_status(self, score: int) -> str:
        """Determine lead status based on score."""
        for status, threshold in sorted(
            self.LEAD_QUALIFICATION_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
        ):
            if score >= threshold:
                return status
        return "cold"

    def _calculate_engagement_metrics(self, events: List[LeadScoringEvent]) -> Dict[str, Any]:
        """Calculate engagement quality metrics."""
        if not events:
            return {}
        now = datetime.now(timezone.utc)
        event_dates = [e.created_at for e in events]
        return {
            "days_since_last_activity": (now - max(event_dates)).days,
            "activity_span_days": (max(event_dates) - min(event_dates)).days,
            "avg_events_per_day": len(events)
            / max(1, (max(event_dates) - min(event_dates)).days + 1),
            "engagement_consistency": len(set(e.created_at.date() for e in events)),
            "peak_activity_hour": max(
                set(e.created_at.hour for e in events),
                key=lambda h: sum(1 for e in events if e.created_at.hour == h),
            ),
            "session_depth": sum(1 for e in events if e.event_category == "assessment")
            / max(1, sum(1 for e in events if e.event_type == "assessment_start")),
        }

    def _analyze_engagement_patterns(self, events: List[LeadScoringEvent]) -> Dict[str, Any]:
        """Analyze engagement patterns from events."""
        if not events:
            return {}
        daily_events = {}
        for event in events:
            date_key = event.created_at.date()
            if date_key not in daily_events:
                daily_events[date_key] = []
            daily_events[date_key].append(event)
        return {
            "most_active_day": max(daily_events.keys(), key=lambda d: len(daily_events[d]))
            if daily_events
            else None,
            "avg_daily_events": sum(len(events) for events in daily_events.values())
            / len(daily_events),
            "event_type_distribution": {
                event_type: len([e for e in events if e.event_type == event_type])
                for event_type in set(e.event_type for e in events)
            },
            "engagement_trend": "increasing"
            if len(events) > DEFAULT_RETRIES and events[0].created_at > events[-1].created_at
            else "stable",
        }

    def _analyze_conversion_journey(
        self, events: List[LeadScoringEvent], sessions: List[FreemiumAssessmentSession]
    ) -> Dict[str, Any]:
        """Analyze the conversion journey for a lead."""
        journey_stages = {
            "awareness": len([e for e in events if e.event_type in ["lead_capture", "email_open"]]),
            "interest": len(
                [e for e in events if e.event_type in ["assessment_start", "pricing_viewed"]]
            ),
            "consideration": len(
                [e for e in events if e.event_type in ["assessment_complete", "results_viewed"]]
            ),
            "intent": len(
                [e for e in events if e.event_type in ["demo_requested", "consultation_booked"]]
            ),
            "conversion": len([e for e in events if e.event_type in ["trial_signup", "purchase"]]),
        }
        return {
            "journey_stages": journey_stages,
            "current_stage": max(journey_stages.keys(), key=lambda k: journey_stages[k])
            if any(journey_stages.values())
            else "awareness",
            "assessment_funnel": {
                "sessions_started": len(sessions),
                "sessions_completed": len(
                    [s for s in sessions if s.completion_status == "completed"]
                ),
                "completion_rate": len([s for s in sessions if s.completion_status == "completed"])
                / len(sessions)
                if sessions
                else 0,
                "avg_questions_answered": sum(s.questions_answered for s in sessions)
                / len(sessions)
                if sessions
                else 0,
            },
        }

    def _generate_behavioral_insights(
        self, events: List[LeadScoringEvent], lead: AssessmentLead
    ) -> List[str]:
        """Generate behavioral insights for a lead."""
        insights = []
        if len(events) > 10:
            insights.append("Highly engaged lead with consistent activity")
        elif len(events) > DEFAULT_RETRIES:
            insights.append("Moderately engaged with good interaction frequency")
        if events:
            hours = [e.created_at.hour for e in events]
            if max(set(hours), key=hours.count) < 9 or max(set(hours), key=hours.count) > 17:
                insights.append("Active outside business hours - highly motivated")
        assessment_events = [e for e in events if e.event_category == "assessment"]
        if len(assessment_events) > DEFAULT_RETRIES:
            insights.append("Deep assessment engagement indicates serious interest")
        conversion_events = [e for e in events if e.event_category == "conversion"]
        if len(conversion_events) > 2:
            insights.append("Shows strong conversion signals")
        return insights

    def _suggest_next_actions(
        self,
        events: List[LeadScoringEvent],
        sessions: List[FreemiumAssessmentSession],
        lead: AssessmentLead,
    ) -> List[Dict[str, str]]:
        """Suggest next best actions for lead nurturing."""
        actions = []
        if lead.lead_score >= 150:
            actions.append(
                {
                    "action": "immediate_outreach",
                    "description": "High-value lead ready for sales contact",
                    "priority": "urgent",
                }
            )
        elif lead.lead_score >= DEFAULT_LIMIT:
            actions.append(
                {
                    "action": "schedule_demo",
                    "description": "Qualified lead ready for product demonstration",
                    "priority": "high",
                }
            )
        completed_sessions = [s for s in sessions if s.completion_status == "completed"]
        if completed_sessions and not any(e.event_type == "results_viewed" for e in events):
            actions.append(
                {
                    "action": "results_follow_up",
                    "description": "Send personalized assessment results",
                    "priority": "medium",
                }
            )
        if events and (datetime.now(timezone.utc) - events[0].created_at).days > 7:
            actions.append(
                {
                    "action": "re_engagement_campaign",
                    "description": "Re-engage dormant lead with relevant content",
                    "priority": "low",
                }
            )
        return actions

    def _group_conversions_by_type(self, conversions: List[ConversionEvent]) -> Dict[str, int]:
        """Group conversions by type."""
        conversion_types = {}
        for conversion in conversions:
            conv_type = conversion.conversion_type
            conversion_types[conv_type] = conversion_types.get(conv_type, 0) + 1
        return conversion_types

    def _calculate_avg_conversion_time(
        self, leads: List[AssessmentLead], conversions: List[ConversionEvent]
    ) -> Optional[float]:
        """Calculate average time from lead creation to conversion."""
        if not conversions:
            return None
        lead_dict = {lead.id: lead for lead in leads}
        conversion_times = []
        for conversion in conversions:
            if conversion.lead_id in lead_dict:
                lead_created = lead_dict[conversion.lead_id].created_at
                time_to_convert = (conversion.created_at - lead_created).total_seconds() / 3600
                conversion_times.append(time_to_convert)
        return sum(conversion_times) / len(conversion_times) if conversion_times else None

    def _calculate_lead_status_distribution(self, leads: List[AssessmentLead]) -> Dict[str, int]:
        """Calculate distribution of leads by status."""
        status_counts = {}
        for lead in leads:
            status = lead.lead_status or "cold"
            status_counts[status] = status_counts.get(status, 0) + 1
        return status_counts

    def _calculate_retention_metrics(
        self, leads: List[AssessmentLead], events: List[LeadScoringEvent]
    ) -> Dict[str, Any]:
        """Calculate retention metrics for the cohort."""
        if not leads or not events:
            return {}
        lead_weekly_activity = {}
        for event in events:
            lead_id = event.lead_id
            week = event.created_at.isocalendar()[1]
            if lead_id not in lead_weekly_activity:
                lead_weekly_activity[lead_id] = set()
            lead_weekly_activity[lead_id].add(week)
        total_leads = len(leads)
        retention_data = {}
        for week_num in range(1, 53):
            active_leads = sum(1 for weeks in lead_weekly_activity.values() if week_num in weeks)
            retention_data[f"week_{week_num}"] = (
                active_leads / total_leads if total_leads > 0 else 0
            )
        return retention_data
