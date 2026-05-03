from app.services.infographic_planner import plan_gas_tax_public_explainer, plan_infographics


def _sample_tree():
    return {
        "id": "root",
        "type": "central",
        "question": "Should Australia tax gas more?",
        "summary": "Australia is debating whether gas exporters pay enough for public resources.",
        "scores": {
            "confidence": "high",
            "contestedness": "disputed",
            "salience": "high",
            "stance_summary": "The debate weighs public revenue against investment certainty.",
        },
        "children": [
            {
                "id": "tax25",
                "type": "downstream",
                "question": "25% windfall tax: implement the proposed tax",
                "summary": "Supporters say revenue could fund relief; opponents warn about investment.",
                "scores": {"confidence": "medium", "contestedness": "disputed", "salience": "high"},
                "children": [
                    {
                        "id": "revenue",
                        "type": "downstream",
                        "question": "How much revenue would the tax raise?",
                        "summary": "Revenue estimates are material but contested.",
                        "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high", "stance_summary": "Revenue could be significant, but estimates depend on design."},
                        "children": [],
                    },
                    {
                        "id": "risk",
                        "type": "downstream",
                        "question": "Would investors flee?",
                        "summary": "Investment flight claims are disputed.",
                        "scores": {"confidence": "low", "contestedness": "contested", "salience": "moderate", "stance_summary": "Evidence does not support a precise 12-month capital-flight timeline."},
                        "children": [],
                    },
                ],
            },
            {
                "id": "norway",
                "type": "analogy",
                "question": "Where has something like this been tried elsewhere?",
                "summary": "Norway and the UK show different resource tax outcomes.",
                "scores": {"confidence": "high", "contestedness": "contested", "salience": "high"},
                "children": [
                    {
                        "id": "norway-child",
                        "type": "analogy",
                        "question": "How did Norway's petroleum tax work?",
                        "summary": "Norway paired high tax rates with neutrality and a sovereign wealth fund.",
                        "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"},
                        "children": [],
                    }
                ],
            },
        ],
    }


def test_plan_infographics_returns_renderable_sequence():
    plan = plan_infographics(
        {
            "topic": "Gas windfall tax",
            "intent": "Explain the debate",
            "stakeholders": [{"name": "Households"}, {"name": "Gas exporters"}],
        },
        _sample_tree(),
    )

    assert plan["schema_version"] == "infographic-plan/v1"
    assert plan["topic"] == "Gas windfall tax"
    assert plan["slide_count"] >= 6
    assert len(plan["sequence"]) == plan["slide_count"]

    first = plan["sequence"][0]
    assert first["slide_type"] == "overview"
    assert first["title"]
    assert first["image_prompt"].startswith("Create one simple educational infographic slide")
    assert "do not invent" in first["image_prompt"].lower()
    assert "sketchnote" in first["image_prompt"].lower()
    assert "no dense paragraphs" in plan["style_preset"].lower()


def test_plan_infographics_includes_precedent_and_confidence_slides():
    plan = plan_infographics({"topic": "Gas windfall tax"}, _sample_tree())
    slide_types = [s["slide_type"] for s in plan["sequence"]]

    assert "precedent_timeline" in slide_types
    assert "confidence_map" in slide_types

    confidence_slide = next(s for s in plan["sequence"] if s["slide_type"] == "confidence_map")
    assert any("High-confidence points" in f["text"] for f in confidence_slide["facts"])


def test_plan_infographics_includes_story_depth_slides_when_nodes_exist():
    tree = _sample_tree()
    tree["children"].extend([
        {"id": "worked", "type": "analogy", "question": "Which countries tried higher resource or windfall taxes, and where did it work?", "summary": "Norway is often cited as a success case.", "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"}, "children": []},
        {"id": "backfire", "type": "analogy", "question": "Where did resource or windfall tax reforms backfire, and why?", "summary": "Australia's RSPT fight shows campaign and design risks.", "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"}, "children": []},
        {"id": "campaign", "type": "free", "question": "What misinformation or misleading claims commonly appear in resource-tax debates?", "summary": "Campaigns can simplify complex tax designs into slogans.", "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"}, "children": []},
        {"id": "debt", "type": "upstream", "question": "How has Australian government debt changed since 2006, and who was in power?", "summary": "Debt timelines should show government changes and economic shocks.", "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"}, "children": []},
    ])

    plan = plan_infographics({"topic": "Gas windfall tax"}, tree, format="tiktok")
    slide_types = [s["slide_type"] for s in plan["sequence"]]

    assert "country_success_cases" in slide_types
    assert "country_backfire_cases" in slide_types
    assert "campaign_influence" in slide_types
    assert "debt_chapter_intro" in slide_types
    assert "debt_who_in_power" in slide_types
    assert "debt_why_not_paid_down" in slide_types
    assert "debt_unwind_options" in slide_types


def test_plan_infographics_splits_cases_and_adds_number_slides():
    plan = plan_infographics({"topic": "Gas windfall tax"}, _sample_tree(), format="tiktok")
    slide_types = [s["slide_type"] for s in plan["sequence"]]

    assert "tax_revenue_numbers" in slide_types
    assert "spending_numbers" in slide_types
    assert "extra_money_sources" in slide_types
    assert "tax_per_person" in slide_types
    assert "tax_pressure_reasons" in slide_types
    assert "spending_breakdown_welfare" in slide_types
    assert "spending_breakdown_health" in slide_types
    assert "spending_breakdown_defence" in slide_types
    assert slide_types.index("extra_money_sources") == slide_types.index("spending_timeline") + 1
    assert slide_types.index("tax_per_person") == slide_types.index("extra_money_sources") + 1
    assert slide_types.index("tax_pressure_reasons") == slide_types.index("tax_per_person") + 1
    assert slide_types.index("spending_breakdown_welfare") == slide_types.index("spending_numbers") + 1
    assert "supporters_case" in slide_types
    assert "opponents_case" in slide_types
    assert "viewpoint_compare" not in slide_types

    tax_slide = next(s for s in plan["sequence"] if s["slide_type"] == "tax_revenue_numbers")
    assert any("$338b" in f["text"] for f in tax_slide["facts"])
    spending_slide = next(s for s in plan["sequence"] if s["slide_type"] == "spending_numbers")
    assert any("37%" in f["text"] for f in spending_slide["facts"])
    welfare_slide = next(s for s in plan["sequence"] if s["slide_type"] == "spending_breakdown_welfare")
    assert welfare_slide["parent"] == "spending_numbers"
    assert welfare_slide["depth"] == 2
    assert welfare_slide["template_id"] == "SPENDING_BREAKDOWN"
    assert welfare_slide["render_contract"]["map_to_reference_blocks"]["left_total_spend"] == "Welfare $291b"
    extra_money_slide = next(s for s in plan["sequence"] if s["slide_type"] == "extra_money_sources")
    assert extra_money_slide["chapter"] == "Money context"
    assert extra_money_slide["parent"] == "spending_timeline"
    assert any("Total cash receipts rose from $236.7b" in f["text"] for f in extra_money_slide["facts"])
    tax_per_person_slide = next(s for s in plan["sequence"] if s["slide_type"] == "tax_per_person")
    assert tax_per_person_slide["chapter"] == "Money context"
    assert tax_per_person_slide["depth"] == 3
    assert tax_per_person_slide["parent"] == "extra_money_sources"
    assert any("$10,400 to about $23,800" in f["text"] for f in tax_per_person_slide["facts"])
    tax_pressure_slide = next(s for s in plan["sequence"] if s["slide_type"] == "tax_pressure_reasons")
    assert tax_pressure_slide["parent"] == "tax_per_person"
    assert tax_pressure_slide["slide_id"] == "money.tax_pressure_reasons"
    assert any("bracket creep" in f["text"] for f in tax_pressure_slide["facts"])


def test_detail_contracts_use_meaningful_labels_not_placeholders():
    plan = plan_infographics({"topic": "Gas windfall tax"}, _sample_tree(), format="tiktok")

    detail_slide = next(s for s in plan["sequence"] if s["slide_type"] == "spending_detail_gillard_ndis")
    blocks = detail_slide["render_contract"]["map_to_reference_blocks"]
    middle_labels = {blocks[f"middle_bucket_{i}"]["label"] for i in range(1, 5)}

    assert "Scale" not in middle_labels
    assert "Evidence" not in middle_labels
    assert {"What it pays for", "Who benefits", "What can go wrong", "Debt context"} <= middle_labels


def test_plan_infographics_adds_backend_timeline_metadata_to_every_slide():
    tree = _sample_tree()
    tree["children"].append(
        {
            "id": "debt",
            "type": "upstream",
            "question": "How has Australian government debt changed since 2006, and who was in power?",
            "summary": "Debt timelines should show government changes and economic shocks.",
            "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"},
            "children": [],
        }
    )

    plan = plan_infographics({"topic": "Gas windfall tax"}, tree, format="tiktok")
    slides = plan["sequence"]

    assert all(slide["chapter"] for slide in slides)
    assert all("parent_slide_index" in slide for slide in slides)

    by_type = {slide["slide_type"]: (index, slide) for index, slide in enumerate(slides)}
    spending_numbers_index, _ = by_type["spending_numbers"]
    _, welfare_slide = by_type["spending_breakdown_welfare"]
    _, debt_fault_slide = by_type["debt_fault_map"]

    assert welfare_slide["chapter"] == "Where the money goes"
    assert welfare_slide["depth"] == 2
    assert welfare_slide["parent"] == "spending_numbers"
    assert welfare_slide["parent_slide_index"] == spending_numbers_index
    assert debt_fault_slide["chapter"] == "Debt chapter"
    assert debt_fault_slide["depth"] == 2
    assert debt_fault_slide["parent_slide_index"] == by_type["debt_why_not_paid_down"][0]


def test_plan_infographics_adds_stable_slide_ids_and_dependencies():
    tree = _sample_tree()
    tree["children"].append(
        {
            "id": "debt",
            "type": "upstream",
            "question": "How has Australian government debt changed since 2006, and who was in power?",
            "summary": "Debt timelines should show government changes and economic shocks.",
            "scores": {"confidence": "medium", "contestedness": "contested", "salience": "high"},
            "children": [],
        }
    )
    plan = plan_infographics({"topic": "Gas windfall tax"}, tree, format="tiktok")
    slides = plan["sequence"]
    by_type = {slide["slide_type"]: slide for slide in slides}

    assert all(slide["slide_id"] for slide in slides)
    assert all(slide["sequence_index"] == index for index, slide in enumerate(slides))

    assert by_type["extra_money_sources"]["slide_id"] == "money.extra_sources"
    assert by_type["tax_per_person"]["slide_id"] == "money.tax_per_person"
    assert by_type["tax_per_person"]["parent_slide_id"] == "money.extra_sources"
    assert "money.extra_sources" in by_type["tax_per_person"]["depends_on"]
    assert by_type["debt_why_not_paid_down"]["slide_id"] == "debt.why_not_paid_down"
    assert by_type["debt_fault_map"]["parent_slide_id"] == "debt.why_not_paid_down"

    regenerated = plan_infographics({"topic": "Gas windfall tax"}, tree, format="tiktok")
    ids = [slide["slide_id"] for slide in slides]
    regenerated_ids = [slide["slide_id"] for slide in regenerated["sequence"]]
    assert ids == regenerated_ids


def test_plan_gas_tax_public_explainer_returns_15_slide_public_cut():
    plan = plan_gas_tax_public_explainer({"topic": "Gas windfall tax"}, _sample_tree(), format="tiktok")
    slides = plan["sequence"]
    slide_types = [slide["slide_type"] for slide in slides]

    assert plan["schema_version"] == "infographic-plan/v1"
    assert plan["planner"] == "gas_tax_public_explainer"
    assert plan["output_format"] == "tiktok"
    assert plan["aspect_ratio"] == "9:16"
    assert plan["slide_count"] == 15
    assert len(slides) == 15

    assert slide_types[:3] == ["public_hook", "public_surface_claim", "public_resource_rent"]
    assert "tax_revenue_numbers" in slide_types
    assert "spending_numbers" in slide_types
    assert "tax_per_person" in slide_types
    assert "extra_money_sources" in slide_types
    assert "debt_why_not_paid_down" in slide_types
    assert slide_types[-1] == "public_honest_answer"

    assert all(slide["slide_id"] for slide in slides)
    assert all(slide["sequence_index"] == index for index, slide in enumerate(slides))
    assert all("…" not in label for slide in slides for label in slide["labels"])

    resource_slide = next(slide for slide in slides if slide["slide_type"] == "public_resource_rent")
    assert any("Resource rent" in label for label in resource_slide["labels"])
    conclusion = slides[-1]
    assert conclusion["render_contract"]["publication_role"] == "public_explainer"
    assert "conclusion.recommendation" in conclusion["render_contract"]["source_slide_ids"]
