from typing import List, Union

import httpx
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from revChatGPT.typings import Error as revChatGPTError
from sqlalchemy import select, and_, delete

import api.globals as g
from api.database import get_async_session_context
from api.exceptions import InvalidParamsException, AuthorityDenyException, InternalException
from api.models import User, RevConversation, ConversationHistoryDocument, BaseConversation
from api.response import response
from api.schema import RevConversationSchema, BaseConversationSchema, ApiConversationSchema
from api.users import current_active_user, current_super_user
from api.sources import RevChatGPTManager
from utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

manager = RevChatGPTManager()


async def _get_conversation_by_id(conversation_id: str, user: User = Depends(current_active_user)):
    async with get_async_session_context() as session:
        r = await session.execute(select(RevConversation).where(RevConversation.conversation_id == conversation_id))
        conversation = r.scalars().one_or_none()
        if conversation is None:
            raise InvalidParamsException("errors.conversationNotFound")
        if not user.is_superuser and conversation.user_id != user.id:
            raise AuthorityDenyException
        return conversation


@router.get("/conv", tags=["conversation"],
            response_model=List[Union[BaseConversationSchema, RevConversationSchema, ApiConversationSchema]])
async def get_all_conversations(user: User = Depends(current_active_user), fetch_all: bool = False):
    """
    返回自己的有效会话
    对于管理员，返回所有对话，并可以指定是否只返回有效会话
    """
    if fetch_all and not user.is_superuser:
        raise AuthorityDenyException()

    stat = and_(BaseConversation.user_id == user.id, BaseConversation.is_valid)
    if fetch_all:
        stat = None
    async with get_async_session_context() as session:
        if stat is not None:
            r = await session.execute(select(BaseConversation).where(stat))
        else:
            r = await session.execute(select(BaseConversation))
        results = r.scalars().all()
        results = jsonable_encoder(results)
        return results


@router.get("/conv/{conversation_id}", tags=["conversation"], response_model=ConversationHistoryDocument)
async def get_conversation_history(refresh: bool = False,
                                   conversation: RevConversation = Depends(_get_conversation_by_id)):
    try:
        result = await manager.get_conversation_history(conversation.conversation_id, refresh=refresh)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise InvalidParamsException("errors.conversationNotFound")
        raise InternalException()
    except ValueError as e:
        raise InternalException(str(e))
    return result


@router.delete("/conv/{conversation_id}", tags=["conversation"])
async def delete_conversation(conversation: RevConversation = Depends(_get_conversation_by_id)):
    """remove conversation from database and chatgpt server"""
    if not conversation.is_valid:
        raise InvalidParamsException("errors.conversationAlreadyDeleted")
    try:
        await manager.delete_conversation(conversation.conversation_id)
    except revChatGPTError as e:
        logger.warning(f"delete conversation {conversation.conversation_id} failed: {e.code} {e.message}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 404:
            raise e
    async with get_async_session_context() as session:
        conversation.is_valid = False
        session.add(conversation)
        await session.commit()
    return response(200)


@router.delete("/conv/{conversation_id}/vanish", tags=["conversation"])
async def vanish_conversation(conversation: RevConversation = Depends(_get_conversation_by_id)):
    if conversation.is_valid:
        try:
            await manager.delete_conversation(conversation.conversation_id)
        except revChatGPTError as e:
            logger.warning(f"delete conversation {conversation.conversation_id} failed: {e.code} {e.message}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise e
    async with get_async_session_context() as session:
        await session.execute(
            delete(RevConversation).where(RevConversation.conversation_id == conversation.conversation_id))
        await session.commit()
    return response(200)


@router.patch("/conv/{conversation_id}", tags=["conversation"], response_model=RevConversationSchema)
async def update_conversation_title(title: str, conversation: RevConversation = Depends(_get_conversation_by_id)):
    await manager.set_conversation_title(conversation.conversation_id,
                                         title)
    async with get_async_session_context() as session:
        conversation.title = title
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
    result = jsonable_encoder(conversation)
    return result


@router.patch("/conv/{conversation_id}/assign/{username}", tags=["conversation"])
async def assign_conversation(username: str, conversation_id: str, _user: User = Depends(current_super_user)):
    async with get_async_session_context() as session:
        user = await session.execute(select(User).where(User.username == username))
        user = user.scalars().one_or_none()
        if user is None:
            raise InvalidParamsException("errors.userNotFound")
        conversation = await session.execute(
            select(RevConversation).where(RevConversation.conversation_id == conversation_id))
        conversation = conversation.scalars().one_or_none()
        if conversation is None:
            raise InvalidParamsException("errors.conversationNotFound")
        conversation.user_id = user.id
        session.add(conversation)
        await session.commit()
    return response(200)


@router.delete("/conv", tags=["conversation"])
async def delete_all_conversation(_user: User = Depends(current_super_user)):
    await manager.clear_conversations()
    async with get_async_session_context() as session:
        await session.execute(delete(RevConversation))
        await session.commit()
    return response(200)


@router.patch("/conv/{conversation_id}/gen_title", tags=["conversation"], response_model=RevConversationSchema)
async def generate_conversation_title(message_id: str,
                                      conversation: RevConversation = Depends(_get_conversation_by_id)):
    if conversation.title is not None:
        raise InvalidParamsException("errors.conversationTitleAlreadyGenerated")
    async with get_async_session_context() as session:
        result = await manager.generate_conversation_title(conversation.id, message_id)
        if result["title"]:
            conversation.title = result["title"]
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
        else:
            raise InvalidParamsException(f"{result['message']}")
    result = jsonable_encoder(conversation)
    return result