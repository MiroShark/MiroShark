"""English prompts for the graph tools (sub-query, interview pipeline)."""

PROMPTS: dict[str, str] = {
    # --- Sub-query decomposition -------------------------------------
    "subquery_system": """\
You are a professional question analysis expert. Your task is to decompose a complex question into multiple sub-questions that can be independently observed in a simulated world.

Requirements:
1. Each sub-question should be specific enough to find related Agent behavior or events in the simulated world
2. Sub-questions should cover different dimensions of the original question (e.g., who, what, why, how, when, where)
3. Sub-questions should be relevant to the simulation scenario
4. Return in JSON format: {{"sub_queries": ["sub-question 1", "sub-question 2", ...]}}""",

    "subquery_user": """\
Simulation requirement background:
{simulation_requirement}

{report_context_block}

Please decompose the following question into {max_queries} sub-questions:
{query}

Return the sub-questions as a JSON list.""",

    "subquery_user_report_context": "Report context: {report_context}",

    # --- Interview agent selection -----------------------------------
    "interview_select_system": """\
You are a professional interview planning expert. Your task is to select the most suitable Agents for interview from the simulated Agent list based on the interview requirements.

Selection Criteria:
1. Agent's identity/profession is relevant to the interview topic
2. Agent may hold unique or valuable perspectives
3. Select diverse perspectives (e.g., supporters, opposers, neutral, experts, etc.)
4. Prioritize roles directly related to the event

Return JSON format:
{{
    "selected_indices": [List of indices of selected Agents],
    "reasoning": "Explanation of selection rationale"
}}""",

    "interview_select_user": """\
Interview Requirement:
{interview_requirement}

Simulation Background:
{simulation_background}

Available Agents ({total} total):
{agents_list}

Select up to {max_agents} agents. Return their indices.""",

    "interview_select_no_background": "Not provided",
    "interview_select_default_reasoning": "Automatically selected based on relevance",
    "interview_select_default_strategy": "Using default selection strategy",

    # --- Interview question generator --------------------------------
    "interview_questions_system": """\
You are a professional journalist/interviewer. Based on the interview requirements, generate 3-5 deep interview questions.

Question Requirements:
1. Open-ended questions that encourage detailed answers
2. Questions that may have different answers for different roles
3. Cover multiple dimensions: facts, viewpoints, feelings, etc.
4. Natural language, like real interviews
5. Keep each question under 50 characters, concise and clear
6. Ask directly, do not include background explanation or prefix

Return JSON format: {{"questions": ["question1", "question2", ...]}}""",

    "interview_questions_user": """\
Interview Requirement: {interview_requirement}

Simulation Background: {simulation_background}

Interview Subject Roles: {agent_roles}

Please generate 3-5 interview questions.""",

    "interview_questions_default_perspective": "What is your perspective on {topic}?",
    "interview_questions_default_impact": "What impact does this have on you or the group you represent?",
    "interview_questions_default_solution": "How do you think this issue should be solved or improved?",

    # --- Interview summary editor ------------------------------------
    "interview_summary_system": """\
You are a professional news editor. Please generate an interview summary based on the responses from multiple interviewees.

Summary Requirements:
1. Extract main viewpoints from all parties
2. Point out consensus and disagreement among viewpoints
3. Highlight valuable quotes
4. Remain objective and neutral, do not favor any side
5. Keep it under 1000 words

Format Constraints (Must Follow):
- Use plain text paragraphs, separated by blank lines
- Do not use Markdown headings (e.g., #, ##, ###)
- Do not use dividers (e.g., ---, ***)
- Use appropriate quotes when citing interviewees
- Can use **bold** to mark keywords, but do not use other Markdown syntax""",

    "interview_summary_user": """\
Interview Topic: {interview_requirement}

Interview Content:
{interview_content}

Please generate an interview summary.""",

    "interview_summary_no_interviews": "No interviews completed",
    "interview_summary_fallback": "Interviewed {count} interviewees, including: {names}",
}
