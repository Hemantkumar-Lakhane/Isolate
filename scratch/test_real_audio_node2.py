import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from api.routers.meeting_intelligence import (
    transcribe_audio_file,
    extract_structured_intelligence,
)

async def test_real_audio():
    audio_file = Path("uploads/audio/34300003-f38_demosmb.mp3")
    print(f"Testing real audio file: {audio_file} (exists: {audio_file.exists()})")

    transcript, lang, provider, duration = await transcribe_audio_file(
        file_path=audio_file,
        language_hint="Auto Detect",
    )
    print(f"\n--- TRANSCRIPTION RESULT ---")
    print(f"Provider: {provider}")
    print(f"Detected Language: {lang}")
    print(f"Duration: {duration}s")
    print(f"Transcript:\n{transcript}")

    extraction, model, cost, t_in, t_out = await extract_structured_intelligence(
        transcript=transcript,
        contact_name="Rahul Sharma",
        conversation_date="2026-09-27",
        conversation_type="Online Meeting",
    )

    print(f"\n--- STRUCTURED EXTRACTION RESULT ---")
    print(f"Model Used: {model}")
    print(f"Cost USD: ${cost:.6f}")
    print(f"Tokens: In={t_in}, Out={t_out}")
    print(f"Summary:\n{extraction.summary}\n")

    print(f"People ({len(extraction.people)}):")
    for p in extraction.people:
        print(f"  - {p.name}")
        print(f"    Facts: {p.facts}")
        print(f"    Interests: {p.interests}")
        print(f"    Needs: {p.needs}")
        print(f"    Opportunities: {p.opportunities}")

    print(f"\nAGREED COMMITMENTS ({len(extraction.commitments)}):")
    for c in extraction.commitments:
        print(f"  - [{c.owner}] {c.commitment} (Due: {c.due_date})")

    print(f"\nAI SUGGESTED ACTIONS ({len(extraction.suggested_actions)}):")
    for a in extraction.suggested_actions:
        print(f"  - {a.action}: {a.reason}")

    print(f"\nOPEN QUESTIONS ({len(extraction.open_questions)}):")
    for q in extraction.open_questions:
        print(f"  - {q}")

if __name__ == "__main__":
    asyncio.run(test_real_audio())
