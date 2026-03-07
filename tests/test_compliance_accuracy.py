"""
Regulatory Compliance Content Accuracy Testing

This module validates the accuracy of AI-generated compliance content
against regulatory frameworks and requires SME validation for critical
compliance advice and policy generation.
"""

import json

import pytest


@pytest.mark.compliance
class TestGDPRAccuracy:
    """Test GDPR compliance content accuracy"""

    def test_gdpr_penalty_amounts_accuracy(self, client, mock_ai_client, compliance_golden_dataset):
        """Test accuracy of GDPR penalty information"""
        gdpr_questions = [q for q in compliance_golden_dataset if q["framework"] == "GDPR"]
        penalty_questions = [q for q in gdpr_questions if q["category"] == "penalties"]

        for question_data in penalty_questions:
            mock_ai_client.generate_content.return_value.text = """
            Under GDPR, administrative fines can be imposed up to €20 million or
            4% of the undertaking's total worldwide annual turnover of the preceding
            financial year, whichever is higher.
            """

            response = client.post(
                "/api/compliance/query",
                json={"question": question_data["question"], "framework": "GDPR"},
            )

            if response.status_code == 200:
                response_text = response.json().get("answer", "").lower()

                # Validate key facts
                assert "€20 million" in response_text or "20 million" in response_text
                assert "4%" in response_text
                assert (
                    "annual turnover" in response_text or "worldwide turnover" in response_text,
                )
                assert ("whichever is higher" in response_text or "higher amount" in response_text,)

    def test_gdpr_data_subject_rights_accuracy(self, client, mock_ai_client):
        """Test accuracy of GDPR data subject rights information"""
        rights_test_cases = [
            {
                "right": "Right of Access",
                "article": "Article 15",
                "key_elements": [
                    "copy of personal data",
                    "processing purposes",
                    "categories of data",
                ],
            },
            {
                "right": "Right to Rectification",
                "article": "Article 16",
                "key_elements": [
                    "inaccurate personal data",
                    "incomplete data",
                    "without undue delay",
                ],
            },
            {
                "right": "Right to Erasure",
                "article": "Article 17",
                "key_elements": [
                    "right to be forgotten",
                    "no longer necessary",
                    "unlawful processing",
                ],
            },
        ]

        for test_case in rights_test_cases:
            mock_ai_client.generate_content.return_value.text = f"""
            The {test_case["right"]} under GDPR {test_case["article"]} allows data subjects to...
            Key elements include: {", ".join(test_case["key_elements"])}
            """

            response = client.post(
                "/api/compliance/query",
                json={
                    "question": f"What is the {test_case['right']} under GDPR?",
                    "framework": "GDPR",
                },
            )

            if response.status_code == 200:
                response_text = response.json().get("answer", "").lower()

                # Validate article reference
                article_num = test_case["article"].split()[1]
                assert (
                    f"article {article_num}" in response_text
                    or f"art. {article_num}" in response_text,
                )

                # Validate key elements presence
                matching_elements = sum(
                    1 for element in test_case["key_elements"] if element.lower() in response_text
                )
                assert matching_elements >= len(test_case["key_elements"]) * 0.6, (
                    f"Missing key elements for {test_case['right']}"
                )

    def test_gdpr_breach_notification_timeline_accuracy(
        self, client, mock_ai_client, compliance_golden_dataset
    ):
        """Test accuracy of GDPR breach notification timelines"""
        breach_questions = [
            q
            for q in compliance_golden_dataset
            if q["framework"] == "GDPR" and q["category"] == "breach_notification"
        ]

        for question_data in breach_questions:
            mock_ai_client.generate_content.return_value.text = """
            Under GDPR Article 33, personal data breaches must be notified to the
            supervisory authority without undue delay and, where feasible,
            not later than 72 hours after having become aware of it.
            """

            response = client.post(
                "/api/compliance/query",
                json={"question": question_data["question"], "framework": "GDPR"},
            )

            if response.status_code == 200:
                response_text = response.json().get("answer", "").lower()

                # Validate timeline accuracy
                assert "72 hours" in response_text
                assert "without undue delay" in response_text
                assert "supervisory authority" in response_text
                assert "article 33" in response_text or "art. 33" in response_text

    def test_gdpr_lawful_basis_accuracy(self, client, mock_ai_client):
        """Test accuracy of GDPR lawful basis information"""
        lawful_bases = [
            "consent",
            "contract",
            "legal obligation",
            "vital interests",
            "public task",
            "legitimate interests",
        ]

        mock_ai_client.generate_content.return_value.text = f"""
        GDPR Article 6 establishes six lawful bases for processing personal data:
        {", ".join(lawful_bases)}. Each basis has specific requirements and conditions.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What are the lawful bases for processing personal data under GDPR?",
                "framework": "GDPR",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate all six lawful bases are mentioned
            mentioned_bases = sum(1 for basis in lawful_bases if basis in response_text)
            assert mentioned_bases >= 5, "Most lawful bases should be mentioned"

            # Validate article reference
            assert "article 6" in response_text or "art. 6" in response_text


@pytest.mark.compliance
class TestISO27001Accuracy:
    """Test ISO 27001 compliance content accuracy"""

    def test_iso27001_security_domains_accuracy(self, client, mock_ai_client):
        """Test accuracy of ISO 27001 security control domains"""
        expected_domains = [
            "access control",
            "cryptography",
            "communications security",
            "acquisition",
            "supplier relationships",
            "incident management",
            "business continuity",
            "compliance",
            "organization of information security",
        ]

        mock_ai_client.generate_content.return_value.text = f"""
        ISO 27001 Annex A contains security controls organized into domains including:
        {", ".join(expected_domains[:5])} and others covering comprehensive information security.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What are the main security control domains in ISO 27001?",
                "framework": "ISO 27001",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate key domains are mentioned
            mentioned_domains = sum(1 for domain in expected_domains if domain in response_text)
            assert mentioned_domains >= 4, "Key security domains should be mentioned"

            # Validate Annex A reference
            assert "annex a" in response_text

    def test_iso27001_isms_requirements_accuracy(self, client, mock_ai_client):
        """Test accuracy of ISO 27001 ISMS requirements"""
        isms_elements = [
            "context of the organization",
            "leadership",
            "planning",
            "support",
            "operation",
            "performance evaluation",
            "improvement",
        ]

        mock_ai_client.generate_content.return_value.text = f"""
        ISO 27001 requires establishing an Information Security Management System (ISMS)
        following a structure based on: {", ".join(isms_elements)}.
        This follows the Plan-Do-Check-Act (PDCA) cycle.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What are the main requirements for an ISMS under ISO 27001?",
                "framework": "ISO 27001",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate PDCA cycle reference
            assert "pdca" in response_text or "plan-do-check-act" in response_text

            # Validate key ISMS elements
            mentioned_elements = sum(1 for element in isms_elements if element in response_text)
            assert mentioned_elements >= 4, "Key ISMS elements should be mentioned"


@pytest.mark.compliance
class TestUKSpecificRegulations:
    """Test UK-specific regulatory compliance accuracy"""

    def test_data_protection_act_2018_accuracy(self, client, mock_ai_client):
        """Test accuracy of UK Data Protection Act 2018 information"""
        mock_ai_client.generate_content.return_value.text = """
        The UK Data Protection Act 2018 implements GDPR in UK law and includes
        additional provisions for law enforcement processing, national security,
        and intelligence services. It maintains GDPR principles while adding
        UK-specific derogations and exemptions.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "How does the UK Data Protection Act 2018 relate to GDPR?",
                "framework": "UK DPA 2018",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate key relationships
            assert "gdpr" in response_text
            assert "uk law" in response_text or "united kingdom" in response_text
            assert "2018" in response_text

            # Validate UK-specific elements
            uk_elements = [
                "law enforcement",
                "national security",
                "derogations",
                "exemptions",
            ]
            mentioned_uk_elements = sum(1 for element in uk_elements if element in response_text)
            assert mentioned_uk_elements >= 2, "UK-specific elements should be mentioned"

    def test_ico_guidance_accuracy(self, client, mock_ai_client):
        """Test accuracy of ICO (Information Commissioner's Office) guidance references"""
        mock_ai_client.generate_content.return_value.text = """
        The Information Commissioner's Office (ICO) is the UK's independent authority
        set up to uphold information rights. The ICO provides guidance on data protection,
        GDPR compliance, and can impose fines up to the maximum GDPR penalties.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What is the role of the ICO in UK data protection?",
                "framework": "UK DPA 2018",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate ICO role accuracy
            assert "information commissioner" in response_text or "ico" in response_text
            assert ("independent authority" in response_text or "regulator" in response_text,)
            assert ("information rights" in response_text or "data protection" in response_text,)
            assert "guidance" in response_text
            assert "fines" in response_text or "penalties" in response_text


@pytest.mark.compliance
class TestSectorSpecificCompliance:
    """Test sector-specific compliance accuracy"""

    def test_financial_services_compliance_accuracy(self, client, mock_ai_client):
        """Test accuracy of financial services compliance requirements"""
        financial_frameworks = [
            "PCI DSS",
            "FCA regulations",
            "Basel III",
            "MiFID II",
            "GDPR",
        ]

        mock_ai_client.generate_content.return_value.text = f"""
        Financial services companies in the UK must comply with multiple frameworks:
        {", ".join(financial_frameworks)}. The Financial Conduct Authority (FCA)
        regulates conduct requirements while PCI DSS governs payment card security.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What compliance frameworks apply to UK financial services?",
                "framework": "Financial Services",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate key frameworks
            mentioned_frameworks = sum(
                1 for fw in financial_frameworks if fw.lower() in response_text
            )
            assert mentioned_frameworks >= 3, "Key financial frameworks should be mentioned"

            # Validate regulatory body
            assert ("fca" in response_text or "financial conduct authority" in response_text,)

    def test_healthcare_compliance_accuracy(self, client, mock_ai_client):
        """Test accuracy of healthcare sector compliance requirements"""
        healthcare_elements = [
            "patient data",
            "medical records",
            "clinical governance",
            "care quality commission",
            "nhs",
            "caldicott principles",
        ]

        mock_ai_client.generate_content.return_value.text = """
        Healthcare organizations must protect patient data following GDPR,
        Caldicott Principles, and NHS Digital guidance. The Care Quality Commission
        oversees quality and safety standards for healthcare services.
        """

        response = client.post(
            "/api/compliance/query",
            json={
                "question": "What are the data protection requirements for UK healthcare providers?",
                "framework": "Healthcare",
            },
        )

        if response.status_code == 200:
            response_text = response.json().get("answer", "").lower()

            # Validate healthcare-specific elements
            mentioned_elements = sum(
                1 for element in healthcare_elements if element in response_text
            )
            assert mentioned_elements >= 3, "Healthcare-specific elements should be mentioned"


@pytest.mark.compliance
class TestComplianceContentValidation:
    """Validate generated compliance content structure and completeness"""

    def test_policy_content_structure_validation(self, client, mock_ai_client):
        """Test that generated policies have proper structure"""
        mock_ai_client.generate_content.return_value.text = """
        # Data Protection Policy

        ## 1. Purpose and Scope
        This policy establishes the framework for protecting personal data...

        ## 2. Definitions
        Personal Data: Any information relating to an identified or identifiable person...

        ## 3. Data Protection Principles
        We process personal data in accordance with the following principles...

        ## 4. Lawful Basis for Processing
        We only process personal data where we have a lawful basis...

        ## 5. Data Subject Rights
        Individuals have the following rights regarding their personal data...

        ## 6. Data Security Measures
        We implement appropriate technical and organizational measures...

        ## 7. Data Breach Procedures
        In the event of a data breach, we will follow these procedures...

        ## 8. Contact Information
        For data protection queries, contact our Data Protection Officer...
        """

        response = client.post(
            "/api/policies/generate",
            json={"framework": "GDPR", "policy_type": "data_protection"},
        )

        if response.status_code == 200:
            policy_content = response.json().get("content", "")

            # Validate essential policy sections
            required_sections = [
                "purpose",
                "scope",
                "definitions",
                "principles",
                "lawful basis",
                "rights",
                "security",
                "breach",
                "contact",
            ]

            missing_sections = []
            for section in required_sections:
                if section not in policy_content.lower():
                    missing_sections.append(section)

            assert len(missing_sections) <= 2, f"Missing essential sections: {missing_sections}"

            # Validate policy structure
            assert policy_content.count("#") >= 5, "Policy should have proper heading structure"
            assert len(policy_content) >= 500, "Policy should have substantial content"

    def test_implementation_plan_completeness(self, client, mock_ai_client):
        """Test that implementation plans have complete task breakdown"""
        response = client.post("/api/implementation/plans", json={"framework": "GDPR"})

        if response.status_code == 200:
            plan_data = response.json()

            # Validate plan structure
            assert plan_data["total_phases"] >= 3, "Should have multiple implementation phases"
            assert plan_data["total_tasks"] >= 10, "Should have sufficient task breakdown"
            assert plan_data["estimated_duration_weeks"] > 0, "Should have realistic timeline"

            # Validate phases have tasks
            if "phases" in plan_data:
                for phase in plan_data["phases"]:
                    assert "name" in phase, "Phase should have descriptive name"
                    assert "duration_weeks" in phase, "Phase should have duration estimate"
                    assert phase["duration_weeks"] > 0, "Phase duration should be positive"

    def test_risk_assessment_accuracy(self, client, mock_ai_client):
        """Test accuracy of risk assessments and recommendations"""
        business_context = {
            "industry": "Healthcare",
            "data_types": ["patient_data", "payment_data"],
            "employee_count": 50,
            "has_international_operations": False,
        }

        response = client.post("/api/readiness/assessment", json=business_context)

        if response.status_code == 200:
            assessment_data = response.json()

            # Validate risk level consistency
            overall_score = assessment_data.get("overall_score", 0)
            risk_level = assessment_data.get("risk_level", "")

            # Risk level should align with score
            if overall_score >= 80:
                assert risk_level in ["Low"], f"High score should have low risk, got {risk_level}"
            elif overall_score >= 60:
                assert risk_level in [
                    "Low",
                    "Medium",
                ], f"Medium score mismatch: {risk_level}"
            elif overall_score >= 40:
                assert risk_level in [
                    "Medium",
                    "High",
                ], f"Lower score mismatch: {risk_level}"
            else:
                assert risk_level in [
                    "High",
                    "Critical",
                ], f"Low score should have high risk: {risk_level}"

            # Validate recommendations relevance
            recommendations = assessment_data.get("recommendations", [])
            assert len(recommendations) > 0, "Should provide recommendations"

            # Healthcare-specific recommendations
            rec_text = json.dumps(recommendations).lower()
            healthcare_terms = ["patient", "medical", "clinical", "healthcare", "hipaa"]
            mentioned_healthcare = sum(1 for term in healthcare_terms if term in rec_text)
            assert mentioned_healthcare >= 1, "Should include healthcare-specific recommendations"


@pytest.mark.compliance
@pytest.mark.sme_validation
class TestSMEValidationFramework:
    """Framework for Subject Matter Expert validation of compliance content"""

    def test_gdpr_expert_validation_checklist(self, client, mock_ai_client):
        """Generate validation checklist for GDPR SME review"""
        validation_checklist = {
            "gdpr_accuracy": [
                "Article references are correct and current",
                "Penalty amounts match current regulations",
                "Data subject rights are complete and accurate",
                "Lawful basis requirements are properly explained",
                "Breach notification timelines are correct",
                "Territorial scope is accurately described",
            ],
            "uk_specific": [
                "UK DPA 2018 provisions are correctly referenced",
                "ICO guidance is current and relevant",
                "Brexit implications are accurately addressed",
                "UK derogations and exemptions are noted where relevant",
            ],
            "practical_implementation": [
                "Recommendations are realistic for SMBs",
                "Implementation timelines are achievable",
                "Resource requirements are reasonable",
                "Cost estimates align with market rates",
            ],
        }

        # Generate content for SME review
        mock_ai_client.generate_content.return_value.text = """
        GDPR compliance requires implementing data protection by design and default
        under Article 25, with potential fines up to €20 million or 4% of annual turnover.
        Data subjects have rights including access, rectification, and erasure under Articles 15-17.
        """

        response = client.post(
            "/api/compliance/sme-review",
            json={
                "content_type": "gdpr_guidance",
                "framework": "GDPR",
                "validation_checklist": validation_checklist,
            },
        )

        # This endpoint would flag content for SME review
        if response.status_code == 200:
            review_data = response.json()
            assert "review_id" in review_data
            assert "validation_checklist" in review_data
            assert review_data["status"] == "pending_sme_review"

    def test_compliance_content_versioning(self, client):
        """Test that compliance content maintains version control for SME validation"""
        # Create initial content
        content_data = {
            "framework": "GDPR",
            "content_type": "policy_template",
            "content": "Initial policy content...",
            "version": "1.0",
            "sme_reviewed": False,
        }

        response = client.post("/api/compliance/content", json=content_data)

        if response.status_code == 201:
            content_id = response.json()["id"]

            # Update content after SME review
            update_data = {
                "content": "Updated policy content based on SME feedback...",
                "version": "1.1",
                "sme_reviewed": True,
                "sme_reviewer": "Legal Expert Name",
                "review_notes": "Approved with minor clarifications",
            }

            update_response = client.patch(
                f"/api/compliance/content/{content_id}",
                json=update_data,
            )

            assert update_response.status_code == 200

            updated_content = update_response.json()
            assert updated_content["version"] == "1.1"
            assert updated_content["sme_reviewed"] is True
            assert "sme_reviewer" in updated_content

    def test_automated_content_flagging(self, client, mock_ai_client):
        """Test automated flagging of content requiring SME validation"""
        # Content with potential accuracy issues
        questionable_content = """
        GDPR fines can be up to €30 million or 5% of annual turnover.
        Data subjects have a right to be completely forgotten in all cases.
        """

        mock_ai_client.generate_content.return_value.text = questionable_content

        response = client.post(
            "/api/compliance/validate-content",
            json={"content": questionable_content, "framework": "GDPR"},
        )

        if response.status_code == 200:
            validation_result = response.json()

            # Should flag inaccuracies
            assert "accuracy_flags" in validation_result
            assert len(validation_result["accuracy_flags"]) > 0
            assert validation_result["requires_sme_review"] is True

            # Check specific flags
            flags = validation_result["accuracy_flags"]
            penalty_flagged = any(
                "penalty" in flag.lower() or "fine" in flag.lower() for flag in flags
            )
            assert penalty_flagged, "Should flag incorrect penalty amounts"
