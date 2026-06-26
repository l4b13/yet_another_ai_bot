from sqlalchemy.ext.asyncio import AsyncSession
from models import User, Conversation, Message
from langchain.messages import HumanMessage, AIMessage


class ChatService:
    @classmethod
    async def _get_user(
        cls,
        db_session: AsyncSession,
        chat_id: int,
        username: str = None,
        fullname: str = None
    ):
        user = await User.get_one(db_session, chat_id)
        if not user:
            user = await User(
                chat_id=str(chat_id),
                username=username,
                fullname=fullname
            ).save(db_session)
        else:
            user.username = username
            user.fullname = fullname
            await user.save(db_session)
        return user

    @classmethod
    async def _get_conv(
        cls, db_session: AsyncSession, user_id: int, new: bool = False
    ):
        conv = await Conversation.get_last(db_session, user_id)
        if new or conv is None:
            conv = await Conversation(
                user_id=user_id
            ).save(db_session)
        return conv

    @classmethod
    async def get_user(
        cls,
        db_session: AsyncSession,
        chat_id: int,
        username: str = None,
        fullname: str = None
    ):
        user = await cls._get_user(db_session, chat_id, username, fullname)
        return user

    @classmethod
    async def get_conv(
        cls, db_session: AsyncSession, user_id: int, new: bool = False
    ):
        return await cls._get_conv(db_session, user_id, new)

    @classmethod
    async def get_conv_by_chat_id(
        cls, db_session: AsyncSession, chat_id: int, new: bool = False
    ):
        user = await cls._get_user(db_session, chat_id)
        return await cls._get_conv(db_session, user.id, new)

    @classmethod
    async def get_last_messages(
        cls, db_session: AsyncSession, conv_id: int, limit: int = 10
    ):
        messages = await Message.get_many(db_session, conv_id, limit)
        return messages

    @classmethod
    async def get_last_messages_as_langchain(
        cls, db_session: AsyncSession, conv_id: int, limit: int = 10
    ):
        messages = await Message.get_many(db_session, conv_id, limit)
        result: list[HumanMessage | AIMessage] = []
        for message in messages[::-1]:
            if message.is_bot:
                result.append(AIMessage(content=message.text))
            else:
                result.append(HumanMessage(content=message.text))
        return result

    @classmethod
    async def answer(cls, db_session: AsyncSession):
        pass
