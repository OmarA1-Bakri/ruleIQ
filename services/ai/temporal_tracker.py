#!/usr/bin/env python3
"""
Production-grade Temporal Tracker for Compliance Timeline Management
Tracks regulation changes, deadlines, and temporal patterns in compliance requirements
"""

import asyncio
import logging
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import re

from neo4j import AsyncGraphDatabase
from pydantic import BaseModel, Field
import numpy as np

logger = logging.getLogger(__name__)


class ComplianceEventType(str, Enum):
    """Types of compliance timeline events"""

    REGULATION_EFFECTIVE = "regulation_effective"
    DEADLINE = "deadline"
    AMENDMENT = "amendment"
    GRACE_PERIOD_END = "grace_period_end"
    REVIEW_DATE = "review_date"
    CERTIFICATION_RENEWAL = "certification_renewal"
    AUDIT_SCHEDULED = "audit_scheduled"
    ENFORCEMENT_ACTION = "enforcement_action"


class ComplianceUrgency(str, Enum):
    """Urgency levels for compliance actions"""

    CRITICAL = "critical"  # < 30 days
    HIGH = "high"  # 30-90 days
    MEDIUM = "medium"  # 90-180 days
    LOW = "low"  # 180-365 days
    PLANNING = "planning"  # > 365 days


@dataclass
class ComplianceEvent:
    """Represents a temporal compliance event"""

    event_id: str
    regulation_id: str
    regulation_title: str
    event_type: ComplianceEventType
    event_date: datetime
    urgency: ComplianceUrgency
    description: str
    action_required: str
    impact_score: float  # 0-10 scale
    affected_systems: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_effort_hours: int = 0
    completion_status: str = "pending"
    notes: str = ""


@dataclass
class ComplianceTimeline:
    """Timeline view of compliance obligations"""

    business_profile: Dict[str, Any]
    current_date: datetime
    events_30_days: List[ComplianceEvent]
    events_90_days: List[ComplianceEvent]
    events_180_days: List[ComplianceEvent]
    events_365_days: List[ComplianceEvent]
    overdue_events: List[ComplianceEvent]
    upcoming_amendments: List[Dict[str, Any]]
    seasonal_patterns: Dict[str, Any]
    resource_forecast: Dict[str, Any]


@dataclass
class AmendmentAlert:
    """Alert for regulation amendments"""

    regulation_id: str
    regulation_title: str
    amendment_date: datetime
    amendment_type: str  # major, minor, clarification
    summary: str
    impact_areas: List[str]
    required_actions: List[str]
    implementation_timeline: int  # days
    risk_if_ignored: str


class TemporalMetrics(BaseModel):
    """Metrics for temporal compliance tracking"""

    total_deadlines: int = 0
    critical_deadlines: int = 0
    overdue_items: int = 0
    upcoming_30_days: int = 0
    upcoming_90_days: int = 0
    average_lead_time_days: float = 0.0
    compliance_velocity: float = 0.0  # Items completed per month
    amendment_frequency: float = 0.0  # Amendments per year
    seasonal_peak_months: List[int] = Field(default_factory=list)
    resource_utilization: float = 0.0


class TemporalTracker:
    """
    Production-grade temporal tracker for compliance timelines.
    Monitors deadlines, amendments, and temporal patterns.
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = None

        # Temporal patterns and seasonality
        self.seasonal_patterns = self._load_seasonal_patterns()

        # Resource planning parameters
        self.resource_params = {
            "hours_per_day": 8,
            "days_per_week": 5,
            "compliance_team_size": 3,
            "buffer_percentage": 0.2,  # 20% buffer for unexpected work
        }

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Establish connection to Neo4j"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.neo4j_uri,
                auth=(self.neo4j_user, self.neo4j_password),
            )
            # Verify connectivity
            async with self.driver.session() as session:
                await session.run("RETURN 1")
            logger.info("✅ Connected to Neo4j for temporal tracking")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close Neo4j connection"""
        if self.driver:
            await self.driver.close()

    def _load_seasonal_patterns(self) -> Dict[str, Any]:
        """Load known seasonal patterns in compliance"""
        return {
            "year_end_reporting": {
                "months": [11, 12, 1],
                "impact_multiplier": 1.5,
                "affected_regulations": ["financial_reporting", "tax", "audit"],
            },
            "gdpr_reviews": {
                "months": [5],  # Anniversary of GDPR
                "impact_multiplier": 1.2,
                "affected_regulations": ["data_protection", "privacy"],
            },
            "fiscal_year_planning": {
                "months": [3, 4],
                "impact_multiplier": 1.3,
                "affected_regulations": ["budget", "financial_planning"],
            },
            "audit_season": {
                "months": [2, 3, 4],
                "impact_multiplier": 1.4,
                "affected_regulations": ["sox", "financial_audit", "iso"],
            },
        }

    async def extract_temporal_requirements(self, regulation_id: str) -> List[ComplianceEvent]:
        """
        Extract temporal requirements from regulation metadata.

        Args:
            regulation_id: Regulation identifier

        Returns:
            List of compliance events with deadlines
        """
        async with self.driver.session() as session:
            # Get regulation with temporal metadata
            query = """
            MATCH (r:Regulation {id: $regulation_id})
            RETURN r
            """

            result = await session.run(query, regulation_id=regulation_id)
            record = await result.single()

            if not record:
                return []

            regulation = dict(record["r"])
            events = []

            # Extract deadline from various fields
            deadline_patterns = [
                r'deadline["\']?\s*:\s*["\']?(\d{4}-\d{2}-\d{2})',
                r'effective_date["\']?\s*:\s*["\']?(\d{4}-\d{2}-\d{2})',
                r'compliance_date["\']?\s*:\s*["\']?(\d{4}-\d{2}-\d{2})',
            ]

            # Check for deadlines in string fields
            reg_str = str(regulation)
            for pattern in deadline_patterns:
                matches = re.findall(pattern, reg_str, re.IGNORECASE)
                for match in matches:
                    try:
                        event_date = datetime.strptime(match, "%Y-%m-%d")

                        # Create compliance event
                        event = ComplianceEvent(
                            event_id=f"{regulation_id}_{match}",
                            regulation_id=regulation_id,
                            regulation_title=regulation.get("title", "Unknown"),
                            event_type=ComplianceEventType.DEADLINE,
                            event_date=event_date,
                            urgency=self._calculate_urgency(event_date),
                            description=f"Compliance deadline for {regulation.get('title', '')}",
                            action_required="Ensure full compliance implementation",
                            impact_score=regulation.get("base_risk_score", 5.0),
                            estimated_effort_hours=self._estimate_effort_from_complexity(
                                regulation.get("implementation_complexity", 5),
                            ),
                        )
                        events.append(event)
                    except ValueError:
                        continue

            # Check for typical implementation timeline
            timeline = regulation.get("typical_timeline", "")
            if timeline:
                days = self._parse_timeline_to_days(timeline)
                if days:
                    future_date = datetime.now() + timedelta(days=days)
                    event = ComplianceEvent(
                        event_id=f"{regulation_id}_typical",
                        regulation_id=regulation_id,
                        regulation_title=regulation.get("title", "Unknown"),
                        event_type=ComplianceEventType.DEADLINE,
                        event_date=future_date,
                        urgency=self._calculate_urgency(future_date),
                        description=f"Typical implementation timeline for {regulation.get('title', '')}",
                        action_required="Complete implementation",
                        impact_score=regulation.get("base_risk_score", 5.0),
                        estimated_effort_hours=self._estimate_effort_from_complexity(
                            regulation.get("implementation_complexity", 5),
                        ),
                    )
                    events.append(event)

            return events

    def _parse_timeline_to_days(self, timeline: str) -> Optional[int]:
        """Parse timeline string to days"""
        timeline_lower = timeline.lower()

        # Parse month-based timelines
        month_match = re.search(
            r"(\d+)[-\s]*(?:to[-\s]*)?(\d+)?\s*month",
            timeline_lower,
        )
        if month_match:
            min_months = int(month_match.group(1))
            max_months = (int(month_match.group(2)) if month_match.group(2) else min_months,)
            avg_months = (min_months + max_months) / 2
            return int(avg_months * 30)

        # Parse week-based timelines
        week_match = re.search(r"(\d+)[-\s]*(?:to[-\s]*)?(\d+)?\s*week", timeline_lower)
        if week_match:
            min_weeks = int(week_match.group(1))
            max_weeks = int(week_match.group(2)) if week_match.group(2) else min_weeks
            avg_weeks = (min_weeks + max_weeks) / 2
            return int(avg_weeks * 7)

        # Parse day-based timelines
        day_match = re.search(r"(\d+)[-\s]*(?:to[-\s]*)?(\d+)?\s*day", timeline_lower)
        if day_match:
            min_days = int(day_match.group(1))
            max_days = int(day_match.group(2)) if day_match.group(2) else min_days
            return int((min_days + max_days) / 2)

        return None

    def _calculate_urgency(self, event_date: datetime) -> ComplianceUrgency:
        """Calculate urgency based on days until event"""
        days_until = (event_date - datetime.now()).days

        if days_until < 0:
            return ComplianceUrgency.CRITICAL  # Overdue
        elif days_until < 30:
            return ComplianceUrgency.CRITICAL
        elif days_until < 90:
            return ComplianceUrgency.HIGH
        elif days_until < 180:
            return ComplianceUrgency.MEDIUM
        elif days_until < 365:
            return ComplianceUrgency.LOW
        else:
            return ComplianceUrgency.PLANNING

    def _estimate_effort_from_complexity(self, complexity: int) -> int:
        """Estimate effort hours from complexity score"""
        # Base hours by complexity level
        base_hours = {
            1: 20,
            2: 40,
            3: 60,
            4: 80,
            5: 120,
            6: 160,
            7: 200,
            8: 280,
            9: 360,
            10: 480,
        }
        return base_hours.get(complexity, 100)

    async def generate_compliance_timeline(
        self, business_profile: Dict[str, Any], horizon_days: int = 365
    ) -> ComplianceTimeline:
        """
        Generate comprehensive compliance timeline for business.

        Args:
            business_profile: Business context
            horizon_days: Days to look ahead

        Returns:
            Complete compliance timeline with events and forecasts
        """
        current_date = datetime.now()
        horizon_date = current_date + timedelta(days=horizon_days)

        async with self.driver.session() as session:
            # Get applicable regulations
            regulations = await self._get_applicable_regulations(
                business_profile,
                session,
            )

            # Extract all temporal events
            all_events = []
            for reg in regulations:
                events = await self.extract_temporal_requirements(reg["id"])
                all_events.extend(events)

            # Add enforcement-based events
            enforcement_events = await self._get_enforcement_events(
                business_profile,
                session,
                horizon_date,
            )
            all_events.extend(enforcement_events)

            # Categorize events by timeline
            events_30 = [e for e in all_events if 0 <= (e.event_date - current_date).days <= 30]
            events_90 = [e for e in all_events if 30 < (e.event_date - current_date).days <= 90]
            events_180 = [e for e in all_events if 90 < (e.event_date - current_date).days <= 180]
            events_365 = [e for e in all_events if 180 < (e.event_date - current_date).days <= 365]
            overdue = [e for e in all_events if (e.event_date - current_date).days < 0]

            # Sort by date
            for event_list in [events_30, events_90, events_180, events_365, overdue]:
                event_list.sort(key=lambda x: x.event_date)

            # Get upcoming amendments
            amendments = await self._get_upcoming_amendments(
                [reg["id"] for reg in regulations],
                session,
            )

            # Analyze seasonal patterns
            seasonal = self._analyze_seasonal_impact(all_events)

            # Generate resource forecast
            resource_forecast = self._generate_resource_forecast(
                all_events,
                horizon_days,
            )

            return ComplianceTimeline(
                business_profile=business_profile,
                current_date=current_date,
                events_30_days=events_30,
                events_90_days=events_90,
                events_180_days=events_180,
                events_365_days=events_365,
                overdue_events=overdue,
                upcoming_amendments=amendments,
                seasonal_patterns=seasonal,
                resource_forecast=resource_forecast,
            )

    async def _get_applicable_regulations(
        self, business_profile: Dict[str, Any], session: Any
    ) -> List[Dict[str, Any]]:
        """Get regulations applicable to business profile"""

        # For now, get all regulations with temporal data
        query = """
        MATCH (r:Regulation)
        WHERE r.typical_timeline IS NOT NULL
           OR r.enforcement_frequency IS NOT NULL
        RETURN r
        LIMIT 100
        """

        result = await session.run(query)
        regulations = []
        async for record in result:
            regulations.append(dict(record["r"]))

        return regulations

    async def _get_enforcement_events(
        self, business_profile: Dict[str, Any], session: Any, horizon_date: datetime
    ) -> List[ComplianceEvent]:
        """Generate events based on enforcement patterns"""

        # Query enforcement data
        query = """
        MATCH (e:EnforcementAction)
        WHERE e.date >= $start_date
        RETURN e
        ORDER BY e.date DESC
        LIMIT 50
        """

        result = await session.run(
            query,
            start_date=(datetime.now() - timedelta(days=365)).isoformat(),
        )

        events = []
        async for record in result:
            enforcement = dict(record["e"])

            # Create predictive event based on pattern
            if enforcement.get("recurring", False):
                next_date = datetime.now() + timedelta(days=365)
                event = ComplianceEvent(
                    event_id=f"enforce_{enforcement.get('id', 'unknown')}",
                    regulation_id=enforcement.get("regulation_id", ""),
                    regulation_title=enforcement.get("regulation_title", ""),
                    event_type=ComplianceEventType.ENFORCEMENT_ACTION,
                    event_date=next_date,
                    urgency=ComplianceUrgency.MEDIUM,
                    description="Predicted enforcement review based on historical pattern",
                    action_required="Ensure compliance to avoid enforcement action",
                    impact_score=8.0,
                    estimated_effort_hours=40,
                )
                events.append(event)

        return events

    async def _get_upcoming_amendments(
        self, regulation_ids: List[str], session: Any
    ) -> List[Dict[str, Any]]:
        """Get predicted amendments based on patterns"""

        amendments = []

        # Simulate amendment predictions based on regulation age
        for reg_id in regulation_ids[:10]:  # Limit to avoid too many
            # Create synthetic amendment prediction
            amendment = {
                "regulation_id": reg_id,
                "predicted_date": (datetime.now() + timedelta(days=180)).isoformat(),
                "probability": 0.3,
                "expected_impact": "minor",
                "preparation_advice": "Monitor regulatory body announcements",
            }
            amendments.append(amendment)

        return amendments

    def _analyze_seasonal_impact(self, events: List[ComplianceEvent]) -> Dict[str, Any]:
        """Analyze seasonal patterns in compliance events"""

        # Count events by month
        month_counts = {}
        for event in events:
            month = event.event_date.month
            month_counts[month] = month_counts.get(month, 0) + 1

        # Identify peak months
        if month_counts:
            avg_count = np.mean(list(month_counts.values()))
            peak_months = [
                month for month, count in month_counts.items() if count > avg_count * 1.2
            ]
        else:
            peak_months = []

        # Apply known seasonal patterns
        impacted_periods = []
        for pattern_name, pattern in self.seasonal_patterns.items():
            if any(month in pattern["months"] for month in peak_months):
                impacted_periods.append(
                    {
                        "period": pattern_name,
                        "months": pattern["months"],
                        "impact_multiplier": pattern["impact_multiplier"],
                    },
                )

        return {
            "peak_months": peak_months,
            "impacted_periods": impacted_periods,
            "recommendation": self._generate_seasonal_recommendation(peak_months),
        }

    def _generate_seasonal_recommendation(self, peak_months: List[int]) -> str:
        """Generate recommendation based on seasonal patterns"""

        if not peak_months:
            return "No significant seasonal patterns detected"

        month_names = {
            1: "January",
            2: "February",
            3: "March",
            4: "April",
            5: "May",
            6: "June",
            7: "July",
            8: "August",
            9: "September",
            10: "October",
            11: "November",
            12: "December",
        }

        peak_names = [month_names[m] for m in peak_months]

        return f"Plan for increased compliance workload in {', '.join(peak_names)}. Consider temporary resource augmentation."  # noqa: E501

    def _generate_resource_forecast(
        self, events: List[ComplianceEvent], horizon_days: int
    ) -> Dict[str, Any]:
        """Generate resource utilization forecast"""

        # Calculate monthly workload
        monthly_hours = {}
        current_date = datetime.now()

        for event in events:
            if (event.event_date - current_date).days <= horizon_days:
                month_key = f"{event.event_date.year}-{event.event_date.month:02d}"
                monthly_hours[month_key] = (
                    monthly_hours.get(month_key, 0) + event.estimated_effort_hours,
                )

        # Calculate team capacity
        monthly_capacity = (
            self.resource_params["hours_per_day"]
            * self.resource_params["days_per_week"]
            * 4
            * self.resource_params["compliance_team_size"]
            * (1 - self.resource_params["buffer_percentage"]),
        )

        # Identify resource constraints
        constrained_months = [
            month for month, hours in monthly_hours.items() if hours > monthly_capacity
        ]

        # Calculate average utilization
        if monthly_hours:
            avg_utilization = np.mean(list(monthly_hours.values())) / monthly_capacity
        else:
            avg_utilization = 0

        return {
            "monthly_workload": monthly_hours,
            "monthly_capacity": monthly_capacity,
            "constrained_months": constrained_months,
            "average_utilization": avg_utilization,
            "recommendation": self._generate_resource_recommendation(
                avg_utilization,
                constrained_months,
            ),
        }

    def _generate_resource_recommendation(
        self, avg_utilization: float, constrained_months: List[str]
    ) -> str:
        """Generate resource planning recommendation"""

        if avg_utilization > 0.9:
            return "Critical: Team is over-capacity. Immediate resource augmentation required."
        elif avg_utilization > 0.7:
            if constrained_months:
                return f"High utilization with constraints in {len(constrained_months)} months. Plan for temporary resources."  # noqa: E501
            else:
                return "High but manageable utilization. Monitor closely for changes."
        elif avg_utilization > 0.5:
            return "Optimal utilization level. Team has capacity for additional initiatives."
        else:
            return "Low utilization. Consider additional compliance improvements or automation projects."

    async def track_amendment_patterns(
        self, regulation_id: str, lookback_years: int = 3
    ) -> Dict[str, Any]:
        """
        Track amendment patterns for a regulation.

        Args:
            regulation_id: Regulation identifier
            lookback_years: Years of history to analyze

        Returns:
            Amendment pattern analysis
        """
        async with self.driver.session():
            # Simulate amendment history (in production, would query real data)
            amendment_history = self._simulate_amendment_history(
                regulation_id,
                lookback_years,
            )

            # Analyze patterns
            patterns = {
                "total_amendments": len(amendment_history),
                "amendments_per_year": len(amendment_history) / lookback_years,
                "average_days_between": self._calculate_avg_days_between(
                    amendment_history,
                ),
                "trend": self._analyze_amendment_trend(amendment_history),
                "next_predicted": self._predict_next_amendment(amendment_history),
                "stability_score": self._calculate_stability_score(amendment_history),
            }

            return patterns

    def _simulate_amendment_history(
        self, regulation_id: str, lookback_years: int
    ) -> List[Dict[str, Any]]:
        """Simulate amendment history for demonstration"""

        history = []
        base_date = datetime.now() - timedelta(days=365 * lookback_years)

        # Generate random amendments
        num_amendments = np.random.poisson(2 * lookback_years)  # Average 2 per year

        for i in range(num_amendments):
            days_offset = np.random.randint(0, 365 * lookback_years)
            amendment_date = base_date + timedelta(days=days_offset)

            history.append(
                {
                    "date": amendment_date,
                    "type": np.random.choice(["major", "minor", "clarification"]),
                    "description": f"Amendment {i + 1} for {regulation_id}",
                },
            )

        history.sort(key=lambda x: x["date"])
        return history

    def _calculate_avg_days_between(self, amendment_history: List[Dict[str, Any]]) -> float:
        """Calculate average days between amendments"""

        if len(amendment_history) < 2:
            return 0

        days_between = []
        for i in range(1, len(amendment_history)):
            days = (amendment_history[i]["date"] - amendment_history[i - 1]["date"]).days
            days_between.append(days)

        return np.mean(days_between) if days_between else 0

    def _analyze_amendment_trend(self, amendment_history: List[Dict[str, Any]]) -> str:
        """Analyze trend in amendment frequency"""

        if len(amendment_history) < 3:
            return "insufficient_data"

        # Split history into halves
        midpoint = len(amendment_history) // 2
        first_half = amendment_history[:midpoint]
        second_half = amendment_history[midpoint:]

        # Compare frequency
        first_rate = len(first_half) / (
            (first_half[-1]["date"] - first_half[0]["date"]).days / 365,
        )
        second_rate = len(second_half) / (
            (second_half[-1]["date"] - second_half[0]["date"]).days / 365,
        )

        if second_rate > first_rate * 1.2:
            return "increasing"
        elif second_rate < first_rate * 0.8:
            return "decreasing"
        else:
            return "stable"

    def _predict_next_amendment(
        self, amendment_history: List[Dict[str, Any]]
    ) -> Optional[datetime]:
        """Predict next amendment date based on patterns"""

        if not amendment_history:
            return None

        avg_days = self._calculate_avg_days_between(amendment_history)
        if avg_days > 0:
            last_date = amendment_history[-1]["date"]
            return last_date + timedelta(days=avg_days)

        return None

    def _calculate_stability_score(self, amendment_history: List[Dict[str, Any]]) -> float:
        """Calculate regulation stability score (0-1, higher is more stable)"""

        if not amendment_history:
            return 1.0  # No amendments = stable

        # Factors affecting stability
        amendment_rate = len(amendment_history) / 3  # Per year over 3 years
        major_amendments = sum(1 for a in amendment_history if a["type"] == "major")

        # Calculate score
        rate_factor = max(0, 1 - (amendment_rate / 5))  # 5+ per year = 0
        major_factor = max(0, 1 - (major_amendments / 3))  # 3+ major = 0

        return rate_factor * 0.7 + major_factor * 0.3

    async def generate_compliance_calendar(
        self, business_profile: Dict[str, Any], months_ahead: int = 12
    ) -> Dict[str, List[ComplianceEvent]]:
        """
        Generate month-by-month compliance calendar.

        Args:
            business_profile: Business context
            months_ahead: Number of months to forecast

        Returns:
            Calendar organized by month
        """
        timeline = await self.generate_compliance_timeline(
            business_profile,
            horizon_days=months_ahead * 30,
        )

        # Organize events by month
        calendar = {}
        all_events = (
            timeline.overdue_events
            + timeline.events_30_days
            + timeline.events_90_days
            + timeline.events_180_days
            + timeline.events_365_days,
        )

        for event in all_events:
            month_key = event.event_date.strftime("%Y-%m")
            if month_key not in calendar:
                calendar[month_key] = []
            calendar[month_key].append(event)

        # Sort events within each month
        for month in calendar:
            calendar[month].sort(key=lambda x: x.event_date)

        return calendar


async def main():
    """Test the temporal tracker"""

    # Neo4j connection details
    neo4j_uri = "bolt://localhost:7688"
    # Security: Credentials now loaded from environment via Doppler
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not neo4j_password:
        raise ValueError("NEO4J_PASSWORD environment variable not set. Configure via Doppler.")

    async with TemporalTracker(neo4j_uri, neo4j_user, neo4j_password) as tracker:
        # Test business profile
        business_profile = {
            "industry": "finance",
            "sub_industry": "fintech",
            "country": "UK",
            "processes_payments": True,
            "stores_customer_data": True,
            "has_eu_customers": True,
            "annual_revenue": 25000000,
            "employee_count": 100,
        }

        logger.info("📅 Generating Compliance Timeline...")

        # Generate compliance timeline
        timeline = await tracker.generate_compliance_timeline(business_profile)

        logger.info("\n⏰ Compliance Timeline Analysis:")
        logger.info(f"  Current Date: {timeline.current_date.strftime('%Y-%m-%d')}")
        logger.info(f"  Overdue Items: {len(timeline.overdue_events)}")
        logger.info(f"  Next 30 Days: {len(timeline.events_30_days)} events")
        logger.info(f"  Next 90 Days: {len(timeline.events_90_days)} events")
        logger.info(f"  Next 180 Days: {len(timeline.events_180_days)} events")
        logger.info(f"  Next 365 Days: {len(timeline.events_365_days)} events")

        if timeline.overdue_events:
            logger.info("\n🚨 OVERDUE ITEMS:")
            for event in timeline.overdue_events[:3]:
                days_overdue = (datetime.now() - event.event_date).days
                logger.info(f"  • {event.regulation_title}")
                logger.info(
                    f"    {days_overdue} days overdue - {event.action_required}",
                )

        if timeline.events_30_days:
            logger.info("\n📌 NEXT 30 DAYS:")
            for event in timeline.events_30_days[:5]:
                days_until = (event.event_date - datetime.now()).days
                logger.info(f"  • {event.regulation_title}")
                logger.info(f"    In {days_until} days - {event.action_required}")
                logger.info(f"    Effort: {event.estimated_effort_hours} hours")

        # Seasonal patterns
        if timeline.seasonal_patterns.get("peak_months"):
            logger.info("\n📊 Seasonal Patterns:")
            logger.info(f"  Peak Months: {timeline.seasonal_patterns['peak_months']}")
            logger.info(
                f"  Recommendation: {timeline.seasonal_patterns['recommendation']}",
            )

        # Resource forecast
        if timeline.resource_forecast:
            logger.info("\n👥 Resource Forecast:")
            logger.info(
                f"  Average Utilization: {timeline.resource_forecast['average_utilization']:.1%}",
            )
            logger.info(
                f"  Monthly Capacity: {timeline.resource_forecast['monthly_capacity']} hours",
            )
            if timeline.resource_forecast["constrained_months"]:
                logger.info(
                    f"  Constrained Months: {len(timeline.resource_forecast['constrained_months'])}",
                )
            logger.info(
                f"  Recommendation: {timeline.resource_forecast['recommendation']}",
            )

        # Test amendment tracking
        logger.info("\n📝 Amendment Pattern Analysis:")

        test_regulation = "gdpr-eu-2016-679"
        patterns = await tracker.track_amendment_patterns(test_regulation)

        logger.info(f"  Regulation: {test_regulation}")
        logger.info(f"  Total Amendments (3 years): {patterns['total_amendments']}")
        logger.info(f"  Amendments Per Year: {patterns['amendments_per_year']:.1f}")
        logger.info(f"  Trend: {patterns['trend']}")
        logger.info(f"  Stability Score: {patterns['stability_score']:.2f}")
        if patterns["next_predicted"]:
            logger.info(
                f"  Next Predicted: {patterns['next_predicted'].strftime('%Y-%m-%d')}",
            )

        # Generate compliance calendar
        logger.info("\n📆 Compliance Calendar (Next 3 Months):")

        calendar = await tracker.generate_compliance_calendar(
            business_profile,
            months_ahead=3,
        )

        for month_key in sorted(list(calendar.keys()))[:3]:
            events = calendar[month_key]
            logger.info(f"\n  {month_key}:")
            for event in events[:3]:
                logger.info(
                    f"    • {event.event_date.strftime('%d')}: {event.regulation_title[:50]}",
                )
                logger.info(
                    f"      {event.urgency.value.upper()} - {event.action_required[:50]}",
                )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())
