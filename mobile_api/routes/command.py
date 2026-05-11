"""mobile_api/routes/command.py — Send a text command to JARVIS."""

from fastapi import APIRouter
from pydantic import BaseModel

from events.bus import bus, Event

router = APIRouter()


class CommandRequest(BaseModel):
    text: str


@router.post("/command")
async def send_command(req: CommandRequest):
    """
    Publish a voice.command event — identical to what the voice layer produces.
    JARVIS processes it normally: intent classification → skill or agent.
    """
    if not req.text.strip():
        return {"status": "ignored", "reason": "empty command"}

    await bus.publish(Event("voice.command", {"text": req.text.strip(), "source": "mobile"}))
    return {"status": "dispatched", "text": req.text.strip()}
