from typing import List

from botbuilder.core import (
    ActivityHandler,
    ConversationState,
    MessageFactory,
    TurnContext,
)
from botbuilder.core.integration import BotFrameworkHttpClient
from botbuilder.core.skills import SkillConversationIdFactory

from botbuilder.schema import ActivityTypes, ChannelAccount

from config import DefaultConfig, SkillConfiguration


class RootBot(ActivityHandler):
    def __init__(
        self,
        conversation_state: ConversationState,
        skills_config: SkillConfiguration,
        conversation_id_factory: SkillConversationIdFactory,
        skill_client: BotFrameworkHttpClient,
        config: DefaultConfig,
    ):
        self._conversation_id_factory = conversation_id_factory
        self._bot_id = config.APP_ID
        self._skill_client = skill_client
        self._skills_config = skills_config
        self._conversation_state = conversation_state
        self._active_skill_property = conversation_state.create_property(
            "activeSkillProperty"
        )

    async def on_turn(self, turn_context: TurnContext):
        if turn_context.activity.type == ActivityTypes.end_of_conversation:
            # Handle end of conversation back from the skill
            # forget skill invocation
            await self._active_skill_property.delete(turn_context)
            await self._conversation_state.save_changes(turn_context, force=True)

            # We are back
            await turn_context.send_activity(
                MessageFactory.text(
                    'Back in the root bot. Say "skill" and I\'ll patch you through'
                )
            )
        else:
            await super().on_turn(turn_context)

    async def on_message_activity(self, turn_context: TurnContext):
        # If there is an active skill
        active_skill_id: str = await self._active_skill_property.get(turn_context)
        skill_conversation_id = await self._conversation_id_factory.create_skill_conversation_id(
            TurnContext.get_conversation_reference(turn_context.activity)
        )

        if active_skill_id:
            # NOTE: Always SaveChanges() before calling a skill so that any activity generated by the skill
            # will have access to current accurate state.
            await self._conversation_state.save_changes(turn_context, force=True)

            # route activity to the skill
            await self._skill_client.post_activity(
                self._bot_id,
                self._skills_config.SKILLS[active_skill_id].app_id,
                self._skills_config.SKILLS[active_skill_id].skill_endpoint,
                self._skills_config.SKILL_HOST_ENDPOINT,
                skill_conversation_id,
                turn_context.activity,
            )
        else:
            if "skill" in turn_context.activity.text:
                await turn_context.send_activity(
                    MessageFactory.text("Got it, connecting you to the skill...")
                )

                # save ConversationReferene for skill
                await self._active_skill_property.set(turn_context, "SkillBot")

                # NOTE: Always SaveChanges() before calling a skill so that any activity generated by the
                # skill will have access to current accurate state.
                await self._conversation_state.save_changes(turn_context, force=True)

                await self._skill_client.post_activity(
                    self._bot_id,
                    self._skills_config.SKILLS["SkillBot"].app_id,
                    self._skills_config.SKILLS["SkillBot"].skill_endpoint,
                    self._skills_config.SKILL_HOST_ENDPOINT,
                    skill_conversation_id,
                    turn_context.activity,
                )
            else:
                # just respond
                await turn_context.send_activity(
                    MessageFactory.text(
                        "Me no nothin'. Say \"skill\" and I'll patch you through"
                    )
                )

    async def on_members_added_activity(
        self, members_added: List[ChannelAccount], turn_context: TurnContext
    ):
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    MessageFactory.text("Hello and welcome!")
                )
