"""
Summarization Module
Supports two modes:
1. LOCAL mode (default) - Extracts key points from transcript using text analysis
2. CLAUDE mode (optional) - Uses Claude API for AI-powered summaries

PRIVACY NOTE:
- Local mode: 100% offline, nothing leaves your device
- Claude mode: Only transcript text is sent (never audio)
- Anthropic does NOT train on API data by default
"""
import os
import re
import json
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import Optional, Dict, Callable, List
from dotenv import load_dotenv

from config import CLAUDE_MODEL, SUMMARIES_DIR

# Load environment variables from project root .env
load_dotenv(Path(__file__).parent.parent / ".env")


class LocalSummarizer:
    """
    100% offline summarizer using extractive text analysis.
    No data ever leaves your machine.
    """

    # Words that indicate action items
    ACTION_WORDS = [
        'need to', 'should', 'must', 'have to', 'going to', 'will',
        'plan to', 'make sure', 'follow up', 'take care', 'responsible',
        'deadline', 'by tomorrow', 'by next', 'assigned', 'task',
        'action item', 'todo', 'to-do', 'let\'s', "let's",
    ]

    # Words that indicate questions
    QUESTION_WORDS = [
        'how', 'what', 'why', 'when', 'where', 'who', 'which',
        'could we', 'should we', 'can we', 'is there', 'are there',
        'do we', 'does anyone', 'any thoughts', 'any questions',
    ]

    # Words that indicate decisions
    DECISION_WORDS = [
        'decided', 'agreed', 'conclusion', 'final', 'approved',
        'go with', 'settled', 'confirmed', 'chosen', 'selected',
        'consensus', 'moving forward with', 'we\'ll go', "we'll go",
    ]

    # Common filler/stop words to ignore in scoring
    STOP_WORDS = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'shall', 'can',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
        'as', 'into', 'through', 'during', 'before', 'after', 'and',
        'but', 'or', 'nor', 'not', 'so', 'yet', 'both', 'either',
        'neither', 'each', 'every', 'all', 'any', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'only', 'own', 'same',
        'than', 'too', 'very', 'just', 'because', 'if', 'when', 'that',
        'this', 'it', 'i', 'me', 'my', 'we', 'our', 'you', 'your',
        'he', 'she', 'they', 'them', 'his', 'her', 'its', 'their',
        'what', 'which', 'who', 'whom', 'these', 'those', 'am',
        'about', 'up', 'out', 'then', 'there', 'here', 'also',
        'like', 'well', 'back', 'even', 'still', 'way', 'take',
        'come', 'make', 'know', 'get', 'got', 'go', 'going',
        'thing', 'things', 'think', 'right', 'really', 'much',
        'said', 'say', 'says', 'one', 'two', 'okay', 'yeah', 'yes',
        'no', 'um', 'uh', 'ah', 'oh', 'hmm', 'actually', 'basically',
        'something', 'kind', 'sort', 'lot', 'now', 'don\'t', "don't",
    }

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def _score_sentences(self, sentences: List[str]) -> List[tuple]:
        """Score sentences by importance using word frequency"""
        # Count meaningful word frequencies across all sentences
        word_freq = Counter()
        for sentence in sentences:
            words = re.findall(r'\b[a-z]+\b', sentence.lower())
            for word in words:
                if word not in self.STOP_WORDS and len(word) > 2:
                    word_freq[word] += 1

        # Score each sentence
        scored = []
        for i, sentence in enumerate(sentences):
            words = re.findall(r'\b[a-z]+\b', sentence.lower())
            meaningful_words = [w for w in words if w not in self.STOP_WORDS and len(w) > 2]
            if not meaningful_words:
                scored.append((0, i, sentence))
                continue

            # Base score from word frequency
            score = sum(word_freq.get(w, 0) for w in meaningful_words) / len(meaningful_words)

            # Boost first and last sentences (often contain key info)
            if i < 3:
                score *= 1.3
            if i >= len(sentences) - 3:
                score *= 1.2

            # Boost longer sentences (more content)
            if len(meaningful_words) > 5:
                score *= 1.1

            scored.append((score, i, sentence))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    def _extract_by_pattern(self, sentences: List[str], keywords: List[str]) -> List[str]:
        """Extract sentences matching keyword patterns"""
        matches = []
        for sentence in sentences:
            lower = sentence.lower()
            for keyword in keywords:
                if keyword in lower:
                    cleaned = sentence.strip().rstrip('.')
                    if cleaned not in matches:
                        matches.append(cleaned)
                    break
        return matches

    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics from text using noun phrase frequency"""
        words = re.findall(r'\b[a-z]+\b', text.lower())
        meaningful = [w for w in words if w not in self.STOP_WORDS and len(w) > 3]
        freq = Counter(meaningful)
        # Return top topics
        return [word for word, count in freq.most_common(10) if count >= 2]

    def summarize(
        self,
        transcript: Dict,
        meeting_title: str = "Meeting",
        on_progress: Optional[Callable] = None
    ) -> Optional[Dict]:
        """Generate summary using local text analysis"""
        if on_progress:
            on_progress("Analyzing transcript locally...")

        full_text = transcript.get('full_text', '')
        segments = transcript.get('segments', [])

        if not full_text:
            if on_progress:
                on_progress("Error: Empty transcript")
            return None

        sentences = self._split_sentences(full_text)

        if on_progress:
            on_progress(f"Processing {len(sentences)} sentences...")

        # Score and rank sentences
        scored = self._score_sentences(sentences)

        # Extract top sentences for executive summary (maintain original order)
        top_count = max(3, len(sentences) // 5)
        top_indices = sorted([idx for _, idx, _ in scored[:top_count]])
        executive_sentences = [sentences[i] for i in top_indices]
        executive_summary = ' '.join(executive_sentences[:4])

        # Extract key discussion points (top unique topics)
        topics = self._extract_topics(full_text)
        key_points = []
        for topic in topics[:8]:
            # Find best sentence for this topic
            for sentence in sentences:
                if topic in sentence.lower() and sentence not in key_points:
                    key_points.append(sentence)
                    break

        # Extract action items
        action_items = self._extract_by_pattern(sentences, self.ACTION_WORDS)

        # Extract questions/concerns
        questions = [s for s in sentences if '?' in s]
        questions += self._extract_by_pattern(sentences, self.QUESTION_WORDS)
        questions = list(dict.fromkeys(questions))  # deduplicate

        # Extract decisions
        decisions = self._extract_by_pattern(sentences, self.DECISION_WORDS)

        # Generate time-based sections if segments available
        next_steps = []
        if segments:
            # Last few segments often contain next steps
            last_segments = segments[-5:]
            for seg in last_segments:
                text = seg.get('text', '').strip()
                if len(text) > 15:
                    next_steps.append(text)

        # Build word count stats
        word_count = len(full_text.split())
        duration = transcript.get('duration', 0)

        if on_progress:
            on_progress("Building summary...")

        summary = {
            "executive_summary": executive_summary or "Transcript captured but no clear summary points detected.",
            "key_discussion_points": key_points[:6] if key_points else ["General discussion captured in transcript"],
            "decisions_made": decisions[:5] if decisions else ["No explicit decisions detected"],
            "action_items": action_items[:8] if action_items else ["Review transcript for specific action items"],
            "questions_concerns": questions[:5] if questions else ["No explicit questions detected"],
            "next_steps": next_steps[:4] if next_steps else ["Review the full transcript for details"],
            "participants": [],
            "sentiment": f"Transcript contains {word_count} words over {duration:.0f} seconds.",
            "raw_summary": executive_summary,
            "meeting_title": meeting_title,
            "generated_at": datetime.now().isoformat(),
            "transcript_duration": duration,
            "model_used": "local-extractive",
            "privacy": {
                "audio_sent_to_api": False,
                "transcript_sent_to_api": False,
                "api_provider": "None - 100% local",
                "data_used_for_training": False
            }
        }

        if on_progress:
            on_progress("Summary generated locally!")

        return summary


class MeetingSummarizer:
    """
    Meeting summarizer with two modes:
    - Local (default): 100% offline extractive summarization
    - Claude API (optional): AI-powered summaries when API key available
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.client = None
        self.local_summarizer = LocalSummarizer()
        self.use_local = True  # Default to local mode

    def _init_client(self):
        """Initialize Anthropic client"""
        if self.client is None:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def set_api_key(self, api_key: str):
        """Set or update API key"""
        self.api_key = api_key
        self.client = None

    def set_mode(self, use_local: bool):
        """Switch between local and Claude API mode"""
        self.use_local = use_local

    def summarize(
        self,
        transcript: Dict,
        meeting_title: str = "Meeting",
        on_progress: Optional[Callable] = None
    ) -> Optional[Dict]:
        """
        Generate meeting summary. Uses local mode by default,
        falls back to local if Claude API fails.
        """
        # Use local summarizer if selected or no API key
        if self.use_local or not self.api_key:
            summary = self.local_summarizer.summarize(
                transcript, meeting_title, on_progress
            )
            if summary:
                summary_path = self._save_summary(summary)
                summary["summary_file"] = str(summary_path)
            return summary

        # Try Claude API
        try:
            return self._summarize_with_claude(transcript, meeting_title, on_progress)
        except Exception as e:
            error_msg = str(e)
            print(f"Claude API failed: {error_msg}")
            if on_progress:
                on_progress(f"API failed, using local summarizer...")
            # Fallback to local
            summary = self.local_summarizer.summarize(
                transcript, meeting_title, on_progress
            )
            if summary:
                summary_path = self._save_summary(summary)
                summary["summary_file"] = str(summary_path)
            return summary

    def _summarize_with_claude(
        self,
        transcript: Dict,
        meeting_title: str,
        on_progress: Optional[Callable]
    ) -> Optional[Dict]:
        """Generate summary using Claude API"""
        self._init_client()

        if on_progress:
            on_progress("Generating summary with Claude API...")

        transcript_text = transcript.get('full_text', '')
        if not transcript_text:
            if on_progress:
                on_progress("Error: Empty transcript")
            return None

        prompt = self._create_summary_prompt(transcript_text, meeting_title)

        message = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        summary = self._parse_summary_response(response_text)

        summary["meeting_title"] = meeting_title
        summary["generated_at"] = datetime.now().isoformat()
        summary["transcript_duration"] = transcript.get("duration", 0)
        summary["model_used"] = CLAUDE_MODEL
        summary["privacy"] = {
            "audio_sent_to_api": False,
            "transcript_sent_to_api": True,
            "api_provider": "Anthropic",
            "data_used_for_training": False
        }

        summary_path = self._save_summary(summary)
        summary["summary_file"] = str(summary_path)

        if on_progress:
            on_progress("Summary generated with Claude!")

        return summary

    def _create_summary_prompt(self, transcript: str, title: str) -> str:
        """Create prompt for Claude to generate meeting summary"""
        return f"""You are an expert meeting analyst. Analyze this meeting transcript and provide a comprehensive summary.

Meeting Title: {title}

TRANSCRIPT:
{transcript}

Please provide a structured summary with the following sections:

## 1. EXECUTIVE SUMMARY
A brief 2-3 sentence overview of what was discussed.

## 2. KEY DISCUSSION POINTS
List the main topics discussed with brief explanations.

## 3. DECISIONS MADE
List any decisions that were made during the meeting.

## 4. ACTION ITEMS
List action items in this format:
- [ ] Task description | Assigned to: [Person if mentioned] | Due: [Date if mentioned]

## 5. QUESTIONS & CONCERNS RAISED
List any questions or concerns that came up.

## 6. NEXT STEPS
What should happen after this meeting?

## 7. PARTICIPANTS
List participants if their names were mentioned.

## 8. MEETING SENTIMENT
Brief note on the overall tone/sentiment of the meeting.

Be concise but thorough. Focus on actionable information."""

    def _parse_summary_response(self, response: str) -> Dict:
        """Parse Claude's response into structured format"""
        sections = {
            "executive_summary": "",
            "key_discussion_points": [],
            "decisions_made": [],
            "action_items": [],
            "questions_concerns": [],
            "next_steps": [],
            "participants": [],
            "sentiment": "",
            "raw_summary": response
        }

        # Simple parsing - split by section headers
        current_section = None
        lines = response.split('\n')

        for line in lines:
            line = line.strip()

            if 'EXECUTIVE SUMMARY' in line.upper():
                current_section = 'executive_summary'
            elif 'KEY DISCUSSION' in line.upper():
                current_section = 'key_discussion_points'
            elif 'DECISIONS MADE' in line.upper():
                current_section = 'decisions_made'
            elif 'ACTION ITEMS' in line.upper():
                current_section = 'action_items'
            elif 'QUESTIONS' in line.upper() or 'CONCERNS' in line.upper():
                current_section = 'questions_concerns'
            elif 'NEXT STEPS' in line.upper():
                current_section = 'next_steps'
            elif 'PARTICIPANTS' in line.upper():
                current_section = 'participants'
            elif 'SENTIMENT' in line.upper():
                current_section = 'sentiment'
            elif line and current_section:
                if current_section == 'executive_summary':
                    sections['executive_summary'] += line + ' '
                elif current_section == 'sentiment':
                    sections['sentiment'] += line + ' '
                elif line.startswith(('-', '*', '•', '[')):
                    sections[current_section].append(line.lstrip('-*• '))

        sections['executive_summary'] = sections['executive_summary'].strip()
        sections['sentiment'] = sections['sentiment'].strip()

        return sections

    def _save_summary(self, summary: Dict) -> Path:
        """Save summary to local file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        title_slug = summary.get('meeting_title', 'meeting').lower().replace(' ', '_')[:20]
        filename = f"summary_{title_slug}_{timestamp}.json"
        filepath = SUMMARIES_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # Also save a readable markdown version
        md_path = filepath.with_suffix('.md')
        self._save_markdown(summary, md_path)

        return filepath

    def _save_markdown(self, summary: Dict, filepath: Path):
        """Save summary as readable Markdown file"""
        md_content = f"""# {summary.get('meeting_title', 'Meeting Summary')}

**Generated:** {summary.get('generated_at', 'Unknown')}
**Duration:** {summary.get('transcript_duration', 0):.1f} seconds

---

## Executive Summary

{summary.get('executive_summary', 'No summary available.')}

## Key Discussion Points

"""
        for point in summary.get('key_discussion_points', []):
            md_content += f"- {point}\n"

        md_content += "\n## Decisions Made\n\n"
        for decision in summary.get('decisions_made', []):
            md_content += f"- {decision}\n"

        md_content += "\n## Action Items\n\n"
        for item in summary.get('action_items', []):
            md_content += f"- [ ] {item}\n"

        md_content += "\n## Next Steps\n\n"
        for step in summary.get('next_steps', []):
            md_content += f"- {step}\n"

        md_content += f"""
---

*Privacy: Audio processed locally. Only transcript text sent to API. No data used for AI training.*
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)


def format_summary_for_display(summary: Dict) -> str:
    """Format summary for display in UI"""
    if not summary:
        return "No summary available."

    output = []
    output.append(f"📋 {summary.get('meeting_title', 'Meeting Summary')}\n")
    output.append("=" * 50)

    if summary.get('executive_summary'):
        output.append(f"\n📝 Summary:\n{summary['executive_summary']}\n")

    if summary.get('action_items'):
        output.append("\n✅ Action Items:")
        for item in summary['action_items']:
            output.append(f"  • {item}")

    if summary.get('decisions_made'):
        output.append("\n🎯 Decisions:")
        for decision in summary['decisions_made']:
            output.append(f"  • {decision}")

    if summary.get('next_steps'):
        output.append("\n➡️ Next Steps:")
        for step in summary['next_steps']:
            output.append(f"  • {step}")

    return "\n".join(output)
