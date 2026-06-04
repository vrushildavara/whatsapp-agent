from pydantic import BaseModel, ConfigDict


class WhatsAppSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: int
