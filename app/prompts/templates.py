INTENT_ROUTER_PROMPT = """
Classify the user query into one of:
- job_search
- job_compare
- identity_query
- out_of_scope
- chitchat
Return only label text.
""".strip()

ENTITY_EXTRACT_PROMPT = """
Extract entities for job search:
- position: list[str]
- location: list[str]
- salary_range: str | null
- level: str | null
- skills: list[str]
Return JSON only.
""".strip()

SALARY_PARSER_PROMPT = """
Convert a natural language salary to numeric range VND.
Return JSON only with:
- min_value: int | null
- max_value: int | null
- currency: "VND"
""".strip()
