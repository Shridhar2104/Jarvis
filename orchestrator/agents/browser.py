"""
orchestrator/agents/browser.py — Multi-step browser research agent

Given a research goal, the agent:
  1. Generates a list of search queries via LLM
  2. Fetches search results and page content
  3. Summarises findings into a structured report
  4. Saves the report to a specified output path

Params (from job.context_json):
    goal:        str   — research objective in natural language
    output_path: str   — where to save the report (default: ~/Desktop)
    max_queries: int   — max number of search queries to run (default: 5)
"""

import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

import aiohttp
from openai import AsyncOpenAI

from config import LLM_MODEL, OPENAI_API_KEY
from orchestrator.agents.base import BaseAgent, AgentFailedError
from db.models import Job

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)


class BrowserAgent(BaseAgent):

    async def run(self) -> str:
        ctx = self.job.context_json
        goal: str = ctx.get("goal", self.job.intent)
        output_path = Path(ctx.get("output_path", "~/Desktop")).expanduser()
        max_queries: int = int(ctx.get("max_queries", 5))

        self._log(f"Research goal: {goal}")

        # Step 1: Generate search queries
        queries = await self._generate_queries(goal, max_queries)
        self._log(f"Generated {len(queries)} search queries")

        # Step 2: Fetch and scrape results
        findings: list[dict] = []
        async with aiohttp.ClientSession() as session:
            for query in queries:
                results = await self._search(session, query)
                findings.extend(results)
                self._log(f"Fetched {len(results)} results for: {query}")
                await asyncio.sleep(0.5)  # polite crawl delay

        # Step 3: Synthesise findings
        report = await self._synthesise(goal, findings)

        # Step 4: Save report
        filename = f"jarvis_research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = output_path / filename
        report_path.write_text(report)
        self._log(f"Report saved: {report_path}")

        return f"Research complete. Report saved to {filename}."

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _generate_queries(self, goal: str, max_queries: int) -> list[str]:
        response = await _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Generate a JSON array of search query strings for researching the given goal. Return only valid JSON."},
                {"role": "user", "content": f"Goal: {goal}\nMax queries: {max_queries}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        data = json.loads(response.choices[0].message.content or "[]")
        # Handle both {"queries": [...]} and [...]
        if isinstance(data, dict):
            return data.get("queries", [])[:max_queries]
        return data[:max_queries]

    async def _search(self, session: aiohttp.ClientSession, query: str) -> list[dict]:
        """
        Stub: search via DuckDuckGo or similar.
        TODO: integrate a real search API (SerpAPI, Bing, DuckDuckGo).
        """
        self._log(f"[stub] Searching: {query}")
        return [{"query": query, "title": "(stub)", "url": "", "snippet": ""}]

    async def _synthesise(self, goal: str, findings: list[dict]) -> str:
        findings_text = "\n\n".join(
            f"**{f['title']}**\n{f['snippet']}" for f in findings if f.get("snippet")
        ) or "(no content retrieved)"

        response = await _client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a research analyst. Write a structured Markdown report based on the findings provided."},
                {"role": "user", "content": f"Research goal: {goal}\n\nFindings:\n{findings_text}"},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or "No report generated."
