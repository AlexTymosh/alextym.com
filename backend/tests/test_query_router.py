from app.rag.query_router import route_query


def test_query_router_routes_hard_skills() -> None:
    route = route_query("What are Alex's hard skills?")

    assert route.intent == "hard_skills"
    assert route.topic_hints == ("hard-skills",)
    assert "python" in route.tag_hints
    assert route.should_offer_handoff is False
    assert "hard-skills" in route.retrieval_text("skills")
    assert route.payload_filter() is None


def test_query_router_routes_soft_skills() -> None:
    route = route_query("What are Alex's soft skills?")

    assert route.intent == "soft_skills"
    assert route.topic_hints == ("soft-skills-working-style",)
    assert "working-style" in route.tag_hints
    assert route.payload_filter() is None


def test_query_router_routes_right_to_work_with_handoff() -> None:
    route = route_query("Can Alex provide a share code?")

    assert route.intent == "right_to_work"
    assert route.topic_hints == ("right-to-work-uk-location",)
    assert "share-code" in route.tag_hints
    assert route.should_offer_handoff is True
    assert route.payload_filter() is None


def test_query_router_routes_availability_with_handoff() -> None:
    route = route_query("When can Alex start a new job?")

    assert route.intent == "availability"
    assert route.topic_hints == ("availability-start-date",)
    assert "start-date" in route.tag_hints
    assert route.should_offer_handoff is True
    assert route.payload_filter() is None


def test_query_router_routes_projects() -> None:
    route = route_query("Tell me about Alex's RAG portfolio project.")

    assert route.intent == "projects"
    assert "project-ai-portfolio-rag-chat" in route.topic_hints
    assert "project-gdpr-aware-saas-automation-platform" in route.topic_hints
    assert "rag" in route.tag_hints
    assert route.payload_filter() is None


def test_query_router_routes_education() -> None:
    route = route_query("What is Alex's education?")

    assert route.intent == "education"
    assert "education" in route.section_hints
    assert "training" in route.section_hints
    assert route.payload_filter() is None


def test_query_router_routes_experience() -> None:
    route = route_query("Tell me about Alex's Odoo and ERP experience.")

    assert route.intent == "experience"
    assert "erp" in route.tag_hints
    assert "experience" in route.section_hints
    assert route.payload_filter() is None


def test_query_router_routes_out_of_scope_subjects() -> None:
    route = route_query("Who is Elon Musk?")

    assert route.intent == "out_of_scope"
    assert route.topic_hints == ()
    assert route.tag_hints == ()
    assert route.payload_filter() is None


def test_query_router_returns_general_profile_for_broad_profile_query() -> None:
    route = route_query("Tell me about Alex.")

    assert route.intent == "general_profile"
    assert "profile" in route.tag_hints
    assert route.payload_filter() is None


def test_query_router_keeps_broad_hints_out_of_payload_filter() -> None:
    route = route_query("What are Alex's hard skills?")

    assert route.topic_hints == ("hard-skills",)
    assert route.tag_hints
    assert route.payload_filter() is None


def test_query_router_routes_case_limitations_to_case_studies() -> None:
    route = route_query(
        "What limitations applied to the site owner's corporate credit-risk analysis?"
    )

    assert route.intent == "general_profile"
    assert route.source_scope == "case_studies"
    assert route.case_section_hints == ("limitations", "analysis")
    assert route.select_single_case is True
    assert route.payload_filter() is not None
    assert route.payload_filter().source_group_any == ("case-studies",)


def test_query_router_keeps_personal_limitations_on_public_boundary() -> None:
    route = route_query("What are Alex's professional limitations?")

    assert route.intent == "public_boundary"
    assert route.source_scope == "resume"
    assert route.select_single_case is False
    assert route.payload_filter() is not None
    assert route.payload_filter().source_group_any == ("resume",)


def test_query_router_separates_service_design_from_commercial_services() -> None:
    case_route = route_query(
        "How did the site owner design an end-to-end international employment service?"
    )
    commercial_route = route_query("What services does Alex offer?")

    assert case_route.intent == "general_profile"
    assert case_route.source_scope == "case_studies"
    assert case_route.case_section_hints == ("implementation",)
    assert case_route.select_single_case is True

    assert commercial_route.intent == "services"
    assert commercial_route.source_scope == "resume"
    assert commercial_route.select_single_case is False


def test_query_router_uses_token_boundaries_for_service_terms() -> None:
    route = route_query("Has Alex worked with microservices?")

    assert route.intent != "services"


def test_query_router_models_multiple_case_section_intents() -> None:
    route = route_query(
        "Give an example where Alex rejected additional automation because ROI was too low."
    )

    assert route.source_scope == "case_studies"
    assert route.case_section_hints == ("limitations", "implementation")
    assert route.select_single_case is True
