"""

# Constants
HTTP_OK = 200


Regulation API client for fetching real regulation data from official sources.
Uses XML APIs instead of scraping for better reliability and structure.
"""

import asyncio
import requests
import defusedxml.ElementTree as ET  # Use defusedxml to prevent XXE attacks
from typing import Dict, Any, List
from datetime import datetime
import json
import logging
from pathlib import Path
import hashlib
import re
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RegulationAPIClient:
    """Client for fetching regulation data from official APIs."""

    def __init__(self) -> None:
        self.cache_dir = Path("data/regulation_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.executor = ThreadPoolExecutor(max_workers=3)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/xml, text/xml, */*",
            "Accept-Language": "en-GB,en;q=0.9",
        }
        self.api_endpoints = {
            "uk_legislation": {
                "base_url": "https://www.legislation.gov.uk",
                "data_format": "/data.xml",
                "atom_feed": "/data.feed",
                "publication_log": "/new/data.feed",
            },
            "fca_handbook": {
                "base_url": "https://www.handbook.fca.org.uk",
                "api_path": "/api/handbook",
            },
            "ico": {
                "base_url": "https://ico.org.uk",
                "enforcement_path": "/action-weve-taken/enforcement/",
            },
            "eur_lex": {
                "base_url": "https://eur-lex.europa.eu",
                "ws_path": "/webservices/rest/",
                "search_api": "https://publications.europa.eu/webapi/rdf/sparql",
            },
        }

    async def __aenter__(self) -> Any:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.executor.shutdown(wait=False)

    async def fetch_uk_legislation(self, url: str) -> Dict[str, Any]:
        """
        Fetch UK legislation data using the official XML API.

        Args:
            url: The legislation.gov.uk URL

        Returns:
            Parsed regulation data with requirements and penalties
        """
        if not url.endswith("/data.xml"):
            base_url = url.replace("/contents", "").rstrip("/")
            api_url = base_url + "/data.xml"
        else:
            api_url = url
        logger.info("Fetching UK legislation from: %s" % api_url)
        url_hash = hashlib.md5(api_url.encode(), usedforsecurity=False).hexdigest()
        cache_file = self.cache_dir / f"uk_{url_hash}.json"
        if cache_file.exists():
            logger.info("Using cached data for %s" % api_url)
            with open(cache_file, "r") as f:
                return json.load(f)
        loop = asyncio.get_event_loop()
        try:
            logger.info("Making request to %s" % api_url)
            response = await loop.run_in_executor(
                self.executor, lambda: requests.get(api_url, headers=self.headers, timeout=30)
            )
            logger.info("Response status: %s" % response.status_code)
            if response.status_code == HTTP_OK:
                xml_content = response.text
                logger.info("Received %s characters of XML" % len(xml_content))
                parsed_data = self._parse_clml_xml(xml_content, api_url)
                with open(cache_file, "w") as f:
                    json.dump(parsed_data, f, indent=2)
                return parsed_data
            else:
                logger.error("Failed to fetch %s: %s" % (api_url, response.status_code))
                logger.error("Error response: %s" % response.text[:500])
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}",
                }
        except (OSError, json.JSONDecodeError, requests.RequestException) as e:
            logger.error("Error fetching %s: %s" % (api_url, e))
            return {"success": False, "error": str(e)}

    def _parse_clml_xml(self, xml_content: str, url: str) -> Dict[str, Any]:
        """Parse Crown Legislation Markup Language (CLML) XML."""
        try:
            root = ET.fromstring(xml_content)
            namespaces = {
                "leg": "http://www.legislation.gov.uk/namespaces/legislation",
                "dc": "http://purl.org/dc/elements/1.1/",
                "atom": "http://www.w3.org/2005/Atom",
                "ukm": "http://www.legislation.gov.uk/namespaces/metadata",
            }
            title = self._get_xml_text(root, ".//dc:title", namespaces, "Unknown Title")
            description = self._get_xml_text(root, ".//dc:description", namespaces, "")
            doc_type = self._get_xml_text(root, ".//ukm:DocumentMainType", namespaces, "")
            year = self._get_xml_text(root, ".//ukm:Year", namespaces, "")
            number = self._get_xml_text(root, ".//ukm:Number", namespaces, "")
            requirements = self._extract_requirements_from_xml(root, namespaces)
            penalties = self._extract_penalties_from_xml(root, namespaces)
            enforcement = self._extract_enforcement_from_xml(root, namespaces)
            dates = self._extract_dates_from_xml(root, namespaces)
            controls = self._extract_controls_from_xml(root, namespaces)
            return {
                "success": True,
                "url": url,
                "fetched_at": datetime.now().isoformat(),
                "metadata": {
                    "title": title,
                    "description": description,
                    "type": doc_type,
                    "year": year,
                    "number": number,
                },
                "requirements": requirements,
                "penalties": penalties,
                "enforcement": enforcement,
                "dates": dates,
                "controls": controls,
                "xml_length": len(xml_content),
            }
        except (ValueError, TypeError) as e:
            logger.error("Error parsing CLML XML: %s" % e)
            return {"success": False, "error": f"XML parsing error: {str(e)}"}

    def _get_xml_text(self, element, xpath: str, namespaces: dict, default: str = "") -> str:
        """Safely extract text from XML element."""
        try:
            found = element.find(xpath, namespaces)
            return found.text if found is not None and found.text else default
        except OSError:
            return default

    def _extract_requirements_from_xml(self, root, namespaces) -> List[Dict[str, Any]]:
        """Extract legal requirements from CLML XML."""
        requirements = []
        provisions = root.findall(".//leg:P1", namespaces) or root.findall(".//leg:P", namespaces)
        for provision in provisions[:50]:
            text_content = "".join(provision.itertext()).strip()
            if any(
                keyword in text_content.lower()
                for keyword in ["shall", "must", "required", "obliged", "duty"]
            ):
                prov_num = provision.get("id", "")
                requirements.append(
                    {
                        "id": prov_num,
                        "text": text_content[:500],
                        "type": "mandatory",
                        "keywords": self._extract_requirement_keywords(text_content),
                    }
                )
        return requirements

    def _extract_requirement_keywords(self, text: str) -> List[str]:
        """Extract key compliance keywords from requirement text."""
        keywords = []
        keyword_patterns = {
            "data_protection": ["personal data", "data protection", "privacy", "GDPR"],
            "security": ["security", "encryption", "access control", "authentication"],
            "reporting": ["report", "notify", "inform", "disclose"],
            "consent": ["consent", "permission", "authorization"],
            "retention": ["retain", "retention", "storage period"],
            "audit": ["audit", "review", "assessment", "monitoring"],
        }
        text_lower = text.lower()
        for category, patterns in keyword_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                keywords.append(category)
        return keywords

    def _extract_penalties_from_xml(self, root, namespaces) -> List[Dict[str, Any]]:
        """Extract penalty information from CLML XML."""
        penalties = []
        penalty_sections = root.findall(".//leg:P1group", namespaces)
        for section in penalty_sections:
            section_text = "".join(section.itertext()).strip().lower()
            if any(
                keyword in section_text
                for keyword in ["penalty", "fine", "offence", "sanction", "imprisonment"]
            ):
                money_matches = re.findall(
                    "£[\\d,]+(?:\\.\\d{2})?(?:\\s*(?:million|billion))?",
                    section_text,
                    re.IGNORECASE,
                )
                for match in money_matches[:3]:
                    penalties.append(
                        {"type": "financial", "amount": match, "context": section_text[:200]}
                    )
                percent_matches = re.findall(
                    "(\\d+(?:\\.\\d+)?)\\s*%\\s*of\\s*(?:annual\\s*)?(?:global\\s*)?(?:turnover|revenue)",
                    section_text,
                )
                for match in percent_matches[:2]:
                    penalties.append(
                        {
                            "type": "percentage",
                            "amount": f"{match}% of turnover",
                            "context": section_text[:200],
                        }
                    )
                if "imprison" in section_text:
                    prison_match = re.search("(?:up to\\s*)?(\\d+)\\s*(?:year|month)", section_text)
                    if prison_match:
                        penalties.append(
                            {
                                "type": "criminal",
                                "description": f"Imprisonment up to {prison_match.group(0)}",
                                "context": section_text[:200],
                            }
                        )
        return penalties

    def _extract_enforcement_from_xml(self, root, namespaces) -> Dict[str, Any]:
        """Extract enforcement provisions from CLML XML."""
        enforcement = {"authority": [], "powers": [], "procedures": []}
        for element in root.findall(".//leg:P1", namespaces):
            text = "".join(element.itertext()).strip()
            authorities = [
                "Information Commissioner",
                "FCA",
                "Financial Conduct Authority",
                "Prudential Regulation Authority",
                "PRA",
                "Secretary of State",
                "Ofcom",
                "Competition and Markets Authority",
            ]
            for authority in authorities:
                if authority in text:
                    enforcement["authority"].append(authority)
            if any(
                power in text.lower()
                for power in ["investigate", "inspect", "audit", "enforce", "prosecute"]
            ):
                enforcement["powers"].append(text[:200])
        enforcement["authority"] = list(set(enforcement["authority"]))
        return enforcement

    def _extract_dates_from_xml(self, root, namespaces) -> List[Dict[str, Any]]:
        """Extract important dates from CLML XML."""
        dates = []
        commencement = self._get_xml_text(root, ".//ukm:CommencementDate", namespaces, "")
        if commencement:
            dates.append(
                {
                    "type": "commencement",
                    "date": commencement,
                    "description": "Regulation comes into force",
                }
            )
        enactment = self._get_xml_text(root, ".//ukm:EnactmentDate", namespaces, "")
        if enactment:
            dates.append(
                {"type": "enactment", "date": enactment, "description": "Date of enactment"}
            )
        for element in root.findall(".//leg:P1", namespaces):
            text = "".join(element.itertext()).strip()
            date_patterns = [
                "by\\s+(\\d{1,2}\\s+\\w+\\s+\\d{4})",
                "before\\s+(\\d{1,2}\\s+\\w+\\s+\\d{4})",
                "within\\s+(\\d+)\\s+(?:days|months|years)",
                "no later than\\s+(\\d{1,2}\\s+\\w+\\s+\\d{4})",
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches[:2]:
                    dates.append({"type": "deadline", "date": match, "context": text[:150]})
        return dates

    def _extract_controls_from_xml(self, root, namespaces) -> List[str]:
        """Extract suggested compliance controls from CLML XML."""
        controls = set()
        control_map = {
            "access_control": ["access control", "authorization", "permission"],
            "encryption": ["encrypt", "cryptograph"],
            "audit_logging": ["audit", "log", "record keeping"],
            "risk_assessment": ["risk assessment", "risk analysis"],
            "incident_response": ["incident", "breach notification"],
            "data_minimization": ["data minimization", "minimize", "necessary"],
            "consent_management": ["consent", "opt-in", "opt-out"],
            "training": ["training", "awareness", "education"],
            "dpia": ["data protection impact assessment", "DPIA"],
            "security_testing": ["testing", "vulnerability", "penetration test"],
        }
        all_text = "".join(root.itertext()).lower()
        for control_name, keywords in control_map.items():
            if any(keyword in all_text for keyword in keywords):
                controls.add(control_name)
        return list(controls)

    async def fetch_fca_enforcement(self) -> List[Dict[str, Any]]:
        """Fetch FCA enforcement data."""
        url = "https://www.fca.org.uk/news/search-results/enforcement"
        try:
            async with self.session.get(url) as response:
                if response.status == HTTP_OK:
                    await response.text()
                    enforcements = []
                    return enforcements
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Error fetching FCA enforcement: %s" % e)
            return []

    async def fetch_regulation_updates(self, since_date: str) -> List[Dict[str, Any]]:
        """
        Fetch recent regulation updates using ATOM feeds.

        Args:
            since_date: ISO date string to fetch updates since

        Returns:
            List of regulation updates
        """
        feed_url = "https://www.legislation.gov.uk/new/data.feed"
        updates = []
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                self.executor, lambda: requests.get(feed_url, headers=self.headers, timeout=30)
            )
            if response.status_code == HTTP_OK:
                content = response.text
                root = ET.fromstring(content)
                namespaces = {"atom": "http://www.w3.org/2005/Atom"}
                entries = root.findall(".//atom:entry", namespaces)
                for entry in entries[:20]:
                    updates.append(
                        {
                            "title": self._get_xml_text(entry, "atom:title", namespaces),
                            "updated": self._get_xml_text(entry, "atom:updated", namespaces),
                            "link": entry.find("atom:link", namespaces).get("href")
                            if entry.find("atom:link", namespaces) is not None
                            else "",
                            "summary": self._get_xml_text(entry, "atom:summary", namespaces),
                        }
                    )
        except (requests.RequestException, KeyError, IndexError) as e:
            logger.error("Error fetching regulation updates: %s" % e)
        return updates


async def test_api_client() -> None:
    """Test the regulation API client."""
    async with RegulationAPIClient() as client:
        test_urls = [
            "https://www.legislation.gov.uk/ukpga/2018/12/contents",
            "https://www.legislation.gov.uk/ukpga/2000/8/contents",
            "https://www.legislation.gov.uk/uksi/2017/692/contents",
        ]
        for test_url in test_urls[:1]:
            logger.info("Testing with %s" % test_url)
            result = await client.fetch_uk_legislation(test_url)
            if result["success"]:
                logger.info("✅ Successfully fetched regulation")
                logger.info("  Title: %s" % result["metadata"]["title"])
                logger.info("  Requirements found: %s" % len(result["requirements"]))
                logger.info("  Penalties found: %s" % len(result["penalties"]))
                logger.info("  Controls identified: %s" % result["controls"])
                filename = f"data/sample_{test_url.split('/')[-2]}_result.json"
                with open(filename, "w") as f:
                    json.dump(result, f, indent=2)
                logger.info("  Saved to: %s" % filename)
            else:
                logger.error("❌ Failed: %s" % result.get("error"))
        updates = await client.fetch_regulation_updates("2024-01-01")
        logger.info("Found %s recent regulation updates" % len(updates))


if __name__ == "__main__":
    asyncio.run(test_api_client())
